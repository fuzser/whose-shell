from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from PySide6.QtGui import QColor

from app.ui.terminal.terminal_style import DEFAULT_BG, DEFAULT_FG, TerminalStyle, default_style, style_with_foreground


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
    width: int = 1
    continuation: bool = False


class TerminalBuffer:
    """保存终端字符网格和光标位置."""

    def __init__(self, cols: int = 100, rows: int = 32, scrollback_limit: int = 1000) -> None:
        self.cols = cols
        self.rows = rows
        self.scrollback_limit = scrollback_limit
        self.cursor_col = 0
        self.cursor_row = 0
        self._grid = [self._blank_line() for _ in range(rows)]
        self._grid_wraps = [False for _ in range(rows)]
        self._scrollback: list[list[TerminalCell]] = []
        self._scrollback_wraps: list[bool] = []

    def write_text(
        self,
        text: str,
        foreground: QColor | None = None,
        style: TerminalStyle | None = None,
    ) -> None:
        active_style = style.copy() if style is not None else default_style()
        if foreground is not None:
            active_style = style_with_foreground(active_style, foreground)
        for char in text:
            if char == "\n":
                self.newline()
            elif char == "\r":
                self.cursor_col = 0
            elif char == "\b":
                self.cursor_col = max(0, self.cursor_col - 1)
            elif char == "\t":
                spaces = 4 - (self.cursor_col % 4)
                self.write_text(" " * spaces, style=active_style)
            elif char >= " ":
                self._put_char(char, active_style)

    def newline(self, soft_wrap: bool = False) -> None:
        if soft_wrap and 0 <= self.cursor_row < len(self._grid_wraps):
            self._grid_wraps[self.cursor_row] = True
        self.cursor_col = 0
        self.cursor_row += 1
        if self.cursor_row >= self.rows:
            self._scroll_up()
            self.cursor_row = self.rows - 1

    def clear_screen(self) -> None:
        self._grid = [self._blank_line() for _ in range(self.rows)]
        self._grid_wraps = [False for _ in range(self.rows)]
        self.cursor_col = 0
        self.cursor_row = 0

    def clear_console(self) -> None:
        """清空当前 console 显示和本地 scrollback."""
        self._scrollback.clear()
        self._scrollback_wraps.clear()
        self.clear_screen()

    def archive_screen_to_scrollback(self) -> None:
        """把当前屏幕内容归档到 scrollback, 然后清空活动屏幕."""
        last_content_index = self._last_content_line_index(self._grid, self._grid_wraps)
        for row_index, row in enumerate(self._grid[: last_content_index + 1]):
            if not self._row_text(row) and not self._grid_wraps[row_index]:
                continue
            self._scrollback.append([self._copy_cell(cell) for cell in row])
            self._scrollback_wraps.append(self._grid_wraps[row_index])
        self._scrollback = self._scrollback[-self.scrollback_limit :]
        self._scrollback_wraps = self._scrollback_wraps[-self.scrollback_limit :]
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
            self._clear_cell(self.cursor_row, col)

    def move_cursor(self, row: int, col: int) -> None:
        self.cursor_row = max(0, min(self.rows - 1, row))
        self.cursor_col = max(0, min(self.cols - 1, col))

    def resize(self, cols: int, rows: int) -> None:
        new_cols = max(1, cols)
        new_rows = max(1, rows)
        if new_cols == self.cols and new_rows == self.rows:
            return

        old_cursor_index = self.cursor_line_index()
        logical_lines, cursor_line, cursor_offset = self._logical_lines_with_cursor(old_cursor_index)
        wrapped_lines, new_cursor_index, new_cursor_col = self._wrap_logical_lines(
            logical_lines,
            new_cols,
            cursor_line,
            cursor_offset,
        )

        self.cols = new_cols
        self.rows = new_rows
        self._scrollback = []
        self._scrollback_wraps = []
        self._grid = [self._blank_line() for _ in range(self.rows)]
        self._grid_wraps = [False for _ in range(self.rows)]
        top_padding, visible_start = self._load_wrapped_lines(wrapped_lines)
        self._scrollback = self._scrollback[-self.scrollback_limit :]
        self._scrollback_wraps = self._scrollback_wraps[-self.scrollback_limit :]
        self._place_cursor_after_resize(new_cursor_index, new_cursor_col, top_padding, visible_start)

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

    def _all_wraps(self) -> list[bool]:
        return self._scrollback_wraps + self._grid_wraps

    def _logical_lines_with_cursor(self, cursor_line_index: int) -> tuple[list[str], int, int]:
        lines = self._all_cells()
        wraps = self._all_wraps()
        last_content_index = self._last_content_line_index(lines, wraps)
        last_line_index = max(cursor_line_index, last_content_index)
        lines = lines[: last_line_index + 1]
        wraps = wraps[: last_line_index + 1]
        logical_lines: list[str] = []
        current_parts: list[str] = []
        current_index = 0
        cursor_line = 0
        cursor_offset = 0

        for row_index, row in enumerate(lines):
            row_text = self._row_text(row)
            row_start = sum(len(part) for part in current_parts)
            if row_index == cursor_line_index:
                cursor_line = current_index
                cursor_offset = row_start + self._cursor_text_offset(row, self.cursor_col)

            current_parts.append(row_text)
            if self._is_soft_wrapped_row(row_index, lines, wraps):
                continue

            logical_lines.append("".join(current_parts))
            current_parts = []
            current_index += 1

        if current_parts:
            logical_lines.append("".join(current_parts))
        if not logical_lines:
            logical_lines.append("")
        return logical_lines, min(cursor_line, len(logical_lines) - 1), cursor_offset

    def _last_content_line_index(self, lines: list[list[TerminalCell]], wraps: list[bool]) -> int:
        for index in range(len(lines) - 1, -1, -1):
            if self._row_text(lines[index]) or wraps[index]:
                return index
        return 0

    def _wrap_logical_lines(
        self,
        logical_lines: list[str],
        cols: int,
        cursor_line: int,
        cursor_offset: int,
    ) -> tuple[list[tuple[str, bool]], int, int]:
        wrapped_lines: list[tuple[str, bool]] = []
        new_cursor_index = 0
        new_cursor_col = 0

        for line_index, line in enumerate(logical_lines):
            if line_index == cursor_line:
                new_cursor_index = len(wrapped_lines) + (cursor_offset // cols)
                new_cursor_col = cursor_offset % cols

            if not line:
                wrapped_lines.append(("", False))
                continue

            start = 0
            while start < len(line):
                end = start + cols
                wrapped_lines.append((line[start:end], end < len(line)))
                start += cols

        if not wrapped_lines:
            wrapped_lines.append(("", False))
        return wrapped_lines, min(new_cursor_index, len(wrapped_lines) - 1), new_cursor_col

    def _load_wrapped_lines(self, wrapped_lines: list[tuple[str, bool]]) -> tuple[int, int]:
        visible_lines = wrapped_lines[-self.rows :]
        scrollback_lines = wrapped_lines[: -self.rows]
        self._scrollback = [self._line_to_cells(line) for line, _ in scrollback_lines]
        self._scrollback_wraps = [soft_wrap for _, soft_wrap in scrollback_lines]
        bottom_padding = max(0, self.rows - len(visible_lines))
        self._grid = [self._line_to_cells(line) for line, _ in visible_lines]
        self._grid_wraps = [soft_wrap for _, soft_wrap in visible_lines]
        self._grid.extend(self._blank_line() for _ in range(bottom_padding))
        self._grid_wraps.extend(False for _ in range(bottom_padding))
        visible_start = len(scrollback_lines)
        return 0, visible_start

    def _place_cursor_after_resize(
        self,
        cursor_index: int,
        cursor_col: int,
        top_padding: int,
        visible_start: int,
    ) -> None:
        self.cursor_row = max(0, min(self.rows - 1, top_padding + cursor_index - visible_start))
        self.cursor_col = max(0, min(self.cols - 1, cursor_col))

    def _row_text(self, row: list[TerminalCell]) -> str:
        return "".join(cell.char for cell in row if not cell.continuation).rstrip()

    def _cursor_text_offset(self, row: list[TerminalCell], cursor_col: int) -> int:
        offset = 0
        for col, cell in enumerate(row[:cursor_col]):
            if cell.continuation:
                continue
            offset += max(1, cell.width)
        return offset

    def _is_soft_wrapped_row(self, row_index: int, lines: list[list[TerminalCell]], wraps: list[bool]) -> bool:
        if row_index >= len(lines) - 1:
            return False
        if not self._row_text(lines[row_index + 1]):
            return False
        return wraps[row_index]

    def _line_to_cells(self, line: str) -> list[TerminalCell]:
        cells = self._blank_line()
        col = 0
        for char in line:
            width = self._char_width(char)
            if width <= 0:
                continue
            if col >= self.cols or (width == 2 and col == self.cols - 1):
                break
            cells[col] = TerminalCell(char=char, width=width)
            if width == 2 and col + 1 < self.cols:
                cells[col + 1] = TerminalCell(continuation=True)
            col += width
        return cells

    def _put_char(self, char: str, style: TerminalStyle) -> None:
        width = self._char_width(char)
        if width <= 0:
            return
        if width == 2 and self.cursor_col == self.cols - 1:
            self.newline(soft_wrap=True)

        self._clear_cell(self.cursor_row, self.cursor_col)
        self._grid[self.cursor_row][self.cursor_col] = TerminalCell(
            char=char,
            foreground=QColor(style.foreground),
            background=QColor(style.background),
            bold=style.bold,
            italic=style.italic,
            underline=style.underline,
            inverse=style.inverse,
            width=width,
        )
        if width == 2 and self.cursor_col + 1 < self.cols:
            self._grid[self.cursor_row][self.cursor_col + 1] = TerminalCell(continuation=True)
        self.cursor_col += width
        if self.cursor_col >= self.cols:
            self.newline(soft_wrap=True)

    def _clear_cell(self, row: int, col: int) -> None:
        cell = self._grid[row][col]
        if cell.continuation and col > 0 and self._grid[row][col - 1].width == 2:
            self._grid[row][col - 1] = TerminalCell()
        if cell.width == 2 and col + 1 < self.cols:
            self._grid[row][col + 1] = TerminalCell()
        self._grid[row][col] = TerminalCell()

    def _char_width(self, char: str) -> int:
        if unicodedata.combining(char):
            return 0
        return 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1

    def _scroll_up(self) -> None:
        self._scrollback.append(self._grid.pop(0))
        self._scrollback_wraps.append(self._grid_wraps.pop(0))
        if len(self._scrollback) > self.scrollback_limit:
            self._scrollback.pop(0)
            self._scrollback_wraps.pop(0)
        self._grid.append(self._blank_line())
        self._grid_wraps.append(False)

    def _blank_line(self) -> list[TerminalCell]:
        return [TerminalCell() for _ in range(self.cols)]

    def _copy_cell(self, cell: TerminalCell) -> TerminalCell:
        return TerminalCell(
            char=cell.char,
            foreground=QColor(cell.foreground),
            background=QColor(cell.background),
            bold=cell.bold,
            italic=cell.italic,
            underline=cell.underline,
            inverse=cell.inverse,
            dirty=cell.dirty,
            width=cell.width,
            continuation=cell.continuation,
        )
