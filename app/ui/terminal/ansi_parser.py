from __future__ import annotations

import codecs
import re

from app.ui.terminal.terminal_buffer import TerminalBuffer
from app.ui.terminal.terminal_style import TerminalStyle, apply_sgr, default_style


CSI_RE = re.compile(r"\x1b\[([0-9;:?=>]*)([@-~])")
OSC_PREFIX = "\x1b]"
OSC_BEL = "\x07"
OSC_ST = "\x1b\\"


class AnsiParser:
    """基础 ANSI/VT 控制序列解析器."""

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._pending = ""
        self._style: TerminalStyle = default_style()

    def feed(self, data: bytes, buffer: TerminalBuffer) -> None:
        text = self._pending + self._decoder.decode(data)
        self._pending = ""
        position = 0
        plain_start = 0
        while position < len(text):
            if text[position] != "\x1b":
                position += 1
                continue

            if position > plain_start:
                buffer.write_text(text[plain_start:position], style=self._style)

            if position + 1 >= len(text):
                self._pending = text[position:]
                return

            marker = text[position + 1]
            if marker == "[":
                match = CSI_RE.match(text, position)
                if match is None:
                    self._pending = text[position:]
                    return
                self._apply_csi(match.group(1), match.group(2), buffer)
                position = match.end()
            elif marker == "]":
                end = self._find_osc_end(text, position + len(OSC_PREFIX))
                if end is None:
                    self._pending = text[position:]
                    return
                position = end
            else:
                # 跳过当前尚未支持的短 ESC 序列, 避免控制字符残片显示到终端.
                position += 2

            plain_start = position
        if position < len(text):
            self._pending = text[position:]
            return
        if plain_start < len(text):
            buffer.write_text(text[plain_start:], style=self._style)

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

    def _find_osc_end(self, text: str, start: int) -> int | None:
        bel_index = text.find(OSC_BEL, start)
        st_index = text.find(OSC_ST, start)
        if bel_index == -1 and st_index == -1:
            return None
        if bel_index != -1 and (st_index == -1 or bel_index < st_index):
            return bel_index + len(OSC_BEL)
        return st_index + len(OSC_ST)
