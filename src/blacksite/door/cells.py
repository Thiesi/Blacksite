"""Width-safe cells and lazy terminal diffs (terminal UI §6)."""

import re
import unicodedata
from dataclasses import dataclass

from blacksite.door.palette import Style


def clean_text(text: str) -> str:
    if not text or text.isprintable():
        return text
    # Drop escape strings as units, not just their leading control byte.
    text = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\|$)", "", text)
    text = re.sub(r"\x1b[P^_].*?(?:\x1b\\|$)", "", text, flags=re.DOTALL)
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"\x1b(?:[ -/]*[@-~]|.*$)", "", text)
    return "".join(ch for ch in text if not unicodedata.category(ch).startswith("C"))


def cell_width(ch: str) -> int:
    if ord(ch) < 127:
        return 1
    if unicodedata.combining(ch) or unicodedata.category(ch) in ("Mn", "Me"):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def display_width(text: str) -> int:
    text = clean_text(text)
    return len(text) if text.isascii() else sum(cell_width(ch) for ch in text)


def truncate(text: str, width: int, ellipsis: bool = True) -> str:
    text = clean_text(text)
    if display_width(text) <= width:
        return text
    suffix = "." * min(3, max(0, width)) if ellipsis else ""
    budget = max(0, width - len(suffix))
    result = ""
    used = 0
    for ch in text:
        size = cell_width(ch)
        if used + size > budget:
            break
        if size or result:
            result += ch
        used += size
    return result + suffix


@dataclass(frozen=True)
class Cell:
    glyph: str = " "
    style: Style = Style()


class CellBuffer:
    def __init__(self, width: int, height: int, style: Style = Style()) -> None:
        if width < 1 or height < 1:
            raise ValueError("terminal dimensions must be positive")
        self.width, self.height = width, height
        empty = Cell(style=style)
        self.cells = [[empty] * width for _ in range(height)]

    def _clear_glyph(self, x: int, y: int) -> None:
        row = self.cells[y]
        if row[x].glyph == "" and x > 0:
            row[x - 1] = Cell(style=row[x - 1].style)
        elif x + 1 < self.width and row[x + 1].glyph == "":
            row[x + 1] = Cell(style=row[x + 1].style)
        if row[x].glyph != " ":
            row[x] = Cell(style=row[x].style)

    def fill(self, x: int, y: int, width: int, height: int, style: Style = Style()) -> None:
        empty = Cell(style=style)
        for row_index in range(max(0, y), min(self.height, y + height)):
            left = max(0, x)
            right = min(self.width - (row_index == self.height - 1), x + width)
            if left >= right:
                continue
            if self.cells[row_index][left].glyph == "":
                self._clear_glyph(left, row_index)
            if right < self.width and self.cells[row_index][right].glyph == "":
                self._clear_glyph(right, row_index)
            self.cells[row_index][left:right] = [empty] * (right - left)

    def put(self, x: int, y: int, text: str, style: Style = Style()) -> None:
        if not 0 <= y < self.height:
            return
        limit = self.width - (y == self.height - 1)
        text = clean_text(text)
        if text.isascii():
            left, right = max(0, x), min(limit, x + len(text))
            if left < right:
                if self.cells[y][left].glyph == "":
                    self._clear_glyph(left, y)
                if right < self.width and self.cells[y][right].glyph == "":
                    self._clear_glyph(right, y)
                self.cells[y][left:right] = [Cell(ch, style) for ch in text[left - x:right - x]]
            return
        for ch in text:
            size = cell_width(ch)
            if size == 0:
                previous = x - 1
                if 0 <= previous < limit:
                    if self.cells[y][previous].glyph == "":
                        previous -= 1
                    old = self.cells[y][previous]
                    if old.glyph.strip() and len(old.glyph) < 32:
                        self.cells[y][previous] = Cell(old.glyph + ch, old.style)
                continue
            if x + size > limit:
                break
            if x >= 0:
                self._clear_glyph(x, y)
                if size == 2:
                    self._clear_glyph(x + 1, y)
                self.cells[y][x] = Cell(ch, style)
                if size == 2:
                    self.cells[y][x + 1] = Cell("", style)
            x += size

    def copy_from(self, source: "CellBuffer", x: int, y: int, width: int, height: int) -> None:
        """Copy already width-checked cells at the same screen coordinates.

        Cells are immutable. This lets a cached terrain layer be reused
        without re-measuring its strings or sharing mutable row lists.
        Cropped wide glyphs become blanks, and the last terminal cell is
        still excluded, exactly as in put/fill.
        """
        if (source.width, source.height) != (self.width, self.height):
            raise ValueError('cell-buffer copy requires matching dimensions')
        if source is self:
            return
        for row_index in range(max(0, y), min(self.height, y + height)):
            left, right = max(0, x), min(self.width - (row_index == self.height - 1), x + width)
            if left >= right:
                continue
            if self.cells[row_index][left].glyph == '':
                self._clear_glyph(left, row_index)
            if right < self.width and self.cells[row_index][right].glyph == '':
                self._clear_glyph(right, row_index)
            cells = source.cells[row_index][left:right]
            if cells[0].glyph == '':
                cells[0] = Cell(style=cells[0].style)
            if right < source.width and source.cells[row_index][right].glyph == '':
                cells[-1] = Cell(style=cells[-1].style)
            self.cells[row_index][left:right] = cells

    def diff(self, previous: "CellBuffer | None") -> bytes:
        if previous is not None and (previous.width, previous.height) != (self.width, self.height):
            previous = None
        output = bytearray()
        cursor: tuple[int, int] | None = None
        active: Style | None = None
        for y, row in enumerate(self.cells):
            x = 0
            limit = self.width - (y == self.height - 1)
            while x < limit:
                cell = row[x]
                if not cell.glyph or (previous is not None and cell == previous.cells[y][x]):
                    x += 1
                    continue
                end = x
                run: list[str] = []
                while end < limit:
                    next_cell = row[end]
                    if not next_cell.glyph or (next_cell.style is not cell.style and next_cell.style != cell.style):
                        break
                    if previous is not None and next_cell == previous.cells[y][end]:
                        break
                    run.append(next_cell.glyph)
                    end += 1 if ord(next_cell.glyph[0]) < 127 else cell_width(next_cell.glyph[0])
                if cursor != (x, y):
                    output.extend(f"\x1b[{y + 1};{x + 1}H".encode("ascii"))
                if active is not cell.style and active != cell.style:
                    output.extend(cell.style.sgr())
                    active = cell.style
                output.extend("".join(run).encode("utf-8"))
                cursor = (end, y)
                x = end
        return bytes(output)

    def full(self) -> bytes:
        return self.diff(None)

    def screen_text(self) -> str:
        return "\n".join("".join(cell.glyph for cell in row) for row in self.cells)
