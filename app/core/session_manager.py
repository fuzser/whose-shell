from __future__ import annotations

from PySide6.QtCore import QObject

from app.backends.local_backend_factory import create_local_backend
from app.backends.ssh_backend import SshTerminalBackend
from app.common.models import (
    ConnectionRecord,
    ConnectionType,
    ManagedTerminalSession,
    SessionRecord,
    SshConnectionConfig,
    TerminalSessionConfig,
)
from app.common.signals import EventBus
from app.storage.repositories import ConnectionRepository, SessionRepository
from app.storage.secrets import SecretStore


class SessionManager(QObject):
    """创建和管理终端会话."""

    def __init__(
        self,
        event_bus: EventBus,
        connection_repository: ConnectionRepository,
        session_repository: SessionRepository,
        secret_store: SecretStore,
    ) -> None:
        super().__init__()
        self._event_bus = event_bus
        self._connections = connection_repository
        self._sessions = session_repository
        self._secrets = secret_store

    def create_local_terminal(self) -> ManagedTerminalSession:
        config = TerminalSessionConfig(
            name="Local Shell",
            connection_type=ConnectionType.LOCAL,
        )
        connection = self._connections.ensure_local_connection()
        session = self._sessions.create_session(connection, "Local Shell", config.cwd)
        backend = create_local_backend(config)
        self._event_bus.status_message.emit(f"Local shell session #{session.id} created.")
        return ManagedTerminalSession(backend=backend, session=session)

    def create_ssh_terminal(self, config: SshConnectionConfig) -> ManagedTerminalSession:
        """创建 SSH 终端后端."""
        connection = self._connections.save_ssh_connection(config)
        if config.password:
            try:
                self._secrets.set_connection_password(connection.id, config.password)
            except Exception as exc:
                self._event_bus.status_message.emit(f"SSH password was not saved: {exc}")
        title = f"SSH {config.username}@{config.host}"
        session = self._sessions.create_session(connection, title, config.default_directory)
        backend = SshTerminalBackend(config)
        self._event_bus.status_message.emit(f"SSH session #{session.id} created for {config.username}@{config.host}.")
        return ManagedTerminalSession(backend=backend, session=session)

    def create_terminal_from_connection(self, connection_id: int) -> ManagedTerminalSession:
        """按已保存连接创建终端会话."""
        connection = self._connections.get_connection(connection_id)
        if connection.connection_type == ConnectionType.LOCAL:
            return self.create_local_terminal()
        if connection.connection_type == ConnectionType.SSH:
            return self._create_ssh_terminal_from_record(connection)
        raise ValueError(f"Unsupported connection type: {connection.connection_type}")

    def close_session(self, session_id: int, exit_code: int | None = None) -> SessionRecord:
        """标记会话关闭."""
        session = self._sessions.close_session(session_id, exit_code)
        self._event_bus.status_message.emit(f"Session #{session.id} closed.")
        return session

    def list_connections(self) -> list[ConnectionRecord]:
        return self._connections.list_connections()

    def list_recent_sessions(self, limit: int = 50) -> list[SessionRecord]:
        return self._sessions.list_recent_sessions(limit)

    def get_connection(self, connection_id: int) -> ConnectionRecord:
        return self._connections.get_connection(connection_id)

    def update_ssh_connection(self, connection_id: int, config: SshConnectionConfig) -> ConnectionRecord:
        connection = self._connections.update_ssh_connection(connection_id, config)
        if config.password:
            try:
                self._secrets.set_connection_password(connection.id, config.password)
            except Exception as exc:
                self._event_bus.status_message.emit(f"SSH password was not saved: {exc}")
        self._event_bus.status_message.emit(f"SSH connection updated: {connection.name}.")
        return connection

    def delete_ssh_connection(self, connection_id: int) -> None:
        connection = self._connections.get_connection(connection_id)
        if connection.connection_type != ConnectionType.SSH:
            raise ValueError("Only SSH connections can be deleted.")
        self._connections.delete_ssh_connection(connection_id)
        try:
            self._secrets.delete_connection_password(connection_id)
        except Exception as exc:
            self._event_bus.status_message.emit(f"SSH password was not deleted: {exc}")
        self._event_bus.status_message.emit(f"SSH connection deleted: {connection.name}.")

    def _create_ssh_terminal_from_record(self, connection: ConnectionRecord) -> ManagedTerminalSession:
        if not connection.host or not connection.port or not connection.username:
            raise ValueError(f"SSH connection is incomplete: {connection.id}")
        try:
            password = self._secrets.get_connection_password(connection.id)
        except Exception as exc:
            password = None
            self._event_bus.status_message.emit(f"SSH password was not loaded: {exc}")
        config = SshConnectionConfig(
            host=connection.host,
            port=connection.port,
            username=connection.username,
            password=password,
            private_key_path=connection.private_key_path,
            default_directory=connection.default_directory,
        )
        title = f"SSH {connection.username}@{connection.host}"
        session = self._sessions.create_session(connection, title, connection.default_directory)
        backend = SshTerminalBackend(config)
        self._event_bus.status_message.emit(f"SSH session #{session.id} opened from saved connection.")
        return ManagedTerminalSession(backend=backend, session=session)
