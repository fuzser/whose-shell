from __future__ import annotations

import asyncio
import os
import sqlite3
import stat
from dataclasses import dataclass

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.backends.sftp_backend import SftpBackend, SftpError
from app.common.models import ConnectionType, FileEntryType, SshConnectionConfig
from app.common.signals import EventBus
from app.core.file_manager import FileManager
from app.core.session_manager import SessionManager
from app.storage.migrations import migrate
from app.storage.repositories import (
    CommandRepository,
    ConnectionRepository,
    FavoriteRepository,
    SessionRepository,
    SettingsRepository,
)
from app.ui.files.file_manager_dock import RemoteFileTableModel


@dataclass
class _FakeAttrs:
    permissions: int
    size: int | None = None
    mtime: int | None = None


@dataclass
class _FakeName:
    filename: str
    attrs: _FakeAttrs


class _FakeSftp:
    def __init__(self) -> None:
        self.mkdir_calls: list[str] = []
        self.rename_calls: list[tuple[str, str]] = []
        self.remove_calls: list[str] = []
        self.rmdir_calls: list[str] = []

    async def scandir(self, path: str):
        assert path == "/srv"
        return [
            _FakeName("zeta.txt", _FakeAttrs(stat.S_IFREG | 0o644, size=9, mtime=1_700_000_000)),
            _FakeName("app", _FakeAttrs(stat.S_IFDIR | 0o755, mtime=1_700_000_100)),
        ]

    async def mkdir(self, path: str) -> None:
        self.mkdir_calls.append(path)

    async def rename(self, source: str, target: str) -> None:
        self.rename_calls.append((source, target))

    async def remove(self, path: str) -> None:
        self.remove_calls.append(path)

    async def rmdir(self, path: str) -> None:
        self.rmdir_calls.append(path)


class _FakeAsyncGeneratorSftp(_FakeSftp):
    async def scandir(self, path: str):
        assert path == "/srv"
        yield _FakeName("logs", _FakeAttrs(stat.S_IFDIR | 0o755, mtime=1_700_000_200))
        yield _FakeName("readme.txt", _FakeAttrs(stat.S_IFREG | 0o644, size=11, mtime=1_700_000_300))


class _FakeConnection:
    def __init__(self, sftp: _FakeSftp) -> None:
        self.sftp = sftp
        self.closed = False

    async def start_sftp_client(self) -> _FakeSftp:
        return self.sftp

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class _FakeAsyncssh:
    class PermissionDenied(Exception):
        pass

    class SFTPNoSuchFile(Exception):
        pass

    class SFTPPermissionDenied(Exception):
        pass

    def __init__(self, sftp: _FakeSftp | None = None, error: Exception | None = None) -> None:
        self.sftp = sftp or _FakeSftp()
        self.error = error
        self.kwargs: dict[str, object] | None = None
        self.connection: _FakeConnection | None = None

    async def connect(self, **kwargs):
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        self.connection = _FakeConnection(self.sftp)
        return self.connection


class _FakeSecretStore:
    def __init__(self) -> None:
        self.passwords: dict[int, str] = {}

    def set_connection_password(self, connection_id: int, password: str) -> None:
        self.passwords[connection_id] = password

    def get_connection_password(self, connection_id: int) -> str | None:
        return self.passwords.get(connection_id)

    def delete_connection_password(self, connection_id: int) -> None:
        self.passwords.pop(connection_id, None)

    def set_connection_passphrase(self, connection_id: int, passphrase: str) -> None:
        _ = (connection_id, passphrase)

    def get_connection_passphrase(self, connection_id: int) -> str | None:
        _ = connection_id
        return None

    def delete_connection_passphrase(self, connection_id: int) -> None:
        _ = connection_id


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    return connection


def _session_manager(connection: sqlite3.Connection, secrets: _FakeSecretStore) -> SessionManager:
    return SessionManager(
        EventBus(),
        ConnectionRepository(connection),
        SessionRepository(connection),
        CommandRepository(connection),
        FavoriteRepository(connection),
        SettingsRepository(connection),
        secrets,
    )


