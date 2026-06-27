from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.common.models import (
    ConflictPolicy,
    FileEntry,
    FileEntryType,
    FileTransferRecord,
    TransferDirection,
    TransferStatus,
)
from app.backends.sftp_backend import SftpBackend, SftpOperationResult
from app.storage.repositories import FileTransferRepository


class FileManager:
    """文件管理服务边界, UI 和远程后端通过这里复用基础规则."""

    def __init__(self, transfer_repository: FileTransferRepository | None = None) -> None:
        self._transfers = transfer_repository

    def get_local_entry(self, path: str | Path) -> FileEntry:
        """读取本地路径元数据."""
        local_path = self._normalize_path(path)
        if not local_path.exists():
            raise FileNotFoundError(f"Local path does not exist: {local_path}")
        return self._entry_from_path(local_path)

    def list_local_directory(self, path: str | Path) -> list[FileEntry]:
        """列出本地目录内容, 目录优先并按名称排序."""
        local_path = self._normalize_path(path)
        if not local_path.exists():
            raise FileNotFoundError(f"Local directory does not exist: {local_path}")
        if not local_path.is_dir():
            raise NotADirectoryError(f"Local path is not a directory: {local_path}")

        entries = [self._entry_from_path(child) for child in local_path.iterdir()]
        return sorted(
            entries,
            key=lambda item: (
                item.entry_type != FileEntryType.DIRECTORY,
                item.name.lower(),
                item.name,
            ),
        )

    def local_target_exists(self, path: str | Path) -> bool:
        """检查本地目标路径是否已存在, 供冲突策略使用."""
        return self._normalize_path(path).exists()

    def create_local_directory(self, parent_path: str | Path, name: str) -> FileEntry:
        """在本地目录下创建新文件夹."""
        parent = self._require_local_directory(parent_path)
        directory_name = self._validate_local_name(name, "Directory name")
        target = parent / directory_name
        if target.exists():
            raise FileExistsError(f"Local path already exists: {target}")
        target.mkdir()
        return self._entry_from_path(target)

    def create_local_file(self, parent_path: str | Path, name: str) -> FileEntry:
        """在本地目录下创建空文件."""
        parent = self._require_local_directory(parent_path)
        file_name = self._validate_local_name(name, "File name")
        target = parent / file_name
        if target.exists():
            raise FileExistsError(f"Local path already exists: {target}")
        target.touch()
        return self._entry_from_path(target)

    def rename_local_path(self, path: str | Path, new_name: str) -> FileEntry:
        """重命名本地文件或目录, 不允许跨目录移动."""
        source = self._require_existing_local_path(path)
        target_name = self._validate_local_name(new_name, "New name")
        target = source.with_name(target_name)
        if target == source:
            return self._entry_from_path(source)
        if target.exists():
            raise FileExistsError(f"Local path already exists: {target}")
        source.rename(target)
        return self._entry_from_path(target)

    def delete_local_path(self, path: str | Path) -> None:
        """删除本地文件或目录, UI 必须先完成用户确认."""
        target = self._require_existing_local_path(path)
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
            return
        target.unlink()

    def copy_local_path(self, source_path: str | Path, target_directory: str | Path) -> FileEntry:
        """复制本地文件或目录到目标目录, 不静默覆盖已有目标."""
        source = self._require_existing_local_path(source_path)
        target_parent = self._require_local_directory(target_directory)
        target = target_parent / source.name
        if target.exists():
            raise FileExistsError(f"Local path already exists: {target}")
        if source.is_dir() and not source.is_symlink():
            self._reject_copy_into_self(source, target_parent)
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
        return self._entry_from_path(target)

    def list_transfer_records(
        self,
        limit: int = 100,
        status: TransferStatus | None = None,
        connection_id: int | None = None,
    ) -> list[FileTransferRecord]:
        """列出传输队列记录."""
        if self._transfers is None:
            return []
        return self._transfers.list_transfers(limit=limit, status=status, connection_id=connection_id)

    async def list_remote_directory(self, backend: SftpBackend, path: str) -> list[FileEntry]:
        """通过 SFTP 后端列出远程目录."""
        return await backend.list_directory(path)

    async def create_remote_directory(self, backend: SftpBackend, parent_path: str, name: str) -> SftpOperationResult:
        """创建远程目录, 具体 IO 由 SFTP 后端执行."""
        return await backend.create_directory(parent_path, name)

    async def rename_remote_path(self, backend: SftpBackend, path: str, new_name: str) -> SftpOperationResult:
        """重命名远程文件或目录, 不允许跨目录移动."""
        return await backend.rename_path(path, new_name)

    async def delete_remote_path(
        self,
        backend: SftpBackend,
        path: str,
        *,
        is_directory: bool = False,
    ) -> SftpOperationResult:
        """删除远程文件或空目录, UI 必须先完成用户确认."""
        return await backend.delete_path(path, is_directory=is_directory)

    def create_transfer_record(
        self,
        direction: TransferDirection,
        source_path: str | Path,
        target_path: str | Path,
        conflict_policy: ConflictPolicy = ConflictPolicy.SKIP,
        connection_id: int | None = None,
        host: str | None = None,
        total_bytes: int | None = None,
    ) -> FileTransferRecord:
        """创建传输记录."""
        if self._transfers is None:
            raise RuntimeError("File transfer repository is not configured.")
        return self._transfers.create_transfer(
            direction=direction,
            source_path=str(source_path),
            target_path=str(target_path),
            conflict_policy=conflict_policy,
            connection_id=connection_id,
            host=host,
            total_bytes=total_bytes,
        )

    def mark_transfer_running(self, transfer_id: int) -> FileTransferRecord:
        """标记传输开始运行."""
        if self._transfers is None:
            raise RuntimeError("File transfer repository is not configured.")
        return self._transfers.mark_running(transfer_id)

    def update_transfer_progress(
        self,
        transfer_id: int,
        bytes_transferred: int,
        total_bytes: int | None = None,
    ) -> FileTransferRecord:
        """更新传输进度."""
        if self._transfers is None:
            raise RuntimeError("File transfer repository is not configured.")
        return self._transfers.update_progress(transfer_id, bytes_transferred, total_bytes)

    def update_transfer_target_path(self, transfer_id: int, target_path: str) -> FileTransferRecord:
        """更新传输最终目标路径."""
        if self._transfers is None:
            raise RuntimeError("File transfer repository is not configured.")
        return self._transfers.update_target_path(transfer_id, target_path)

    def complete_transfer(
        self,
        transfer_id: int,
        bytes_transferred: int | None = None,
    ) -> FileTransferRecord:
        """标记传输完成."""
        if self._transfers is None:
            raise RuntimeError("File transfer repository is not configured.")
        return self._transfers.complete_transfer(transfer_id, bytes_transferred)

    def fail_transfer(self, transfer_id: int, error_message: str) -> FileTransferRecord:
        """标记传输失败."""
        if self._transfers is None:
            raise RuntimeError("File transfer repository is not configured.")
        return self._transfers.fail_transfer(transfer_id, error_message)

    def _normalize_path(self, path: str | Path) -> Path:
        try:
            return Path(path).expanduser().resolve(strict=False)
        except RuntimeError as exc:
            raise ValueError(f"Invalid local path: {path}") from exc

    def _require_existing_local_path(self, path: str | Path) -> Path:
        local_path = self._normalize_path(path)
        if not local_path.exists():
            raise FileNotFoundError(f"Local path does not exist: {local_path}")
        return local_path

    def _require_local_directory(self, path: str | Path) -> Path:
        local_path = self._require_existing_local_path(path)
        if not local_path.is_dir():
            raise NotADirectoryError(f"Local path is not a directory: {local_path}")
        return local_path

    def _validate_local_name(self, name: str, label: str) -> str:
        value = name.strip()
        if not value:
            raise ValueError(f"{label} cannot be empty.")
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError(f"{label} must be a single file or directory name.")
        return value

    def _reject_copy_into_self(self, source: Path, target_parent: Path) -> None:
        try:
            target_parent.relative_to(source)
        except ValueError:
            return
        raise ValueError(f"Cannot copy a directory into itself: {source}")

    def _entry_from_path(self, path: Path) -> FileEntry:
        stat = path.stat()
        entry_type = self._entry_type(path)
        return FileEntry(
            path=str(path),
            name=path.name or str(path),
            entry_type=entry_type,
            size=stat.st_size if entry_type == FileEntryType.FILE else None,
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            is_hidden=path.name.startswith("."),
        )

    def _entry_type(self, path: Path) -> FileEntryType:
        if path.is_symlink():
            return FileEntryType.SYMLINK
        if path.is_dir():
            return FileEntryType.DIRECTORY
        if path.is_file():
            return FileEntryType.FILE
        return FileEntryType.OTHER
