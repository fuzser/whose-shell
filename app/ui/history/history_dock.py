from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class HistoryDock(QWidget):
    """命令历史占位面板."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("Command history is not implemented yet.", self)
        label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(label)

