from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.common.models import (
    ConflictPolicy,
    FileEntry,
    FileEntryType,
    FileTransferRecord,
    TransferDirection,
)
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
        """创建传输记录, Phase 1 不执行真实 IO."""
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

    def _normalize_path(self, path: str | Path) -> Path:
        try:
            return Path(path).expanduser().resolve(strict=False)
        except RuntimeError as exc:
            raise ValueError(f"Invalid local path: {path}") from exc

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
