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


def ansi_256_color(index: int) -> QColor:
    """把 xterm 256 色索引转换为 QColor."""
    index = max(0, min(255, index))
    if index < 8:
        return QColor(ANSI_NORMAL_COLORS[index])
    if index < 16:
        return QColor(ANSI_BRIGHT_COLORS[index - 8])
    if index < 232:
        value = index - 16
        red = value // 36
        green = (value % 36) // 6
        blue = value % 6
        return QColor(_color_cube_channel(red), _color_cube_channel(green), _color_cube_channel(blue))
    gray = 8 + (index - 232) * 10
    return QColor(gray, gray, gray)


def truecolor(red: int, green: int, blue: int) -> QColor:
    """把 SGR truecolor 参数转换为 QColor."""
    return QColor(_clamp_color(red), _clamp_color(green), _clamp_color(blue))


def apply_sgr(style: TerminalStyle, params: list[int]) -> TerminalStyle:
    """应用当前支持的 SGR 参数."""
    if not params:
        params = [0]

    next_style = style.copy()
    index = 0
    while index < len(params):
        code = params[index]
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
        elif code in {38, 48}:
            color, consumed = _extended_color(params, index + 1)
            if color is not None:
                if code == 38:
                    next_style.foreground = color
                else:
                    next_style.background = color
            index += consumed
        index += 1
    return next_style


def _extended_color(params: list[int], start: int) -> tuple[QColor | None, int]:
    if start >= len(params):
        return None, 0

    mode = params[start]
    if mode == 5:
        if start + 1 >= len(params):
            return None, 1
        return ansi_256_color(params[start + 1]), 2
    if mode == 2:
        if start + 3 >= len(params):
            return None, 1
        return truecolor(params[start + 1], params[start + 2], params[start + 3]), 4
    return None, 1


def _color_cube_channel(value: int) -> int:
    return 0 if value == 0 else 55 + value * 40


def _clamp_color(value: int) -> int:
    return max(0, min(255, value))
