from __future__ import annotations

from threading import RLock
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.backends.terminal_base import TerminalBackend
from app.common.models import TerminalSessionConfig
from app.common.platform import default_shell_command


class LocalPosixBackend(TerminalBackend):
    """Linux/macOS 本地 PTY 后端."""

    def __init__(self, config: TerminalSessionConfig) -> None:
        super().__init__()
        self._config = config
        self._cols = config.cols
        self._rows = config.rows
        self._worker: PosixPtyWorker | None = None

    def start(self) -> None:
        if self._worker is not None:
            return
        self._worker = PosixPtyWorker(self._config, self._cols, self._rows)
        self._worker.output_received.connect(self.output_received.emit)
        self._worker.connected.connect(self.connected.emit)
        self._worker.closed.connect(self._handle_worker_closed)
        self._worker.error.connect(self.error.emit)
        self._worker.start()

    def write(self, data: bytes) -> None:
        if self._worker is not None:
            self._worker.write(data)

    def resize(self, cols: int, rows: int) -> None:
        self._cols = cols
        self._rows = rows
        if self._worker is not None:
            self._worker.resize(cols, rows)

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.request_stop()

    def _handle_worker_closed(self, exit_code: int) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning() and QThread.currentThread() != worker:
            worker.wait(1000)
        self._worker = None
        self.closed.emit(exit_code)


class PosixPtyWorker(QThread):
    """在后台线程中运行 POSIX PTY 会话."""

    output_received = Signal(bytes)
    connected = Signal()
    closed = Signal(int)
    error = Signal(str)

    def __init__(self, config: TerminalSessionConfig, cols: int, rows: int) -> None:
        super().__init__()
        self._config = config
        self._cols = cols
        self._rows = rows
        self._master_fd: int | None = None
        self._process: Any | None = None
        self._pending_input: list[bytes] = []
        self._lock = RLock()
        self._stopping = False
        self._closed = False

    def run(self) -> None:
        try:
            self._spawn_pty_process()
            pending_input = self._take_pending_input()
            self.connected.emit()
            for data in pending_input:
                self._write_to_pty(data)
            self._read_output_loop()
            self._emit_closed(self._exit_code())
        except Exception as exc:
            if not self._stopping:
                self.error.emit(f"POSIX PTY error: {exc}")
            self._emit_closed(0 if self._stopping else 1)
        finally:
            self._close_master_fd()
            self._close_process()

    def write(self, data: bytes) -> None:
        """线程安全写入 POSIX PTY."""
        with self._lock:
            if self._master_fd is None:
                self._pending_input.append(data)
                return
        self._write_to_pty(data)

    def resize(self, cols: int, rows: int) -> None:
        """线程安全调整 POSIX PTY 大小."""
        self._cols = cols
        self._rows = rows
        with self._lock:
            master_fd = self._master_fd
            process = self._process
        if master_fd is None:
            return
        self._set_winsize(master_fd, cols, rows)
        self._send_sigwinch(process)

    def request_stop(self) -> None:
        """请求关闭本地 PTY 会话."""
        self._stopping = True
        self._terminate_process()
        self._close_master_fd()

    def _spawn_pty_process(self) -> None:
        import os
        import pty
        import subprocess

        master_fd, slave_fd = pty.openpty()
        self._set_winsize(slave_fd, self._cols, self._rows)
        command = self._config.command or default_shell_command()
        env = os.environ.copy()
        env.setdefault("TERM", "xterm-256color")
        try:
            process = subprocess.Popen(
                command,
                cwd=self._config.cwd,
                env=env,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                start_new_session=True,
            )
        except Exception:
            os.close(master_fd)
            raise
        finally:
            os.close(slave_fd)

        with self._lock:
            self._master_fd = master_fd
            self._process = process

    def _read_output_loop(self) -> None:
        import errno
        import os
        import select

        while not self._stopping and self._is_alive():
            with self._lock:
                master_fd = self._master_fd
            if master_fd is None:
                break
            try:
                readable, _, _ = select.select([master_fd], [], [], 0.1)
            except OSError:
                break
            if not readable:
                continue
            try:
                data = os.read(master_fd, 4096)
            except OSError as exc:
                if exc.errno == errno.EIO:
                    break
                raise
            if not data:
                break
            self.output_received.emit(data)

    def _write_to_pty(self, data: bytes) -> None:
        import os

        with self._lock:
            master_fd = self._master_fd
        if master_fd is None:
            return
        try:
            os.write(master_fd, data)
        except OSError as exc:
            if not self._stopping:
                self.error.emit(f"POSIX PTY write error: {exc}")

    def _take_pending_input(self) -> list[bytes]:
        with self._lock:
            pending_input = list(self._pending_input)
            self._pending_input.clear()
        return pending_input

    def _is_alive(self) -> bool:
        with self._lock:
            process = self._process
        return process is not None and process.poll() is None

    def _exit_code(self) -> int:
        with self._lock:
            process = self._process
        if process is None:
            return 0
        result = process.poll()
        return int(result) if result is not None else 0

    def _terminate_process(self) -> None:
        import os
        import signal

        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGHUP)
        except OSError:
            try:
                process.terminate()
            except OSError:
                pass

    def _close_process(self) -> None:
        with self._lock:
            process = self._process
        if process is None:
            return
        try:
            process.wait(timeout=1.0)
        except Exception:
            self._kill_process_group(process)
            try:
                process.wait(timeout=1.0)
            except Exception:
                pass

    def _close_master_fd(self) -> None:
        import os

        with self._lock:
            if self._master_fd is None:
                return
            master_fd = self._master_fd
            self._master_fd = None
        try:
            os.close(master_fd)
        except OSError:
            pass

    def _set_winsize(self, fd: int, cols: int, rows: int) -> None:
        import fcntl
        import struct
        import termios

        packed_size = struct.pack("HHHH", max(1, rows), max(1, cols), 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, packed_size)

    def _send_sigwinch(self, process: Any | None) -> None:
        if process is None or process.poll() is not None:
            return
        try:
            import os
            import signal

            os.killpg(process.pid, signal.SIGWINCH)
        except OSError:
            return

    def _kill_process_group(self, process: Any) -> None:
        import os
        import signal

        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            try:
                process.kill()
            except OSError:
                pass

    def _emit_closed(self, exit_code: int) -> None:
        if self._closed:
            return
        self._closed = True
        self.closed.emit(exit_code)
