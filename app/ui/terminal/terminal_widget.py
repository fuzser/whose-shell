from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QMenu

from app.ui.terminal.ansi_parser import AnsiParser
from app.ui.terminal.keymap import KeyMapper
from app.ui.terminal.terminal_buffer import DEFAULT_BG, DEFAULT_FG, TerminalBuffer


class TerminalWidget(QAbstractScrollArea):
    """自绘终端控件."""

    input_requested = Signal(bytes)
    resized = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._buffer = TerminalBuffer()
        self._parser = AnsiParser()
        self._keymap = KeyMapper()
        self._font = QFont("Cascadia Mono", 11)
        self._font.setStyleHint(QFont.Monospace)
        self._selection_anchor: tuple[int, int] | None = None
        self._selection_cursor: tuple[int, int] | None = None
        self._is_selecting = False
        self._cursor_visible = True
        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(530)
        self._cursor_timer.timeout.connect(self._blink_cursor)
        self._cursor_timer.start()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.IBeamCursor)
        self.viewport().setCursor(Qt.IBeamCursor)
        self.viewport().setAutoFillBackground(False)
        self._recalculate_grid()

    def append_output(self, data: bytes) -> None:
        self._parser.feed(data, self._buffer)
        self._clear_selection()
        self._reset_cursor_blink()
        self.viewport().update()

    def append_system_message(self, message: str, color: QColor) -> None:
        self._buffer.write_text(f"\r\n{message}\r\n", color)
        self._clear_selection()
        self._reset_cursor_blink()
        self.viewport().update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._recalculate_grid()

    def keyPressEvent(self, event) -> None:
        data = self._keymap.to_bytes(event)
        if data:
            self._clear_selection()
            self.input_requested.emit(data)
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.setFocus(Qt.MouseFocusReason)
            cell = self._point_to_cell(event.position().toPoint())
            self._selection_anchor = cell
            self._selection_cursor = cell
            self._is_selecting = True
            self.viewport().update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_selecting and event.buttons() & Qt.LeftButton:
            self._selection_cursor = self._point_to_cell(event.position().toPoint())
            self.viewport().update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._is_selecting:
            self._selection_cursor = self._point_to_cell(event.position().toPoint())
            self._is_selecting = False
            if self._selection_anchor == self._selection_cursor:
                self._clear_selection()
            self.viewport().update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        copy_action = menu.addAction("Copy")
        copy_action.setEnabled(self._has_selection())
        paste_action = menu.addAction("Paste")
        paste_action.setEnabled(bool(QApplication.clipboard().text()))
        menu.addSeparator()
        clear_action = menu.addAction("Clear Console")

        selected = menu.exec(event.globalPos())
        if selected == copy_action:
            self._copy_selection()
        elif selected == paste_action:
            self._paste_clipboard()
        elif selected == clear_action:
            self._clear_console()
        event.accept()

    def paintEvent(self, event: QPaintEvent) -> None:
        _ = event
        painter = QPainter(self.viewport())
        painter.fillRect(self.viewport().rect(), DEFAULT_BG)
        painter.setFont(self._font)
        self._paint_selection(painter)

        metrics = QFontMetrics(self._font)
        ascent = metrics.ascent()
        for row_index, row in enumerate(self._buffer.visible_cells()):
            y = row_index * self._cell_height + ascent
            for col_index, cell in enumerate(row):
                if cell.char == " ":
                    continue
                painter.setPen(cell.foreground)
                painter.drawText(col_index * self._cell_width, y, cell.char)

        self._paint_cursor(painter)

    def _paint_cursor(self, painter: QPainter) -> None:
        if not self._cursor_visible:
            return
        x = self._buffer.cursor_col * self._cell_width
        y = self._buffer.cursor_row * self._cell_height
        painter.fillRect(x, y, max(2, self._cell_width), self._cell_height, QColor("#eceff4"))

    def _blink_cursor(self) -> None:
        self._cursor_visible = not self._cursor_visible
        self.viewport().update()

    def _reset_cursor_blink(self) -> None:
        self._cursor_visible = True
        self._cursor_timer.start()

    def _recalculate_grid(self) -> None:
        metrics = QFontMetrics(self._font)
        self._cell_width = max(1, metrics.horizontalAdvance("M"))
        self._cell_height = max(1, metrics.height())
        cols = max(20, self.viewport().width() // self._cell_width)
        rows = max(8, self.viewport().height() // self._cell_height)
        self._buffer.resize(cols, rows)
        self._clamp_selection_to_grid()
        self.resized.emit(cols, rows)

    def _point_to_cell(self, point: QPoint) -> tuple[int, int]:
        col = max(0, min(self._buffer.cols - 1, point.x() // self._cell_width))
        row = max(0, min(self._buffer.rows - 1, point.y() // self._cell_height))
        return row, col

    def _normalized_selection(self) -> tuple[tuple[int, int], tuple[int, int]] | None:
        if self._selection_anchor is None or self._selection_cursor is None:
            return None
        start = self._selection_anchor
        end = self._selection_cursor
        if start > end:
            start, end = end, start
        return start, end

    def _has_selection(self) -> bool:
        selection = self._normalized_selection()
        return selection is not None and selection[0] != selection[1]

    def _paint_selection(self, painter: QPainter) -> None:
        selection = self._normalized_selection()
        if selection is None:
            return

        (start_row, start_col), (end_row, end_col) = selection
        painter.setBrush(QColor("#3b4252"))
        painter.setPen(Qt.NoPen)
        for row in range(start_row, end_row + 1):
            left_col = start_col if row == start_row else 0
            right_col = end_col if row == end_row else self._buffer.cols - 1
            painter.drawRect(
                left_col * self._cell_width,
                row * self._cell_height,
                (right_col - left_col + 1) * self._cell_width,
                self._cell_height,
            )

    def _selected_text(self) -> str:
        selection = self._normalized_selection()
        if selection is None:
            return ""

        (start_row, start_col), (end_row, end_col) = selection
        lines = self._buffer.visible_lines()
        selected_lines: list[str] = []
        for row in range(start_row, end_row + 1):
            line = lines[row]
            left_col = start_col if row == start_row else 0
            right_col = end_col if row == end_row else self._buffer.cols - 1
            selected_lines.append(line[left_col : right_col + 1].rstrip())
        return "\n".join(selected_lines)

    def _copy_selection(self) -> None:
        text = self._selected_text()
        if text:
            QApplication.clipboard().setText(text)

    def _paste_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if text:
            self._clear_selection()
            self.input_requested.emit(text.encode("utf-8"))

    def _clear_console(self) -> None:
        self._buffer.clear_console()
        self._clear_selection()
        self._reset_cursor_blink()
        self.viewport().update()

    def _clear_selection(self) -> None:
        self._selection_anchor = None
        self._selection_cursor = None
        self._is_selecting = False

    def _clamp_selection_to_grid(self) -> None:
        if self._selection_anchor is not None:
            self._selection_anchor = self._clamp_cell(self._selection_anchor)
        if self._selection_cursor is not None:
            self._selection_cursor = self._clamp_cell(self._selection_cursor)

    def _clamp_cell(self, cell: tuple[int, int]) -> tuple[int, int]:
        row, col = cell
        return (
            max(0, min(self._buffer.rows - 1, row)),
            max(0, min(self._buffer.cols - 1, col)),
        )
