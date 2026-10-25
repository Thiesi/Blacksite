"""The auto view's inspector (F10): what it chose, by which rule, and why.

A development aid. It draws over the bottom of the viewport and never
touches the panel, so DANGER and vitals stay readable underneath it.
"""

from collections.abc import Iterable

from blacksite.door.cells import CellBuffer, truncate
from blacksite.door.layout import Rect
from blacksite.door.present.context import Decision
from blacksite.door.present.paint import Paint


def inputs(decision: Decision) -> str:
    seen = decision.inputs
    parts = [f"safety {seen.get('safety')}", f"places {seen.get('places')}", f"moved {seen.get('moved') or '-'}"]
    if seen.get("threat_age") is not None:
        parts.append(f"threat {seen['threat_age']:.0f} s ago")
    if seen.get("look_left") is not None:
        parts.append(f"look {seen['look_left']:.1f} s")
    return "  ".join(parts)


def render(buffer: CellBuffer, area: Rect, paint: Paint, decision: Decision | None,
           changes: Iterable[tuple[float, Decision]], now: float) -> None:
    if decision is None or area.width < 30 or area.height < 6:
        return
    history = list(changes)
    rows = max(0, min(len(history), area.height // 2 - 4))
    height = 4 + rows
    y0 = area.y + area.height - height
    width = area.width
    fill = paint("panel_text")
    for y in range(y0, y0 + height):
        buffer.put(area.x, y, " " * width, fill)
    title = "─ AUTO, F10 hides "
    buffer.put(area.x, y0, title + "─" * max(0, width - len(title)), paint("panel_rule"))
    head = f" {decision.tag}  rule {decision.rule}"
    buffer.put(area.x, y0 + 1, truncate(head, width), paint("panel_strong", bold=True))
    buffer.put(area.x, y0 + 2, truncate(f"   {decision.why}", width), paint("panel_text"))
    buffer.put(area.x, y0 + 3, truncate(f"   {inputs(decision)}", width), paint("panel_dim"))
    for index, (at, change) in enumerate(history[-rows:] if rows else []):
        line = f" {now - at:5.1f} s ago  {change.tag:<8} {change.rule:<7} {change.why}"
        buffer.put(area.x, y0 + 4 + index, truncate(line, width), paint("panel_label"))
