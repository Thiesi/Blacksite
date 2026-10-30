"""P5 screen composition from V1 1060c9d, using P2's shared rectangles.

Zone rule drawing is new; Lattice drawing remains its existing renderer
until P7. Every kind shares this frame/header/log/hint. No place card,
scene, street, trial key, threat inference or Toast.full is imported.
"""

from dataclasses import replace
from typing import Any

from blacksite.door.cells import CellBuffer, display_width, truncate
from blacksite.layout import Layout
from blacksite.door.present import chrome, zone
from blacksite.door.present.paint import Paint
from blacksite.door.views import render_text
from blacksite.door.views.lattice import render_lattice


def safety(body: dict[str, Any]) -> str:
    value = body.get('body_safety', body.get('me', {}).get('safety', 'safe'))
    return value if value in ('safe', 'pocket', 'contested', 'open') else 'contested'


def menu(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint) -> None:
    """Trial menu colours, with the existing shared P2 menu geometry."""
    shape = layout.menu_for(body.get('kind') == 'contracts')
    rows, cursor = body.get('rows', []), body.get('cursor', 0)
    label = '  '.join(str(c.get('label', c)) if isinstance(c, dict) else str(c) for c in body.get('columns', []))
    buffer.put(shape.columns.x, shape.columns.y, truncate(label, shape.columns.width), paint('panel_label'))
    selected = cursor if type(cursor) is int else next((i for i, row in enumerate(rows) if row.get('id') == cursor), 0)
    available = shape.listing.height
    first = max(0, min(len(rows) - max(1, available), selected - max(1, available) + 1))
    for index, row in enumerate(rows[first:first + available], first):
        text = truncate('  '.join(str(cell) for cell in row.get('cells', [])), shape.listing.width)
        text += ' ' * (shape.listing.width - display_width(text))
        buffer.put(shape.listing.x, shape.listing.y + index - first, text,
                   paint('panel_text', reverse=cursor == index or cursor == row.get('id')))
    for index, line in enumerate(str(body.get('detail', '')).splitlines()[:shape.detail.height]):
        buffer.put(shape.detail.x, shape.detail.y + index, truncate(line, shape.detail.width), paint('panel_text'))
    actions = '  '.join(f"{a.get('key', '')} {a.get('label', '')}" for a in body.get('actions', []))
    buffer.put(shape.actions.x, shape.actions.y, truncate(actions + '  Esc/B back', shape.actions.width), paint('key_text'))


def render(buffer: CellBuffer, layout: Layout, paint: Paint, kind: str, body: dict[str, Any],
           logs: list[dict[str, Any]], hint: str, now: float, *, flash: bool = False,
           toast: tuple[str, str, float] | None = None, handle: str = '') -> None:
    """Compose all kinds, including nested Wake and talker menus."""
    word = safety(body)
    chrome.frame(buffer, layout, paint, word, side=kind in ('zone', 'lattice'), flash=flash)
    if kind == 'zone':
        zone.render(buffer, body, layout, paint)
    elif kind == 'lattice':
        # P7 replaces sector/room drawing; P5 supplies only the common chrome.
        render_lattice(buffer, body, layout, paint.palette)
    elif kind == 'menu':
        area = layout.overlay
        buffer.fill(area.x, area.y, area.width, area.height, paint('panel_text'))
        style = paint('panel_rule')
        buffer.put(area.x, area.y, '┌' + '─' * (area.width - 2) + '┐', style)
        buffer.put(area.x, area.bottom - 1, '└' + '─' * (area.width - 2) + '┘', style)
        for y in range(area.y + 1, area.bottom - 1):
            buffer.put(area.x, y, '│', style)
            buffer.put(area.right - 1, y, '│', style)
        buffer.put(area.x + 2, area.y, truncate(' ' + str(body.get('title', '')) + ' ', area.width - 4), paint('head_zone', bold=True))
        menu(buffer, body, layout, paint)
    else:
        render_text(buffer, body, replace(layout, text_area=layout.full_text_area), paint.palette)
    if kind != 'zone':
        me = body.get('me', {})
        chrome.header(buffer, layout, paint,
                      [(str(body.get('title', 'Karst')), 'head_zone'), (word.upper(), 'word_' + word)],
                      [(truncate(handle, layout.header_slots.handle_width), 'panel_label'),
                       (str(me.get('clock', '')), 'head_info')])
    chrome.log(buffer, layout, paint, logs, now)
    chrome.hints(buffer, layout, paint, hint)
    if toast:
        buffer.put(layout.log.x, layout.separator.y, truncate(toast[0], layout.log.width), paint(toast[1]))
