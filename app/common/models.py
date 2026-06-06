from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConnectionType(str, Enum):
    LOCAL = "local"
    SSH = "ssh"


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
    password: str | None = None
    private_key_path: str | None = None
    default_directory: str | None = None
    cols: int = 100
    rows: int = 32
    accept_unknown_host: bool = True
