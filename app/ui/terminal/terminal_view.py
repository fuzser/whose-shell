from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.backends.terminal_base import TerminalBackend
from app.ui.terminal.terminal_widget import TerminalWidget


class TerminalView(QWidget):
    """终端视图, 连接 UI 控件和后端."""

    _INFO_COLOR = QColor("#88c0d0")
    _SUCCESS_COLOR = QColor("#a3be8c")
    _ERROR_COLOR = QColor("#bf616a")

    def __init__(self, backend: TerminalBackend, session_id: int, connection_id: int, parent=None) -> None:
        super().__init__(parent)
        self._backend = backend
        self.session_id = session_id
        self.connection_id = connection_id
        self.is_connected = True
        self._terminal = TerminalWidget(self)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocusProxy(self._terminal)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._terminal)

        self._terminal.input_requested.connect(self._backend.write)
        self._terminal.resized.connect(self._backend.resize)
        self._backend.output_received.connect(self._terminal.append_output)
        self._backend.connected.connect(self._show_connected)
        self._backend.error.connect(self._show_error)
        self._backend.closed.connect(self._handle_closed)

    def show_connecting(self) -> None:
        self._show_connecting()

    def show_disconnecting(self) -> None:
        self._terminal.set_terminal_cursor_enabled(False)
        self._terminal.append_system_message("[disconnecting] Disconnecting...", self._ERROR_COLOR)

    def show_restored_disconnected(self) -> None:
        self.is_connected = False
        self._terminal.set_terminal_cursor_enabled(False)
        self._terminal.append_system_message("[disconnected] Restored from previous session.", self._ERROR_COLOR)

    def content_snapshot(self) -> str:
        return self._terminal.content_snapshot()

    def restore_content_snapshot(self, content: str) -> None:
        self._terminal.restore_content_snapshot(content)

    def archive_screen_to_scrollback(self) -> None:
        self._terminal.archive_screen_to_scrollback()

    def sync_backend_size(self) -> None:
        """把当前可见终端尺寸同步给后端 PTY."""
        if self._terminal.sync_terminal_size():
            self._backend.resize(*self._terminal.terminal_size())

    def apply_font_settings(self, family: str, point_size: int) -> None:
        """应用终端字体设置并同步后端尺寸."""
        self._terminal.set_terminal_font(family, point_size)
        self.sync_backend_size()

    def focus_terminal(self) -> None:
        self._terminal.setFocus(Qt.OtherFocusReason)

    def _show_error(self, message: str) -> None:
        self._terminal.append_system_message(f"[error] {message}", self._ERROR_COLOR)

    def _handle_closed(self, exit_code: int) -> None:
        self.is_connected = False
        self._terminal.set_terminal_cursor_enabled(False)
        self._terminal.append_system_message(f"[disconnected] Connection closed with exit code {exit_code}.", self._ERROR_COLOR)

    def _show_connecting(self) -> None:
        self._terminal.set_terminal_cursor_enabled(True)
        self._terminal.append_system_message("[connecting] Connecting...", self._INFO_COLOR)

    def _show_connected(self) -> None:
        self.is_connected = True
        self._terminal.set_terminal_cursor_enabled(True)
        # 真实 PTY 会用绝对坐标重绘输入行, 连接提示不能留在同一个终端坐标空间里.
        self._terminal.clear_screen()
