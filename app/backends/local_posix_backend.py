from __future__ import annotations

from app.backends.qprocess_backend import QProcessTerminalBackend
from app.common.models import TerminalSessionConfig


class LocalPosixBackend(QProcessTerminalBackend):
    """POSIX 本地 shell 后端.

    TODO: 用 pty/select 或 asyncio PTY worker 替换当前 QProcess 基线.
    """

    def __init__(self, config: TerminalSessionConfig) -> None:
        super().__init__(config)

