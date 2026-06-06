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

    def write_text(self, text: str, foreground: QColor | None = None) -> None:
        for char in text:
            if char == "\n":
                self.newline()
            elif char == "\r":
                self.cursor_col = 0
            elif char == "\b":
                self.cursor_col = max(0, self.cursor_col - 1)
            elif char == "\t":
                spaces = 4 - (self.cursor_col % 4)
                self.write_text(" " * spaces, foreground)
            elif char >= " ":
                self._put_char(char, foreground)

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

    def clear_console(self) -> None:
        """清空当前 console 显示和本地 scrollback."""
        self._scrollback.clear()
        self.clear_screen()

    def clear_line(self, mode: int = 0) -> None:
        """按 ANSI EL 模式清理当前行, 不改变光标位置."""
        if mode == 1:
            start_col = 0
            end_col = self.cursor_col
        elif mode == 2:
            start_col = 0
            end_col = self.cols - 1
        else:
            start_col = self.cursor_col
            end_col = self.cols - 1

        for col in range(start_col, end_col + 1):
            self._grid[self.cursor_row][col] = TerminalCell()

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

    def max_scroll_offset(self) -> int:
        """返回可向上回滚的历史行数."""
        return len(self._scrollback)

    def total_line_count(self) -> int:
        return len(self._scrollback) + len(self._grid)

    def cursor_line_index(self) -> int:
        return len(self._scrollback) + self.cursor_row

    def visible_start_index(self, scroll_offset: int = 0) -> int:
        offset = max(0, min(scroll_offset, self.max_scroll_offset()))
        return max(0, self.total_line_count() - self.rows - offset)

    def all_lines(self) -> list[str]:
        return ["".join(cell.char for cell in row) for row in self._all_cells()]

    def visible_lines(self, scroll_offset: int = 0) -> list[str]:
        return ["".join(cell.char for cell in row) for row in self.visible_cells(scroll_offset)]

    def visible_cells(self, scroll_offset: int = 0) -> list[list[TerminalCell]]:
        all_cells = self._all_cells()
        start = self.visible_start_index(scroll_offset)
        visible = all_cells[start : start + self.rows]
        if len(visible) < self.rows:
            visible = [self._blank_line() for _ in range(self.rows - len(visible))] + visible
        return visible

    def _all_cells(self) -> list[list[TerminalCell]]:
        return self._scrollback + self._grid

    def _put_char(self, char: str, foreground: QColor | None = None) -> None:
        self._grid[self.cursor_row][self.cursor_col] = TerminalCell(
            char=char,
            foreground=QColor(foreground or DEFAULT_FG),
        )
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
