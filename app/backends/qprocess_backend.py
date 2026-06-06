from __future__ import annotations

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer

from app.backends.terminal_base import TerminalBackend
from app.common.models import TerminalSessionConfig
from app.common.platform import default_shell_command


class QProcessTerminalBackend(TerminalBackend):
    """基线本地进程后端.

    当前实现用于最小可用版本. 它不是完整 PTY, 不能满足 TUI 程序兼容目标.
    """

    def __init__(self, config: TerminalSessionConfig) -> None:
        super().__init__()
        self._config = config
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.readyReadStandardError.connect(self._read_output)
        self._process.started.connect(self.connected.emit)
        self._process.finished.connect(self._handle_finished)
        self._process.errorOccurred.connect(self._handle_error)
        self._pending_command = ""

    def start(self) -> None:
        command = self._config.command or default_shell_command()
        program = command[0]
        arguments = command[1:]
        if self._config.cwd:
            self._process.setWorkingDirectory(self._config.cwd)
        self._process.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
        self._process.start(program, arguments)

    def write(self, data: bytes) -> None:
        if self._process.state() == QProcess.Running:
            echo_data, process_data = self._handle_local_input(data)
            if echo_data:
                self.output_received.emit(echo_data)
            if process_data:
                self._process.write(process_data)

    def resize(self, cols: int, rows: int) -> None:
        _ = (cols, rows)
        # TODO: 完整 PTY 后端接入后, 在这里转发终端尺寸.

    def stop(self) -> None:
        if self._process.state() != QProcess.NotRunning:
            self._process.terminate()
            QTimer.singleShot(1500, self._kill_if_still_running)

    def _read_output(self) -> None:
        data = bytes(self._process.readAllStandardOutput())
        if data:
            self.output_received.emit(data)

    def _handle_finished(self, exit_code: int) -> None:
        self.closed.emit(exit_code)

    def _handle_error(self, error: QProcess.ProcessError) -> None:
        self.error.emit(f"Process error: {error.name}")

    def _kill_if_still_running(self) -> None:
        if self._process.state() != QProcess.NotRunning:
            self._process.kill()

    def _handle_local_input(self, data: bytes) -> tuple[bytes, bytes]:
        # QProcess stdin 不是 PTY, 先在本地完成行编辑, 回车时再提交最终命令.
        text = data.decode("utf-8", errors="ignore")
        visible_chars: list[str] = []
        process_chunks: list[bytes] = []
        index = 0
        while index < len(text):
            char = text[index]
            if char == "\x1b":
                index = self._skip_escape_sequence(text, index)
                continue
            if char == "\b":
                if self._pending_command:
                    visible_chars.append("\b \b")
                    self._pending_command = self._pending_command[:-1]
            elif char in {"\r", "\n"}:
                visible_chars.append("\r\n")
                process_chunks.append((self._pending_command + "\r\n").encode("utf-8"))
                self._pending_command = ""
                if char == "\r" and index + 1 < len(text) and text[index + 1] == "\n":
                    index += 1
            elif char == "\x03":
                process_chunks.append(b"\x03")
                self._pending_command = ""
            elif char == "\t" or char >= " ":
                visible_chars.append(char)
                self._pending_command += char
            index += 1
        return "".join(visible_chars).encode("utf-8"), b"".join(process_chunks)

    def _skip_escape_sequence(self, text: str, start: int) -> int:
        index = start + 1
        if index >= len(text):
            return len(text)
        if text[index] == "[":
            index += 1
            while index < len(text) and not ("@" <= text[index] <= "~"):
                index += 1
            return min(len(text), index + 1)
        return min(len(text), index + 1)
