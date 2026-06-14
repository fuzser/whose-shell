from __future__ import annotations

import asyncio
import os
import sqlite3
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.backends.ssh_backend import SshTerminalBackend, SshTerminalWorker
from app.backends.terminal_base import TerminalBackend
from app.common.models import ConnectionType, ManagedTerminalSession, SessionRecord, SessionStatus, SshConnectionConfig
from app.common.signals import EventBus
from app.core.session_manager import SessionManager
from app.core.terminal_manager import TerminalManager
from app.storage.migrations import migrate
from app.storage.repositories import (
    CommandRepository,
    ConnectionRepository,
    FavoriteRepository,
    SessionRepository,
    SettingsRepository,
)
from app.ui.sessions.ssh_connection_dialog import SshConnectionDialog


class _FakeSecretStore:
    def __init__(self) -> None:
        self.passwords: dict[int, str] = {}
        self.passphrases: dict[int, str] = {}

    def set_connection_password(self, connection_id: int, password: str) -> None:
        self.passwords[connection_id] = password

    def get_connection_password(self, connection_id: int) -> str | None:
        return self.passwords.get(connection_id)

    def delete_connection_password(self, connection_id: int) -> None:
        self.passwords.pop(connection_id, None)

    def set_connection_passphrase(self, connection_id: int, passphrase: str) -> None:
        self.passphrases[connection_id] = passphrase

    def get_connection_passphrase(self, connection_id: int) -> str | None:
        return self.passphrases.get(connection_id)

    def delete_connection_passphrase(self, connection_id: int) -> None:
        self.passphrases.pop(connection_id, None)


class _SynchronouslyClosingBackend(TerminalBackend):
    def start(self) -> None:
        self.connected.emit()

    def write(self, data: bytes) -> None:
        _ = data

    def resize(self, cols: int, rows: int) -> None:
        _ = (cols, rows)

    def stop(self) -> None:
        self.closed.emit(0)


class _SlowClosingBackend(TerminalBackend):
    def __init__(self) -> None:
        super().__init__()
        self.start_count = 0

    def start(self) -> None:
        self.start_count += 1
        self.connected.emit()

    def write(self, data: bytes) -> None:
        _ = data

    def resize(self, cols: int, rows: int) -> None:
        _ = (cols, rows)

    def stop(self) -> None:
        return None


class _FakeStdin:
    def __init__(self) -> None:
        self.data = b""

    def write(self, data: bytes) -> None:
        self.data += data

    async def drain(self) -> None:
        return None


class _FakeRuntimeSessionManager:
    def __init__(self, backend: TerminalBackend | None = None) -> None:
        self.closed_sessions: list[int] = []
        self.backend = backend or _SynchronouslyClosingBackend()
        self._managed = ManagedTerminalSession(
            backend=self.backend,
            session=SessionRecord(
                id=1,
                connection_id=1,
                title="Local Shell",
                connection_type=ConnectionType.LOCAL,
                status=SessionStatus.RUNNING,
            ),
        )

    def create_local_terminal(self) -> ManagedTerminalSession:
        return self._managed

    def close_session(self, session_id: int, exit_code: int | None = None) -> SessionRecord:
        _ = exit_code
        self.closed_sessions.append(session_id)
        return self._managed.session

    def reopen_session(self, session_id: int) -> SessionRecord:
        _ = session_id
        return self._managed.session

    def ssh_config_from_connection(self, connection_id: int) -> SshConnectionConfig:
        _ = connection_id
        return SshConnectionConfig(
            host="example.com",
            port=22,
            username="alice",
            default_directory="/updated",
        )


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


def test_session_manager_saves_loads_and_deletes_private_key_passphrases() -> None:
    connection = _connection()
    secrets = _FakeSecretStore()
    manager = _session_manager(connection, secrets)

    managed = manager.create_ssh_terminal(
        SshConnectionConfig(
            host="example.com",
            port=22,
            username="alice",
            auth_method="private_key",
            private_key_path="/tmp/id_ed25519",
            private_key_passphrase="key-passphrase",
        )
    )

    connection_id = managed.session.connection_id
    assert secrets.passphrases[connection_id] == "key-passphrase"

    reopened = manager.create_terminal_from_connection(connection_id)

    assert reopened.backend._config.private_key_passphrase == "key-passphrase"

    manager.delete_ssh_connection(connection_id)

    assert connection_id not in secrets.passphrases


