from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SessionsDock(QWidget):
    """会话和连接管理占位面板."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(
            "Sessions\n\n"
            "- Local shell is available.\n"
            "- SSH connections are not implemented yet.\n"
            "- Favorites are not implemented yet.",
            self,
        )
        label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(label)

