"""Generic view rendering interface, extended by S06 and S13."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from blacksite.door.cells import CellBuffer, clean_text, display_width, truncate
from blacksite.door.chrome import box, render_frame
from blacksite.door.layout import Layout, Rect
from blacksite.door.palette import Palette

Renderer = Callable[[CellBuffer, dict[str, Any], Layout, Palette], None]


def render_text(buffer: CellBuffer, body: dict[str, Any], layout: Layout, palette: Palette) -> None:
    area, text_area = layout.viewport, layout.text_area
    buffer.put(text_area.x, area.y, truncate(str(body.get("title", "")), text_area.width), palette.style("title"))
    for index, line in enumerate(body.get("lines", [])[:text_area.height]):
        text = line.get("text", "") if isinstance(line, dict) else str(line)
        role = line.get("role", "text") if isinstance(line, dict) else "text"
        buffer.put(text_area.x, text_area.y + index, truncate(text, text_area.width), palette.style(role))
    if body.get("pages", 1) > 1:
        buffer.put(text_area.x, area.bottom - 1,
                   f"Page {body.get('page', 1)}/{body['pages']}  PgUp/PgDn  Esc back", palette.style("hint"))


def menu_rect(layout: Layout) -> Rect:
    return layout.overlay


def render_menu(buffer: CellBuffer, body: dict[str, Any], layout: Layout, palette: Palette) -> None:
    shape = layout.menu_for(body.get('kind') == 'contracts')
    rows = body.get("rows", [])
    available = shape.listing.height
    columns = body.get("columns", [])
    label = "  ".join(str(c.get("label", c)) if isinstance(c, dict) else str(c) for c in columns)
    buffer.put(shape.columns.x, shape.columns.y, truncate(label, shape.columns.width), palette.style("muted"))
    cursor = body.get("cursor", 0)
    selected_index = cursor if type(cursor) is int else next((i for i, row in enumerate(rows) if row.get("id") == cursor), 0)
    first = max(0, min(len(rows) - max(1, available), selected_index - max(1, available) + 1))
    for index, row in enumerate(rows[first:first + max(0, available)], first):
        text = "  ".join(str(cell) for cell in row.get("cells", []))
        selected = cursor == index or cursor == row.get("id")
        buffer.put(shape.listing.x, shape.listing.y + index - first,
                   truncate(text, shape.listing.width).ljust(shape.listing.width), palette.style("text", reverse=selected))
    for index, line in enumerate(str(body.get("detail", "")).splitlines()[:shape.detail.height]):
        buffer.put(shape.detail.x, shape.detail.y + index, truncate(line, shape.detail.width), palette.style())
    actions = "  ".join(f"{a.get('key', '')} {a.get('label', '')}" for a in body.get("actions", []))
    buffer.put(shape.actions.x, shape.actions.y, truncate(actions + "  Esc/B back", shape.actions.width), palette.style("hint"))


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
