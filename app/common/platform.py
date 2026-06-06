from __future__ import annotations

import os
import platform


def current_platform() -> str:
    """返回标准化平台名称."""
    return platform.system().lower()


def default_shell_command() -> list[str]:
    """根据当前系统选择默认本地 shell."""
    system = current_platform()
    if system == "windows":
        pwsh = os.environ.get("ComSpec")
        if pwsh:
            return [pwsh]
        return ["cmd.exe"]
    shell = os.environ.get("SHELL")
    return [shell] if shell else ["/bin/sh"]