def test_sftp_backend_maps_remote_entries_and_reuses_ssh_config() -> None:
    fake_asyncssh = _FakeAsyncssh()
    backend = SftpBackend(
        SshConnectionConfig(
            host="example.test",
            port=2222,
            username="alice",
            password="secret",
            private_key_path="/keys/id_ed25519",
            private_key_passphrase="key-passphrase",
            accept_unknown_host=True,
        ),
        asyncssh_module=fake_asyncssh,
    )

    entries = asyncio.run(backend.list_directory("/srv"))

    assert [entry.name for entry in entries] == ["app", "zeta.txt"]
    assert entries[0].entry_type == FileEntryType.DIRECTORY
    assert entries[1].entry_type == FileEntryType.FILE
    assert entries[1].size == 9
    assert entries[1].permissions == "0o644"
    assert fake_asyncssh.kwargs == {
        "host": "example.test",
        "port": 2222,
        "username": "alice",
        "password": "secret",
        "client_keys": ["/keys/id_ed25519"],
        "passphrase": "key-passphrase",
        "known_hosts": None,
    }
    assert fake_asyncssh.connection is not None
    assert fake_asyncssh.connection.closed


def test_sftp_backend_accepts_async_generator_scandir_results() -> None:
    backend = SftpBackend(
        SshConnectionConfig(host="example.test", port=22, username="alice"),
        asyncssh_module=_FakeAsyncssh(_FakeAsyncGeneratorSftp()),
    )

    entries = asyncio.run(backend.list_directory("/srv"))

    assert [entry.name for entry in entries] == ["logs", "readme.txt"]
    assert entries[0].entry_type == FileEntryType.DIRECTORY
    assert entries[1].size == 11


def test_sftp_backend_formats_permission_and_missing_path_errors() -> None:
    permission_backend = SftpBackend(
        SshConnectionConfig(host="example.test", port=22, username="alice"),
        asyncssh_module=_FakeAsyncssh(error=_FakeAsyncssh.SFTPPermissionDenied("denied")),
    )
    missing_backend = SftpBackend(
        SshConnectionConfig(host="example.test", port=22, username="alice"),
        asyncssh_module=_FakeAsyncssh(error=_FakeAsyncssh.SFTPNoSuchFile("missing")),
    )

    with pytest.raises(SftpError, match="permission denied"):
        asyncio.run(permission_backend.list_directory("/srv"))
    with pytest.raises(SftpError, match="does not exist"):
        asyncio.run(missing_backend.list_directory("/srv"))


def test_file_manager_delegates_remote_operations_to_sftp_backend() -> None:
    fake_sftp = _FakeSftp()
    backend = SftpBackend(
        SshConnectionConfig(host="example.test", port=22, username="alice"),
        asyncssh_module=_FakeAsyncssh(fake_sftp),
    )
    manager = FileManager()

    result = asyncio.run(manager.create_remote_directory(backend, "/srv", "logs"))
    renamed = asyncio.run(manager.rename_remote_path(backend, "/srv/logs", "archive"))
    deleted = asyncio.run(manager.delete_remote_path(backend, "/srv/archive", is_directory=True))

    assert result.path == "/srv/logs"
    assert renamed.path == "/srv/archive"
    assert deleted.path == "/srv/archive"
    assert fake_sftp.mkdir_calls == ["/srv/logs"]
    assert fake_sftp.rename_calls == [("/srv/logs", "/srv/archive")]
    assert fake_sftp.rmdir_calls == ["/srv/archive"]


def test_session_manager_lists_only_ssh_connections_for_sftp_panel() -> None:
    connection = _connection()
    manager = _session_manager(connection, _FakeSecretStore())
    manager.create_local_terminal()
    ssh_session = manager.create_ssh_terminal(
        SshConnectionConfig(host="example.test", port=22, username="alice", password="secret")
    )

    connections = manager.list_ssh_connections()

    assert [item.id for item in connections] == [ssh_session.session.connection_id]
    assert all(item.connection_type == ConnectionType.SSH for item in connections)


def test_remote_file_table_model_renders_entries() -> None:
    app = QApplication.instance() or QApplication([])
    _ = app
    model = RemoteFileTableModel()
    model.set_entries(
        [
            FileManager().get_local_entry(os.getcwd()),
        ]
    )

    assert model.rowCount() == 1
    assert model.columnCount() == 5
    assert model.headerData(0, Qt.Horizontal) == "Name"
