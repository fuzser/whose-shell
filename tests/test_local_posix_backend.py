from __future__ import annotations

import re
import shutil
import sys
import time

import pytest
from PySide6.QtCore import QCoreApplication

from app.backends.local_posix_backend import LocalPosixBackend
from app.common.models import ConnectionType, TerminalSessionConfig


pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX PTY backend is not used on Windows.")


def _qt_app() -> QCoreApplication:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def _wait_until(app: QCoreApplication, predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    app.processEvents()
    return predicate()


def _output_text(chunks: list[bytes]) -> str:
    return b"".join(chunks).decode("utf-8", errors="replace")


def test_local_posix_backend_exposes_real_tty_and_resize() -> None:
    shell = shutil.which("sh") or "/bin/sh"
    app = _qt_app()
    backend = LocalPosixBackend(
        TerminalSessionConfig(
            name="Local Shell",
            connection_type=ConnectionType.LOCAL,
            command=[shell],
            cols=77,
            rows=19,
        )
    )
    output_chunks: list[bytes] = []
    connected: list[bool] = []
    closed_codes: list[int] = []
    errors: list[str] = []
    backend.output_received.connect(output_chunks.append)
    backend.connected.connect(lambda: connected.append(True))
    backend.closed.connect(closed_codes.append)
    backend.error.connect(errors.append)

    backend.start()
    try:
        assert _wait_until(app, lambda: bool(connected)), errors
        backend.resize(77, 19)
        backend.write(
            b"/usr/bin/env python3 -c 'import sys; "
            b"print(\"WHOSE_SHELL_ISATTY=%s,%s\" % (sys.stdin.isatty(), sys.stdout.isatty()))'\r"
        )
        assert _wait_until(app, lambda: "WHOSE_SHELL_ISATTY=True,True" in _output_text(output_chunks)), _output_text(
            output_chunks
        )

        backend.write(b"stty size; echo WHOSE_SHELL_SIZE_DONE\r")
        assert _wait_until(app, lambda: "WHOSE_SHELL_SIZE_DONE" in _output_text(output_chunks)), _output_text(
            output_chunks
        )
        assert re.search(r"\b19\s+77\b", _output_text(output_chunks)), _output_text(output_chunks)
        assert not errors
    finally:
        backend.stop()
        _wait_until(app, lambda: bool(closed_codes), timeout=3.0)
