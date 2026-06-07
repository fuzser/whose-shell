from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConnectionType(str, Enum):
    LOCAL = "local"
    SSH = "ssh"


class SessionStatus(str, Enum):
    RUNNING = "running"
    CLOSED = "closed"


@dataclass(frozen=True)
class TerminalSessionConfig:
    """终端会话配置."""

    name: str
    connection_type: ConnectionType
    command: list[str] | None = None
    cwd: str | None = None
    cols: int = 100
    rows: int = 32


@dataclass(frozen=True)
class SshConnectionConfig:
    """SSH 连接配置.

    密码只用于当前连接, 不能写入普通文件或 SQLite.
    """

    host: str
    port: int
    username: str
    name: str | None = None
    password: str | None = None
    private_key_path: str | None = None
    default_directory: str | None = None
    cols: int = 100
    rows: int = 32
    accept_unknown_host: bool = True


@dataclass(frozen=True)
class ConnectionRecord:
    """已保存连接元数据."""

    id: int
    name: str
    connection_type: ConnectionType
    host: str | None = None
    port: int | None = None
    username: str | None = None
    private_key_path: str | None = None
    default_directory: str | None = None
    auth_method: str | None = None
    last_used_at: str | None = None


@dataclass(frozen=True)
class SessionRecord:
    """终端会话运行记录."""

    id: int
    connection_id: int
    title: str
    connection_type: ConnectionType
    status: SessionStatus
    host: str | None = None
    cwd: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    exit_code: int | None = None


@dataclass(frozen=True)
class ManagedTerminalSession:
    """后端和会话元数据的组合结果."""

    backend: object
    session: SessionRecord


@dataclass(frozen=True)
class SavedTerminalTab:
    """退出应用时保存的终端标签页快照."""

    connection_id: int
    title: str
    tab_order: int
    is_current: bool
    content: str
