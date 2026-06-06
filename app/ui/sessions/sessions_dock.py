from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.common.models import ConnectionRecord, ConnectionType, SessionRecord
from app.core.session_manager import SessionManager


class SessionsDock(QWidget):
    """会话和连接管理面板."""

    new_local_requested = Signal()
    new_ssh_requested = Signal()
    open_connection_requested = Signal(int)
    edit_connection_requested = Signal(int)
    delete_connection_requested = Signal(int)

    def __init__(self, session_manager: SessionManager, parent=None) -> None:
        super().__init__(parent)
        self._session_manager = session_manager

        self._connections = QListWidget(self)
        self._connections.setSelectionMode(QAbstractItemView.SingleSelection)
        self._connections.itemDoubleClicked.connect(lambda _item: self._open_selected_connection())
        self._connections.setContextMenuPolicy(Qt.CustomContextMenu)
        self._connections.customContextMenuRequested.connect(self._show_connection_menu)

        self._recent_sessions = QListWidget(self)
        self._recent_sessions.setSelectionMode(QAbstractItemView.NoSelection)

        self._recent_toggle = QToolButton(self)
        self._recent_toggle.setCheckable(True)
        self._recent_toggle.setChecked(False)
        self._recent_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._recent_toggle.clicked.connect(self._set_recent_expanded)

        new_local = QPushButton("New Local", self)
        new_local.clicked.connect(self.new_local_requested.emit)

        new_ssh = QPushButton("New SSH", self)
        new_ssh.clicked.connect(self.new_ssh_requested.emit)

        self._refresh_button = QToolButton(self)
        self._refresh_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self._refresh_button.setToolTip("Refresh connections and sessions")
        self._refresh_button.clicked.connect(self._refresh_with_feedback)

        button_row = QHBoxLayout()
        button_row.addWidget(new_local)
        button_row.addWidget(new_ssh)

        connection_title_row = QHBoxLayout()
        connection_title_row.addWidget(QLabel("Connections", self))
        connection_title_row.addStretch(1)
        connection_title_row.addWidget(self._refresh_button)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addLayout(connection_title_row)
        layout.addWidget(self._connections, 2)
        layout.addWidget(self._recent_toggle)
        layout.addWidget(self._recent_sessions, 1)

        self.refresh()
        self._set_recent_expanded(False)

    def refresh(self) -> None:
        """刷新连接和最近会话列表."""
        self._connections.clear()
        for connection in self._session_manager.list_connections():
            self._add_connection(connection)

        self._recent_sessions.clear()
        recent_sessions = self._session_manager.list_recent_sessions()
        for session in recent_sessions:
            self._add_session(session)
        self._update_recent_toggle_text(len(recent_sessions))
        self._refresh_button.setEnabled(True)

    def _refresh_with_feedback(self) -> None:
        """给用户明确的手动刷新反馈."""
        self._refresh_button.setEnabled(False)
        self._connections.clear()
        self._recent_sessions.clear()
        self._update_recent_toggle_text(0)
        QTimer.singleShot(300, self.refresh)

    def _add_connection(self, connection: ConnectionRecord) -> None:
        label = connection.name
        if connection.connection_type == ConnectionType.LOCAL:
            label = "Local Shell"
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, connection.id)
        item.setData(Qt.UserRole + 1, connection.connection_type.value)
        self._connections.addItem(item)

    def _add_session(self, session: SessionRecord) -> None:
        started_at = session.started_at or ""
        item = QListWidgetItem(f"#{session.id} {session.title} [{session.status.value}] {started_at}")
        self._recent_sessions.addItem(item)

    def _open_selected_connection(self) -> None:
        item = self._connections.currentItem()
        if item is None:
            return
        connection_id = item.data(Qt.UserRole)
        if connection_id is None:
            return
        self.open_connection_requested.emit(int(connection_id))

    def _show_connection_menu(self, position) -> None:
        item = self._connections.itemAt(position)
        if item is None:
            return
        self._connections.setCurrentItem(item)
        connection_id = int(item.data(Qt.UserRole))
        connection_type = item.data(Qt.UserRole + 1)
        is_ssh = connection_type == ConnectionType.SSH.value

        menu = QMenu(self)
        open_action = menu.addAction("Open")
        edit_action = menu.addAction("Edit Configuration")
        delete_action = menu.addAction("Delete")
        edit_action.setEnabled(is_ssh)
        delete_action.setEnabled(is_ssh)

        selected = menu.exec(self._connections.viewport().mapToGlobal(position))
        if selected == open_action:
            self.open_connection_requested.emit(connection_id)
        elif selected == edit_action and is_ssh:
            self.edit_connection_requested.emit(connection_id)
        elif selected == delete_action and is_ssh:
            self.delete_connection_requested.emit(connection_id)

    def _set_recent_expanded(self, expanded: bool) -> None:
        self._recent_toggle.setChecked(expanded)
        self._recent_toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self._recent_sessions.setVisible(expanded)

    def _update_recent_toggle_text(self, count: int) -> None:
        self._recent_toggle.setText(f"Recent Sessions ({count})")
