"""Independent ANSI replay model: reject writes into the autowrap corner."""

import codecs
import re
import unicodedata


class FakeTerminal:
    def __init__(self, width: int = 80, height: int = 24) -> None:
        self.width, self.height = width, height
        self.grid = [[" " for _ in range(width)] for _ in range(height)]
        self.styles: dict[tuple[int, int], str] = {}
        self.x = self.y = 0
        self.pending = ""
        self.decoder = codecs.getincrementaldecoder("utf-8")()
        self.written = bytearray()
        self.style = "0"
        self.cursor_visible = True

    def write(self, data: bytes) -> None:
        self.written.extend(data)
        self.pending += self.decoder.decode(data)
        while self.pending:
            if self.pending.startswith("\x1b"):
                match = re.match(r"\x1b\[([0-?]*)([ -/]*)([@-~])", self.pending)
                if match is None:
                    if len(self.pending) > 128:
                        raise AssertionError("unsafe escape output")
                    return
                args, _, final = match.groups()
                self.pending = self.pending[match.end():]
                if final in ("H", "f"):
                    parts = [int(value or 1) for value in args.split(";")]
                    self.y = parts[0] - 1
                    self.x = (parts[1] if len(parts) > 1 else 1) - 1
                elif final == "m":
                    self.style = args
                elif final == "J" and args == "2":
                    self.grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
                elif final in ("h", "l") and args == "?25":
                    self.cursor_visible = final == "h"
                elif final not in ("h", "l"):
                    raise AssertionError(f"unexpected output sequence {match.group()!r}")
                continue
            ch, self.pending = self.pending[0], self.pending[1:]
            if ch == "\r":
                self.x = 0
                continue
            if ch == "\n":
                self.y = min(self.height - 1, self.y + 1)
                continue
            if ord(ch) < 32 or 0x7f <= ord(ch) < 0xa0:
                raise AssertionError("control character reached terminal")
            if unicodedata.combining(ch) or unicodedata.category(ch) in ("Mn", "Me"):
                previous = self.x - 1
                if previous >= 0:
                    if not self.grid[self.y][previous]:
                        previous -= 1
                    self.grid[self.y][previous] += ch
                continue
            size = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
            if self.x >= self.width:
                self.x = 0
                self.y += 1
            assert 0 <= self.y < self.height and 0 <= self.x < self.width
            assert self.x + size <= self.width
            assert not (self.y == self.height - 1 and self.x + size == self.width), "bottom-right cell written"
            self.grid[self.y][self.x] = ch
            self.styles[(self.x, self.y)] = self.style
            if size == 2:
                self.grid[self.y][self.x + 1] = ""
            self.x += size

    def cell(self, x: int, y: int) -> str:
        return self.grid[y][x]

    def screen_text(self) -> str:
        return "\n".join("".join(row) for row in self.grid)
