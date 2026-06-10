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

        CREATE TABLE IF NOT EXISTS active_terminal_tabs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            tab_order INTEGER NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 0,
            content TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(connection_id) REFERENCES connections(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_active_terminal_tabs_order
            ON active_terminal_tabs(tab_order);

        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_text TEXT NOT NULL,
            session_id INTEGER,
            connection_id INTEGER,
            connection_type TEXT NOT NULL,
            host TEXT,
            cwd TEXT,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            exit_code INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE SET NULL,
            FOREIGN KEY(connection_id) REFERENCES connections(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_commands_started_at
            ON commands(started_at DESC, id DESC);

        CREATE INDEX IF NOT EXISTS idx_commands_connection_id
            ON commands(connection_id);

        CREATE INDEX IF NOT EXISTS idx_commands_host
            ON commands(host);

        CREATE INDEX IF NOT EXISTS idx_commands_command_text
            ON commands(command_text);

        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_text TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_used_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_favorites_last_used_at
            ON favorites(last_used_at DESC, created_at DESC);

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    connection.commit()
