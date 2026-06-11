from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path


AUTO_LOCAL_SHELL = "auto"


@dataclass(frozen=True)
class LocalShellOption:
    """可用于本地终端的 shell 选项."""

    value: str
    label: str
    command: list[str]


@dataclass(frozen=True)
class LocalShellResolution:
    """本地 shell 偏好的解析结果."""

    command: list[str]
    resolved_shell: str
    used_fallback: bool = False
    fallback_message: str | None = None


def current_platform() -> str:
    """返回标准化平台名称."""
    return platform.system().lower()


def default_shell_command() -> list[str]:
    """根据当前系统选择默认本地 shell."""
    return resolve_local_shell_preference(AUTO_LOCAL_SHELL).command


def available_local_shell_options() -> list[LocalShellOption]:
    """列出当前系统可用的本地 shell 选项."""
    system = current_platform()
    if system == "windows":
        options: list[LocalShellOption] = []
        for shell in ("pwsh.exe", "powershell.exe"):
            option = _windows_shell_option(shell)
            if option is not None:
                options.append(option)
        comspec = os.environ.get("ComSpec")
        if comspec and _path_is_executable(comspec):
            options.append(LocalShellOption(value="cmd.exe", label="Command Prompt", command=[comspec]))
        else:
            option = _windows_shell_option("cmd.exe")
            if option is not None:
                options.append(option)
        return _unique_shell_options(options)

    options = []
    shell = os.environ.get("SHELL")
    if shell and _path_is_executable(shell):
        options.append(LocalShellOption(value=shell, label=Path(shell).name, command=[shell]))
    if _path_is_executable("/bin/sh"):
        options.append(LocalShellOption(value="/bin/sh", label="/bin/sh", command=["/bin/sh"]))
    return _unique_shell_options(options)


def resolve_local_shell_preference(preference: str | None) -> LocalShellResolution:
    """解析本地 shell 设置, 无效时回退到自动检测."""
    normalized = (preference or AUTO_LOCAL_SHELL).strip() or AUTO_LOCAL_SHELL
    options = available_local_shell_options()
    if normalized != AUTO_LOCAL_SHELL:
        for option in options:
            if normalized in {option.value, option.command[0]}:
                return LocalShellResolution(command=option.command, resolved_shell=option.value)

    if options:
        fallback_message = None
        used_fallback = False
        if normalized != AUTO_LOCAL_SHELL:
            used_fallback = True
            fallback_message = f"Saved shell '{normalized}' is unavailable. Falling back to auto."
        return LocalShellResolution(
            command=options[0].command,
            resolved_shell=options[0].value,
            used_fallback=used_fallback,
            fallback_message=fallback_message,
        )

    fallback = ["cmd.exe"] if current_platform() == "windows" else ["/bin/sh"]
    return LocalShellResolution(
        command=fallback,
        resolved_shell=fallback[0],
        used_fallback=normalized != AUTO_LOCAL_SHELL,
        fallback_message="No preferred shell was available. Falling back to platform default.",
    )


def _windows_shell_option(shell: str) -> LocalShellOption | None:
    shell_path = shutil.which(shell)
    if not shell_path:
        return None
    labels = {
        "pwsh.exe": "PowerShell 7",
        "powershell.exe": "Windows PowerShell",
        "cmd.exe": "Command Prompt",
    }
    return LocalShellOption(value=shell, label=labels.get(shell, shell), command=[shell_path])


def _path_is_executable(path: str) -> bool:
    if Path(path).is_file():
        return True
    return shutil.which(path) is not None


def _unique_shell_options(options: list[LocalShellOption]) -> list[LocalShellOption]:
    seen: set[str] = set()
    unique: list[LocalShellOption] = []
    for option in options:
        key = option.value.lower() if current_platform() == "windows" else option.value
        if key in seen:
            continue
        seen.add(key)
        unique.append(option)
    return unique
