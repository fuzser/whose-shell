from __future__ import annotations

from app.backends.qprocess_backend import QProcessTerminalBackend
from app.common.models import TerminalSessionConfig


class LocalWindowsBackend(QProcessTerminalBackend):
    """Windows 本地 shell 后端.

    TODO: 用 pywinpty/ConPTY 替换当前 QProcess 基线, 以支持真正的 PTY 行为.
    """

    def __init__(self, config: TerminalSessionConfig) -> None:
        super().__init__(config)

