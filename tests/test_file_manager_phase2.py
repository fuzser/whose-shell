from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.file_manager import FileManager
from app.ui.files.file_manager_dock import FileManagerDock


def test_file_manager_creates_renames_and_deletes_local_folder(tmp_path) -> None:
    manager = FileManager()

    created = manager.create_local_directory(tmp_path, "drafts")
    created_path = Path(created.path)
    assert created_path.is_dir()

    renamed = manager.rename_local_path(created_path, "archive")
    renamed_path = Path(renamed.path)
    assert renamed_path.is_dir()
    assert not created_path.exists()

    manager.delete_local_path(renamed_path)

    assert not renamed_path.exists()


def test_file_manager_creates_renames_and_deletes_local_file(tmp_path) -> None:
    manager = FileManager()
    created = manager.create_local_file(tmp_path, "old.txt")
    source = Path(created.path)
    assert source.read_text(encoding="utf-8") == ""

    renamed = manager.rename_local_path(source, "new.txt")
    renamed_path = Path(renamed.path)
    assert renamed_path.read_text(encoding="utf-8") == ""
    assert not source.exists()

    manager.delete_local_path(renamed_path)

    assert not renamed_path.exists()


def test_file_manager_copies_local_file_and_directory_without_overwrite(tmp_path) -> None:
    manager = FileManager()
    source_file = tmp_path / "source.txt"
    source_file.write_text("payload", encoding="utf-8")
    source_dir = tmp_path / "folder"
    source_dir.mkdir()
    (source_dir / "nested.txt").write_text("nested", encoding="utf-8")
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    copied_file = manager.copy_local_path(source_file, target_dir)
    copied_dir = manager.copy_local_path(source_dir, target_dir)

    assert Path(copied_file.path).read_text(encoding="utf-8") == "payload"
    assert (Path(copied_dir.path) / "nested.txt").read_text(encoding="utf-8") == "nested"
    with pytest.raises(FileExistsError):
        manager.copy_local_path(source_file, target_dir)


def test_file_manager_rejects_copying_directory_into_itself(tmp_path) -> None:
    manager = FileManager()
    source_dir = tmp_path / "folder"
    nested_dir = source_dir / "nested"
    nested_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match="Cannot copy a directory into itself"):
        manager.copy_local_path(source_dir, nested_dir)


def test_file_manager_rejects_unsafe_local_names(tmp_path) -> None:
    manager = FileManager()
    existing = tmp_path / "existing"
    existing.mkdir()

    with pytest.raises(ValueError, match="cannot be empty"):
        manager.create_local_directory(tmp_path, "   ")

    with pytest.raises(ValueError, match="single file or directory name"):
        manager.create_local_directory(tmp_path, "../outside")

    with pytest.raises(FileExistsError):
        manager.create_local_directory(tmp_path, "existing")

    with pytest.raises(ValueError, match="cannot be empty"):
        manager.create_local_file(tmp_path, "   ")

    with pytest.raises(ValueError, match="single file or directory name"):
        manager.create_local_file(tmp_path, "nested/file.txt")

    with pytest.raises(FileExistsError):
        manager.create_local_file(tmp_path, "existing")


def test_file_manager_rejects_rename_conflict(tmp_path) -> None:
    manager = FileManager()
    source = tmp_path / "source.txt"
    target = tmp_path / "target.txt"
    source.write_text("source", encoding="utf-8")
    target.write_text("target", encoding="utf-8")

    with pytest.raises(FileExistsError):
        manager.rename_local_path(source, "target.txt")

    assert source.exists()
    assert target.read_text(encoding="utf-8") == "target"


def test_file_manager_dock_loads_local_path_and_reports_invalid_path(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    _ = app
    messages: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)

    dock = FileManagerDock(file_manager=FileManager())
    dock.status_message.connect(messages.append)

    assert dock._set_local_root(tmp_path)
    assert dock._local_path.text() == str(tmp_path.resolve())

    assert not dock._set_local_root(tmp_path / "missing")
    assert "does not exist" in messages[-1]


def test_file_manager_dock_tracks_parent_and_back_navigation(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    _ = app
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    parent = tmp_path / "parent"
    child = parent / "child"
    child.mkdir(parents=True)

    dock = FileManagerDock(file_manager=FileManager())
    assert dock._set_local_root(parent)
    assert dock._set_local_root(child)

    dock._go_to_parent_local()
    assert dock._local_path.text() == str(parent.resolve())

    dock._go_back_local()
    assert dock._local_path.text() == str(child.resolve())


def test_file_manager_dock_pastes_copied_local_item(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    _ = app
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    source = tmp_path / "source.txt"
    target_dir = tmp_path / "target"
    source.write_text("payload", encoding="utf-8")
    target_dir.mkdir()

    dock = FileManagerDock(file_manager=FileManager())
    dock._copy_local(source)
    dock._paste_local(target_dir)

    assert (target_dir / "source.txt").read_text(encoding="utf-8") == "payload"
