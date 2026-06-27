from __future__ import annotations

import asyncio
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.common.models import ConflictPolicy, FileEntry, FileEntryType, SshConnectionConfig


class SftpError(RuntimeError):
    """SFTP 操作失败时抛出的可展示错误."""


@dataclass(frozen=True)
class SftpOperationResult:
    """后台 SFTP 操作的轻量结果."""

    path: str
    message: str


@dataclass(frozen=True)
class SftpTransferResult:
    """SFTP 单文件传输结果."""

    path: str
    bytes_transferred: int
    skipped: bool = False
    message: str = ""


class SftpBackend:
    """基于 asyncssh 的短连接 SFTP 操作封装."""

    def __init__(self, config: SshConnectionConfig, asyncssh_module: Any | None = None) -> None:
        self._config = config
        self._asyncssh_module = asyncssh_module

    async def list_directory(self, path: str) -> list[FileEntry]:
        """列出远程目录, 目录优先并按名称排序."""
        normalized = self._normalize_remote_path(path)
        asyncssh = self._load_asyncssh()
        connection = None
        try:
            connection = await asyncssh.connect(**self._connect_kwargs())
            sftp = await connection.start_sftp_client()
            entries = await self._scan_directory(sftp, normalized)
        except Exception as exc:
            raise SftpError(self._format_error(exc, asyncssh)) from exc
        finally:
            if connection is not None:
                connection.close()
                await connection.wait_closed()

        return sorted(
            entries,
            key=lambda item: (
                item.entry_type != FileEntryType.DIRECTORY,
                item.name.lower(),
                item.name,
            ),
        )

    async def create_directory(self, parent_path: str, name: str) -> SftpOperationResult:
        target = self._join_remote_path(parent_path, self._validate_remote_name(name, "Directory name"))
        await self._run_sftp_call(lambda sftp: sftp.mkdir(target))
        return SftpOperationResult(path=target, message=f"Created remote folder: {target}")

    async def rename_path(self, path: str, new_name: str) -> SftpOperationResult:
        source = self._normalize_remote_path(path)
        target = self._join_remote_path(self._parent_remote_path(source), self._validate_remote_name(new_name, "New name"))
        if source == target:
            return SftpOperationResult(path=target, message=f"Remote item unchanged: {target}")
        await self._run_sftp_call(lambda sftp: sftp.rename(source, target))
        return SftpOperationResult(path=target, message=f"Renamed remote item: {target}")

    async def delete_path(self, path: str, *, is_directory: bool = False) -> SftpOperationResult:
        target = self._normalize_remote_path(path)
        if is_directory:
            await self._run_sftp_call(lambda sftp: sftp.rmdir(target))
        else:
            await self._run_sftp_call(lambda sftp: sftp.remove(target))
        return SftpOperationResult(path=target, message=f"Deleted remote item: {target}")

    async def upload_file(
        self,
        local_path: str | Path,
        remote_directory: str,
        conflict_policy: ConflictPolicy = ConflictPolicy.SKIP,
        progress_callback=None,
    ) -> SftpTransferResult:
        """上传单个本地文件到远程目录."""
        source = Path(local_path).expanduser().resolve(strict=True)
        if not source.is_file():
            raise ValueError(f"Upload source must be a file: {source}")
        remote_target = self._join_remote_path(remote_directory, source.name)
        asyncssh = self._load_asyncssh()
        connection = None
        try:
            connection = await asyncssh.connect(**self._connect_kwargs())
            sftp = await connection.start_sftp_client()
            target = await self._resolve_remote_conflict(sftp, remote_target, conflict_policy)
            if target is None:
                return SftpTransferResult(
                    path=remote_target,
                    bytes_transferred=0,
                    skipped=True,
                    message=f"Skipped existing remote file: {remote_target}",
                )
            total_bytes = source.stat().st_size
            transferred = await self._upload_bytes(sftp, source, target, total_bytes, progress_callback)
            return SftpTransferResult(
                path=target,
                bytes_transferred=transferred,
                message=f"Uploaded file: {target}",
            )
        except Exception as exc:
            raise SftpError(self._format_error(exc, asyncssh)) from exc
        finally:
            if connection is not None:
                connection.close()
                await connection.wait_closed()

    async def download_file(
        self,
        remote_path: str,
        local_directory: str | Path,
        conflict_policy: ConflictPolicy = ConflictPolicy.SKIP,
        progress_callback=None,
    ) -> SftpTransferResult:
        """下载单个远程文件到本地目录."""
        remote_source = self._normalize_remote_path(remote_path)
        target_directory = Path(local_directory).expanduser().resolve(strict=True)
        if not target_directory.is_dir():
            raise NotADirectoryError(f"Download target must be a local directory: {target_directory}")
        local_target = self._resolve_local_conflict(
            target_directory / self._remote_basename(remote_source),
            conflict_policy,
        )
        if local_target is None:
            return SftpTransferResult(
                path=str(target_directory / self._remote_basename(remote_source)),
                bytes_transferred=0,
                skipped=True,
                message=f"Skipped existing local file: {target_directory / self._remote_basename(remote_source)}",
            )

        asyncssh = self._load_asyncssh()
        connection = None
        try:
            connection = await asyncssh.connect(**self._connect_kwargs())
            sftp = await connection.start_sftp_client()
            attrs = await self._maybe_await(sftp.stat(remote_source))
            total_bytes = getattr(attrs, "size", None)
            transferred = await self._download_bytes(
                sftp,
                remote_source,
                local_target,
                total_bytes,
                progress_callback,
            )
            return SftpTransferResult(
                path=str(local_target),
                bytes_transferred=transferred,
                message=f"Downloaded file: {local_target}",
            )
        except Exception as exc:
            raise SftpError(self._format_error(exc, asyncssh)) from exc
        finally:
            if connection is not None:
                connection.close()
                await connection.wait_closed()

    def _load_asyncssh(self):
        if self._asyncssh_module is not None:
            return self._asyncssh_module
        try:
            import asyncssh
        except ImportError as exc:
            raise SftpError("asyncssh is not installed. Run: pip install -e .") from exc
        return asyncssh

    async def _run_sftp_call(self, operation) -> None:
        asyncssh = self._load_asyncssh()
        connection = None
        try:
            connection = await asyncssh.connect(**self._connect_kwargs())
            sftp = await connection.start_sftp_client()
            result = operation(sftp)
            if hasattr(result, "__await__"):
                await result
        except Exception as exc:
            raise SftpError(self._format_error(exc, asyncssh)) from exc
        finally:
            if connection is not None:
                connection.close()
                await connection.wait_closed()

    async def _upload_bytes(
        self,
        sftp,
        source: Path,
        target: str,
        total_bytes: int,
        progress_callback,
    ) -> int:
        transferred = 0
        remote_file = await self._maybe_await(sftp.open(target, "wb"))
        try:
            with source.open("rb") as local_file:
                while True:
                    chunk = local_file.read(1024 * 256)
                    if not chunk:
                        break
                    await self._maybe_await(remote_file.write(chunk))
                    transferred += len(chunk)
                    self._emit_progress(progress_callback, transferred, total_bytes)
        finally:
            await self._close_sftp_file(remote_file)
        return transferred

    async def _download_bytes(
        self,
        sftp,
        source: str,
        target: Path,
        total_bytes: int | None,
        progress_callback,
    ) -> int:
        transferred = 0
        remote_file = await self._maybe_await(sftp.open(source, "rb"))
        try:
            with target.open("wb") as local_file:
                while True:
                    chunk = await self._maybe_await(remote_file.read(1024 * 256))
                    if not chunk:
                        break
                    if isinstance(chunk, str):
                        chunk = chunk.encode("utf-8")
                    local_file.write(chunk)
                    transferred += len(chunk)
                    self._emit_progress(progress_callback, transferred, total_bytes)
        finally:
            await self._close_sftp_file(remote_file)
        return transferred

    async def _close_sftp_file(self, file_obj) -> None:
        close = getattr(file_obj, "close", None)
        if close is not None:
            result = close()
            if hasattr(result, "__await__"):
                await result

    def _emit_progress(self, progress_callback, transferred: int, total_bytes: int | None) -> None:
        if progress_callback is not None:
            progress_callback(transferred, total_bytes)

    async def _resolve_remote_conflict(self, sftp, target: str, policy: ConflictPolicy) -> str | None:
        if not await self._remote_exists(sftp, target):
            return target
        if policy == ConflictPolicy.SKIP:
            return None
        if policy == ConflictPolicy.OVERWRITE:
            return target
        if policy == ConflictPolicy.RENAME:
            return await self._next_remote_copy_path(sftp, target)
        raise ValueError(f"Unsupported conflict policy: {policy}")

    async def _remote_exists(self, sftp, path: str) -> bool:
        try:
            await self._maybe_await(sftp.stat(path))
            return True
        except Exception:
            return False

    async def _next_remote_copy_path(self, sftp, target: str) -> str:
        parent = self._parent_remote_path(target)
        name = self._remote_basename(target)
        stem, suffix = self._split_name_suffix(name)
        for index in range(1, 1000):
            candidate_name = f"{stem} copy{'' if index == 1 else f' {index}'}{suffix}"
            candidate = self._join_remote_path(parent, candidate_name)
            if not await self._remote_exists(sftp, candidate):
                return candidate
        raise FileExistsError(f"No available remote copy name for: {target}")

    def _resolve_local_conflict(self, target: Path, policy: ConflictPolicy) -> Path | None:
        if not target.exists():
            return target
        if policy == ConflictPolicy.SKIP:
            return None
        if policy == ConflictPolicy.OVERWRITE:
            return target
        if policy == ConflictPolicy.RENAME:
            return self._next_local_copy_path(target)
        raise ValueError(f"Unsupported conflict policy: {policy}")

    def _next_local_copy_path(self, target: Path) -> Path:
        for index in range(1, 1000):
            candidate = target.with_name(
                f"{target.stem} copy{'' if index == 1 else f' {index}'}{target.suffix}"
            )
            if not candidate.exists():
                return candidate
        raise FileExistsError(f"No available local copy name for: {target}")

    async def _scan_directory(self, sftp, path: str) -> list[FileEntry]:
        if hasattr(sftp, "scandir"):
            names = await self._collect_results(sftp.scandir(path))
            return [self._entry_from_sftp_name(path, item) for item in names]

        names = await self._collect_results(sftp.listdir(path))
        entries: list[FileEntry] = []
        for name in names:
            child_path = self._join_remote_path(path, str(name))
            attrs = await self._maybe_await(sftp.stat(child_path))
            entries.append(self._entry_from_attrs(child_path, str(name), attrs))
        return entries

    async def _collect_results(self, value) -> list:
        result = await self._maybe_await(value)
        if hasattr(result, "__aiter__"):
            items = []
            async for item in result:
                items.append(item)
            return items
        return list(result)

    async def _maybe_await(self, value):
        if hasattr(value, "__await__"):
            return await value
        return value

    def _entry_from_sftp_name(self, directory: str, item) -> FileEntry:
        name = str(getattr(item, "filename", item))
        attrs = getattr(item, "attrs", None)
        return self._entry_from_attrs(self._join_remote_path(directory, name), name, attrs)

    def _entry_from_attrs(self, path: str, name: str, attrs) -> FileEntry:
        permissions = getattr(attrs, "permissions", None)
        entry_type = self._entry_type(permissions)
        size = getattr(attrs, "size", None) if entry_type == FileEntryType.FILE else None
        modified_at = self._format_modified_time(getattr(attrs, "mtime", None))
        permission_text = self._format_permissions(permissions)
        return FileEntry(
            path=path,
            name=name,
            entry_type=entry_type,
            size=size,
            modified_at=modified_at,
            permissions=permission_text,
            is_hidden=name.startswith("."),
        )

    def _entry_type(self, permissions: int | None) -> FileEntryType:
        if permissions is None:
            return FileEntryType.OTHER
        mode = stat.S_IFMT(permissions)
        if mode == stat.S_IFDIR:
            return FileEntryType.DIRECTORY
        if mode == stat.S_IFLNK:
            return FileEntryType.SYMLINK
        if mode == stat.S_IFREG:
            return FileEntryType.FILE
        return FileEntryType.OTHER

    def _format_modified_time(self, timestamp: int | float | None) -> str | None:
        if timestamp is None:
            return None
        return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")

    def _format_permissions(self, permissions: int | None) -> str | None:
        if permissions is None:
            return None
        return oct(permissions & 0o777)

    def _connect_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "host": self._config.host,
            "port": self._config.port,
            "username": self._config.username,
        }
        if self._config.password:
            kwargs["password"] = self._config.password
        if self._config.private_key_path:
            kwargs["client_keys"] = [self._config.private_key_path]
        if self._config.private_key_passphrase:
            kwargs["passphrase"] = self._config.private_key_passphrase
        if self._config.accept_unknown_host:
            kwargs["known_hosts"] = None
        return kwargs

    def _format_error(self, exc: Exception, asyncssh_module: Any) -> str:
        if isinstance(exc, SftpError):
            return str(exc)
        if isinstance(exc, getattr(asyncssh_module, "PermissionDenied", ())):
            return "SFTP authentication failed. Check the username, password, private key, or key passphrase."
        if isinstance(exc, getattr(asyncssh_module, "SFTPNoSuchFile", ())):
            return "SFTP path does not exist."
        if isinstance(exc, getattr(asyncssh_module, "SFTPPermissionDenied", ())):
            return "SFTP permission denied for this path."
        if isinstance(exc, OSError):
            return f"SFTP connection failed. Check the host, port, and network: {exc}"
        return f"SFTP operation failed: {exc}"

    def _normalize_remote_path(self, path: str) -> str:
        value = path.strip() or "."
        return value.replace("\\", "/")

    def _parent_remote_path(self, path: str) -> str:
        normalized = self._normalize_remote_path(path).rstrip("/")
        if not normalized or normalized == "/":
            return "/"
        parent = normalized.rsplit("/", 1)[0]
        return parent or "/"

    def _remote_basename(self, path: str) -> str:
        value = self._normalize_remote_path(path).rstrip("/")
        name = value.rsplit("/", 1)[-1]
        if not name:
            raise ValueError(f"Remote path has no file name: {path}")
        return name

    def _split_name_suffix(self, name: str) -> tuple[str, str]:
        if "." not in name or name.startswith(".") and name.count(".") == 1:
            return name, ""
        stem, suffix = name.rsplit(".", 1)
        return stem, f".{suffix}"

    def _join_remote_path(self, parent: str, name: str) -> str:
        normalized_parent = self._normalize_remote_path(parent).rstrip("/")
        if not normalized_parent:
            return name
        if normalized_parent == "/":
            return f"/{name}"
        return f"{normalized_parent}/{name}"

    def _validate_remote_name(self, name: str, label: str) -> str:
        value = name.strip()
        if not value:
            raise ValueError(f"{label} cannot be empty.")
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError(f"{label} must be a single file or directory name.")
        return value


