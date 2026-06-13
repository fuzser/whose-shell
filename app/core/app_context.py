from __future__ import annotations

from dataclasses import dataclass

from app.common.signals import EventBus
from app.core.session_manager import SessionManager
from app.core.terminal_manager import TerminalManager
from app.storage.db import Database
from app.storage.repositories import (
    CommandRepository,
    ConnectionRepository,
    FavoriteRepository,
    SessionRepository,
    SettingsRepository,
)
from app.storage.secrets import SecretStore


@dataclass
class AppContext:
    """应用服务容器."""

    event_bus: EventBus
    database: Database
    session_manager: SessionManager
    terminal_manager: TerminalManager
    settings_repository: SettingsRepository

    @classmethod
    def create_default(cls) -> "AppContext":
        event_bus = EventBus()
        database = Database()
        connection_repository = ConnectionRepository(database.connection)
        session_repository = SessionRepository(database.connection)
        command_repository = CommandRepository(database.connection)
        favorite_repository = FavoriteRepository(database.connection)
        settings_repository = SettingsRepository(database.connection)
        secret_store = SecretStore()
        session_manager = SessionManager(
            event_bus,
            connection_repository,
            session_repository,
            command_repository,
            favorite_repository,
            settings_repository,
            secret_store,
        )
        terminal_manager = TerminalManager(session_manager)
        return cls(
            event_bus=event_bus,
            database=database,
            session_manager=session_manager,
            terminal_manager=terminal_manager,
            settings_repository=settings_repository,
        )
