from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConnectionType(str, Enum):
    LOCAL = "local"
    SSH = "ssh"


class SessionStatus(str, Enum):
    RUNNING = "running"
    CLOSED = "closed"


class ThemeMode(str, Enum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


DEFAULT_TERMINAL_FONT_FAMILY = "Cascadia Code"


def resolve_terminal_font_family(family: str | None) -> str:
    """解析终端字体设置, 空值表示使用默认字体."""
    return family or DEFAULT_TERMINAL_FONT_FAMILY


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
    auth_method: str | None = None
    password: str | None = None
    private_key_path: str | None = None
    private_key_passphrase: str | None = None
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
class CommandRecord:
    """已记录的单行命令历史."""

    id: int
    command_text: str
    connection_type: ConnectionType
    session_id: int | None = None
    connection_id: int | None = None
    host: str | None = None
    cwd: str | None = None
    started_at: str | None = None
    exit_code: int | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class FavoriteCommand:
    """收藏的命令文本."""

    id: int
    command_text: str
    created_at: str | None = None
    last_used_at: str | None = None


@dataclass(frozen=True)
class AppSettings:
    """应用级持久化设置."""

    terminal_cols: int = 100
    terminal_rows: int = 32
    terminal_font_family: str = ""
    terminal_font_size: int = 12
    default_local_shell: str = ""
    restore_tabs_on_startup: bool = True
    theme_mode: ThemeMode = ThemeMode.SYSTEM


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
