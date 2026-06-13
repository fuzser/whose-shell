from __future__ import annotations


class CommandInputCapture:
    """从终端输入字节流中提取已提交的单行命令."""

    def __init__(self) -> None:
        self._buffer = ""
        self._escape_pending = False

    def feed(self, data: bytes) -> list[str]:
        """处理输入字节, 返回本次提交的命令列表."""
        commands: list[str] = []
        text = data.decode("utf-8", errors="ignore")
        for char in text:
            if self._escape_pending:
                self._escape_pending = self._consume_escape(char)
                continue
            if char == "\x1b":
                self._escape_pending = True
                continue
            if char in {"\r", "\n"}:
                command = self._buffer.strip()
                self._buffer = ""
                if command:
                    commands.append(command)
                continue
            if char in {"\x03", "\x15"}:
                self._buffer = ""
                continue
            if char in {"\x08", "\x7f"}:
                self._buffer = self._buffer[:-1]
                continue
            if char == "\t" or char < " ":
                continue
            self._buffer += char
        return commands

    def _consume_escape(self, char: str) -> bool:
        """跳过方向键等 ANSI 输入序列, 避免把控制符写入历史."""
        if char == "[":
            return True
        return char.isdigit() or char == ";"
