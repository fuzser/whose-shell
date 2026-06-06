from __future__ import annotations

import re

from app.ui.terminal.terminal_buffer import TerminalBuffer


CSI_RE = re.compile(r"\x1b\[([0-9;?]*)([A-Za-z])")


class AnsiParser:
    """基础 ANSI/VT 控制序列解析器."""

    def feed(self, data: bytes, buffer: TerminalBuffer) -> None:
        text = data.decode("utf-8", errors="replace")
        position = 0
        for match in CSI_RE.finditer(text):
            if match.start() > position:
                buffer.write_text(text[position : match.start()])
            self._apply_csi(match.group(1), match.group(2), buffer)
            position = match.end()
        if position < len(text):
            buffer.write_text(text[position:])

    def _apply_csi(self, params: str, command: str, buffer: TerminalBuffer) -> None:
        numbers = self._numbers(params)
        if command == "J":
            buffer.clear_screen()
        elif command == "K":
            buffer.clear_line()
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
        elif command == "m":
            # TODO: 接入颜色和样式状态, 当前先跳过 SGR 防止控制码显示.
            return

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

