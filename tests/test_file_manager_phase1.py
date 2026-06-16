from __future__ import annotations

import sqlite3

import pytest

from app.common.models import (
    ConflictPolicy,
    FileEntryType,
    TransferDirection,
    TransferStatus,
)
from app.core.file_manager import FileManager
from app.storage.migrations import migrate
from app.storage.repositories import FileTransferRepository


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    return connection


def test_file_manager_lists_local_directory_with_directories_first(tmp_path) -> None:
    directory = tmp_path / "folder"
    directory.mkdir()
    file_path = tmp_path / "alpha.txt"
    file_path.write_text("hello", encoding="utf-8")

    entries = FileManager().list_local_directory(tmp_path)

    assert [entry.name for entry in entries] == ["folder", "alpha.txt"]
    assert entries[0].entry_type == FileEntryType.DIRECTORY
    assert entries[0].size is None
    assert entries[1].entry_type == FileEntryType.FILE
    assert entries[1].size == 5
    assert entries[1].modified_at is not None


def test_file_manager_rejects_missing_and_non_directory_paths(tmp_path) -> None:
    manager = FileManager()
    file_path = tmp_path / "file.txt"
    file_path.write_text("content", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        manager.list_local_directory(tmp_path / "missing")

    with pytest.raises(NotADirectoryError):
        manager.list_local_directory(file_path)


def test_file_manager_detects_local_target_conflicts(tmp_path) -> None:
    target = tmp_path / "exists.txt"
    target.write_text("content", encoding="utf-8")
    manager = FileManager()

    assert manager.local_target_exists(target)
    assert not manager.local_target_exists(tmp_path / "new.txt")


def test_file_manager_creates_transfer_record_through_repository(tmp_path) -> None:
    connection = _connection()
    manager = FileManager(FileTransferRepository(connection))
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")

    transfer = manager.create_transfer_record(
        TransferDirection.UPLOAD,
        source,
        "/tmp/source.txt",
        conflict_policy=ConflictPolicy.SKIP,
        host="example.test",
        total_bytes=7,
    )

    assert transfer.status == TransferStatus.QUEUED
    assert transfer.source_path == str(source)
    assert transfer.target_path == "/tmp/source.txt"
    assert transfer.host == "example.test"
    assert transfer.total_bytes == 7


def test_file_manager_requires_transfer_repository(tmp_path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")

    with pytest.raises(RuntimeError, match="repository is not configured"):
        FileManager().create_transfer_record(TransferDirection.UPLOAD, source, "/tmp/source.txt")
