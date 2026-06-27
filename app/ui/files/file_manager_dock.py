from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFileSystemModel,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QSplitter,
    QStyle,
    QTableView,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from app.backends.sftp_backend import SftpDirectoryListWorker, SftpOperationWorker, SftpTransferWorker
from app.common.models import (
    ConflictPolicy,
    FileEntry,
    FileEntryType,
    FileTransferRecord,
    TransferDirection,
    TransferStatus,
)
from app.core.file_manager import FileManager
from app.core.session_manager import SessionManager


class RemoteFileTableModel(QAbstractTableModel):
    """远程文件列表表格模型."""

    _HEADERS = ("Name", "Size", "Type", "Modified", "Permissions")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: list[FileEntry] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._HEADERS)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        entry = self._entries[index.row()]
        if role == Qt.DisplayRole:
            return self._display_value(entry, index.column())
        if role == Qt.TextAlignmentRole and index.column() == 1:
            return Qt.AlignRight | Qt.AlignVCenter
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._HEADERS[section]
        return super().headerData(section, orientation, role)

    def set_entries(self, entries: list[FileEntry]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def entry_at(self, row: int) -> FileEntry | None:
        if row < 0 or row >= len(self._entries):
            return None
        return self._entries[row]

    def _display_value(self, entry: FileEntry, column: int) -> str:
        if column == 0:
            return entry.name
        if column == 1:
            return "" if entry.size is None else str(entry.size)
        if column == 2:
            return entry.entry_type.value
        if column == 3:
            return entry.modified_at or ""
        if column == 4:
            return entry.permissions or ""
        return ""


class TransferTableModel(QAbstractTableModel):
    """传输队列表格模型."""

    _HEADERS = ("Direction", "Status", "Progress", "Source", "Target", "Policy", "Error")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: list[FileTransferRecord] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._records)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._HEADERS)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        record = self._records[index.row()]
        if role == Qt.DisplayRole:
            return self._display_value(record, index.column())
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._HEADERS[section]
        return super().headerData(section, orientation, role)

    def set_records(self, records: list[FileTransferRecord]) -> None:
        self.beginResetModel()
        self._records = list(records)
        self.endResetModel()

    def upsert_record(self, record: FileTransferRecord) -> None:
        for index, current in enumerate(self._records):
            if current.id == record.id:
                self._records[index] = record
                model_index = self.index(index, 0)
                self.dataChanged.emit(model_index, self.index(index, self.columnCount() - 1))
                return
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._records.insert(0, record)
        self.endInsertRows()

    def _display_value(self, record: FileTransferRecord, column: int) -> str:
        if column == 0:
            return record.direction.value
        if column == 1:
            return record.status.value
        if column == 2:
            return self._progress_text(record)
        if column == 3:
            return record.source_path
        if column == 4:
            return record.target_path
        if column == 5:
            return record.conflict_policy.value
        if column == 6:
            return record.error_message or ""
        return ""

    def _progress_text(self, record: FileTransferRecord) -> str:
        if record.total_bytes in {None, 0}:
            return str(record.bytes_transferred)
        percent = min(100, int(record.bytes_transferred * 100 / record.total_bytes))
        return f"{percent}% ({record.bytes_transferred}/{record.total_bytes})"


