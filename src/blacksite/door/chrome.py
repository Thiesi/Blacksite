"""The shared frame, view headers, shells and transient chrome.

P2 preserves the existing draw order and glyph/style output. Content
renderers receive Layout and draw only inside their content rectangles.
"""

from typing import Any

from blacksite.layout import Layout, Rect
from blacksite.door.cells import CellBuffer, display_width, truncate
from blacksite.door.palette import Palette
from blacksite.door.log import rows as log_rows


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


def render_frame(buffer: CellBuffer, layout: Layout, palette: Palette, header: str,
                 lines: list[dict[str, Any]], hint: str) -> None:
    box(buffer, layout.frame, palette, truncate(header, layout.header.width))
    style = palette.style("border")
    buffer.put(layout.separator.x, layout.separator.y, "├" + "─" * (layout.separator.width - 2) + "┤", style)
    for y in range(layout.divider.y, layout.divider.bottom):
        buffer.put(layout.divider.x, y, "│", style)
    for index, line in enumerate(log_rows(lines[-layout.log.height:], layout.log.width)[-layout.log.height:]):
        buffer.put(layout.log.x, layout.log.y + index, line["text"], palette.style(line["role"]))
    buffer.put(layout.hint.x, layout.hint.y, truncate(hint, layout.hint.width), palette.style("hint"))


def _zone_header(buffer: CellBuffer, layout: Layout, body: dict[str, Any], palette: Palette) -> None:
    me = body["me"]
    slots = layout.header_slots
    header = f"{me['zone_name']}  "
    buffer.put(slots.zone_title.x, slots.zone_title.y, truncate(header, slots.zone_title.width), palette.style("title"))
    safety = me["safety"].upper()
    sx = min((slots.heat_safety_right if me.get("heat_until") else slots.safety_right) - len(safety), slots.zone_title.x + display_width(header))
    buffer.put(sx, slots.zone_title.y, safety, palette.style("safety_" + me["safety"]))
    if service := body.get('service'):
        start = sx+len(safety)+2
        buffer.put(start, slots.zone_title.y, truncate(service.get('summary', ''), max(0, slots.service_right-start)), palette.style('ui_highlight'))
    buffer.put(slots.clock.x, slots.clock.y, me.get("clock", ""), palette.style("title"))
    if me.get("heat_until"):
        buffer.put(slots.heat.x, slots.heat.y, "HEAT", palette.style("warning"))


def render_view_shell(buffer: CellBuffer, layout: Layout, palette: Palette,
                      kind: str, body: dict[str, Any]) -> None:
    if kind == "menu":
        box(buffer, layout.overlay, palette, str(body.get("title", "")))
    elif kind == "zone":
        _zone_header(buffer, layout, body, palette)
    elif kind == "lattice":
        area = layout.header_slots.lattice_title
        buffer.put(area.x, area.y, truncate(str(body.get("title", "LATTICE")), area.width), palette.style("title"))


def render_effects(buffer: CellBuffer, layout: Layout, palette: Palette,
                   toast: tuple[str, str, float] | None, flashed: bool) -> None:
    if toast:
        buffer.put(layout.log.x, layout.separator.y, truncate(toast[0], layout.log.width), palette.style(toast[1]))
    if flashed:
        for x in range(layout.frame.x, layout.frame.right - 1):
            buffer.put(x, layout.frame.y, "-", palette.style("warning"))
        for y in range(layout.frame.y + 1, layout.frame.bottom - 1):
            buffer.put(layout.frame.x, y, "|", palette.style("warning"))
            buffer.put(layout.frame.right - 1, y, "|", palette.style("warning"))


def cursor(layout: Layout, hint: str, visible: bool) -> bytes:
    if not visible:
        return b"\x1b[?25l"
    column = min(layout.hint.right, layout.hint.x + 1 + display_width(hint))
    return f"\x1b[{layout.hint.y + 1};{column}H\x1b[?25h".encode("ascii")
