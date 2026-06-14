from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.common.models import ConnectionRecord, SshConnectionConfig


class SshConnectionDialog(QDialog):
    """SSH 连接输入弹窗."""

    def __init__(self, parent=None, connection: ConnectionRecord | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit SSH Connection" if connection else "New SSH Shell")

        self._name = QLineEdit(self)
        self._name.setPlaceholderText("Production Server")
        self._host = QLineEdit(self)
        self._host.setPlaceholderText("example.com")
        self._port = QSpinBox(self)
        self._port.setRange(1, 65535)
        self._port.setValue(22)
        self._username = QLineEdit(self)
        self._auth_method = QComboBox(self)
        self._auth_method.addItem("Password", "password")
        self._auth_method.addItem("Private key", "private_key")
        self._auth_method.addItem("No stored secret", "none")
        self._auth_method.currentIndexChanged.connect(self._sync_auth_fields)
        self._password = QLineEdit(self)
        self._password.setEchoMode(QLineEdit.Password)
        self._private_key = QLineEdit(self)
        self._private_key_passphrase = QLineEdit(self)
        self._private_key_passphrase.setEchoMode(QLineEdit.Password)
        self._default_directory = QLineEdit(self)
        self._accept_unknown_host = QCheckBox(self)
        self._accept_unknown_host.setChecked(True)
        if connection is not None:
            self._name.setText(connection.name)
            self._host.setText(connection.host or "")
            self._port.setValue(connection.port or 22)
            self._username.setText(connection.username or "")
            self._private_key.setText(connection.private_key_path or "")
            self._default_directory.setText(connection.default_directory or "")
            self._password.setPlaceholderText("Leave blank to keep existing password")
            self._private_key_passphrase.setPlaceholderText("Leave blank to keep existing passphrase")
            self._select_auth_method(connection.auth_method)

        browse_key = QPushButton("Browse", self)
        browse_key.clicked.connect(self._browse_private_key)

        key_row = QHBoxLayout()
        key_row.addWidget(self._private_key, 1)
        key_row.addWidget(browse_key)

        form = QFormLayout()
        form.addRow("Connection name", self._name)
        form.addRow("Host", self._host)
        form.addRow("Port", self._port)
        form.addRow("Username", self._username)
        form.addRow("Authentication", self._auth_method)
        form.addRow("Password", self._password)
        form.addRow("Private key", key_row)
        form.addRow("Key passphrase", self._private_key_passphrase)
        form.addRow("Default directory", self._default_directory)
        form.addRow("Accept unknown host", self._accept_unknown_host)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._sync_auth_fields()

    def connection_config(self) -> SshConnectionConfig:
        """返回当前输入的 SSH 连接配置."""
        password = self._password.text() or None
        private_key_path = self._private_key.text().strip() or None
        private_key_passphrase = self._private_key_passphrase.text() or None
        default_directory = self._default_directory.text().strip() or None
        return SshConnectionConfig(
            host=self._host.text().strip(),
            port=self._port.value(),
            username=self._username.text().strip(),
            name=self._name.text().strip() or None,
            auth_method=self._auth_method.currentData(),
            password=password,
            private_key_path=private_key_path,
            private_key_passphrase=private_key_passphrase,
            default_directory=default_directory,
            accept_unknown_host=self._accept_unknown_host.isChecked(),
        )

    def _browse_private_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select private key")
        if path:
            self._private_key.setText(path)

    def _accept_if_valid(self) -> None:
        message = self._validation_message()
        if message:
            QMessageBox.warning(self, "SSH Connection", message)
            return
        self.accept()

    def _select_auth_method(self, auth_method: str | None) -> None:
        index = self._auth_method.findData(auth_method or "password")
        if index >= 0:
            self._auth_method.setCurrentIndex(index)

    def _sync_auth_fields(self) -> None:
        auth_method = self._auth_method.currentData()
        password_enabled = auth_method == "password"
        private_key_enabled = auth_method == "private_key"
        self._password.setEnabled(password_enabled)
        self._private_key.setEnabled(private_key_enabled)
        self._private_key_passphrase.setEnabled(private_key_enabled)

    def _validation_message(self) -> str | None:
        if not self._host.text().strip():
            return "Host is required."
        if not self._username.text().strip():
            return "Username is required."

        auth_method = self._auth_method.currentData()
        if auth_method == "password":
            return None
        if auth_method == "private_key":
            private_key = self._private_key.text().strip()
            if not private_key:
                return "Private key path is required for private-key authentication."
            if not Path(private_key).is_file():
                return "Private key path does not exist."
            return None
        return None
