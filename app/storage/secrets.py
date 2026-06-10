from __future__ import annotations


class SecretStore:
    """通过 keyring 保存连接密钥, 避免写入明文 SQLite."""

    _service_name = "whose-shell"

    def set_connection_password(self, connection_id: int, password: str) -> None:
        keyring = self._keyring()
        keyring.set_password(self._service_name, self._password_key(connection_id), password)

    def get_connection_password(self, connection_id: int) -> str | None:
        keyring = self._keyring()
        return keyring.get_password(self._service_name, self._password_key(connection_id))

    def delete_connection_password(self, connection_id: int) -> None:
        keyring = self._keyring()
        try:
            keyring.delete_password(self._service_name, self._password_key(connection_id))
        except keyring.errors.PasswordDeleteError:
            return

    def set_connection_passphrase(self, connection_id: int, passphrase: str) -> None:
        keyring = self._keyring()
        keyring.set_password(self._service_name, self._passphrase_key(connection_id), passphrase)

    def get_connection_passphrase(self, connection_id: int) -> str | None:
        keyring = self._keyring()
        return keyring.get_password(self._service_name, self._passphrase_key(connection_id))

    def delete_connection_passphrase(self, connection_id: int) -> None:
        keyring = self._keyring()
        try:
            keyring.delete_password(self._service_name, self._passphrase_key(connection_id))
        except keyring.errors.PasswordDeleteError:
            return

    def _password_key(self, connection_id: int) -> str:
        return f"connection:{connection_id}:password"

    def _passphrase_key(self, connection_id: int) -> str:
        return f"connection:{connection_id}:passphrase"

    def _keyring(self):
        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError("keyring is not installed. Run: pip install -e .") from exc
        return keyring
