from __future__ import annotations

import sqlite3

import pytest

from app.common.models import (
    AppSettings,
    ConflictPolicy,
    ConnectionType,
    SshConnectionConfig,
    ThemeMode,
    TransferDirection,
    TransferStatus,
)
from app.storage.migrations import migrate
from app.storage.repositories import (
    CommandRepository,
    ConnectionRepository,
    FavoriteRepository,
    FileTransferRepository,
    SessionRepository,
    SettingsRepository,
)


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    return connection


def test_migrate_creates_phase_one_tables_idempotently() -> None:
    connection = _connection()

    migrate(connection)

    rows = connection.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table'
          AND name IN ('commands', 'favorites', 'settings')
        """
    ).fetchall()
    assert {row["name"] for row in rows} == {"commands", "favorites", "settings"}


def test_migrate_creates_file_transfers_table_idempotently() -> None:
    connection = _connection()

    migrate(connection)

    row = connection.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'file_transfers'
        """
    ).fetchone()
    assert row["name"] == "file_transfers"


def test_migrate_preserves_existing_connection_and_session_rows() -> None:
    connection = _connection()
    connections = ConnectionRepository(connection)
    sessions = SessionRepository(connection)
    local_connection = connections.ensure_local_connection()
    session = sessions.create_session(local_connection, "Local Shell")

    migrate(connection)

    assert connections.get_connection(local_connection.id).name == "Local Shell"
    assert sessions.get_session(session.id).title == "Local Shell"


def test_command_repository_creates_lists_searches_and_filters_commands() -> None:
    connection = _connection()
    connections = ConnectionRepository(connection)
    sessions = SessionRepository(connection)
    commands = CommandRepository(connection)
    local_connection = connections.ensure_local_connection()
    session = sessions.create_session(local_connection, "Local Shell", "C:/workspace")

    first = commands.create_command(
        "dir",
        ConnectionType.LOCAL,
        session_id=session.id,
        connection_id=local_connection.id,
        cwd="C:/workspace",
        started_at="2026-06-10 10:00:00",
    )
    second = commands.create_command(
        "echo hello",
        ConnectionType.LOCAL,
        session_id=session.id,
        connection_id=local_connection.id,
        cwd="C:/workspace",
        started_at="2026-06-10 10:01:00",
        exit_code=0,
    )

    assert [command.command_text for command in commands.list_commands()] == ["echo hello", "dir"]
    assert commands.list_commands(search_text="hello") == [second]
    assert commands.list_commands(connection_id=local_connection.id) == [second, first]
    assert commands.update_exit_code(first.id, 1).exit_code == 1


def test_command_repository_keeps_command_snapshot_after_connection_delete() -> None:
    connection = _connection()
    connections = ConnectionRepository(connection)
    sessions = SessionRepository(connection)
    commands = CommandRepository(connection)
    local_connection = connections.ensure_local_connection()
    session = sessions.create_session(local_connection, "Local Shell")
    command = commands.create_command(
        "whoami",
        ConnectionType.LOCAL,
        session_id=session.id,
        connection_id=local_connection.id,
        host="localhost",
    )

    connection.execute("DELETE FROM connections WHERE id = ?", (local_connection.id,))
    connection.commit()

    preserved = commands.get_command(command.id)
    assert preserved.command_text == "whoami"
    assert preserved.session_id is None
    assert preserved.connection_id is None
    assert preserved.host == "localhost"


def test_command_repository_rejects_empty_commands() -> None:
    commands = CommandRepository(_connection())

    with pytest.raises(ValueError, match="Command text cannot be empty"):
        commands.create_command("   ", ConnectionType.LOCAL)


def test_favorite_repository_adds_lists_and_removes_favorites() -> None:
    favorites = FavoriteRepository(_connection())

    favorite = favorites.add_favorite(" git status ")
    duplicate = favorites.add_favorite("git status")

    assert favorite.command_text == "git status"
    assert duplicate.id == favorite.id
    assert favorites.is_favorite("git status")
    assert [item.command_text for item in favorites.list_favorites()] == ["git status"]

    favorites.remove_favorite("git status")

    assert not favorites.is_favorite("git status")


def test_settings_repository_returns_defaults_and_persists_values() -> None:
    connection = _connection()
    settings = SettingsRepository(connection)

    assert settings.get_settings() == AppSettings()

    saved = settings.save_settings(
        AppSettings(
            terminal_cols=120,
            terminal_rows=40,
            terminal_font_family="Cascadia Mono",
            terminal_font_size=14,
            default_local_shell="pwsh.exe",
            restore_tabs_on_startup=False,
            theme_mode=ThemeMode.DARK,
        )
    )

    assert saved.terminal_cols == 120
    assert saved.terminal_rows == 40
    assert saved.terminal_font_family == "Cascadia Mono"
    assert saved.terminal_font_size == 14
    assert saved.default_local_shell == "pwsh.exe"
    assert not saved.restore_tabs_on_startup
    assert saved.theme_mode == ThemeMode.DARK
    assert SettingsRepository(connection).get_settings() == saved


def test_settings_repository_falls_back_when_stored_values_are_invalid() -> None:
    settings = SettingsRepository(_connection())

    settings.set_value("terminal.default_cols", "bad")
    settings.set_value("appearance.theme_mode", "unknown")

    loaded = settings.get_settings()
    assert loaded.terminal_cols == AppSettings().terminal_cols
    assert loaded.theme_mode == ThemeMode.SYSTEM


def test_file_transfer_repository_tracks_status_progress_and_errors() -> None:
    connection = _connection()
    transfers = FileTransferRepository(connection)

    queued = transfers.create_transfer(
        TransferDirection.UPLOAD,
        "C:/local/report.txt",
        "/tmp/report.txt",
        conflict_policy=ConflictPolicy.RENAME,
        host="example.test",
        total_bytes=512,
    )

    assert queued.direction == TransferDirection.UPLOAD
    assert queued.status == TransferStatus.QUEUED
    assert queued.conflict_policy == ConflictPolicy.RENAME
    assert queued.bytes_transferred == 0
    assert queued.total_bytes == 512

    running = transfers.mark_running(queued.id)
    assert running.status == TransferStatus.RUNNING
    assert running.started_at is not None

    progressed = transfers.update_progress(queued.id, 128)
    assert progressed.bytes_transferred == 128

    failed = transfers.fail_transfer(queued.id, "Permission denied")
    assert failed.status == TransferStatus.FAILED
    assert failed.error_message == "Permission denied"
    assert failed.finished_at is not None


def test_file_transfer_repository_keeps_snapshot_after_connection_delete() -> None:
    connection = _connection()
    connections = ConnectionRepository(connection)
    transfers = FileTransferRepository(connection)
    ssh_connection = connections.save_ssh_connection(
        SshConnectionConfig(
            name="Demo SSH",
            host="example.test",
            port=22,
            username="demo",
            auth_method="none",
        )
    )
    transfer = transfers.create_transfer(
        TransferDirection.DOWNLOAD,
        "/remote/file.txt",
        "C:/local/file.txt",
        connection_id=ssh_connection.id,
        host=ssh_connection.host,
    )

    connections.delete_ssh_connection(ssh_connection.id)

    preserved = transfers.get_transfer(transfer.id)
    assert preserved.connection_id is None
    assert preserved.host == "example.test"
    assert preserved.source_path == "/remote/file.txt"
