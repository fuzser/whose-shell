from __future__ import annotations

import importlib.util
from pathlib import Path


_BUILD_SCRIPT = Path(__file__).resolve().parents[1] / "packaging" / "pyinstaller_build.py"
_SPEC = importlib.util.spec_from_file_location("whose_shell_pyinstaller_build", _BUILD_SCRIPT)
assert _SPEC is not None
assert _SPEC.loader is not None
pyinstaller_build = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pyinstaller_build)


def test_windows_build_collects_winpty_binaries(monkeypatch) -> None:
    commands: list[list[str]] = []
    helper_paths = [
        Path("C:/fake/winpty/OpenConsole.exe"),
        Path("C:/fake/winpty/winpty-agent.exe"),
    ]

    monkeypatch.setattr(pyinstaller_build, "_run", commands.append)
    monkeypatch.setattr(pyinstaller_build, "_winpty_helper_binary_paths", lambda: helper_paths)

    pyinstaller_build._run_pyinstaller(build_name="whose-shell", target="win-x64")

    command = commands[0]
    assert command.count("--add-binary") == 2
    command_text = " ".join(str(part) for part in command)
    assert "OpenConsole.exe" in command_text
    assert "winpty-agent.exe" in command_text
    assert "winpty" in command_text


def test_linux_build_does_not_collect_winpty_binaries(monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(pyinstaller_build, "_run", commands.append)

    pyinstaller_build._run_pyinstaller(build_name="whose-shell", target="linux-amd64")

    command = commands[0]
    assert "winpty" not in command
