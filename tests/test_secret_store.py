from __future__ import annotations

import sqlite3
import sys
import types

from app.storage.migrations import migrate
from app.storage.secrets import SecretStore


class _PasswordDeleteError(Exception):
    pass


class _FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}
        self.errors = types.SimpleNamespace(PasswordDeleteError=_PasswordDeleteError)

    def set_password(self, service_name: str, key: str, value: str) -> None:
        self.values[(service_name, key)] = value

    def get_password(self, service_name: str, key: str) -> str | None:
        return self.values.get((service_name, key))

    def delete_password(self, service_name: str, key: str) -> None:
        try:
            del self.values[(service_name, key)]
        except KeyError as exc:
            raise _PasswordDeleteError from exc


def test_secret_store_saves_password_and_passphrase_with_separate_keys(monkeypatch) -> None:
    fake_keyring = _FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    store = SecretStore()

    store.set_connection_password(7, "password-value")
    store.set_connection_passphrase(7, "passphrase-value")

    assert store.get_connection_password(7) == "password-value"
    assert store.get_connection_passphrase(7) == "passphrase-value"

    store.delete_connection_password(7)

    assert store.get_connection_password(7) is None
    assert store.get_connection_passphrase(7) == "passphrase-value"

    store.delete_connection_passphrase(7)

    assert store.get_connection_passphrase(7) is None


def test_secret_store_passphrase_helpers_do_not_write_to_sqlite(monkeypatch) -> None:
    fake_keyring = _FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    migrate(connection)

    SecretStore().set_connection_passphrase(3, "private-passphrase")

    for table in (
        "connections",
        "sessions",
        "active_terminal_tabs",
        "commands",
        "favorites",
        "settings",
        "file_transfers",
    ):
        rows = connection.execute(f"SELECT * FROM {table}").fetchall()
        assert "private-passphrase" not in str([tuple(row) for row in rows])