class FileManagerDock(QWidget):
    """本地和远程文件管理器 Dock."""

    status_message = Signal(str)

    def __init__(
        self,
        parent=None,
        file_manager: FileManager | None = None,
        session_manager: SessionManager | None = None,
    ) -> None:
        super().__init__(parent)
        self._file_manager = file_manager or FileManager()
        self._session_manager = session_manager
        self._local_history: list[str] = []
        self._local_clipboard: Path | None = None
        self._remote_config = None
        self._remote_connection_id: int | None = None
        self._remote_worker: SftpDirectoryListWorker | None = None
        self._remote_operation_worker: SftpOperationWorker | None = None
        self._transfer_workers: dict[int, SftpTransferWorker] = {}
        self._remote_pending_path = "."

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

        self._remote_connections = QComboBox(self)
        self._remote_connections.currentIndexChanged.connect(self._remote_connection_changed)
        self._remote_path = QLineEdit(".", self)
        self._remote_path.returnPressed.connect(self._jump_to_remote_path)
        self._remote_status = QLabel("Select a saved SSH connection to browse remote files.", self)
        self._remote_status.setWordWrap(True)
        self._remote_status.setTextInteractionFlags(Qt.NoTextInteraction)
        self._remote_model = RemoteFileTableModel(self)
        self._remote_view = QTableView(self)
        self._remote_view.setModel(self._remote_model)
        self._remote_view.setSelectionBehavior(QTableView.SelectRows)
        self._remote_view.setSelectionMode(QTableView.SingleSelection)
        self._remote_view.setEditTriggers(QTableView.NoEditTriggers)
        self._remote_view.setAlternatingRowColors(True)
        self._remote_view.doubleClicked.connect(self._open_remote_index)
        self._remote_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._remote_view.customContextMenuRequested.connect(self._show_remote_context_menu)
        self._transfer_model = TransferTableModel(self)
        self._transfer_view = QTableView(self)
        self._transfer_view.setModel(self._transfer_model)
        self._transfer_view.setSelectionBehavior(QTableView.SelectRows)
        self._transfer_view.setEditTriggers(QTableView.NoEditTriggers)
        self._transfer_view.setAlternatingRowColors(True)

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._build_local_panel())
        splitter.addWidget(self._build_remote_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 3)
        layout.addWidget(self._build_transfer_panel(), 1)

        self._set_local_root(root_path)
        self.refresh_remote_connections()
        self._refresh_transfer_records()

    def refresh_remote_connections(self) -> None:
        self._remote_connections.blockSignals(True)
        self._remote_connections.clear()
        self._remote_connections.addItem("Select SSH connection...", None)
        if self._session_manager is not None:
            for connection in self._session_manager.list_ssh_connections():
                self._remote_connections.addItem(connection.name, connection.id)
        self._remote_connections.blockSignals(False)
        has_connections = self._remote_connections.count() > 1
        self._remote_connections.setEnabled(has_connections)
        if not has_connections:
            self._set_remote_status("No saved SSH connections. Create one from Sessions or New SSH Shell first.")

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

    def _build_remote_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)

        connection_row = QHBoxLayout()
        label = QLabel("Remote", panel)
        label.setTextInteractionFlags(Qt.NoTextInteraction)
        connection_row.addWidget(label)
        connection_row.addWidget(self._remote_connections, 1)
        connection_row.addWidget(self._tool_button(QStyle.SP_DialogOpenButton, "Open SFTP browser", self._open_remote_connection))

        path_row = QHBoxLayout()
        path_row.addWidget(self._remote_path, 1)
        path_row.addWidget(self._tool_button(QStyle.SP_BrowserReload, "Refresh remote files", self._refresh_remote))
        path_row.addWidget(self._tool_button(QStyle.SP_FileDialogToParent, "Go to remote parent folder", self._go_to_parent_remote))

        layout.addLayout(connection_row)
        layout.addLayout(path_row)
        layout.addWidget(self._remote_status)
        layout.addWidget(self._remote_view, 1)
        return panel

    def _build_transfer_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        header = QHBoxLayout()
        label = QLabel("Transfers", panel)
        label.setTextInteractionFlags(Qt.NoTextInteraction)
        header.addWidget(label)
        header.addStretch(1)
        header.addWidget(self._tool_button(QStyle.SP_BrowserReload, "Refresh transfer queue", self._refresh_transfer_records))
        layout.addLayout(header)
        layout.addWidget(self._transfer_view, 1)
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
        upload_action = menu.addAction("Upload")

        has_selection = selected_path is not None
        rename_action.setEnabled(has_selection)
        delete_action.setEnabled(has_selection)
        copy_action.setEnabled(has_selection)
        paste_action.setEnabled(self._local_clipboard is not None and target_directory is not None)
        upload_action.setEnabled(has_selection and selected_path is not None and selected_path.is_file() and self._remote_config is not None)

        selected = menu.exec(self._local_view.viewport().mapToGlobal(position))
        self._handle_local_context_action(
            selected,
            new_folder_action,
            new_file_action,
            rename_action,
            delete_action,
            copy_action,
            paste_action,
            upload_action,
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
        upload_action: QAction,
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
        elif selected == upload_action and selected_path is not None:
            self._upload_local_file(selected_path)

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

    def _context_target_directory(self, selected_path: Path | None) -> Path | None:
        if selected_path is not None and selected_path.is_dir():
            return selected_path
        return Path(self._current_local_root())

    def _current_local_root(self) -> str:
        root_index = self._local_view.rootIndex()
        if root_index.isValid():
            return self._local_model.filePath(root_index)
        return str(Path.home())

    def _remote_connection_changed(self) -> None:
        self._remote_config = None
        self._remote_connection_id = None
        self._remote_model.set_entries([])
        self._remote_path.setText(".")
        self._set_remote_status("Open the selected SSH connection to browse remote files.")

    def _open_remote_connection(self) -> None:
        connection_id = self._selected_connection_id()
        if connection_id is None or self._session_manager is None:
            self._set_remote_status("Select a saved SSH connection first.")
            return
        try:
            self._remote_config = self._session_manager.ssh_config_from_connection(connection_id)
            self._remote_connection_id = connection_id
        except Exception as exc:
            self._show_error("Open SFTP failed", exc)
            return
        start_path = self._remote_config.default_directory or "."
        self._start_remote_listing(start_path)

    def _jump_to_remote_path(self) -> None:
        self._start_remote_listing(self._remote_path.text())

    def _refresh_remote(self) -> None:
        self._start_remote_listing(self._remote_path.text())

    def _go_to_parent_remote(self) -> None:
        current = self._remote_path.text().strip() or "."
        parent = self._remote_parent_path(current)
        if parent == current:
            self._set_remote_status("Already at the remote filesystem root.")
            return
        self._start_remote_listing(parent)

    def _open_remote_index(self, index: QModelIndex) -> None:
        entry = self._remote_model.entry_at(index.row())
        if entry is not None and entry.entry_type == FileEntryType.DIRECTORY:
            self._start_remote_listing(entry.path)

    def _show_remote_context_menu(self, position) -> None:
        entry = self._selected_remote_entry()
        menu = QMenu(self)
        new_folder_action = menu.addAction("New Folder")
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        download_action = menu.addAction("Download")

        has_remote = self._remote_config is not None
        has_selection = entry is not None
        new_folder_action.setEnabled(has_remote)
        rename_action.setEnabled(has_remote and has_selection)
        delete_action.setEnabled(has_remote and has_selection)
        download_action.setEnabled(
            has_remote and entry is not None and entry.entry_type == FileEntryType.FILE
        )

        selected = menu.exec(self._remote_view.viewport().mapToGlobal(position))
        if selected == new_folder_action:
            self._new_remote_folder()
        elif selected == rename_action and entry is not None:
            self._rename_remote(entry)
        elif selected == delete_action and entry is not None:
            self._delete_remote(entry)
        elif selected == download_action and entry is not None:
            self._download_remote_file(entry)

    def _new_remote_folder(self) -> None:
        name, accepted = QInputDialog.getText(self, "New Remote Folder", "Folder name:")
        if not accepted:
            return
        self._start_remote_operation("mkdir", self._remote_path.text(), name=name)

    def _rename_remote(self, entry: FileEntry) -> None:
        name, accepted = QInputDialog.getText(self, "Rename Remote Item", "New name:", text=entry.name)
        if not accepted:
            return
        self._start_remote_operation("rename", entry.path, name=name)

    def _delete_remote(self, entry: FileEntry) -> None:
        kind = "folder" if entry.entry_type == FileEntryType.DIRECTORY else "file"
        result = QMessageBox.question(
            self,
            "Delete Remote Item",
            f"Delete this remote {kind}?\n{entry.path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if result != QMessageBox.Yes:
            return
        self._start_remote_operation(
            "delete",
            entry.path,
            is_directory=entry.entry_type == FileEntryType.DIRECTORY,
        )

    def _start_remote_listing(self, path: str) -> None:
        if self._remote_config is None:
            self._set_remote_status("Open a saved SSH connection before browsing remote files.")
            return
        if self._remote_worker is not None:
            self._set_remote_status("Remote file operation is already running.")
            return
        self._remote_pending_path = path.strip() or "."
        self._set_remote_status(f"Loading remote path: {self._remote_pending_path}")
        worker = SftpDirectoryListWorker(self._remote_config, self._remote_pending_path, self)
        self._remote_worker = worker
        worker.loaded.connect(self._remote_listing_loaded)
        worker.failed.connect(self._remote_listing_failed)
        worker.finished.connect(lambda: self._clear_remote_worker(worker))
        worker.start()

    def _remote_listing_loaded(self, entries: list[FileEntry]) -> None:
        self._remote_model.set_entries(entries)
        self._remote_path.setText(self._remote_pending_path)
        self._remote_view.resizeColumnsToContents()
        self._set_remote_status(f"Remote path loaded: {self._remote_pending_path}")

    def _remote_listing_failed(self, message: str) -> None:
        self._remote_model.set_entries([])
        self._set_remote_status(message)
        QMessageBox.warning(self, "SFTP failed", message)

    def _clear_remote_worker(self, worker: SftpDirectoryListWorker) -> None:
        if self._remote_worker is worker:
            self._remote_worker = None
        worker.deleteLater()

    def _start_remote_operation(
        self,
        operation: str,
        path: str,
        *,
        name: str | None = None,
        is_directory: bool = False,
    ) -> None:
        if self._remote_config is None:
            self._set_remote_status("Open a saved SSH connection before changing remote files.")
            return
        if self._remote_operation_worker is not None:
            self._set_remote_status("Remote file operation is already running.")
            return
        worker = SftpOperationWorker(self._remote_config, operation, path, name, is_directory, self)
        self._remote_operation_worker = worker
        worker.completed.connect(self._remote_operation_completed)
        worker.failed.connect(self._remote_operation_failed)
        worker.finished.connect(lambda: self._clear_remote_operation_worker(worker))
        worker.start()

    def _remote_operation_completed(self, result) -> None:
        self._show_status(result.message)
        self._refresh_remote()

    def _remote_operation_failed(self, message: str) -> None:
        self._set_remote_status(message)
        QMessageBox.warning(self, "SFTP operation failed", message)

    def _clear_remote_operation_worker(self, worker: SftpOperationWorker) -> None:
        if self._remote_operation_worker is worker:
            self._remote_operation_worker = None
        worker.deleteLater()

    def _upload_local_file(self, selected_path: Path) -> None:
        if self._remote_config is None:
            self._set_remote_status("Open a saved SSH connection before uploading.")
            return
        policy = self._choose_conflict_policy()
        if policy is None:
            return
        remote_directory = self._remote_path.text().strip() or "."
        target_path = self._remote_join(remote_directory, selected_path.name)
        try:
            transfer = self._file_manager.create_transfer_record(
                TransferDirection.UPLOAD,
                selected_path,
                target_path,
                conflict_policy=policy,
                connection_id=self._remote_connection_id,
                host=self._remote_config.host,
                total_bytes=selected_path.stat().st_size,
            )
        except Exception as exc:
            self._show_error("Upload failed", exc)
            return
        self._start_transfer_worker(transfer, str(selected_path), remote_directory)

    def _download_remote_file(self, entry: FileEntry) -> None:
        if self._remote_config is None:
            self._set_remote_status("Open a saved SSH connection before downloading.")
            return
        if entry.entry_type != FileEntryType.FILE:
            self._set_remote_status("Only single-file downloads are supported in this phase.")
            return
        policy = self._choose_conflict_policy()
        if policy is None:
            return
        local_directory = self._current_local_root()
        target_path = str(Path(local_directory) / entry.name)
        try:
            transfer = self._file_manager.create_transfer_record(
                TransferDirection.DOWNLOAD,
                entry.path,
                target_path,
                conflict_policy=policy,
                connection_id=self._remote_connection_id,
                host=self._remote_config.host,
                total_bytes=entry.size,
            )
        except Exception as exc:
            self._show_error("Download failed", exc)
            return
        self._start_transfer_worker(transfer, entry.path, local_directory)

    def _start_transfer_worker(
        self,
        transfer: FileTransferRecord,
        source_path: str,
        target_directory: str,
    ) -> None:
        if self._remote_config is None:
            return
        try:
            running = self._file_manager.mark_transfer_running(transfer.id)
        except Exception as exc:
            self._show_error("Transfer failed", exc)
            return
        self._transfer_model.upsert_record(running)
        worker = SftpTransferWorker(
            transfer.id,
            self._remote_config,
            transfer.direction.value,
            source_path,
            target_directory,
            transfer.conflict_policy,
            self,
        )
        self._transfer_workers[transfer.id] = worker
        worker.progress.connect(self._transfer_progressed)
        worker.completed.connect(self._transfer_completed)
        worker.failed.connect(self._transfer_failed)
        worker.finished.connect(lambda transfer_id=transfer.id: self._clear_transfer_worker(transfer_id))
        worker.start()
        self._show_status(f"Transfer started: #{transfer.id}")

    def _transfer_progressed(self, transfer_id: int, bytes_transferred: int, total_bytes) -> None:
        try:
            record = self._file_manager.update_transfer_progress(transfer_id, bytes_transferred, total_bytes)
        except Exception as exc:
            self._show_error("Transfer progress failed", exc)
            return
        self._transfer_model.upsert_record(record)

    def _transfer_completed(self, transfer_id: int, result) -> None:
        try:
            self._file_manager.update_transfer_target_path(transfer_id, result.path)
            record = self._file_manager.complete_transfer(transfer_id, result.bytes_transferred)
        except Exception as exc:
            self._show_error("Transfer completion failed", exc)
            return
        self._transfer_model.upsert_record(record)
        self._show_status(result.message or f"Transfer completed: #{transfer_id}")
        self._refresh_local()
        if self._remote_config is not None:
            self._refresh_remote()

    def _transfer_failed(self, transfer_id: int, message: str) -> None:
        try:
            record = self._file_manager.fail_transfer(transfer_id, message)
        except Exception as exc:
            self._show_error("Transfer failure update failed", exc)
            return
        self._transfer_model.upsert_record(record)
        QMessageBox.warning(self, "Transfer failed", message)

    def _clear_transfer_worker(self, transfer_id: int) -> None:
        worker = self._transfer_workers.pop(transfer_id, None)
        if worker is not None:
            worker.deleteLater()

    def _refresh_transfer_records(self) -> None:
        self._transfer_model.set_records(self._file_manager.list_transfer_records())
        self._transfer_view.resizeColumnsToContents()

    def _choose_conflict_policy(self) -> ConflictPolicy | None:
        labels = {
            "Skip existing target": ConflictPolicy.SKIP,
            "Overwrite existing target": ConflictPolicy.OVERWRITE,
            "Rename as copy": ConflictPolicy.RENAME,
        }
        choice, accepted = QInputDialog.getItem(
            self,
            "Conflict Policy",
            "If target exists:",
            list(labels.keys()),
            0,
            False,
        )
        if not accepted:
            return None
        return labels[choice]

    def _selected_connection_id(self) -> int | None:
        value = self._remote_connections.currentData()
        if value is None:
            return None
        return int(value)

    def _selected_remote_entry(self) -> FileEntry | None:
        indexes = self._remote_view.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._remote_model.entry_at(indexes[0].row())

    def _remote_parent_path(self, path: str) -> str:
        normalized = path.strip().replace("\\", "/").rstrip("/")
        if not normalized or normalized == "/":
            return "/"
        parent = normalized.rsplit("/", 1)[0]
        return parent or "/"

    def _remote_join(self, parent: str, name: str) -> str:
        normalized_parent = parent.strip().replace("\\", "/").rstrip("/") or "."
        if normalized_parent == "/":
            return f"/{name}"
        if normalized_parent == ".":
            return name
        return f"{normalized_parent}/{name}"

    def _set_remote_status(self, message: str) -> None:
        self._remote_status.setText(message)
        self._show_status(message)

    def _show_status(self, message: str) -> None:
        self.status_message.emit(message)

    def _show_error(self, title: str, error: Exception) -> None:
        message = str(error)
        self.status_message.emit(message)
        QMessageBox.warning(self, title, message)
