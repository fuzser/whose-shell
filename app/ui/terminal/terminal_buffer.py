from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtGui import QColor


DEFAULT_FG = QColor("#d8dee9")
DEFAULT_BG = QColor("#111318")


@dataclass
class TerminalCell:
    """终端字符单元."""

    char: str = " "
    foreground: QColor = field(default_factory=lambda: QColor(DEFAULT_FG))
    background: QColor = field(default_factory=lambda: QColor(DEFAULT_BG))
    bold: bool = False
    italic: bool = False
    underline: bool = False
    inverse: bool = False
    dirty: bool = True


class TerminalBuffer:
    """保存终端字符网格和光标位置."""

    def __init__(self, cols: int = 100, rows: int = 32, scrollback_limit: int = 1000) -> None:
        self.cols = cols
        self.rows = rows
        self.scrollback_limit = scrollback_limit
        self.cursor_col = 0
        self.cursor_row = 0
        self._grid = [self._blank_line() for _ in range(rows)]
        self._scrollback: list[list[TerminalCell]] = []

    def write_text(self, text: str) -> None:
        for char in text:
            if char == "\n":
                self.newline()
            elif char == "\r":
                self.cursor_col = 0
            elif char == "\b":
                self.cursor_col = max(0, self.cursor_col - 1)
            elif char == "\t":
                spaces = 4 - (self.cursor_col % 4)
                self.write_text(" " * spaces)
            elif char >= " ":
                self._put_char(char)

    def newline(self) -> None:
        self.cursor_col = 0
        self.cursor_row += 1
        if self.cursor_row >= self.rows:
            self._scroll_up()
            self.cursor_row = self.rows - 1

    def clear_screen(self) -> None:
        self._grid = [self._blank_line() for _ in range(self.rows)]
        self.cursor_col = 0
        self.cursor_row = 0

    def clear_line(self) -> None:
        self._grid[self.cursor_row] = self._blank_line()
        self.cursor_col = 0

    def move_cursor(self, row: int, col: int) -> None:
        self.cursor_row = max(0, min(self.rows - 1, row))
        self.cursor_col = max(0, min(self.cols - 1, col))

    def resize(self, cols: int, rows: int) -> None:
        self.cols = max(1, cols)
        self.rows = max(1, rows)
        new_grid = [self._blank_line() for _ in range(self.rows)]
        for row_index, row in enumerate(self._grid[: self.rows]):
            new_grid[row_index][: min(len(row), self.cols)] = row[: self.cols]
        self._grid = new_grid
        self.move_cursor(self.cursor_row, self.cursor_col)

    def visible_lines(self) -> list[str]:
        return ["".join(cell.char for cell in row) for row in self._grid]

    def _put_char(self, char: str) -> None:
        self._grid[self.cursor_row][self.cursor_col] = TerminalCell(char=char)
        self.cursor_col += 1
        if self.cursor_col >= self.cols:
            self.newline()

    def _scroll_up(self) -> None:
        self._scrollback.append(self._grid.pop(0))
        if len(self._scrollback) > self.scrollback_limit:
            self._scrollback.pop(0)
        self._grid.append(self._blank_line())

    def _blank_line(self) -> list[TerminalCell]:
        return [TerminalCell() for _ in range(self.cols)]
