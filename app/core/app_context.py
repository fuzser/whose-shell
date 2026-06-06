from __future__ import annotations

from dataclasses import dataclass

from app.common.signals import EventBus
from app.core.session_manager import SessionManager


@dataclass
class AppContext:
    """应用服务容器."""

    event_bus: EventBus
    session_manager: SessionManager

    @classmethod
    def create_default(cls) -> "AppContext":
        event_bus = EventBus()
        session_manager = SessionManager(event_bus)
        return cls(event_bus=event_bus, session_manager=session_manager)

