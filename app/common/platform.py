from __future__ import annotations

import os
import platform
import shutil


def current_platform() -> str:
    """返回标准化平台名称."""
    return platform.system().lower()


def default_shell_command() -> list[str]:
    """根据当前系统选择默认本地 shell."""
    system = current_platform()
    if system == "windows":
        for shell in ("pwsh.exe", "powershell.exe"):
            shell_path = shutil.which(shell)
            if shell_path:
                return [shell_path]
        comspec = os.environ.get("ComSpec")
        if comspec:
            return [comspec]
        return ["cmd.exe"]
    shell = os.environ.get("SHELL")
    return [shell] if shell else ["/bin/sh"]
