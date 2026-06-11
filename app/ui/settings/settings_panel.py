from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.common.models import AppSettings, DEFAULT_TERMINAL_FONT_FAMILY, ThemeMode
from app.common.platform import AUTO_LOCAL_SHELL, available_local_shell_options, resolve_local_shell_preference
from app.core.session_manager import SessionManager


class SettingsPanel(QWidget):
    """应用设置面板."""

    settings_saved = Signal(AppSettings)

    def __init__(self, session_manager: SessionManager, parent=None) -> None:
        super().__init__(parent)
        self._session_manager = session_manager
        self._shell_options = available_local_shell_options()

        self._cols = QSpinBox(self)
        self._cols.setObjectName("terminalColumnsSpinBox")
        self._cols.setRange(20, 300)

        self._rows = QSpinBox(self)
        self._rows.setObjectName("terminalRowsSpinBox")
        self._rows.setRange(8, 120)

        self._font_family = QComboBox(self)
        self._font_family.setObjectName("terminalFontFamilyComboBox")

        self._font_size = QSpinBox(self)
        self._font_size.setObjectName("terminalFontSizeSpinBox")
        self._font_size.setRange(6, 48)

        self._shell = QComboBox(self)
        self._shell.setObjectName("defaultLocalShellComboBox")

        self._shell_status = QLabel(self)
        self._shell_status.setObjectName("resolvedLocalShellLabel")
        self._shell_status.setWordWrap(True)

        self._restore_tabs = QCheckBox("Restore tabs on startup", self)
        self._restore_tabs.setObjectName("restoreTabsCheckBox")

        self._theme = QComboBox(self)
        self._theme.setObjectName("themeModeComboBox")

        self._status = QLabel(self)
        self._status.setObjectName("settingsStatusLabel")
        self._status.setWordWrap(True)

        self._save = QPushButton("Save", self)
        self._save.setObjectName("saveSettingsButton")
        self._save.clicked.connect(self._save_settings)

        self._build_ui()
        self._populate_font_families()
        self._populate_shells()
        self._populate_theme_modes()
        self._load_settings()
        self._shell.currentIndexChanged.connect(self._update_shell_status)

    def _build_ui(self) -> None:
        form = QFormLayout()
        form.addRow("Terminal columns", self._cols)
        form.addRow("Terminal rows", self._rows)
        form.addRow("Font family", self._font_family)
        form.addRow("Font size", self._font_size)
        form.addRow("Default local shell", self._shell)
        form.addRow("Resolved shell", self._shell_status)
        form.addRow("", self._restore_tabs)
        form.addRow("Theme mode", self._theme)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self._save)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._status)
        layout.addStretch(1)
        layout.addLayout(actions)

    def _populate_shells(self) -> None:
        self._shell.clear()
        automatic = resolve_local_shell_preference(AUTO_LOCAL_SHELL)
        self._shell.addItem(f"Automatic ({automatic.resolved_shell})", AUTO_LOCAL_SHELL)
        for option in self._shell_options:
            self._shell.addItem(option.label, option.value)

    def _populate_font_families(self) -> None:
        self._font_family.clear()
        self._font_family.addItem(f"Default ({DEFAULT_TERMINAL_FONT_FAMILY})", "")
        for family in QFontDatabase.families():
            self._font_family.addItem(family, family)

    def _populate_theme_modes(self) -> None:
        self._theme.clear()
        for mode in ThemeMode:
            self._theme.addItem(mode.value.title(), mode.value)

    def _load_settings(self) -> None:
        settings = self._session_manager.get_settings()
        self._cols.setValue(settings.terminal_cols)
        self._rows.setValue(settings.terminal_rows)
        self._set_combo_value(self._font_family, settings.terminal_font_family, "")
        self._font_size.setValue(settings.terminal_font_size)
        self._restore_tabs.setChecked(settings.restore_tabs_on_startup)
        self._set_combo_value(self._theme, settings.theme_mode.value, ThemeMode.SYSTEM.value)
        self._set_combo_value(self._shell, settings.default_local_shell or AUTO_LOCAL_SHELL, AUTO_LOCAL_SHELL)
        self._update_shell_status()

    def _save_settings(self) -> None:
        shell_value = self._shell.currentData() or AUTO_LOCAL_SHELL
        theme_value = self._theme.currentData() or ThemeMode.SYSTEM.value
        settings = AppSettings(
            terminal_cols=self._cols.value(),
            terminal_rows=self._rows.value(),
            terminal_font_family=str(self._font_family.currentData() or ""),
            terminal_font_size=self._font_size.value(),
            default_local_shell=str(shell_value),
            restore_tabs_on_startup=self._restore_tabs.isChecked(),
            theme_mode=ThemeMode(str(theme_value)),
        )
        saved = self._session_manager.save_settings(settings)
        self._status.setText("Settings saved. New terminal defaults apply to new sessions.")
        self.settings_saved.emit(saved)

    def _update_shell_status(self) -> None:
        value = self._shell.currentData() or AUTO_LOCAL_SHELL
        resolution = resolve_local_shell_preference(str(value))
        if value == AUTO_LOCAL_SHELL:
            self._shell_status.setText(f"Auto resolves to: {resolution.resolved_shell}")
        else:
            self._shell_status.setText(f"Manual override: {resolution.resolved_shell}")

    def _set_combo_value(self, combo: QComboBox, value: str, fallback: str) -> None:
        index = combo.findData(value)
        if index < 0:
            index = combo.findData(fallback)
        combo.setCurrentIndex(max(0, index))
