"""Generic view rendering interface, extended by S06 and S13."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from blacksite.door.cells import CellBuffer, clean_text, display_width, truncate
from blacksite.door.layout import Layout, Rect
from blacksite.door.palette import Palette
from blacksite.door.log import rows as log_rows

Renderer = Callable[[CellBuffer, dict[str, Any], Rect, Palette], None]


def box(buffer: CellBuffer, rect: Rect, palette: Palette, title: str = "") -> None:
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    style = palette.style("border")
    buffer.fill(x, y, w, h, palette.style())
    buffer.put(x, y, "┌" + "─" * (w - 2) + "┐", style)
    buffer.put(x, y + h - 1, "└" + "─" * (w - 2) + "┘", style)
    for row in range(y + 1, y + h - 1):
        buffer.put(x, row, "│", style)
        buffer.put(x + w - 1, row, "│", style)
    if title:
        buffer.put(x + 2, y, truncate(" " + title + " ", w - 4), palette.style("title"))


def render_text(buffer: CellBuffer, body: dict[str, Any], area: Rect, palette: Palette) -> None:
    buffer.put(area.x + 1, area.y, truncate(str(body.get("title", "")), area.width - 2), palette.style("title"))
    lines = body.get("lines", [])
    for index, line in enumerate(lines[:max(0, area.height - 2)]):
        text = line.get("text", "") if isinstance(line, dict) else str(line)
        role = line.get("role", "text") if isinstance(line, dict) else "text"
        buffer.put(area.x + 1, area.y + index + 1, truncate(text, area.width - 2), palette.style(role))
    if body.get("pages", 1) > 1:
        buffer.put(area.x + 1, area.y + area.height - 1,
                   f"Page {body.get('page', 1)}/{body['pages']}  PgUp/PgDn  Esc back", palette.style("hint"))


def menu_rect(layout: Layout) -> Rect:
    width = min(layout.width - 6, 70 if layout.width < 100 else 110)
    height = min(20 if layout.height == 24 else layout.height - 6, layout.viewport.height)
    return Rect((layout.width - width) // 2, 1 + (layout.viewport.height - height) // 2, width, height)


def render_menu(buffer: CellBuffer, body: dict[str, Any], area: Rect, palette: Palette) -> None:
    box(buffer, area, palette, str(body.get("title", "")))
    right = buffer.width >= 100
    list_width = (area.width - 5) // 2 if right else area.width - 4
    rows = body.get("rows", [])
    available = area.height - (5 if right else 9)
    columns = body.get("columns", [])
    label = "  ".join(str(c.get("label", c)) if isinstance(c, dict) else str(c) for c in columns)
    buffer.put(area.x + 2, area.y + 1, truncate(label, list_width), palette.style("muted"))
    cursor = body.get("cursor", 0)
    selected_index = cursor if type(cursor) is int else next((i for i, row in enumerate(rows) if row.get("id") == cursor), 0)
    first = max(0, min(len(rows) - max(1, available), selected_index - max(1, available) + 1))
    for index, row in enumerate(rows[first:first + max(0, available)], first):
        cells = row.get("cells", [])
        text = "  ".join(str(cell) for cell in cells)
        selected = cursor == index or cursor == row.get("id")
        buffer.put(area.x + 2, area.y + 2 + index - first, truncate(text, list_width).ljust(list_width),
                   palette.style("text", reverse=selected))
    detail = str(body.get("detail", ""))
    dx = area.x + list_width + 3 if right else area.x + 2
    dy = area.y + 1 if right else area.y + max(3, area.height - 6)
    dw = area.width - list_width - 5 if right else area.width - 4
    for index, line in enumerate(detail.splitlines()[:max(0, area.y + area.height - 2 - dy)]):
        buffer.put(dx, dy + index, truncate(line, dw), palette.style())
    actions = "  ".join(f"{a.get('key', '')} {a.get('label', '')}" for a in body.get("actions", []))
    buffer.put(area.x + 2, area.y + area.height - 2, truncate(actions + "  Esc/B back", area.width - 4), palette.style("hint"))


def render_frame(buffer: CellBuffer, layout: Layout, palette: Palette, header: str,
                 lines: list[dict[str, Any]], hint: str) -> None:
    box(buffer, Rect(0, 0, layout.width, layout.height), palette, truncate(header, layout.width - 8))
    style = palette.style("border")
    buffer.put(0, layout.separator, "├" + "─" * (layout.width - 2) + "┤", style)
    for y in range(1, layout.separator):
        buffer.put(layout.side.x - 1, y, "│", style)
    for index, line in enumerate(log_rows(lines[-layout.log.height:], layout.log.width)[-layout.log.height:]):
        buffer.put(layout.log.x, layout.log.y + index, line["text"], palette.style(line["role"]))
    buffer.put(1, layout.hint, truncate(hint, layout.width - 2), palette.style("hint"))


@dataclass
class LinePrompt:
    id: str
    label: str
    max_len: int = 200
    text: str = ""

    def key(self, key: str) -> tuple[bool, str | None]:
        if key == "escape":
            return True, None
        if key == "enter":
            return True, self.text
        if key == "backspace":
            self.text = self.text[:-1]
        elif key == "ctrl-u":
            self.text = ""
        elif len(key) == 1 and clean_text(key) == key and len(self.text + key) <= self.max_len and display_width(self.text + key) <= min(200, self.max_len):
            self.text += key
        return False, None