class SftpDirectoryListWorker(QThread):
    """在后台线程中执行远程目录列表."""

    loaded = Signal(list)
    failed = Signal(str)

    def __init__(self, config: SshConnectionConfig, path: str, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._path = path

    def run(self) -> None:
        try:
            entries = asyncio.run(SftpBackend(self._config).list_directory(self._path))
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.loaded.emit(entries)


class SftpOperationWorker(QThread):
    """在后台线程中执行单个远程变更操作."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        config: SshConnectionConfig,
        operation: str,
        path: str,
        name: str | None = None,
        is_directory: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._operation = operation
        self._path = path
        self._name = name
        self._is_directory = is_directory

    def run(self) -> None:
        try:
            result = asyncio.run(self._run_operation())
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.completed.emit(result)

    async def _run_operation(self) -> SftpOperationResult:
        backend = SftpBackend(self._config)
        if self._operation == "mkdir":
            return await backend.create_directory(self._path, self._name or "")
        if self._operation == "rename":
            return await backend.rename_path(self._path, self._name or "")
        if self._operation == "delete":
            return await backend.delete_path(self._path, is_directory=self._is_directory)
        raise ValueError(f"Unsupported SFTP operation: {self._operation}")


class SftpTransferWorker(QThread):
    """在后台线程中执行单文件上传或下载."""

    progress = Signal(int, int, object)
    completed = Signal(int, object)
    failed = Signal(int, str)

    def __init__(
        self,
        transfer_id: int,
        config: SshConnectionConfig,
        direction: str,
        source_path: str,
        target_directory: str,
        conflict_policy: ConflictPolicy,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._transfer_id = transfer_id
        self._config = config
        self._direction = direction
        self._source_path = source_path
        self._target_directory = target_directory
        self._conflict_policy = conflict_policy

    def run(self) -> None:
        try:
            result = asyncio.run(self._run_transfer())
        except Exception as exc:
            self.failed.emit(self._transfer_id, str(exc))
            return
        self.completed.emit(self._transfer_id, result)

    async def _run_transfer(self) -> SftpTransferResult:
        backend = SftpBackend(self._config)
        progress_callback = lambda transferred, total: self.progress.emit(
            self._transfer_id,
            transferred,
            total,
        )
        if self._direction == "upload":
            return await backend.upload_file(
                self._source_path,
                self._target_directory,
                self._conflict_policy,
                progress_callback,
            )
        if self._direction == "download":
            return await backend.download_file(
                self._source_path,
                self._target_directory,
                self._conflict_policy,
                progress_callback,
            )
        raise ValueError(f"Unsupported transfer direction: {self._direction}")
