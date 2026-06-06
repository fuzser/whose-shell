from __future__ import annotations

from PySide6.QtCore import QObject

from app.backends.local_backend_factory import create_local_backend
from app.backends.ssh_backend import SshTerminalBackend
from app.common.models import ConnectionType, SshConnectionConfig, TerminalSessionConfig
from app.common.signals import EventBus


class SessionManager(QObject):
    """创建和管理终端会话."""

    def __init__(self, event_bus: EventBus) -> None:
        super().__init__()
        self._event_bus = event_bus

    def create_local_terminal(self) -> object:
        config = TerminalSessionConfig(
            name="Local Shell",
            connection_type=ConnectionType.LOCAL,
        )
        backend = create_local_backend(config)
        self._event_bus.status_message.emit("Local shell session created.")
        return backend

    def create_ssh_terminal(self, config: SshConnectionConfig) -> SshTerminalBackend:
        """创建 SSH 终端后端."""
        backend = SshTerminalBackend(config)
        self._event_bus.status_message.emit(f"SSH session created for {config.username}@{config.host}.")
        return backend
