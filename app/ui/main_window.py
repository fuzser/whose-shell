from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QMainWindow, QMenu, QMessageBox, QTabWidget

from app.common.models import ConnectionType, SavedTerminalTab
from app.core.app_context import AppContext
from app.ui.files.file_manager_dock import FileManagerDock
from app.ui.history.history_dock import HistoryDock
from app.ui.monitor.monitor_dock import MonitorDock
from app.ui.sessions.ssh_connection_dialog import SshConnectionDialog
from app.ui.sessions.sessions_dock import SessionsDock
from app.ui.terminal.terminal_view import TerminalView


class MainWindow(QMainWindow):
    """主窗口和基础 Dock 布局."""

    _CONNECTED_PREFIX = "🟢 "
    _DISCONNECTED_PREFIX = "🔴 "
    _TAB_CLOSE_CLEANUP_DELAY_MS = 80

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self._context = context
        self._tabs = QTabWidget(self)
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self._tabs.tabBar().customContextMenuRequested.connect(self._show_tab_menu)
        self._sessions_dock_widget: QDockWidget | None = None
        self._sessions_panel: SessionsDock | None = None
        self._closed_session_ids: set[int] = set()
        self._closing_views: list[TerminalView] = []

        self.setWindowTitle("Whose Shell")
        self.resize(1200, 780)
        self.setCentralWidget(self._tabs)

        self._build_actions()
        self._build_docks()
        self._wire_events()
        if not self._restore_active_tabs():
            self._new_local_terminal()

    def _build_actions(self) -> None:
        new_terminal = QAction("New Local Shell", self)
        new_terminal.triggered.connect(self._new_local_terminal)

        new_ssh = QAction("New SSH Shell", self)
        new_ssh.triggered.connect(self._new_ssh_terminal)

        show_sessions = QAction("Sessions", self)
        show_sessions.triggered.connect(self._show_sessions_dock)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)

        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(new_terminal)
        file_menu.addAction(new_ssh)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(show_sessions)

    def _build_docks(self) -> None:
        sessions = SessionsDock(self._context.session_manager, self)
        sessions.new_local_requested.connect(self._new_local_terminal)
        sessions.new_ssh_requested.connect(self._new_ssh_terminal)
        sessions.open_connection_requested.connect(self._open_connection)
        sessions.edit_connection_requested.connect(self._edit_connection)
        sessions.delete_connection_requested.connect(self._delete_connection)
        self._sessions_panel = sessions
        self._sessions_dock_widget = self._dock("Sessions", sessions)

        history = HistoryDock(self)
        files = FileManagerDock(self)
        monitor = MonitorDock(self)

        self.addDockWidget(Qt.LeftDockWidgetArea, self._sessions_dock_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self._dock("History", history))
        self.addDockWidget(Qt.BottomDockWidgetArea, self._dock("File Manager", files))
        self.addDockWidget(Qt.BottomDockWidgetArea, self._dock("Monitor", monitor))

    def _dock(self, title: str, widget) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        return dock

    def _wire_events(self) -> None:
        self._context.event_bus.status_message.connect(self.statusBar().showMessage)

    def _new_local_terminal(self) -> None:
        managed_session = self._context.session_manager.create_local_terminal()
        self._add_terminal_tab(managed_session, "Local")
        self._refresh_sessions_panel()

    def _new_ssh_terminal(self) -> None:
        dialog = SshConnectionDialog(self)
        if dialog.exec() != SshConnectionDialog.Accepted:
            return
        config = dialog.connection_config()
        managed_session = self._context.session_manager.create_ssh_terminal(config)
        self._add_terminal_tab(managed_session, managed_session.session.title)
        self._refresh_sessions_panel()

    def _open_connection(self, connection_id: int) -> None:
        managed_session = self._context.session_manager.create_terminal_from_connection(connection_id)
        self._add_terminal_tab(managed_session, managed_session.session.title)
        self._refresh_sessions_panel()

    def _edit_connection(self, connection_id: int) -> None:
        connection = self._context.session_manager.get_connection(connection_id)
        dialog = SshConnectionDialog(self, connection=connection)
        if dialog.exec() != SshConnectionDialog.Accepted:
            return
        updated = self._context.session_manager.update_ssh_connection(connection_id, dialog.connection_config())
        self._rename_tabs_for_connection(connection_id, updated.name)
        self._refresh_sessions_panel()

    def _delete_connection(self, connection_id: int) -> None:
        connection = self._context.session_manager.get_connection(connection_id)
        result = QMessageBox.question(
            self,
            "Delete SSH Connection",
            f"Delete saved connection {connection.name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if result != QMessageBox.Yes:
            return
        self._close_tabs_for_connection(connection_id)
        self._context.session_manager.delete_ssh_connection(connection_id)
        self._refresh_sessions_panel()

    def _add_terminal_tab(
        self,
        managed_session,
        title: str,
        *,
        start: bool = True,
        content_snapshot: str = "",
        archive_snapshot_on_connect: bool = False,
    ) -> None:
        view = TerminalView(
            managed_session.backend,
            managed_session.session.id,
            managed_session.session.connection_id,
            self,
        )
        managed_session.backend.closed.connect(
            lambda exit_code, session_id=managed_session.session.id: self._handle_terminal_closed(session_id, exit_code)
        )
        index = self._tabs.addTab(view, self._tab_title(title, connected=True))
        self._tabs.tabBar().setTabData(index, title)
        self._tabs.setCurrentIndex(index)
        if content_snapshot:
            view.restore_content_snapshot(content_snapshot)
        if archive_snapshot_on_connect:
            view.archive_snapshot_on_next_connect()
        if start:
            view.show_connecting()
            managed_session.backend.start()
        else:
            view.show_restored_disconnected()
            self._set_tab_connected(index, False)

    def _show_tab_menu(self, position) -> None:
        tab_index = self._tabs.tabBar().tabAt(position)
        if tab_index < 0:
            return
        widget = self._tabs.widget(tab_index)
        if not isinstance(widget, TerminalView):
            return

        connection = self._context.session_manager.get_connection(widget.connection_id)
        is_ssh = connection.connection_type == ConnectionType.SSH

        menu = QMenu(self)
        close_action = menu.addAction("Close Tab")
        lifecycle_action = menu.addAction("Disconnect" if widget.is_connected else "Reconnect")
        menu.addSeparator()
        edit_action = menu.addAction("Edit Configuration")
        edit_action.setEnabled(is_ssh)

        selected = menu.exec(self._tabs.tabBar().mapToGlobal(position))
        if selected == close_action:
            self._close_tab(tab_index)
        elif selected == lifecycle_action:
            if widget.is_connected:
                self._disconnect_tab(tab_index)
            else:
                self._reconnect_tab(tab_index)
        elif selected == edit_action and is_ssh:
            self._edit_connection(widget.connection_id)

    def _show_sessions_dock(self) -> None:
        if self._sessions_dock_widget is None:
            return
        if self.dockWidgetArea(self._sessions_dock_widget) == Qt.NoDockWidgetArea:
            self.addDockWidget(Qt.LeftDockWidgetArea, self._sessions_dock_widget)
        self._sessions_dock_widget.show()
        self._sessions_dock_widget.raise_()
        self._refresh_sessions_panel()

    def _refresh_sessions_panel(self) -> None:
        if self._sessions_panel is not None:
            self._sessions_panel.refresh()

    def _restore_active_tabs(self) -> bool:
        saved_tabs = self._context.session_manager.list_active_tabs()
        if not saved_tabs:
            return False

        current_index = 0
        restored_count = 0
        for saved_tab in saved_tabs:
            try:
                connection = self._context.session_manager.get_connection(saved_tab.connection_id)
                managed_session = self._context.session_manager.create_terminal_from_connection(saved_tab.connection_id)
            except Exception as exc:
                self._context.event_bus.status_message.emit(f"Tab was not restored: {exc}")
                continue
            should_start = connection.connection_type == ConnectionType.LOCAL
            self._add_terminal_tab(
                managed_session,
                saved_tab.title,
                start=should_start,
                content_snapshot=saved_tab.content,
                archive_snapshot_on_connect=should_start and bool(saved_tab.content),
            )
            if saved_tab.is_current:
                current_index = restored_count
            restored_count += 1

        if restored_count == 0:
            return False
        self._tabs.setCurrentIndex(min(current_index, self._tabs.count() - 1))
        self._refresh_sessions_panel()
        return True

    def _save_active_tabs(self) -> None:
        tabs: list[SavedTerminalTab] = []
        for index in range(self._tabs.count()):
            widget = self._tabs.widget(index)
            if not isinstance(widget, TerminalView):
                continue
            title = self._tabs.tabBar().tabData(index) or self._plain_tab_title(self._tabs.tabText(index))
            tabs.append(
                SavedTerminalTab(
                    connection_id=widget.connection_id,
                    title=str(title),
                    tab_order=index,
                    is_current=index == self._tabs.currentIndex(),
                    content=widget.content_snapshot(),
                )
            )
        self._context.session_manager.save_active_tabs(tabs)

    def _rename_tabs_for_connection(self, connection_id: int, title: str) -> None:
        for index in range(self._tabs.count()):
            widget = self._tabs.widget(index)
            if isinstance(widget, TerminalView) and widget.connection_id == connection_id:
                self._tabs.tabBar().setTabData(index, title)
                self._set_tab_connected(index, widget.is_connected)

    def _close_tabs_for_connection(self, connection_id: int) -> None:
        for index in range(self._tabs.count() - 1, -1, -1):
            widget = self._tabs.widget(index)
            if isinstance(widget, TerminalView) and widget.connection_id == connection_id:
                self._close_tab(index, defer_cleanup=False)

    def _close_tab(self, index: int, defer_cleanup: bool = True) -> None:
        widget = self._tabs.widget(index)
        if widget is None:
            return
        self._tabs.removeTab(index)
        self._tabs.tabBar().update()
        self._tabs.update()
        if isinstance(widget, TerminalView):
            if defer_cleanup:
                QTimer.singleShot(
                    self._TAB_CLOSE_CLEANUP_DELAY_MS,
                    lambda widget=widget: self._cleanup_closed_tab(widget),
                )
            else:
                self._cleanup_closed_tab(widget)
        else:
            widget.deleteLater()
            self._refresh_sessions_panel()

    def _cleanup_closed_tab(self, widget: TerminalView) -> None:
        widget.closed.connect(lambda _exit_code, widget=widget: self._finalize_closed_tab(widget))
        was_connected = widget.stop(notify=False)
        self._mark_session_closed(widget.session_id)
        if was_connected:
            self._closing_views.append(widget)
        else:
            self._finalize_closed_tab(widget)

    def _finalize_closed_tab(self, widget: TerminalView) -> None:
        if widget in self._closing_views:
            self._closing_views.remove(widget)
        widget.deleteLater()

    def _disconnect_tab(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if not isinstance(widget, TerminalView) or not widget.is_connected:
            return
        widget.stop()
        self._mark_session_closed(widget.session_id)
        self._set_tab_connected(index, False)

    def _reconnect_tab(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if not isinstance(widget, TerminalView) or widget.is_connected:
            return
        widget.archive_snapshot_on_next_connect()
        widget.reconnect()
        self._closed_session_ids.discard(widget.session_id)
        self._context.session_manager.reopen_session(widget.session_id)
        self._set_tab_connected(index, True)
        self._refresh_sessions_panel()

    def _handle_terminal_closed(self, session_id: int, exit_code: int) -> None:
        for index in range(self._tabs.count()):
            widget = self._tabs.widget(index)
            if isinstance(widget, TerminalView) and widget.session_id == session_id:
                widget.is_connected = False
                self._set_tab_connected(index, False)
                break
        self._mark_session_closed(session_id, exit_code)

    def _mark_session_closed(self, session_id: int, exit_code: int | None = None) -> None:
        if session_id in self._closed_session_ids:
            return
        self._closed_session_ids.add(session_id)
        self._context.session_manager.close_session(session_id, exit_code)
        self._refresh_sessions_panel()

    def _set_tab_connected(self, index: int, connected: bool) -> None:
        widget = self._tabs.widget(index)
        if isinstance(widget, TerminalView):
            widget.is_connected = connected
        title = self._tabs.tabBar().tabData(index) or self._plain_tab_title(self._tabs.tabText(index))
        self._tabs.setTabText(index, self._tab_title(str(title), connected))

    def _tab_title(self, title: str, connected: bool) -> str:
        return f"{self._CONNECTED_PREFIX if connected else self._DISCONNECTED_PREFIX}{title}"

    def _plain_tab_title(self, title: str) -> str:
        for prefix in (self._CONNECTED_PREFIX, self._DISCONNECTED_PREFIX):
            if title.startswith(prefix):
                return title[len(prefix) :]
        return title

    def closeEvent(self, event) -> None:
        self._save_active_tabs()
        for index in range(self._tabs.count()):
            widget = self._tabs.widget(index)
            if isinstance(widget, TerminalView):
                self._cleanup_closed_tab(widget)
        self._context.database.close()
        super().closeEvent(event)
