from __future__ import annotations

import asyncio
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.backends.terminal_base import TerminalBackend
from app.common.models import SshConnectionConfig


class SshTerminalBackend(TerminalBackend):
    """SSH 终端后端."""

    def __init__(self, config: SshConnectionConfig) -> None:
        super().__init__()
        self._config = config
        self._worker: SshTerminalWorker | None = None

    def start(self) -> None:
        if self._worker is not None:
            return
        self._worker = SshTerminalWorker(self._config)
        self._worker.output_received.connect(self.output_received.emit)
        self._worker.connected.connect(self.connected.emit)
        self._worker.closed.connect(self._handle_worker_closed)
        self._worker.error.connect(self.error.emit)
        self._worker.start()

    def write(self, data: bytes) -> None:
        if self._worker is not None:
            self._worker.write(data)

    def resize(self, cols: int, rows: int) -> None:
        if self._worker is not None:
            self._worker.resize(cols, rows)

    def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.request_stop()

    def _handle_worker_closed(self, exit_code: int) -> None:
        self._worker = None
        self.closed.emit(exit_code)


class SshTerminalWorker(QThread):
    """在后台线程中运行 asyncssh 终端会话."""

    output_received = Signal(bytes)
    connected = Signal()
    closed = Signal(int)
    error = Signal(str)

    def __init__(self, config: SshConnectionConfig) -> None:
        super().__init__()
        self._config = config
        self._loop: asyncio.AbstractEventLoop | None = None
        self._write_queue: asyncio.Queue[bytes | None] | None = None
        self._pending_input: list[bytes] = []
        self._process: Any | None = None
        self._connection: Any | None = None
        self._stopping = False
        self._cols = config.cols
        self._rows = config.rows

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_session())
        finally:
            self._loop.close()
            self._loop = None

    def write(self, data: bytes) -> None:
        """线程安全写入远端终端."""
        if self._loop is None or self._write_queue is None:
            self._pending_input.append(data)
            return
        self._loop.call_soon_threadsafe(self._write_queue.put_nowait, data)

    def resize(self, cols: int, rows: int) -> None:
        """线程安全调整远端 PTY 大小."""
        self._cols = cols
        self._rows = rows
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._resize_in_loop, cols, rows)

    def request_stop(self) -> None:
        """请求关闭 SSH 会话."""
        self._stopping = True
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._stop_in_loop)

    async def _run_session(self) -> None:
        try:
            import asyncssh
        except ImportError:
            self.error.emit("asyncssh is not installed. Run: pip install -e .")
            self.closed.emit(1)
            return

        self._write_queue = asyncio.Queue()
        for data in self._pending_input:
            self._write_queue.put_nowait(data)
        self._pending_input.clear()

        connect_kwargs: dict[str, Any] = {
            "host": self._config.host,
            "port": self._config.port,
            "username": self._config.username,
        }
        if self._config.password:
            connect_kwargs["password"] = self._config.password
        if self._config.private_key_path:
            connect_kwargs["client_keys"] = [self._config.private_key_path]
        if self._config.accept_unknown_host:
            # 最小版本允许跳过 known_hosts 校验, 便于连接新主机. 后续应加入主机指纹确认 UI.
            connect_kwargs["known_hosts"] = None

        try:
            self._connection = await asyncssh.connect(**connect_kwargs)
            self._process = await self._connection.create_process(
                term_type="xterm-256color",
                term_size=(self._cols, self._rows),
                encoding=None,
            )
            self.connected.emit()
            if self._config.default_directory:
                await self._write_to_process(f"cd {self._quote_shell_path(self._config.default_directory)}\n".encode())

            reader = asyncio.create_task(self._read_output())
            writer = asyncio.create_task(self._write_input())
            done, pending = await asyncio.wait(
                {reader, writer},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
            exit_code = await self._wait_for_exit()
            self.closed.emit(exit_code)
        except asyncio.CancelledError:
            self.closed.emit(0)
        except Exception as exc:
            self.error.emit(f"SSH error: {exc}")
            self.closed.emit(1)
        finally:
            await self._close_connection()

    async def _read_output(self) -> None:
        while not self._stopping and self._process is not None:
            data = await self._process.stdout.read(4096)
            if not data:
                break
            if isinstance(data, str):
                data = data.encode("utf-8", errors="replace")
            self.output_received.emit(bytes(data))

    async def _write_input(self) -> None:
        while not self._stopping and self._write_queue is not None:
            data = await self._write_queue.get()
            if data is None:
                break
            await self._write_to_process(data)

    async def _write_to_process(self, data: bytes) -> None:
        if self._process is None:
            return
        self._process.stdin.write(data)
        drain = getattr(self._process.stdin, "drain", None)
        if drain is not None:
            await drain()

    async def _wait_for_exit(self) -> int:
        if self._process is None:
            return 0
        result = await self._process.wait()
        if isinstance(result, int):
            return result
        return 0

    async def _close_connection(self) -> None:
        if self._process is not None:
            close = getattr(self._process, "close", None)
            if close is not None:
                close()
            else:
                self._process.terminate()
            wait_closed = getattr(self._process, "wait_closed", None)
            if wait_closed is not None:
                await wait_closed()
        if self._connection is not None:
            self._connection.close()
            await self._connection.wait_closed()

    def _resize_in_loop(self, cols: int, rows: int) -> None:
        if self._process is None:
            return
        self._process.change_terminal_size(cols, rows, 0, 0)

    def _stop_in_loop(self) -> None:
        if self._write_queue is not None:
            self._write_queue.put_nowait(None)
        if self._process is not None:
            self._process.terminate()

    def _quote_shell_path(self, path: str) -> str:
        """为 cd 命令做最小 shell 单引号转义."""
        return "'" + path.replace("'", "'\"'\"'") + "'"
