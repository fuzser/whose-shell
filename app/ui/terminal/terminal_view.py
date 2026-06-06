from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.backends.terminal_base import TerminalBackend
from app.ui.terminal.terminal_widget import TerminalWidget


class TerminalView(QWidget):
    """终端视图, 连接 UI 控件和后端."""

    def __init__(self, backend: TerminalBackend, parent=None) -> None:
        super().__init__(parent)
        self._backend = backend
        self._terminal = TerminalWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._terminal)

        self._terminal.input_requested.connect(self._backend.write)
        self._terminal.resized.connect(self._backend.resize)
        self._backend.output_received.connect(self._terminal.append_output)
        self._backend.error.connect(self._show_error)
        self._backend.closed.connect(self._show_closed)

    def stop(self) -> None:
        self._backend.stop()

    def _show_error(self, message: str) -> None:
        self._terminal.append_output(f"\r\n[error] {message}\r\n".encode("utf-8"))

    def _show_closed(self, exit_code: int) -> None:
        self._terminal.append_output(f"\r\n[closed: {exit_code}]\r\n".encode("utf-8"))

