from __future__ import annotations

from app.ui.terminal.ansi_parser import AnsiParser
from app.ui.terminal.terminal_buffer import TerminalBuffer


def _parse_chunks(*chunks: bytes, cols: int = 80, rows: int = 5) -> TerminalBuffer:
    parser = AnsiParser()
    buffer = TerminalBuffer(cols=cols, rows=rows)
    for chunk in chunks:
        parser.feed(chunk, buffer)
    return buffer


def _line(buffer: TerminalBuffer, index: int = 0) -> str:
    return buffer.all_lines()[index]


def test_sgr_8_16_color_and_style() -> None:
    buffer = _parse_chunks(b"\x1b[31mred\x1b[0m normal \x1b[1;4;93mbright\x1b[0m")
    cells = buffer.visible_cells()[0]

    assert _line(buffer).startswith("red normal bright")
    assert cells[0].foreground.name().lower() == "#cd3131"
    assert cells[3].foreground.name().lower() == "#d8dee9"
    assert cells[11].bold is True
    assert cells[11].underline is True
    assert cells[11].foreground.name().lower() == "#f5f543"


def test_sgr_256_color_and_truecolor() -> None:
    buffer = _parse_chunks(
        b"\x1b[38;5;196mred256\x1b[0m "
        b"\x1b[48;5;27mbluebg\x1b[0m "
        b"\x1b[38;2;255;128;0morange\x1b[0m "
        b"\x1b[48;2;1;2;3mbgtrue\x1b[0m"
    )
    cells = buffer.visible_cells()[0]

    assert _line(buffer).startswith("red256 bluebg orange bgtrue")
    assert cells[0].foreground.name().lower() == "#ff0000"
    assert cells[7].background.name().lower() == "#005fff"
    assert cells[14].foreground.name().lower() == "#ff8000"
    assert cells[21].background.name().lower() == "#010203"
    assert cells[27].background.name().lower() == "#111318"


def test_csi_cursor_and_erase_modes() -> None:
    buffer = _parse_chunks(b"abcde\r\x1b[3GZ")
    assert _line(buffer).startswith("abZde")

    buffer = _parse_chunks(b"line1\nline2\n\x1b[sSAVED\n\x1b[uX")
    assert _line(buffer, 2).startswith("XAVED")

    buffer = _parse_chunks(b"abcdef\n123456\nXYZ\x1b[2;3H\x1b[J", cols=10, rows=4)
    assert _line(buffer, 0).startswith("abcdef")
    assert _line(buffer, 1).startswith("12")
    assert not _line(buffer, 1)[2:].strip()
    assert not _line(buffer, 2).strip()

    buffer = _parse_chunks(b"abcdef\n123456\nXYZ\x1b[2;3H\x1b[1J", cols=10, rows=4)
    assert not _line(buffer, 0).strip()
    assert _line(buffer, 1).startswith("   456")
    assert _line(buffer, 2).startswith("XYZ")

    buffer = _parse_chunks(b"abcdef\r\x1b[3G\x1b[2K", cols=10, rows=2)
    assert not _line(buffer).strip()


def test_incomplete_csi_across_chunks_does_not_render_control_text() -> None:
    buffer = _parse_chunks(b"plain \x1b[", b"31", b"mred\x1b[0", b"m normal")
    cells = buffer.visible_cells()[0]

    assert _line(buffer).startswith("plain red normal")
    assert "\x1b" not in _line(buffer)
    assert cells[6].foreground.name().lower() == "#cd3131"
    assert cells[9].foreground.name().lower() == "#d8dee9"


def test_osc_across_chunks_is_skipped() -> None:
    buffer = _parse_chunks(b"before\x1b]0;", b"title", b"\x1b\\after")

    assert _line(buffer).startswith("beforeafter")
    assert "title" not in _line(buffer)