def test_repository_preserves_explicit_ssh_auth_method_when_secret_is_blank() -> None:
    connection = _connection()
    repository = ConnectionRepository(connection)
    record = repository.save_ssh_connection(
        SshConnectionConfig(
            host="example.com",
            port=22,
            username="alice",
            auth_method="password",
        )
    )

    assert record.auth_method == "password"


def test_ssh_dialog_validates_private_key_path(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    _ = app
    dialog = SshConnectionDialog()
    dialog._host.setText("example.com")
    dialog._username.setText("alice")
    dialog._select_auth_method("private_key")

    assert dialog._validation_message() == "Private key path is required for private-key authentication."

    dialog._private_key.setText(str(tmp_path / "missing_key"))

    assert dialog._validation_message() == "Private key path does not exist."

    key_path = tmp_path / "id_ed25519"
    key_path.write_text("test-key", encoding="utf-8")
    dialog._private_key.setText(str(key_path))

    assert dialog._validation_message() is None


def test_ssh_worker_passes_private_key_passphrase_to_asyncssh() -> None:
    worker = SshTerminalWorker(
        SshConnectionConfig(
            host="example.com",
            port=2222,
            username="alice",
            private_key_path="/tmp/id_ed25519",
            private_key_passphrase="key-passphrase",
            accept_unknown_host=True,
        )
    )

    kwargs = worker._connect_kwargs()

    assert kwargs["client_keys"] == ["/tmp/id_ed25519"]
    assert kwargs["passphrase"] == "key-passphrase"
    assert kwargs["known_hosts"] is None


def test_ssh_worker_enters_default_directory_after_shell_start() -> None:
    worker = SshTerminalWorker(
        SshConnectionConfig(
            host="example.com",
            port=22,
            username="alice",
            default_directory="/srv/user's app",
        )
    )
    stdin = _FakeStdin()
    worker._process = types.SimpleNamespace(stdin=stdin)

    asyncio.run(worker._enter_default_directory("/srv/user's app"))

    command = stdin.data.decode()
    assert "cd '/srv/user'\"'\"'s app'" in command
    assert "\n" not in command


def test_ssh_worker_formats_authentication_failure() -> None:
    class PermissionDenied(Exception):
        pass

    worker = SshTerminalWorker(SshConnectionConfig(host="example.com", port=22, username="alice"))
    asyncssh_module = types.SimpleNamespace(PermissionDenied=PermissionDenied)

    message = worker._format_ssh_error(PermissionDenied("denied"), asyncssh_module)

    assert message == "SSH authentication failed. Check the username, password, private key, or key passphrase."


def test_terminal_manager_handles_backend_that_closes_synchronously_on_stop() -> None:
    session_manager = _FakeRuntimeSessionManager()
    terminal_manager = TerminalManager(session_manager)
    managed = terminal_manager.create_local_terminal()
    terminal_manager.start(managed.session.id)

    assert terminal_manager.close(managed.session.id)
    assert session_manager.closed_sessions == [managed.session.id]


def test_terminal_manager_ignores_reconnect_while_disconnect_is_still_closing() -> None:
    backend = _SlowClosingBackend()
    session_manager = _FakeRuntimeSessionManager(backend)
    terminal_manager = TerminalManager(session_manager)
    managed = terminal_manager.create_local_terminal()
    terminal_manager.start(managed.session.id)

    assert backend.start_count == 1
    assert terminal_manager.disconnect(managed.session.id)
    terminal_manager.reconnect(managed.session.id)

    assert backend.start_count == 1


def test_terminal_manager_refreshes_open_ssh_backend_after_connection_edit() -> None:
    connection = _connection()
    secrets = _FakeSecretStore()
    manager = _session_manager(connection, secrets)
    terminal_manager = TerminalManager(manager)
    managed = terminal_manager.create_ssh_terminal(
        SshConnectionConfig(
            host="example.com",
            port=22,
            username="alice",
            default_directory="/old",
        )
    )

    manager.update_ssh_connection(
        managed.session.connection_id,
        SshConnectionConfig(
            host="example.com",
            port=22,
            username="alice",
            default_directory="/updated",
        ),
    )
    terminal_manager.refresh_ssh_connection_config(managed.session.connection_id)

    assert isinstance(managed.backend, SshTerminalBackend)
    assert managed.backend._config.default_directory == "/updated"
