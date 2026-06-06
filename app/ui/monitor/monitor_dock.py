from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


class MonitorDock(QWidget):
    """本地性能监控基础面板."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(2000)
        self._refresh()

    def _refresh(self) -> None:
        if psutil is None:
            self._label.setText("psutil is not installed. Monitoring is unavailable.")
            return
        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        self._label.setText(
            f"CPU: {cpu:.1f}%\n"
            f"Memory: {memory.percent:.1f}%\n"
            f"Disk: {disk.percent:.1f}%\n\n"
            "Remote monitoring and process table are not implemented yet."
        )

