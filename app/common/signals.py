from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """跨模块事件总线."""

    status_message = Signal(str)

