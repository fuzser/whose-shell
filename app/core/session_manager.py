from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject

from app.backends.local_backend_factory import create_local_backend
from app.backends.ssh_backend import SshTerminalBackend
from app.common.models import (
    AppSettings,
    CommandRecord,
    ConnectionRecord,
    ConnectionType,
    FavoriteCommand,
    ManagedTerminalSession,
    SavedTerminalTab,
    SessionRecord,
    SshConnectionConfig,
    TerminalSessionConfig,
)
from app.common.platform import AUTO_LOCAL_SHELL, resolve_local_shell_preference
from app.common.signals import EventBus
from app.storage.repositories import (
    CommandRepository,
    ConnectionRepository,
    FavoriteRepository,
    SessionRepository,
    SettingsRepository,
)
from app.storage.secrets import SecretStore


class SessionManager(QObject):
    """创建和管理终端会话."""

    def __init__(
        self,
        event_bus: EventBus,
        connection_repository: ConnectionRepository,
        session_repository: SessionRepository,
        command_repository: CommandRepository,
        favorite_repository: FavoriteRepository,
        settings_repository: SettingsRepository,
        secret_store: SecretStore,
    ) -> None:
        super().__init__()
        self._event_bus = event_bus
        self._connections = connection_repository
        self._sessions = session_repository
        self._commands = command_repository
        self._favorites = favorite_repository
        self._settings = settings_repository
        self._secrets = secret_store

    def create_local_terminal(self) -> ManagedTerminalSession:
        settings = self.get_settings()
        config = TerminalSessionConfig(
            name="Local Shell",
            connection_type=ConnectionType.LOCAL,
            command=self._local_shell_command(settings),
            cols=settings.terminal_cols,
            rows=settings.terminal_rows,
        )
        connection = self._connections.ensure_local_connection()
        session = self._sessions.create_session(connection, "Local Shell", config.cwd)
        backend = create_local_backend(config)
        self._event_bus.status_message.emit(f"Local shell session #{session.id} created.")
        return ManagedTerminalSession(backend=backend, session=session)

    def create_ssh_terminal(self, config: SshConnectionConfig) -> ManagedTerminalSession:
        """创建 SSH 终端后端."""
        settings = self.get_settings()
        config = replace(config, cols=settings.terminal_cols, rows=settings.terminal_rows)
        connection = self._connections.save_ssh_connection(config)
        if config.password:
            try:
                self._secrets.set_connection_password(connection.id, config.password)
            except Exception as exc:
                self._event_bus.status_message.emit(f"SSH password was not saved: {exc}")
        if config.private_key_passphrase:
            try:
                self._secrets.set_connection_passphrase(connection.id, config.private_key_passphrase)
            except Exception as exc:
                self._event_bus.status_message.emit(f"SSH private key passphrase was not saved: {exc}")
        title = connection.name
        session = self._sessions.create_session(connection, title, config.default_directory)
        backend = SshTerminalBackend(config)
        self._event_bus.status_message.emit(f"SSH session #{session.id} created for {connection.name}.")
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

    def reopen_session(self, session_id: int) -> SessionRecord:
        """标记会话已重新连接."""
        session = self._sessions.reopen_session(session_id)
        self._event_bus.status_message.emit(f"Session #{session.id} reconnected.")
        return session

    def list_connections(self) -> list[ConnectionRecord]:
        return self._connections.list_connections()

    def list_ssh_connections(self) -> list[ConnectionRecord]:
        """列出已保存 SSH 连接, 供终端和 SFTP 面板复用."""
        return [
            connection
            for connection in self._connections.list_connections()
            if connection.connection_type == ConnectionType.SSH
        ]

    def list_recent_sessions(self, limit: int = 50) -> list[SessionRecord]:
        return self._sessions.list_recent_sessions(limit)

    def record_command(self, session_id: int, command_text: str) -> CommandRecord | None:
        """记录终端提交的单行命令."""
        try:
            session = self._sessions.get_session(session_id)
            return self._commands.create_command(
                command_text,
                session.connection_type,
                session_id=session.id,
                connection_id=session.connection_id,
                host=session.host,
                cwd=session.cwd,
            )
        except ValueError:
            return None

    def list_commands(
        self,
        limit: int = 200,
        search_text: str | None = None,
        host: str | None = None,
        connection_type: ConnectionType | None = None,
    ) -> list[CommandRecord]:
        return self._commands.list_commands(
            limit=limit,
            search_text=search_text,
            host=host,
            connection_type=connection_type,
        )

    def list_favorites(self, limit: int = 200) -> list[FavoriteCommand]:
        return self._favorites.list_favorites(limit)

    def add_favorite(self, command_text: str) -> FavoriteCommand:
        favorite = self._favorites.add_favorite(command_text)
        self._event_bus.status_message.emit(f"Favorite command saved: {favorite.command_text}")
        return favorite

    def remove_favorite(self, command_text: str) -> None:
        self._favorites.remove_favorite(command_text)
        self._event_bus.status_message.emit(f"Favorite command removed: {command_text.strip()}")

    def is_favorite(self, command_text: str) -> bool:
        return self._favorites.is_favorite(command_text)

    def save_active_tabs(self, tabs: list[SavedTerminalTab]) -> None:
        self._sessions.save_active_tabs(tabs)

    def list_active_tabs(self) -> list[SavedTerminalTab]:
        return self._sessions.list_active_tabs()

    def get_settings(self) -> AppSettings:
        return self._settings.get_settings()

    def save_settings(self, settings: AppSettings) -> AppSettings:
        saved = self._settings.save_settings(settings)
        self._event_bus.status_message.emit("Settings saved.")
        return saved

    def get_connection(self, connection_id: int) -> ConnectionRecord:
        return self._connections.get_connection(connection_id)

    def update_ssh_connection(self, connection_id: int, config: SshConnectionConfig) -> ConnectionRecord:
        connection = self._connections.update_ssh_connection(connection_id, config)
        if config.password:
            try:
                self._secrets.set_connection_password(connection.id, config.password)
            except Exception as exc:
                self._event_bus.status_message.emit(f"SSH password was not saved: {exc}")
        if config.private_key_passphrase:
            try:
                self._secrets.set_connection_passphrase(connection.id, config.private_key_passphrase)
            except Exception as exc:
                self._event_bus.status_message.emit(f"SSH private key passphrase was not saved: {exc}")
        self._event_bus.status_message.emit(f"SSH connection updated: {connection.name}.")
        return connection

    def ssh_config_from_connection(self, connection_id: int) -> SshConnectionConfig:
        connection = self._connections.get_connection(connection_id)
        return self._ssh_config_from_connection(connection)

    def delete_ssh_connection(self, connection_id: int) -> None:
        connection = self._connections.get_connection(connection_id)
        if connection.connection_type != ConnectionType.SSH:
            raise ValueError("Only SSH connections can be deleted.")
        self._connections.delete_ssh_connection(connection_id)
        try:
            self._secrets.delete_connection_password(connection_id)
        except Exception as exc:
            self._event_bus.status_message.emit(f"SSH password was not deleted: {exc}")
        try:
            self._secrets.delete_connection_passphrase(connection_id)
        except Exception as exc:
            self._event_bus.status_message.emit(f"SSH private key passphrase was not deleted: {exc}")
        self._event_bus.status_message.emit(f"SSH connection deleted: {connection.name}.")

    def _create_ssh_terminal_from_record(self, connection: ConnectionRecord) -> ManagedTerminalSession:
        config = self._ssh_config_from_connection(connection)
        title = connection.name
        session = self._sessions.create_session(connection, title, connection.default_directory)
        backend = SshTerminalBackend(config)
        self._event_bus.status_message.emit(f"SSH session #{session.id} opened from saved connection.")
        return ManagedTerminalSession(backend=backend, session=session)

    def _ssh_config_from_connection(self, connection: ConnectionRecord) -> SshConnectionConfig:
        if not connection.host or not connection.port or not connection.username:
            raise ValueError(f"SSH connection is incomplete: {connection.id}")
        try:
            password = self._secrets.get_connection_password(connection.id)
        except Exception as exc:
            password = None
            self._event_bus.status_message.emit(f"SSH password was not loaded: {exc}")
        try:
            passphrase = self._secrets.get_connection_passphrase(connection.id)
        except Exception as exc:
            passphrase = None
            self._event_bus.status_message.emit(f"SSH private key passphrase was not loaded: {exc}")
        config = SshConnectionConfig(
            host=connection.host,
            port=connection.port,
            username=connection.username,
            name=connection.name,
            auth_method=connection.auth_method,
            password=password,
            private_key_path=connection.private_key_path,
            private_key_passphrase=passphrase,
            default_directory=connection.default_directory,
            cols=self.get_settings().terminal_cols,
            rows=self.get_settings().terminal_rows,
        )
        return config

    def _local_shell_command(self, settings: AppSettings) -> list[str]:
        resolution = resolve_local_shell_preference(settings.default_local_shell)
        if resolution.used_fallback and settings.default_local_shell != AUTO_LOCAL_SHELL:
            self._settings.save_settings(replace(settings, default_local_shell=AUTO_LOCAL_SHELL))
        if resolution.fallback_message:
            self._event_bus.status_message.emit(resolution.fallback_message)
        return resolution.command
