from __future__ import annotations

import sqlite3

from app.common.models import ConnectionRecord, ConnectionType, SessionRecord, SessionStatus, SshConnectionConfig


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
        name = f"{config.username}@{config.host}:{config.port}"
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
        name = f"{config.username}@{config.host}:{config.port}"
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
        if config.private_key_path:
            return "private_key"
        if config.password:
            return "password"
        return "none"

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
        return self.get_session(session_id)

    def list_recent_sessions(self, limit: int = 50) -> list[SessionRecord]:
        rows = self._connection.execute(
            """
            SELECT * FROM sessions
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._row_to_session(row) for row in rows]

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
