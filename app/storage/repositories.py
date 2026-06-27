from __future__ import annotations

import sqlite3

from app.common.models import (
    AppSettings,
    CommandRecord,
    ConnectionRecord,
    ConnectionType,
    ConflictPolicy,
    FavoriteCommand,
    FileTransferRecord,
    SavedTerminalTab,
    SessionRecord,
    SessionStatus,
    SshConnectionConfig,
    ThemeMode,
    TransferDirection,
    TransferStatus,
)


class ConnectionRepository:
    """读写连接元数据."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def ensure_local_connection(self) -> ConnectionRecord:
        row = self._connection.execute(
            "SELECT * FROM connections WHERE connection_type = ? AND name = ?",
            (ConnectionType.LOCAL.value, "Local Shell"),
        ).fetchone()
        if row is None:
            cursor = self._connection.execute(
                """
                INSERT INTO connections(name, connection_type, last_used_at)
                VALUES(?, ?, CURRENT_TIMESTAMP)
                """,
                ("Local Shell", ConnectionType.LOCAL.value),
            )
            self._connection.commit()
            return self.get_connection(cursor.lastrowid)

        self._touch(row["id"])
        return self.get_connection(row["id"])

    def save_ssh_connection(self, config: SshConnectionConfig) -> ConnectionRecord:
        auth_method = self._auth_method(config)
        name = self._connection_name(config)
        existing = self._connection.execute(
            """
            SELECT * FROM connections
            WHERE connection_type = ? AND host = ? AND port = ? AND username = ?
            """,
            (ConnectionType.SSH.value, config.host, config.port, config.username),
        ).fetchone()
        if existing is None:
            cursor = self._connection.execute(
                """
                INSERT INTO connections(
                    name, connection_type, host, port, username, private_key_path,
                    default_directory, auth_method, last_used_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    name,
                    ConnectionType.SSH.value,
                    config.host,
                    config.port,
                    config.username,
                    config.private_key_path,
                    config.default_directory,
                    auth_method,
                ),
            )
            self._connection.commit()
            return self.get_connection(cursor.lastrowid)

        self._connection.execute(
            """
            UPDATE connections
            SET name = ?,
                private_key_path = ?,
                default_directory = ?,
                auth_method = ?,
                updated_at = CURRENT_TIMESTAMP,
                last_used_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                name,
                config.private_key_path,
                config.default_directory,
                auth_method,
                existing["id"],
            ),
        )
        self._connection.commit()
        return self.get_connection(existing["id"])

    def update_ssh_connection(self, connection_id: int, config: SshConnectionConfig) -> ConnectionRecord:
        """更新已保存 SSH 连接配置."""
        auth_method = self._auth_method(config)
        name = self._connection_name(config)
        self._connection.execute(
            """
            UPDATE connections
            SET name = ?,
                host = ?,
                port = ?,
                username = ?,
                private_key_path = ?,
                default_directory = ?,
                auth_method = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND connection_type = ?
            """,
            (
                name,
                config.host,
                config.port,
                config.username,
                config.private_key_path,
                config.default_directory,
                auth_method,
                connection_id,
                ConnectionType.SSH.value,
            ),
        )
        self._connection.commit()
        return self.get_connection(connection_id)

    def delete_ssh_connection(self, connection_id: int) -> None:
        """删除 SSH 连接和关联 session 记录."""
        self._connection.execute(
            "DELETE FROM connections WHERE id = ? AND connection_type = ?",
            (connection_id, ConnectionType.SSH.value),
        )
        self._connection.commit()

    def list_connections(self) -> list[ConnectionRecord]:
        rows = self._connection.execute(
            """
            SELECT * FROM connections
            ORDER BY
                CASE WHEN last_used_at IS NULL THEN 1 ELSE 0 END,
                last_used_at DESC,
                name ASC
            """
        ).fetchall()
        return [self._row_to_connection(row) for row in rows]

    def get_connection(self, connection_id: int) -> ConnectionRecord:
        row = self._connection.execute("SELECT * FROM connections WHERE id = ?", (connection_id,)).fetchone()
        if row is None:
            raise ValueError(f"Connection not found: {connection_id}")
        return self._row_to_connection(row)

    def _touch(self, connection_id: int) -> None:
        self._connection.execute(
            "UPDATE connections SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?",
            (connection_id,),
        )
        self._connection.commit()

    def _auth_method(self, config: SshConnectionConfig) -> str:
        if config.auth_method in {"password", "private_key", "none"}:
            return config.auth_method
        if config.private_key_path:
            return "private_key"
        if config.password:
            return "password"
        return "none"

    def _connection_name(self, config: SshConnectionConfig) -> str:
        return config.name or f"{config.username}@{config.host}:{config.port}"

    def _row_to_connection(self, row: sqlite3.Row) -> ConnectionRecord:
        return ConnectionRecord(
            id=row["id"],
            name=row["name"],
            connection_type=ConnectionType(row["connection_type"]),
            host=row["host"],
            port=row["port"],
            username=row["username"],
            private_key_path=row["private_key_path"],
            default_directory=row["default_directory"],
            auth_method=row["auth_method"],
            last_used_at=row["last_used_at"],
        )


class SessionRepository:
    """读写终端会话记录."""

    RECENT_SESSION_LIMIT = 50

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_session(
        self,
        connection: ConnectionRecord,
        title: str,
        cwd: str | None = None,
    ) -> SessionRecord:
        cursor = self._connection.execute(
            """
            INSERT INTO sessions(connection_id, title, connection_type, host, cwd, status)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                connection.id,
                title,
                connection.connection_type.value,
                connection.host,
                cwd,
                SessionStatus.RUNNING.value,
            ),
        )
        self._connection.commit()
        self._trim_recent_sessions()
        return self.get_session(cursor.lastrowid)

    def close_session(self, session_id: int, exit_code: int | None = None) -> SessionRecord:
        self._connection.execute(
            """
            UPDATE sessions
            SET status = ?, ended_at = CURRENT_TIMESTAMP, exit_code = ?
            WHERE id = ? AND status != ?
            """,
            (SessionStatus.CLOSED.value, exit_code, session_id, SessionStatus.CLOSED.value),
        )
        self._connection.commit()
        self._trim_recent_sessions()
        return self.get_session(session_id)

    def reopen_session(self, session_id: int) -> SessionRecord:
        """将同一个标签页 session 标记为重新连接中."""
        self._connection.execute(
            """
            UPDATE sessions
            SET status = ?, ended_at = NULL, exit_code = NULL
            WHERE id = ?
            """,
            (SessionStatus.RUNNING.value, session_id),
        )
        self._connection.commit()
        return self.get_session(session_id)

    def list_recent_sessions(self, limit: int = RECENT_SESSION_LIMIT) -> list[SessionRecord]:
        rows = self._connection.execute(
            """
            SELECT * FROM sessions
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def save_active_tabs(self, tabs: list[SavedTerminalTab]) -> None:
        """保存应用退出时仍打开的终端标签页."""
        self._connection.execute("DELETE FROM active_terminal_tabs")
        self._connection.executemany(
            """
            INSERT INTO active_terminal_tabs(connection_id, title, tab_order, is_current, content)
            VALUES(?, ?, ?, ?, ?)
            """,
            [
                (
                    tab.connection_id,
                    tab.title,
                    tab.tab_order,
                    1 if tab.is_current else 0,
                    tab.content,
                )
                for tab in tabs
            ],
        )
        self._connection.commit()

    def list_active_tabs(self) -> list[SavedTerminalTab]:
        rows = self._connection.execute(
            """
            SELECT * FROM active_terminal_tabs
            ORDER BY tab_order ASC, id ASC
            """
        ).fetchall()
        return [
            SavedTerminalTab(
                connection_id=row["connection_id"],
                title=row["title"],
                tab_order=row["tab_order"],
                is_current=bool(row["is_current"]),
                content=row["content"],
            )
            for row in rows
        ]

    def _trim_recent_sessions(self) -> None:
        """只保留最近 session 历史, 但不删除仍在运行的 session."""
        self._connection.execute(
            """
            DELETE FROM sessions
            WHERE status = ?
              AND id NOT IN (
                  SELECT id
                  FROM sessions
                  ORDER BY started_at DESC, id DESC
                  LIMIT ?
              )
            """,
            (SessionStatus.CLOSED.value, self.RECENT_SESSION_LIMIT),
        )
        self._connection.commit()

    def get_session(self, session_id: int) -> SessionRecord:
        row = self._connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise ValueError(f"Session not found: {session_id}")
        return self._row_to_session(row)

    def _row_to_session(self, row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            id=row["id"],
            connection_id=row["connection_id"],
            title=row["title"],
            connection_type=ConnectionType(row["connection_type"]),
            status=SessionStatus(row["status"]),
            host=row["host"],
            cwd=row["cwd"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            exit_code=row["exit_code"],
        )


class CommandRepository:
    """读写命令历史记录."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_command(
        self,
        command_text: str,
        connection_type: ConnectionType,
        session_id: int | None = None,
        connection_id: int | None = None,
        host: str | None = None,
        cwd: str | None = None,
        started_at: str | None = None,
        exit_code: int | None = None,
    ) -> CommandRecord:
        """保存一条已提交的单行命令."""
        normalized_command = command_text.strip()
        if not normalized_command:
            raise ValueError("Command text cannot be empty.")
        cursor = self._connection.execute(
            """
            INSERT INTO commands(
                command_text, session_id, connection_id, connection_type,
                host, cwd, started_at, exit_code
            )
            VALUES(?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)
            """,
            (
                normalized_command,
                session_id,
                connection_id,
                connection_type.value,
                host,
                cwd,
                started_at,
                exit_code,
            ),
        )
        self._connection.commit()
        return self.get_command(cursor.lastrowid)

    def get_command(self, command_id: int) -> CommandRecord:
        row = self._connection.execute("SELECT * FROM commands WHERE id = ?", (command_id,)).fetchone()
        if row is None:
            raise ValueError(f"Command not found: {command_id}")
        return self._row_to_command(row)

    def list_commands(
        self,
        limit: int = 100,
        search_text: str | None = None,
        connection_id: int | None = None,
        host: str | None = None,
        connection_type: ConnectionType | None = None,
    ) -> list[CommandRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if search_text:
            clauses.append("command_text LIKE ?")
            params.append(f"%{search_text}%")
        if connection_id is not None:
            clauses.append("connection_id = ?")
            params.append(connection_id)
        if host:
            clauses.append("host = ?")
            params.append(host)
        if connection_type is not None:
            clauses.append("connection_type = ?")
            params.append(connection_type.value)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = self._connection.execute(
            f"""
            SELECT * FROM commands
            {where_sql}
            ORDER BY started_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self._row_to_command(row) for row in rows]

    def update_exit_code(self, command_id: int, exit_code: int | None) -> CommandRecord:
        self._connection.execute(
            "UPDATE commands SET exit_code = ? WHERE id = ?",
            (exit_code, command_id),
        )
        self._connection.commit()
        return self.get_command(command_id)

    def _row_to_command(self, row: sqlite3.Row) -> CommandRecord:
        return CommandRecord(
            id=row["id"],
            command_text=row["command_text"],
            session_id=row["session_id"],
            connection_id=row["connection_id"],
            connection_type=ConnectionType(row["connection_type"]),
            host=row["host"],
            cwd=row["cwd"],
            started_at=row["started_at"],
            exit_code=row["exit_code"],
            created_at=row["created_at"],
        )


class FavoriteRepository:
    """读写收藏命令."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add_favorite(self, command_text: str) -> FavoriteCommand:
        normalized_command = command_text.strip()
        if not normalized_command:
            raise ValueError("Command text cannot be empty.")
        self._connection.execute(
            """
            INSERT INTO favorites(command_text, last_used_at)
            VALUES(?, CURRENT_TIMESTAMP)
            ON CONFLICT(command_text) DO UPDATE SET last_used_at = CURRENT_TIMESTAMP
            """,
            (normalized_command,),
        )
        self._connection.commit()
        return self.get_favorite(normalized_command)

    def remove_favorite(self, command_text: str) -> None:
        self._connection.execute(
            "DELETE FROM favorites WHERE command_text = ?",
            (command_text.strip(),),
        )
        self._connection.commit()

    def get_favorite(self, command_text: str) -> FavoriteCommand:
        row = self._connection.execute(
            "SELECT * FROM favorites WHERE command_text = ?",
            (command_text.strip(),),
        ).fetchone()
        if row is None:
            raise ValueError(f"Favorite command not found: {command_text}")
        return self._row_to_favorite(row)

    def is_favorite(self, command_text: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM favorites WHERE command_text = ?",
            (command_text.strip(),),
        ).fetchone()
        return row is not None

    def list_favorites(self, limit: int = 100) -> list[FavoriteCommand]:
        rows = self._connection.execute(
            """
            SELECT * FROM favorites
            ORDER BY
                CASE WHEN last_used_at IS NULL THEN 1 ELSE 0 END,
                last_used_at DESC,
                created_at DESC,
                id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._row_to_favorite(row) for row in rows]

    def _row_to_favorite(self, row: sqlite3.Row) -> FavoriteCommand:
        return FavoriteCommand(
            id=row["id"],
            command_text=row["command_text"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
        )


class FileTransferRepository:
    """读写文件传输队列元数据."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_transfer(
        self,
        direction: TransferDirection,
        source_path: str,
        target_path: str,
        conflict_policy: ConflictPolicy = ConflictPolicy.SKIP,
        connection_id: int | None = None,
        host: str | None = None,
        total_bytes: int | None = None,
    ) -> FileTransferRecord:
        """创建一条排队中的传输记录."""
        normalized_source = source_path.strip()
        normalized_target = target_path.strip()
        if not normalized_source:
            raise ValueError("Source path cannot be empty.")
        if not normalized_target:
            raise ValueError("Target path cannot be empty.")
        if total_bytes is not None and total_bytes < 0:
            raise ValueError("Total bytes cannot be negative.")

        cursor = self._connection.execute(
            """
            INSERT INTO file_transfers(
                direction, status, source_path, target_path, connection_id, host,
                total_bytes, conflict_policy
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                direction.value,
                TransferStatus.QUEUED.value,
                normalized_source,
                normalized_target,
                connection_id,
                host,
                total_bytes,
                conflict_policy.value,
            ),
        )
        self._connection.commit()
        return self.get_transfer(cursor.lastrowid)

    def get_transfer(self, transfer_id: int) -> FileTransferRecord:
        row = self._connection.execute(
            "SELECT * FROM file_transfers WHERE id = ?",
            (transfer_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"File transfer not found: {transfer_id}")
        return self._row_to_transfer(row)

    def list_transfers(
        self,
        limit: int = 100,
        status: TransferStatus | None = None,
        connection_id: int | None = None,
    ) -> list[FileTransferRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if connection_id is not None:
            clauses.append("connection_id = ?")
            params.append(connection_id)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = self._connection.execute(
            f"""
            SELECT * FROM file_transfers
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self._row_to_transfer(row) for row in rows]

    def mark_running(self, transfer_id: int) -> FileTransferRecord:
        self._connection.execute(
            """
            UPDATE file_transfers
            SET status = ?,
                started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                error_message = NULL
            WHERE id = ?
            """,
            (TransferStatus.RUNNING.value, transfer_id),
        )
        self._connection.commit()
        return self.get_transfer(transfer_id)

    def update_progress(
        self,
        transfer_id: int,
        bytes_transferred: int,
        total_bytes: int | None = None,
    ) -> FileTransferRecord:
        if bytes_transferred < 0:
            raise ValueError("Bytes transferred cannot be negative.")
        if total_bytes is not None and total_bytes < 0:
            raise ValueError("Total bytes cannot be negative.")
        self._connection.execute(
            """
            UPDATE file_transfers
            SET bytes_transferred = ?,
                total_bytes = COALESCE(?, total_bytes)
            WHERE id = ?
            """,
            (bytes_transferred, total_bytes, transfer_id),
        )
        self._connection.commit()
        return self.get_transfer(transfer_id)

    def update_target_path(self, transfer_id: int, target_path: str) -> FileTransferRecord:
        """更新冲突重命名后的最终目标路径."""
        normalized_target = target_path.strip()
        if not normalized_target:
            raise ValueError("Target path cannot be empty.")
        self._connection.execute(
            """
            UPDATE file_transfers
            SET target_path = ?
            WHERE id = ?
            """,
            (normalized_target, transfer_id),
        )
        self._connection.commit()
        return self.get_transfer(transfer_id)

    def complete_transfer(
        self,
        transfer_id: int,
        bytes_transferred: int | None = None,
    ) -> FileTransferRecord:
        current = self.get_transfer(transfer_id)
        final_bytes = current.bytes_transferred if bytes_transferred is None else bytes_transferred
        if final_bytes < 0:
            raise ValueError("Bytes transferred cannot be negative.")
        self._connection.execute(
            """
            UPDATE file_transfers
            SET status = ?,
                bytes_transferred = ?,
                error_message = NULL,
                finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (TransferStatus.COMPLETED.value, final_bytes, transfer_id),
        )
        self._connection.commit()
        return self.get_transfer(transfer_id)

    def fail_transfer(self, transfer_id: int, error_message: str) -> FileTransferRecord:
        message = error_message.strip()
        if not message:
            raise ValueError("Error message cannot be empty.")
        self._connection.execute(
            """
            UPDATE file_transfers
            SET status = ?,
                error_message = ?,
                finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (TransferStatus.FAILED.value, message, transfer_id),
        )
        self._connection.commit()
        return self.get_transfer(transfer_id)

    def cancel_transfer(self, transfer_id: int) -> FileTransferRecord:
        self._connection.execute(
            """
            UPDATE file_transfers
            SET status = ?,
                finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (TransferStatus.CANCELED.value, transfer_id),
        )
        self._connection.commit()
        return self.get_transfer(transfer_id)

    def _row_to_transfer(self, row: sqlite3.Row) -> FileTransferRecord:
        return FileTransferRecord(
            id=row["id"],
            direction=TransferDirection(row["direction"]),
            status=TransferStatus(row["status"]),
            source_path=row["source_path"],
            target_path=row["target_path"],
            connection_id=row["connection_id"],
            host=row["host"],
            bytes_transferred=row["bytes_transferred"],
            total_bytes=row["total_bytes"],
            conflict_policy=ConflictPolicy(row["conflict_policy"]),
            error_message=row["error_message"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )


class SettingsRepository:
    """读写应用设置."""

    _DEFAULTS = AppSettings()

    _KEYS = {
        "terminal_cols": "terminal.default_cols",
        "terminal_rows": "terminal.default_rows",
        "terminal_font_family": "terminal.font_family",
        "terminal_font_size": "terminal.font_size",
        "default_local_shell": "terminal.default_local_shell",
        "restore_tabs_on_startup": "startup.restore_tabs",
        "theme_mode": "appearance.theme_mode",
    }

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get_settings(self) -> AppSettings:
        values = self._read_values()
        return AppSettings(
            terminal_cols=self._read_int(values, "terminal_cols", self._DEFAULTS.terminal_cols),
            terminal_rows=self._read_int(values, "terminal_rows", self._DEFAULTS.terminal_rows),
            terminal_font_family=values.get(
                self._KEYS["terminal_font_family"],
                self._DEFAULTS.terminal_font_family,
            ),
            terminal_font_size=self._read_int(
                values,
                "terminal_font_size",
                self._DEFAULTS.terminal_font_size,
            ),
            default_local_shell=values.get(
                self._KEYS["default_local_shell"],
                self._DEFAULTS.default_local_shell,
            ),
            restore_tabs_on_startup=self._read_bool(
                values,
                "restore_tabs_on_startup",
                self._DEFAULTS.restore_tabs_on_startup,
            ),
            theme_mode=self._read_theme_mode(values),
        )

    def save_settings(self, settings: AppSettings) -> AppSettings:
        pairs = {
            self._KEYS["terminal_cols"]: str(settings.terminal_cols),
            self._KEYS["terminal_rows"]: str(settings.terminal_rows),
            self._KEYS["terminal_font_family"]: settings.terminal_font_family,
            self._KEYS["terminal_font_size"]: str(settings.terminal_font_size),
            self._KEYS["default_local_shell"]: settings.default_local_shell,
            self._KEYS["restore_tabs_on_startup"]: "true" if settings.restore_tabs_on_startup else "false",
            self._KEYS["theme_mode"]: settings.theme_mode.value,
        }
        self._connection.executemany(
            """
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            pairs.items(),
        )
        self._connection.commit()
        return self.get_settings()

    def set_value(self, key: str, value: str) -> None:
        self._connection.execute(
            """
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        self._connection.commit()

    def get_value(self, key: str, default: str | None = None) -> str | None:
        row = self._connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return row["value"]

    def _read_values(self) -> dict[str, str]:
        rows = self._connection.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def _read_int(self, values: dict[str, str], field: str, default: int) -> int:
        value = values.get(self._KEYS[field])
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def _read_bool(self, values: dict[str, str], field: str, default: bool) -> bool:
        value = values.get(self._KEYS[field])
        if value is None:
            return default
        return value.lower() in {"1", "true", "yes", "on"}

    def _read_theme_mode(self, values: dict[str, str]) -> ThemeMode:
        value = values.get(self._KEYS["theme_mode"], self._DEFAULTS.theme_mode.value)
        try:
            return ThemeMode(value)
        except ValueError:
            return self._DEFAULTS.theme_mode
