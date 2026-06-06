from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from app.storage.migrations import migrate


def default_database_path() -> Path:
    """返回应用默认 SQLite 数据库路径."""
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    if not base:
        base = str(Path.home() / ".whose-shell")
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path / "whose-shell.sqlite3"


class Database:
    """管理 SQLite 连接和初始化."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_database_path()
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        migrate(self._connection)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def close(self) -> None:
        self._connection.close()
