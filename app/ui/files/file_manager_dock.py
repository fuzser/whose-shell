from __future__ import annotations

from PySide6.QtWidgets import QFileSystemModel, QHBoxLayout, QLabel, QTreeView, QWidget


class FileManagerDock(QWidget):
    """两栏文件管理器基础界面."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)

        self._local_model = QFileSystemModel(self)
        root_index = self._local_model.setRootPath("")
        local_view = QTreeView(self)
        local_view.setModel(self._local_model)
        local_view.setRootIndex(root_index)

        remote_placeholder = QLabel("Remote SFTP panel is not implemented yet.", self)
        remote_placeholder.setAlignment(QtAlignmentCenter())

        layout.addWidget(local_view, 1)
        layout.addWidget(remote_placeholder, 1)


def QtAlignmentCenter():
    from PySide6.QtCore import Qt

    return Qt.AlignCenter

