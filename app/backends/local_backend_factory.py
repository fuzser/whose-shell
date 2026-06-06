from __future__ import annotations

from app.backends.local_posix_backend import LocalPosixBackend
from app.backends.local_windows_backend import LocalWindowsBackend
from app.common.models import TerminalSessionConfig
from app.common.platform import current_platform


def create_local_backend(config: TerminalSessionConfig):
    """根据平台创建本地终端后端."""
    if current_platform() == "windows":
        return LocalWindowsBackend(config)
    return LocalPosixBackend(config)

