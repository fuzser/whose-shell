from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class TerminalBackend(QObject):
    """所有终端后端的统一接口."""

    output_received = Signal(bytes)
    connected = Signal()
    closed = Signal(int)
    error = Signal(str)

    def start(self) -> None:
        raise NotImplementedError

    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def resize(self, cols: int, rows: int) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError
