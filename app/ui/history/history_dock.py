from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.common.models import CommandRecord, ConnectionType, FavoriteCommand
from app.core.session_manager import SessionManager


class HistoryDock(QWidget):
    """命令历史面板."""

    rerun_requested = Signal(str)

    _COMMAND_ROLE = Qt.UserRole

    def __init__(self, session_manager: SessionManager, parent=None) -> None:
        super().__init__(parent)
        self._session_manager = session_manager
        self._commands: list[CommandRecord] = []
        self._build_ui()
        self.refresh()

    def refresh(self) -> None:
        self._refresh_hosts()
        self._load_commands()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        filters = QHBoxLayout()
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search commands")
        self._search.textChanged.connect(self._load_commands)
        filters.addWidget(self._search, 2)

        self._host = QComboBox(self)
        self._host.currentIndexChanged.connect(self._load_commands)
        filters.addWidget(self._host, 1)

        self._connection_type = QComboBox(self)
        self._connection_type.addItem("All", None)
        self._connection_type.addItem("Local", ConnectionType.LOCAL)
        self._connection_type.addItem("SSH", ConnectionType.SSH)
        self._connection_type.currentIndexChanged.connect(self._load_commands)
        filters.addWidget(self._connection_type)

        self._favorites_only = QCheckBox("Favorites", self)
        self._favorites_only.toggled.connect(self._load_commands)
        filters.addWidget(self._favorites_only)
        layout.addLayout(filters)

        self._table = QTableWidget(0, 6, self)
        self._table.setHorizontalHeaderLabels(["Fav", "Command", "Type", "Host", "Started", "Exit"])
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            """
            QTableWidget::item:selected {
                background: #e5e7eb;
                color: #111827;
            }
            QTableWidget::item:selected:!active {
                background: #eceff3;
                color: #111827;
            }
            """
        )
        self._table.verticalHeader().hide()
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.doubleClicked.connect(self._rerun_selected)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table, 1)

        actions = QHBoxLayout()
        self._favorite = QPushButton("Favorite", self)
        self._favorite.clicked.connect(self._toggle_selected_favorite)
        actions.addWidget(self._favorite)
        self._rerun = QPushButton("Run", self)
        self._rerun.clicked.connect(self._rerun_selected)
        actions.addWidget(self._rerun)
        self._refresh = QPushButton("Refresh", self)
        self._refresh.clicked.connect(self.refresh)
        actions.addWidget(self._refresh)
        actions.addStretch(1)
        layout.addLayout(actions)

    def _refresh_hosts(self) -> None:
        current = self._host.currentData() if self._host.count() else None
        hosts = sorted({command.host for command in self._session_manager.list_commands() if command.host})
        self._host.blockSignals(True)
        self._host.clear()
        self._host.addItem("All hosts", None)
        for host in hosts:
            self._host.addItem(host, host)
        index = self._host.findData(current)
        self._host.setCurrentIndex(index if index >= 0 else 0)
        self._host.blockSignals(False)

    def _load_commands(self) -> None:
        search = self._search.text().strip() or None
        host = self._host.currentData()
        connection_type = self._connection_type.currentData()
        if self._favorites_only.isChecked():
            favorites = self._session_manager.list_favorites()
            if search:
                favorites = [favorite for favorite in favorites if search.lower() in favorite.command_text.lower()]
            self._commands = []
            self._render_favorites(favorites)
            return
        commands = self._session_manager.list_commands(
            search_text=search,
            host=host,
            connection_type=connection_type,
        )
        self._commands = commands
        self._render_commands()

    def _render_commands(self) -> None:
        self._table.setRowCount(len(self._commands))
        for row, command in enumerate(self._commands):
            favorite = "*" if self._session_manager.is_favorite(command.command_text) else ""
            values = [
                favorite,
                command.command_text,
                command.connection_type.value,
                command.host or "",
                command.started_at or "",
                "" if command.exit_code is None else str(command.exit_code),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(self._COMMAND_ROLE, command.command_text)
                if column != 1:
                    item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(row, column, item)
        self._table.resizeColumnsToContents()

    def _render_favorites(self, favorites: list[FavoriteCommand]) -> None:
        self._table.setRowCount(len(favorites))
        for row, favorite in enumerate(favorites):
            values = [
                "*",
                favorite.command_text,
                "",
                "",
                favorite.last_used_at or favorite.created_at or "",
                "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(self._COMMAND_ROLE, favorite.command_text)
                if column != 1:
                    item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(row, column, item)
        self._table.resizeColumnsToContents()

    def _show_context_menu(self, position) -> None:
        if self._selected_command_text() is None:
            return
        menu = QMenu(self)
        run_action = menu.addAction("Run")
        command_text = self._selected_command_text() or ""
        favorite_label = "Unfavorite" if self._session_manager.is_favorite(command_text) else "Favorite"
        favorite_action = menu.addAction(favorite_label)

        selected = menu.exec(self._table.viewport().mapToGlobal(position))
        if selected == run_action:
            self._rerun_selected()
        elif selected == favorite_action:
            self._toggle_selected_favorite()

    def _toggle_selected_favorite(self) -> None:
        command_text = self._selected_command_text()
        if not command_text:
            return
        if self._session_manager.is_favorite(command_text):
            self._session_manager.remove_favorite(command_text)
        else:
            self._session_manager.add_favorite(command_text)
        self._load_commands()

    def _rerun_selected(self, _index=None) -> None:
        command_text = self._selected_command_text()
        if command_text:
            self.rerun_requested.emit(command_text)

    def _selected_command_text(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 1)
        if item is None:
            return None
        return str(item.data(self._COMMAND_ROLE) or item.text()).strip() or None
