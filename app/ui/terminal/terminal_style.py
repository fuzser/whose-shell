from __future__ import annotations

from dataclasses import dataclass, field, replace

from PySide6.QtGui import QColor


DEFAULT_FG = QColor("#d8dee9")
DEFAULT_BG = QColor("#111318")

ANSI_NORMAL_COLORS = {
    0: QColor("#000000"),
    1: QColor("#cd3131"),
    2: QColor("#0dbc79"),
    3: QColor("#e5e510"),
    4: QColor("#2472c8"),
    5: QColor("#bc3fbc"),
    6: QColor("#11a8cd"),
    7: QColor("#e5e5e5"),
}

ANSI_BRIGHT_COLORS = {
    0: QColor("#666666"),
    1: QColor("#f14c4c"),
    2: QColor("#23d18b"),
    3: QColor("#f5f543"),
    4: QColor("#3b8eea"),
    5: QColor("#d670d6"),
    6: QColor("#29b8db"),
    7: QColor("#ffffff"),
}


@dataclass
class TerminalStyle:
    """终端字符样式状态."""

    foreground: QColor = field(default_factory=lambda: QColor(DEFAULT_FG))
    background: QColor = field(default_factory=lambda: QColor(DEFAULT_BG))
    bold: bool = False
    italic: bool = False
    underline: bool = False
    inverse: bool = False

    def copy(self) -> "TerminalStyle":
        return TerminalStyle(
            foreground=QColor(self.foreground),
            background=QColor(self.background),
            bold=self.bold,
            italic=self.italic,
            underline=self.underline,
            inverse=self.inverse,
        )


def default_style() -> TerminalStyle:
    return TerminalStyle()


def style_with_foreground(style: TerminalStyle, foreground: QColor) -> TerminalStyle:
    return replace(style, foreground=QColor(foreground))


def apply_sgr(style: TerminalStyle, params: list[int]) -> TerminalStyle:
    """应用 Step 1 支持的 SGR 参数."""
    if not params:
        params = [0]

    next_style = style.copy()
    for code in params:
        if code == 0:
            next_style = default_style()
        elif code == 1:
            next_style.bold = True
        elif code == 3:
            next_style.italic = True
        elif code == 4:
            next_style.underline = True
        elif code == 7:
            next_style.inverse = True
        elif code == 22:
            next_style.bold = False
        elif code == 23:
            next_style.italic = False
        elif code == 24:
            next_style.underline = False
        elif code == 27:
            next_style.inverse = False
        elif code == 39:
            next_style.foreground = QColor(DEFAULT_FG)
        elif code == 49:
            next_style.background = QColor(DEFAULT_BG)
        elif 30 <= code <= 37:
            next_style.foreground = QColor(ANSI_NORMAL_COLORS[code - 30])
        elif 40 <= code <= 47:
            next_style.background = QColor(ANSI_NORMAL_COLORS[code - 40])
        elif 90 <= code <= 97:
            next_style.foreground = QColor(ANSI_BRIGHT_COLORS[code - 90])
        elif 100 <= code <= 107:
            next_style.background = QColor(ANSI_BRIGHT_COLORS[code - 100])
    return next_style
