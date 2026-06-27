from __future__ import annotations

import asyncio
import stat
from dataclasses import dataclass

from app.backends.sftp_backend import SftpBackend
from app.common.models import ConflictPolicy, SshConnectionConfig, TransferDirection
from app.core.file_manager import FileManager
from app.storage.migrations import migrate
from app.storage.repositories import FileTransferRepository

import sqlite3


@dataclass
class _FakeAttrs:
    permissions: int
    size: int | None = None
    mtime: int | None = None


class _FakeRemoteFile:
    def __init__(self, initial: bytes = b"") -> None:
        self._data = bytearray(initial)
        self._offset = 0
        self.closed = False

    async def write(self, chunk: bytes) -> None:
        self._data.extend(chunk)

    async def read(self, size: int) -> bytes:
        if self._offset >= len(self._data):
            return b""
        chunk = bytes(self._data[self._offset : self._offset + size])
        self._offset += len(chunk)
        return chunk

    async def close(self) -> None:
        self.closed = True

    @property
    def data(self) -> bytes:
        return bytes(self._data)


class _FakeSftp:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {
            "/srv/report.txt": b"existing",
            "/srv/readme.txt": b"remote-content",
        }
        self.opened: dict[str, _FakeRemoteFile] = {}

    async def stat(self, path: str):
        if path not in self.files:
            raise _FakeAsyncssh.SFTPNoSuchFile(path)
        return _FakeAttrs(stat.S_IFREG | 0o644, size=len(self.files[path]))

    async def open(self, path: str, mode: str):
        if "r" in mode:
            return _FakeRemoteFile(self.files[path])
        remote_file = _FakeRemoteFile()
        self.opened[path] = remote_file
        return remote_file


class _FakeConnection:
    def __init__(self, sftp: _FakeSftp) -> None:
        self.sftp = sftp
        self.closed = False

    async def start_sftp_client(self) -> _FakeSftp:
        return self.sftp

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class _FakeAsyncssh:
    class PermissionDenied(Exception):
        pass

    class SFTPNoSuchFile(Exception):
        pass

    class SFTPPermissionDenied(Exception):
        pass

    def __init__(self, sftp: _FakeSftp) -> None:
        self.sftp = sftp

    async def connect(self, **kwargs):
        _ = kwargs
        return _FakeConnection(self.sftp)


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    return connection


def test_sftp_upload_renames_existing_remote_target_and_reports_progress(tmp_path) -> None:
    sftp = _FakeSftp()
    backend = SftpBackend(
        SshConnectionConfig(host="example.test", port=22, username="alice"),
        asyncssh_module=_FakeAsyncssh(sftp),
    )
    source = tmp_path / "report.txt"
    source.write_bytes(b"new-report")
    progress: list[tuple[int, int | None]] = []

    result = asyncio.run(
        backend.upload_file(
            source,
            "/srv",
            ConflictPolicy.RENAME,
            lambda transferred, total: progress.append((transferred, total)),
        )
    )

    assert result.path == "/srv/report copy.txt"
    assert result.bytes_transferred == len(b"new-report")
    assert sftp.opened["/srv/report copy.txt"].data == b"new-report"
    assert progress[-1] == (len(b"new-report"), len(b"new-report"))


def test_sftp_download_renames_existing_local_target_and_reports_progress(tmp_path) -> None:
    sftp = _FakeSftp()
    backend = SftpBackend(
        SshConnectionConfig(host="example.test", port=22, username="alice"),
        asyncssh_module=_FakeAsyncssh(sftp),
    )
    existing = tmp_path / "readme.txt"
    existing.write_text("local", encoding="utf-8")
    progress: list[tuple[int, int | None]] = []

    result = asyncio.run(
        backend.download_file(
            "/srv/readme.txt",
            tmp_path,
            ConflictPolicy.RENAME,
            lambda transferred, total: progress.append((transferred, total)),
        )
    )

    downloaded = tmp_path / "readme copy.txt"
    assert result.path == str(downloaded)
    assert downloaded.read_bytes() == b"remote-content"
    assert existing.read_text(encoding="utf-8") == "local"
    assert progress[-1] == (len(b"remote-content"), len(b"remote-content"))


def test_file_manager_updates_transfer_target_after_conflict_rename() -> None:
    connection = _connection()
    manager = FileManager(FileTransferRepository(connection))
    transfer = manager.create_transfer_record(
        TransferDirection.DOWNLOAD,
        "/srv/readme.txt",
        "C:/Downloads/readme.txt",
        conflict_policy=ConflictPolicy.RENAME,
    )

    updated = manager.update_transfer_target_path(transfer.id, "C:/Downloads/readme copy.txt")
    completed = manager.complete_transfer(transfer.id, 13)

    assert updated.target_path == "C:/Downloads/readme copy.txt"
    assert completed.target_path == "C:/Downloads/readme copy.txt"
    assert completed.bytes_transferred == 13
