from __future__ import annotations

from threading import RLock
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.backends.terminal_base import TerminalBackend
from app.common.models import TerminalSessionConfig
from app.common.platform import default_shell_command


class LocalWindowsBackend(TerminalBackend):
    """Windows 本地 PTY 后端."""

    def __init__(self, config: TerminalSessionConfig) -> None:
        super().__init__()
        self._config = config
        self._cols = config.cols
        self._rows = config.rows
        self._worker: WindowsPtyWorker | None = None

    def start(self) -> None:
        if self._worker is not None:
            return
        self._worker = WindowsPtyWorker(self._config, self._cols, self._rows)
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


class WindowsPtyWorker(QThread):
    """在后台线程中运行 pywinpty/ConPTY 会话."""

    output_received = Signal(bytes)
    connected = Signal()
    closed = Signal(int)
    error = Signal(str)

    def __init__(self, config: TerminalSessionConfig, cols: int, rows: int) -> None:
        super().__init__()
        self._config = config
        self._cols = cols
        self._rows = rows
        self._pending_input: list[bytes] = []
        self._pty: Any | None = None
        self._lock = RLock()
        self._stopping = False
        self._closed = False

    def run(self) -> None:
        try:
            from winpty import PtyProcess
        except ImportError:
            self.error.emit("pywinpty is not installed. Run: pip install -e .[terminal-windows]")
            self._emit_closed(1)
            return

        try:
            with self._lock:
                self._pty = self._spawn_pty_process(PtyProcess)
                pending_input = list(self._pending_input)
                self._pending_input.clear()

            self.connected.emit()
            for data in pending_input:
                self._write_to_pty(data)
            self._read_output_loop()
            self._emit_closed(self._exit_code())
        except Exception as exc:
            if not self._stopping:
                self.error.emit(f"Windows PTY error: {exc}")
            self._emit_closed(0 if self._stopping else 1)
        finally:
            self._close_pty()

    def write(self, data: bytes) -> None:
        """线程安全写入 Windows PTY."""
        with self._lock:
            if self._pty is None:
                self._pending_input.append(data)
                return
        self._write_to_pty(data)

    def resize(self, cols: int, rows: int) -> None:
        """线程安全调整 Windows PTY 大小."""
        self._cols = cols
        self._rows = rows
        with self._lock:
            if self._pty is None:
                return
            self._pty.setwinsize(rows, cols)

    def request_stop(self) -> None:
        """请求关闭本地 PTY 会话."""
        self._stopping = True
        self._close_pty()

    def _spawn_pty_process(self, pty_process_type) -> Any:
        command = self._config.command or default_shell_command()
        return pty_process_type.spawn(
            command,
            cwd=self._config.cwd,
            dimensions=(self._rows, self._cols),
        )

    def _read_output_loop(self) -> None:
        while not self._stopping and self._is_alive():
            try:
                data = self._read_from_pty()
            except EOFError:
                break
            if not data:
                continue
            self.output_received.emit(data)

    def _read_from_pty(self) -> bytes:
        with self._lock:
            if self._pty is None:
                return b""
            pty = self._pty
        data = pty.read(4096)
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8", errors="replace")
        return bytes(data)

    def _write_to_pty(self, data: bytes) -> None:
        with self._lock:
            if self._pty is None:
                return
            pty = self._pty
        text = data.decode("utf-8", errors="replace")
        pty.write(text)

    def _is_alive(self) -> bool:
        with self._lock:
            if self._pty is None:
                return False
            return bool(self._pty.isalive())

    def _exit_code(self) -> int:
        with self._lock:
            if self._pty is None:
                return 0
            get_exitstatus = getattr(self._pty, "get_exitstatus", None)
            result = self._pty.exitstatus if get_exitstatus is None else get_exitstatus()
        return int(result) if result is not None else 0

    def _close_pty(self) -> None:
        with self._lock:
            if self._pty is None:
                return
            pty = self._pty
            self._pty = None

        for method_name in ("close", "terminate", "kill"):
            method = getattr(pty, method_name, None)
            if method is None:
                continue
            try:
                if method_name == "close":
                    method(force=True)
                else:
                    method()
                return
            except Exception:
                continue

    def _emit_closed(self, exit_code: int) -> None:
        if self._closed:
            return
        self._closed = True
        self.closed.emit(exit_code)
