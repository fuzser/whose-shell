from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.common.models import ConnectionType
from app.common.signals import EventBus
from app.core.session_manager import SessionManager
from app.storage.migrations import migrate
from app.storage.repositories import (
    CommandRepository,
    ConnectionRepository,
    FavoriteRepository,
    SessionRepository,
    SettingsRepository,
)
from app.storage.secrets import SecretStore
from app.ui.history.history_dock import HistoryDock


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    return connection


def _session_manager(connection: sqlite3.Connection) -> SessionManager:
    return SessionManager(
        EventBus(),
        ConnectionRepository(connection),
        SessionRepository(connection),
        CommandRepository(connection),
        FavoriteRepository(connection),
        SettingsRepository(connection),
        SecretStore(),
    )


def test_favorites_filter_shows_one_row_per_favorite_command_text() -> None:
    app = QApplication.instance() or QApplication([])
    _ = app
    connection = _connection()
    commands = CommandRepository(connection)
    favorites = FavoriteRepository(connection)
    commands.create_command(
        "git status",
        ConnectionType.LOCAL,
        started_at="2026-06-13 10:00:00",
    )
    commands.create_command(
        "git status",
        ConnectionType.LOCAL,
        started_at="2026-06-13 10:01:00",
    )
    favorites.add_favorite("git status")

    dock = HistoryDock(_session_manager(connection))
    dock._search.setText("git status")

    assert dock._table.rowCount() == 2

    dock._favorites_only.setChecked(True)

    assert dock._table.rowCount() == 1
    assert dock._table.item(0, 1).text() == "git status"
