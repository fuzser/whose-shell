from __future__ import annotations

from app.backends import local_backend_factory
from app.backends.local_posix_backend import LocalPosixBackend
from app.backends.local_windows_backend import LocalWindowsBackend
from app.common.models import ConnectionType, TerminalSessionConfig


def _config() -> TerminalSessionConfig:
    return TerminalSessionConfig(name="Local Shell", connection_type=ConnectionType.LOCAL)


def test_create_local_backend_uses_windows_pty_backend(monkeypatch) -> None:
    monkeypatch.setattr(local_backend_factory, "current_platform", lambda: "windows")

    backend = local_backend_factory.create_local_backend(_config())

    assert isinstance(backend, LocalWindowsBackend)


def test_create_local_backend_uses_posix_pty_backend_for_linux(monkeypatch) -> None:
    monkeypatch.setattr(local_backend_factory, "current_platform", lambda: "linux")

    backend = local_backend_factory.create_local_backend(_config())

    assert isinstance(backend, LocalPosixBackend)


def test_create_local_backend_uses_posix_pty_backend_for_macos(monkeypatch) -> None:
    monkeypatch.setattr(local_backend_factory, "current_platform", lambda: "darwin")

    backend = local_backend_factory.create_local_backend(_config())

    assert isinstance(backend, LocalPosixBackend)
