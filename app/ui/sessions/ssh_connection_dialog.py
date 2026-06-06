from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.common.models import SshConnectionConfig


class SshConnectionDialog(QDialog):
    """SSH 连接输入弹窗."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New SSH Shell")

        self._host = QLineEdit(self)
        self._host.setPlaceholderText("example.com")
        self._port = QSpinBox(self)
        self._port.setRange(1, 65535)
        self._port.setValue(22)
        self._username = QLineEdit(self)
        self._password = QLineEdit(self)
        self._password.setEchoMode(QLineEdit.Password)
        self._private_key = QLineEdit(self)
        self._default_directory = QLineEdit(self)
        self._accept_unknown_host = QCheckBox(self)
        self._accept_unknown_host.setChecked(True)

        browse_key = QPushButton("Browse", self)
        browse_key.clicked.connect(self._browse_private_key)

        key_row = QHBoxLayout()
        key_row.addWidget(self._private_key, 1)
        key_row.addWidget(browse_key)

        form = QFormLayout()
        form.addRow("Host", self._host)
        form.addRow("Port", self._port)
        form.addRow("Username", self._username)
        form.addRow("Password", self._password)
        form.addRow("Private key", key_row)
        form.addRow("Default directory", self._default_directory)
        form.addRow("Accept unknown host", self._accept_unknown_host)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def connection_config(self) -> SshConnectionConfig:
        """返回当前输入的 SSH 连接配置."""
        password = self._password.text() or None
        private_key_path = self._private_key.text() or None
        default_directory = self._default_directory.text() or None
        return SshConnectionConfig(
            host=self._host.text().strip(),
            port=self._port.value(),
            username=self._username.text().strip(),
            password=password,
            private_key_path=private_key_path,
            default_directory=default_directory,
            accept_unknown_host=self._accept_unknown_host.isChecked(),
        )

    def _browse_private_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select private key")
        if path:
            self._private_key.setText(path)

    def _accept_if_valid(self) -> None:
        if not self._host.text().strip() or not self._username.text().strip():
            return
        self.accept()
