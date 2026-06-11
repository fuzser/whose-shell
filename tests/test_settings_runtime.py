from __future__ import annotations

import sqlite3

from app.common.models import AppSettings, ConnectionType, DEFAULT_TERMINAL_FONT_FAMILY, resolve_terminal_font_family
from app.common.platform import (
    AUTO_LOCAL_SHELL,
    LocalShellResolution,
    available_local_shell_options,
    resolve_local_shell_preference,
)
from app.common.signals import EventBus
from app.core import session_manager as session_manager_module
from app.core.session_manager import SessionManager
from app.storage.migrations import migrate
from app.storage.repositories import ConnectionRepository, SessionRepository, SettingsRepository
from app.storage.secrets import SecretStore


class _FakeBackend:
    pass


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    return connection


def _session_manager(connection: sqlite3.Connection) -> SessionManager:
    return SessionManager(
        EventBus(),
        ConnectionRepository(connection),
        SessionRepository(connection),
        SettingsRepository(connection),
        SecretStore(),
    )


def test_local_shell_auto_prefers_windows_shell_order(monkeypatch) -> None:
    monkeypatch.setattr("app.common.platform.current_platform", lambda: "windows")
    monkeypatch.setattr("app.common.platform.shutil.which", lambda shell: f"C:/bin/{shell}" if shell != "cmd.exe" else None)
    monkeypatch.setenv("ComSpec", "C:/Windows/System32/cmd.exe")
    monkeypatch.setattr("app.common.platform.Path.is_file", lambda self: str(self).endswith(".exe"))

    options = available_local_shell_options()
    resolution = resolve_local_shell_preference(AUTO_LOCAL_SHELL)

    assert [option.value for option in options] == ["pwsh.exe", "powershell.exe", "cmd.exe"]
    assert resolution.resolved_shell == "pwsh.exe"
    assert resolution.command == ["C:/bin/pwsh.exe"]


def test_empty_terminal_font_family_resolves_to_cascadia_code_default() -> None:
    assert DEFAULT_TERMINAL_FONT_FAMILY == "Cascadia Code"
    assert resolve_terminal_font_family("") == "Cascadia Code"
    assert resolve_terminal_font_family(None) == "Cascadia Code"


def test_session_manager_applies_settings_to_new_local_terminal(monkeypatch) -> None:
    connection = _connection()
    settings = SettingsRepository(connection)
    settings.save_settings(
        AppSettings(
            terminal_cols=132,
            terminal_rows=43,
            default_local_shell="pwsh.exe",
        )
    )
    captured = {}

    def fake_backend(config):
        captured["config"] = config
        return _FakeBackend()

    monkeypatch.setattr(session_manager_module, "create_local_backend", fake_backend)
    monkeypatch.setattr(
        session_manager_module,
        "resolve_local_shell_preference",
        lambda preference: LocalShellResolution(command=["C:/bin/pwsh.exe"], resolved_shell="pwsh.exe"),
    )

    managed = _session_manager(connection).create_local_terminal()

    assert isinstance(managed.backend, _FakeBackend)
    assert captured["config"].connection_type == ConnectionType.LOCAL
    assert captured["config"].command == ["C:/bin/pwsh.exe"]
    assert captured["config"].cols == 132
    assert captured["config"].rows == 43


def test_session_manager_resets_unavailable_manual_shell_to_auto(monkeypatch) -> None:
    connection = _connection()
    settings = SettingsRepository(connection)
    settings.save_settings(AppSettings(default_local_shell="missing-shell"))

    monkeypatch.setattr(session_manager_module, "create_local_backend", lambda config: _FakeBackend())
    monkeypatch.setattr(
        session_manager_module,
        "resolve_local_shell_preference",
        lambda preference: LocalShellResolution(
            command=["/bin/sh"],
            resolved_shell="/bin/sh",
            used_fallback=True,
            fallback_message="missing shell",
        ),
    )

    _session_manager(connection).create_local_terminal()

    assert settings.get_settings().default_local_shell == AUTO_LOCAL_SHELL
