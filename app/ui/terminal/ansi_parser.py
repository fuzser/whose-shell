from __future__ import annotations

import codecs

from app.ui.terminal.terminal_buffer import TerminalBuffer
from app.ui.terminal.terminal_style import TerminalStyle, apply_sgr, default_style


OSC_BEL = "\x07"
ESC = "\x1b"

STATE_GROUND = "ground"
STATE_ESCAPE = "escape"
STATE_CSI = "csi"
STATE_OSC = "osc"
STATE_OSC_ESCAPE = "osc_escape"


class AnsiParser:
    """基础 ANSI/VT 控制序列解析器."""

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._style: TerminalStyle = default_style()
        self._state = STATE_GROUND
        self._csi_params = ""

    def feed(self, data: bytes, buffer: TerminalBuffer) -> None:
        for char in self._decoder.decode(data):
            if self._state == STATE_GROUND:
                self._feed_ground(char, buffer)
            elif self._state == STATE_ESCAPE:
                self._feed_escape(char)
            elif self._state == STATE_CSI:
                self._feed_csi(char, buffer)
            elif self._state == STATE_OSC:
                self._feed_osc(char)
            elif self._state == STATE_OSC_ESCAPE:
                self._feed_osc_escape(char)

    def _feed_ground(self, char: str, buffer: TerminalBuffer) -> None:
        if char == ESC:
            self._state = STATE_ESCAPE
            return
        buffer.write_text(char, style=self._style)

    def _feed_escape(self, char: str) -> None:
        if char == "[":
            self._csi_params = ""
            self._state = STATE_CSI
        elif char == "]":
            self._state = STATE_OSC
        elif char == ESC:
            self._state = STATE_ESCAPE
        else:
            # 当前未支持的短 ESC 序列直接跳过, 避免残片显示到终端.
            self._state = STATE_GROUND

    def _feed_csi(self, char: str, buffer: TerminalBuffer) -> None:
        if char == ESC:
            self._csi_params = ""
            self._state = STATE_ESCAPE
            return
        if "@" <= char <= "~":
            self._apply_csi(self._csi_params, char, buffer)
            self._csi_params = ""
            self._state = STATE_GROUND
            return
        self._csi_params += char

    def _feed_osc(self, char: str) -> None:
        if char == OSC_BEL:
            self._state = STATE_GROUND
        elif char == ESC:
            self._state = STATE_OSC_ESCAPE

    def _feed_osc_escape(self, char: str) -> None:
        if char == "\\":
            self._state = STATE_GROUND
        elif char == ESC:
            self._state = STATE_OSC_ESCAPE
        else:
            self._state = STATE_OSC

    def _apply_csi(self, params: str, command: str, buffer: TerminalBuffer) -> None:
        numbers = self._numbers(params)
        if command == "J":
            buffer.clear_screen(numbers[0] if numbers else 0)
        elif command == "K":
            buffer.clear_line(numbers[0] if numbers else 0)
        elif command in {"H", "f"}:
            row = (numbers[0] - 1) if numbers else 0
            col = (numbers[1] - 1) if len(numbers) > 1 else 0
            buffer.move_cursor(row, col)
        elif command == "A":
            buffer.move_cursor(buffer.cursor_row - self._first(numbers), buffer.cursor_col)
        elif command == "B":
            buffer.move_cursor(buffer.cursor_row + self._first(numbers), buffer.cursor_col)
        elif command == "C":
            buffer.move_cursor(buffer.cursor_row, buffer.cursor_col + self._first(numbers))
        elif command == "D":
            buffer.move_cursor(buffer.cursor_row, buffer.cursor_col - self._first(numbers))
        elif command == "G":
            buffer.move_cursor_col(self._first(numbers) - 1)
        elif command == "d":
            buffer.move_cursor_row(self._first(numbers) - 1)
        elif command == "s":
            buffer.save_cursor()
        elif command == "u":
            buffer.restore_cursor()
        elif command == "m":
            self._style = apply_sgr(self._style, numbers)

    def _numbers(self, params: str) -> list[int]:
        if not params:
            return []
        result: list[int] = []
        for part in params.replace("?", "").split(";"):
            if not part:
                result.append(1)
                continue
            try:
                result.append(int(part))
            except ValueError:
                result.append(1)
        return result

    def _first(self, numbers: list[int]) -> int:
        return numbers[0] if numbers else 1
