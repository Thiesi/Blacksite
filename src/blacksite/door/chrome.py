"""The shared frame, view headers, shells and transient chrome.

P2 preserves the existing draw order and glyph/style output. Content
renderers receive Layout and draw only inside their content rectangles.
"""

from typing import Any

from blacksite.layout import Layout, Rect
from blacksite.door.cells import CellBuffer, clean_text, display_width, truncate
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


def _objective_hint(objective: dict[str, Any], width: int | None = None) -> str:
    """UI 11: retain Next, its verb, progress and the server's current cost."""
    action = clean_text(str(objective['next_action'])).strip()
    verb, _, target = action.partition(' ')
    prefix = 'Next: ' + verb
    suffix = f" {objective['progress']} | {objective['cost']}"
    suffix = clean_text(suffix)
    if target and width is not None:
        target = truncate(target, max(0, width-display_width(prefix+' '+suffix)))
    return prefix + (' '+target if target else '') + suffix


def focus_hint(hint: str, width: int, context: list[tuple[str, str]],
               objective: dict[str, Any] | None = None, *,
               fit_all: bool = False, primary: bool = False,
               objective_in_panel: bool = False, escape: str = '') -> str:
    """UI 11: objective/cost, E/J, then whole help groups; never clip a key."""
    raw = '  '.join((prefix + ' ' + label).rstrip() for prefix, label in context)
    if primary:
        # A prompt/channel is one priority field, not optional help groups.
        if escape:
            escape = truncate(clean_text(escape), width)
            field = truncate(clean_text(hint), max(0, width - display_width(escape) - 2))
            return '  '.join(text for text in (field, escape) if text)
        return truncate(clean_text(hint), width)
    if not fit_all and ((not raw and not objective) or raw and not hint.startswith(raw)):
        return hint
    if raw and not hint.startswith(raw):
        context, raw = [], ''
    labels = [clean_text(label).strip() for _, label in context]
    prefixes = [clean_text(prefix) for prefix, _ in context]
    limits = [display_width(label) for label in labels]
    # A shortened name must retain its whole first word and the ellipsis.
    minima = [min(limit, display_width(label.split()[0])+3) if ' ' in label else limit
              for label, limit in zip(labels, limits)]
    objective_group = _objective_hint(objective) if objective and not objective_in_panel else ''

    def fixed_width() -> int:
        groups = [prefix+(' ' if label else '') for prefix, label in zip(prefixes, labels)]
        return display_width('  '.join(([objective_group] if objective_group else [])+groups))

    # Try the shortest legal names before dropping J, then E. The full
    # objective only shortens after both lower-priority groups are gone.
    while prefixes and fixed_width()+sum(minima) > width:
        if len(prefixes) == 1 and prefixes[0].startswith('E/'):
            # A combined group still drops the J alias before its E action.
            prefixes[0] = 'E '+prefixes[0].partition(' ')[2]
            continue
        prefixes.pop()
        labels.pop()
        limits.pop()
        minima.pop()
    if objective and not prefixes and not objective_in_panel:
        objective_group = _objective_hint(objective, width)
    budgets = minima[:]
    available = max(0, width-fixed_width()-sum(budgets))
    for _ in range(available):
        eligible = [i for i in range(len(labels)) if budgets[i] < limits[i]]
        if not eligible:
            break
        index = min(eligible, key=lambda i: budgets[i])
        budgets[index] += 1
    groups = ([objective_group] if objective_group else []) + [(prefix + (' ' + truncate(label, budget) if label else ''))
              for prefix, label, budget in zip(prefixes, labels, budgets)]
    tail = [group for group in hint[len(raw):].strip().split('  ') if group]
    if objective:
        # The legacy objective string also carries its action/journal help.
        # The structured objective above owns the text and unabridged cost.
        tail = ['Q jobs' if 'Next:' in group else group for group in tail]
    tail = ['? help', *(group for group in tail if group != '? help')]
    for group in tail:
        if display_width('  '.join([*groups, group])) <= width:
            groups.append(group)
    return '  '.join(groups)


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
