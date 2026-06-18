from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileSystemModel,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QStyle,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from app.core.file_manager import FileManager


class FileManagerDock(QWidget):
    """本地和远程文件管理器 Dock."""

    status_message = Signal(str)

    def __init__(self, parent=None, file_manager: FileManager | None = None) -> None:
        super().__init__(parent)
        self._file_manager = file_manager or FileManager()
        self._local_history: list[str] = []
        self._local_clipboard: Path | None = None

        self._local_model = QFileSystemModel(self)
        self._local_model.setReadOnly(True)
        root_path = str(Path.home())
        self._local_model.setRootPath(root_path)

        self._local_path = QLineEdit(root_path, self)
        self._local_path.returnPressed.connect(self._jump_to_local_path)

        self._local_view = QTreeView(self)
        self._local_view.setModel(self._local_model)
        self._local_view.setRootIndex(self._local_model.index(root_path))
        self._local_view.setEditTriggers(QTreeView.NoEditTriggers)
        self._local_view.setSelectionBehavior(QTreeView.SelectRows)
        self._local_view.setAlternatingRowColors(True)
        self._local_view.doubleClicked.connect(self._open_local_index)
        self._local_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._local_view.customContextMenuRequested.connect(self._show_local_context_menu)

        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._build_local_panel())
        splitter.addWidget(self._build_remote_placeholder())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self._set_local_root(root_path)

    def _build_local_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)

        header = QHBoxLayout()
        label = QLabel("Local", panel)
        label.setTextInteractionFlags(Qt.NoTextInteraction)
        header.addWidget(label)
        header.addWidget(self._local_path, 1)
        header.addWidget(self._tool_button(QStyle.SP_BrowserReload, "Refresh local files", self._refresh_local))
        header.addWidget(self._tool_button(QStyle.SP_FileDialogToParent, "Go to parent folder", self._go_to_parent_local))
        header.addWidget(self._tool_button(QStyle.SP_ArrowBack, "Go back to previous folder", self._go_back_local))

        layout.addLayout(header)
        layout.addWidget(self._local_view, 1)
        return panel

    def _build_remote_placeholder(self) -> QWidget:
        panel = QFrame(self)
        panel.setFrameShape(QFrame.StyledPanel)
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(panel)

        title = QLabel("Remote", panel)
        title.setTextInteractionFlags(Qt.NoTextInteraction)
        message = QLabel("SFTP browsing starts in Phase 3. No remote connection is selected.", panel)
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.NoTextInteraction)

        layout.addWidget(title)
        layout.addWidget(message, 1)
        return panel

    def _tool_button(self, icon: QStyle.StandardPixmap, tooltip: str, handler) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        button.clicked.connect(handler)
        return button

    def _jump_to_local_path(self) -> None:
        self._set_local_root(self._local_path.text())

    def _refresh_local(self) -> None:
        current_path = self._current_local_root()
        self._local_model.setRootPath("")
        self._set_local_root(current_path, add_history=False)
        self._show_status(f"Local files refreshed: {current_path}")

    def _go_to_parent_local(self) -> None:
        current_path = Path(self._current_local_root())
        parent_path = current_path.parent
        if parent_path == current_path:
            self._show_status("Already at the filesystem root.")
            return
        self._set_local_root(parent_path)

    def _go_back_local(self) -> None:
        if not self._local_history:
            self._show_status("No previous local folder.")
            return
        previous_path = self._local_history.pop()
        self._set_local_root(previous_path, add_history=False)

    def _show_local_context_menu(self, position) -> None:
        index = self._local_view.indexAt(position)
        if index.isValid():
            self._local_view.setCurrentIndex(index)

        selected_path = self._selected_local_path()
        target_directory = self._context_target_directory(selected_path)

        menu = QMenu(self)
        new_folder_action = menu.addAction("New Folder")
        new_file_action = menu.addAction("New File")
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        menu.addSeparator()
        copy_action = menu.addAction("Copy")
        paste_action = menu.addAction("Paste")

        has_selection = selected_path is not None
        rename_action.setEnabled(has_selection)
        delete_action.setEnabled(has_selection)
        copy_action.setEnabled(has_selection)
        paste_action.setEnabled(self._local_clipboard is not None and target_directory is not None)

        selected = menu.exec(self._local_view.viewport().mapToGlobal(position))
        self._handle_local_context_action(
            selected,
            new_folder_action,
            new_file_action,
            rename_action,
            delete_action,
            copy_action,
            paste_action,
            selected_path,
            target_directory,
        )

    def _handle_local_context_action(
        self,
        selected: QAction | None,
        new_folder_action: QAction,
        new_file_action: QAction,
        rename_action: QAction,
        delete_action: QAction,
        copy_action: QAction,
        paste_action: QAction,
        selected_path: Path | None,
        target_directory: Path | None,
    ) -> None:
        if selected == new_folder_action:
            self._new_local_folder(target_directory)
        elif selected == new_file_action:
            self._new_local_file(target_directory)
        elif selected == rename_action and selected_path is not None:
            self._rename_local(selected_path)
        elif selected == delete_action and selected_path is not None:
            self._delete_local(selected_path)
        elif selected == copy_action and selected_path is not None:
            self._copy_local(selected_path)
        elif selected == paste_action and target_directory is not None:
            self._paste_local(target_directory)

    def _new_local_folder(self, parent_path: Path | None = None) -> None:
        parent_path = parent_path or Path(self._current_local_root())
        name, accepted = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not accepted:
            return
        try:
            entry = self._file_manager.create_local_directory(parent_path, name)
        except Exception as exc:
            self._show_error("New folder failed", exc)
            return
        self._set_local_root(str(parent_path))
        self._select_local_path(entry.path)
        self._show_status(f"Created local folder: {entry.path}")

    def _new_local_file(self, parent_path: Path | None = None) -> None:
        parent_path = parent_path or Path(self._current_local_root())
        name, accepted = QInputDialog.getText(self, "New File", "File name:")
        if not accepted:
            return
        try:
            entry = self._file_manager.create_local_file(parent_path, name)
        except Exception as exc:
            self._show_error("New file failed", exc)
            return
        self._set_local_root(str(parent_path))
        self._select_local_path(entry.path)
        self._show_status(f"Created local file: {entry.path}")

    def _rename_local(self, selected_path: Path) -> None:
        name, accepted = QInputDialog.getText(self, "Rename", "New name:", text=selected_path.name)
        if not accepted:
            return
        try:
            entry = self._file_manager.rename_local_path(selected_path, name)
        except Exception as exc:
            self._show_error("Rename failed", exc)
            return
        self._set_local_root(str(Path(entry.path).parent))
        self._select_local_path(entry.path)
        self._show_status(f"Renamed local item: {entry.path}")

    def _delete_local(self, selected_path: Path) -> None:
        kind = "folder and all its contents" if selected_path.is_dir() and not selected_path.is_symlink() else "file"
        result = QMessageBox.question(
            self,
            "Delete Local Item",
            f"Delete this {kind}?\n{selected_path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if result != QMessageBox.Yes:
            return
        parent_path = selected_path.parent
        try:
            self._file_manager.delete_local_path(selected_path)
        except Exception as exc:
            self._show_error("Delete failed", exc)
            return
        self._set_local_root(str(parent_path))
        self._show_status(f"Deleted local item: {selected_path}")

    def _copy_local(self, selected_path: Path) -> None:
        self._local_clipboard = selected_path
        self._show_status(f"Copied local item: {selected_path}")

    def _paste_local(self, target_directory: Path) -> None:
        if self._local_clipboard is None:
            self._show_status("Copy a local file or folder before pasting.")
            return
        try:
            entry = self._file_manager.copy_local_path(self._local_clipboard, target_directory)
        except Exception as exc:
            self._show_error("Paste failed", exc)
            return
        self._set_local_root(str(target_directory), add_history=False)
        self._select_local_path(entry.path)
        self._show_status(f"Pasted local item: {entry.path}")

    def _open_local_index(self, index) -> None:
        path = Path(self._local_model.filePath(index))
        if path.is_dir():
            self._set_local_root(str(path))

    def _set_local_root(self, path: str | Path, *, add_history: bool = True) -> bool:
        previous_path = self._current_local_root()
        try:
            entry = self._file_manager.get_local_entry(path)
            if not Path(entry.path).is_dir():
                raise NotADirectoryError(f"Local path is not a directory: {entry.path}")
        except Exception as exc:
            self._show_error("Local path failed", exc)
            self._local_path.setText(self._current_local_root())
            return False

        root_path = entry.path
        root_index = self._local_model.setRootPath(root_path)
        self._local_view.setRootIndex(root_index)
        self._local_path.setText(root_path)
        if add_history and previous_path != root_path:
            self._local_history.append(previous_path)
        self._show_status(f"Local path: {root_path}")
        return True

    def _select_local_path(self, path: str | Path) -> None:
        index = self._local_model.index(str(path))
        if index.isValid():
            self._local_view.setCurrentIndex(index)
            self._local_view.scrollTo(index)

    def _selected_local_path(self) -> Path | None:
        index = self._local_view.currentIndex()
        if not index.isValid():
            return None
        return Path(self._local_model.filePath(index))

    def _selected_local_directory(self) -> Path | None:
        selected_path = self._selected_local_path()
        if selected_path is None:
            return None
        if selected_path.is_dir():
            return selected_path
        return selected_path.parent

    def _context_target_directory(self, selected_path: Path | None) -> Path | None:
        if selected_path is not None and selected_path.is_dir():
            return selected_path
        return Path(self._current_local_root())

    def _current_local_root(self) -> str:
        root_index = self._local_view.rootIndex()
        if root_index.isValid():
            return self._local_model.filePath(root_index)
        return str(Path.home())

    def _show_status(self, message: str) -> None:
        self.status_message.emit(message)

    def _show_error(self, title: str, error: Exception) -> None:
        message = str(error)
        self.status_message.emit(message)
        QMessageBox.warning(self, title, message)
