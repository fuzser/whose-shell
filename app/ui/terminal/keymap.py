from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent


SPECIAL_KEYS = {
    Qt.Key_Left: b"\x1b[D",
    Qt.Key_Right: b"\x1b[C",
    Qt.Key_Up: b"\x1b[A",
    Qt.Key_Down: b"\x1b[B",
    Qt.Key_Home: b"\x1b[H",
    Qt.Key_End: b"\x1b[F",
    Qt.Key_PageUp: b"\x1b[5~",
    Qt.Key_PageDown: b"\x1b[6~",
    Qt.Key_Backspace: b"\x7f",
    Qt.Key_Return: b"\r",
    Qt.Key_Enter: b"\r",
    Qt.Key_Tab: b"\t",
}


class KeyMapper:
    """把 Qt 按键转换为终端输入字节."""

    def to_bytes(self, event: QKeyEvent) -> bytes:
        if event.key() in SPECIAL_KEYS:
            return SPECIAL_KEYS[event.key()]
        if event.modifiers() & Qt.ControlModifier:
            return self._control_bytes(event)
        text = event.text()
        return text.encode("utf-8") if text else b""

    def _control_bytes(self, event: QKeyEvent) -> bytes:
        key = event.key()
        if Qt.Key_A <= key <= Qt.Key_Z:
            return bytes([key - Qt.Key_A + 1])
        return b""
