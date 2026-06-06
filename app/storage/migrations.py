from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """执行可重复的 SQLite schema 初始化."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            connection_type TEXT NOT NULL,
            host TEXT,
            port INTEGER,
            username TEXT,
            private_key_path TEXT,
            default_directory TEXT,
            auth_method TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_used_at TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_connections_local
            ON connections(connection_type, name)
            WHERE connection_type = 'local';

        CREATE UNIQUE INDEX IF NOT EXISTS idx_connections_ssh
            ON connections(connection_type, host, port, username)
            WHERE connection_type = 'ssh';

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            connection_type TEXT NOT NULL,
            host TEXT,
            cwd TEXT,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ended_at TEXT,
            exit_code INTEGER,
            FOREIGN KEY(connection_id) REFERENCES connections(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_started_at
            ON sessions(started_at DESC);

        CREATE INDEX IF NOT EXISTS idx_sessions_connection_id
            ON sessions(connection_id);
        """
    )
    connection.commit()
