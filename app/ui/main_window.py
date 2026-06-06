from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QMainWindow, QTabWidget

from app.core.app_context import AppContext
from app.ui.files.file_manager_dock import FileManagerDock
from app.ui.history.history_dock import HistoryDock
from app.ui.monitor.monitor_dock import MonitorDock
from app.ui.sessions.ssh_connection_dialog import SshConnectionDialog
from app.ui.sessions.sessions_dock import SessionsDock
from app.ui.terminal.terminal_view import TerminalView


class MainWindow(QMainWindow):
    """主窗口和基础 Dock 布局."""

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self._context = context
        self._tabs = QTabWidget(self)
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)

        self.setWindowTitle("Whose Shell")
        self.resize(1200, 780)
        self.setCentralWidget(self._tabs)

        self._build_actions()
        self._build_docks()
        self._wire_events()
        self._new_local_terminal()

    def _build_actions(self) -> None:
        new_terminal = QAction("New Local Shell", self)
        new_terminal.triggered.connect(self._new_local_terminal)

        new_ssh = QAction("New SSH Shell", self)
        new_ssh.triggered.connect(self._new_ssh_terminal)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)

        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(new_terminal)
        file_menu.addAction(new_ssh)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addAction(new_terminal)
        toolbar.addAction(new_ssh)

    def _build_docks(self) -> None:
        sessions = SessionsDock(self)
        history = HistoryDock(self)
        files = FileManagerDock(self)
        monitor = MonitorDock(self)

        self.addDockWidget(Qt.LeftDockWidgetArea, self._dock("Sessions", sessions))
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
        backend = self._context.session_manager.create_local_terminal()
        view = TerminalView(backend, self)
        index = self._tabs.addTab(view, "Local")
        self._tabs.setCurrentIndex(index)
        backend.start()

    def _new_ssh_terminal(self) -> None:
        dialog = SshConnectionDialog(self)
        if dialog.exec() != SshConnectionDialog.Accepted:
            return
        config = dialog.connection_config()
        backend = self._context.session_manager.create_ssh_terminal(config)
        view = TerminalView(backend, self)
        index = self._tabs.addTab(view, f"SSH {config.username}@{config.host}")
        self._tabs.setCurrentIndex(index)
        backend.start()

    def _close_tab(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if isinstance(widget, TerminalView):
            widget.stop()
        self._tabs.removeTab(index)
        widget.deleteLater()

    def closeEvent(self, event) -> None:
        for index in range(self._tabs.count()):
            widget = self._tabs.widget(index)
            if isinstance(widget, TerminalView):
                widget.stop()
        super().closeEvent(event)
