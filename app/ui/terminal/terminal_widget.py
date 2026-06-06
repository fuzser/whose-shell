from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractScrollArea

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
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.IBeamCursor)
        self.viewport().setAutoFillBackground(False)
        self._recalculate_grid()

    def append_output(self, data: bytes) -> None:
        self._parser.feed(data, self._buffer)
        self.viewport().update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._recalculate_grid()

    def keyPressEvent(self, event) -> None:
        data = self._keymap.to_bytes(event)
        if data:
            self.input_requested.emit(data)
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        _ = event
        painter = QPainter(self.viewport())
        painter.fillRect(self.viewport().rect(), DEFAULT_BG)
        painter.setFont(self._font)
        painter.setPen(DEFAULT_FG)

        metrics = QFontMetrics(self._font)
        ascent = metrics.ascent()
        for row_index, line in enumerate(self._buffer.visible_lines()):
            y = row_index * self._cell_height + ascent
            painter.drawText(0, y, line.rstrip())

        self._paint_cursor(painter)

    def _paint_cursor(self, painter: QPainter) -> None:
        x = self._buffer.cursor_col * self._cell_width
        y = self._buffer.cursor_row * self._cell_height
        painter.fillRect(x, y, max(2, self._cell_width), self._cell_height, QColor("#eceff4"))

    def _recalculate_grid(self) -> None:
        metrics = QFontMetrics(self._font)
        self._cell_width = max(1, metrics.horizontalAdvance("M"))
        self._cell_height = max(1, metrics.height())
        cols = max(20, self.viewport().width() // self._cell_width)
        rows = max(8, self.viewport().height() // self._cell_height)
        self._buffer.resize(cols, rows)
        self.resized.emit(cols, rows)

