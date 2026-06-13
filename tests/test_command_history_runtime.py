from __future__ import annotations

import sqlite3

from app.common.signals import EventBus
from app.core.command_capture import CommandInputCapture
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


def test_command_input_capture_records_submitted_single_line_commands() -> None:
    capture = CommandInputCapture()

    assert capture.feed(b"dir") == []
    assert capture.feed(b"\x7f") == []
    assert capture.feed(b"r\r") == ["dir"]


def test_command_input_capture_ignores_empty_and_control_sequences() -> None:
    capture = CommandInputCapture()

    assert capture.feed(b"   \r") == []
    assert capture.feed(b"git status\x1b[D\r") == ["git status"]
    assert capture.feed(b"partial\x03\r") == []


def test_session_manager_records_commands_with_session_metadata() -> None:
    connection = _connection()
    manager = _session_manager(connection)
    local_connection = ConnectionRepository(connection).ensure_local_connection()
    session = SessionRepository(connection).create_session(local_connection, "Local Shell", "C:/work")

    command = manager.record_command(session.id, " git status ")

    assert command is not None
    assert command.command_text == "git status"
    assert command.session_id == session.id
    assert command.connection_id == local_connection.id
    assert command.connection_type == session.connection_type
    assert command.cwd == "C:/work"
    assert manager.list_commands(search_text="status") == [command]


def test_session_manager_favorites_commands() -> None:
    manager = _session_manager(_connection())

    favorite = manager.add_favorite(" pytest ")

    assert favorite.command_text == "pytest"
    assert manager.is_favorite("pytest")
    assert [item.command_text for item in manager.list_favorites()] == ["pytest"]

    manager.remove_favorite("pytest")

    assert not manager.is_favorite("pytest")
