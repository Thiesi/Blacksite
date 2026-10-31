"""Draw only the place records already disclosed by the server (P6)."""

from dataclasses import dataclass
from typing import Any

from blacksite.place import Theme, DEFAULT_THEME, theme_over
from blacksite.door.palette import Style
from blacksite.door.present.paint import Paint


def stable(x: int, y: int) -> int:
    return (x * 73856093 ^ y * 19349663) & 0xFFFF


@dataclass
class Places:
    look: dict[str, Any]
    viewport: dict[str, int]

    def __post_init__(self) -> None:
        self.base = theme_over(DEFAULT_THEME, Theme(**self.look['theme']))
        self.grounds: dict[tuple[int, int], tuple[Theme, tuple[float, float]]] = {}
        for region in self.look.get('regions', []):
            theme = Theme(**region['theme'])
            if 'rect' in region:
                rx, ry, rw, rh = region['rect']
                centre = rx + (rw - 1) / 2, ry + (rh - 1) / 2
                cells = ((x, y) for y in range(ry, ry + rh) for x in range(rx, rx + rw))
            else:
                cx, cy, radius = region['circle']
                centre = cx, cy
                cells = ((x, y) for y in range(cy - radius, cy + radius + 1)
                         for x in range(cx - radius * 2, cx + radius * 2 + 1)
                         if (x - cx) ** 2 + 4 * (y - cy) ** 2 <= 4 * radius ** 2)
            for at in cells:
                if (self.viewport['x'] <= at[0] < self.viewport['x'] + self.viewport['w']
                        and self.viewport['y'] <= at[1] < self.viewport['y'] + self.viewport['h']):
                    previous = self.grounds.get(at, (self.base, (0., 0.)))[0]
                    self.grounds[at] = theme_over(previous, theme), centre
        self.signs = {(sign['at'][0] + i, sign['at'][1]): (ch, sign['role'])
                      for sign in self.look.get('signs', []) for i, ch in enumerate(sign['text'])}
        self.marks = {(mark['at'][0] + i, mark['at'][1]): (ch, mark['role'])
                      for mark in self.look.get('marks', []) for i, ch in enumerate(mark['text'])}
        self.glints = {tuple(at) for at in self.look.get('glints', [])}
        self.cells: dict[tuple[tuple[int, int], str, bool, bool], tuple[str, Style]] = {}

    def theme(self, at: tuple[int, int]) -> Theme:
        return self.grounds.get(at, (self.base, (0., 0.)))[0]

    def cell(self, paint: Paint, entry: dict[str, Any], at: tuple[int, int], *,
             roof: bool, beside_wall: bool, live: bool) -> tuple[str, Style]:
        # The look and viewport are immutable for this cache. Memory dimming,
        # warnings and live overlays are applied by the caller afterwards.
        key = at, entry.get('id', ''), roof, beside_wall
        if key not in self.cells:
            self.cells[key] = self._cell(paint, entry, at, roof=roof, beside_wall=beside_wall)
        return self.cells[key]

    def _cell(self, paint: Paint, entry: dict[str, Any], at: tuple[int, int], *,
              roof: bool, beside_wall: bool) -> tuple[str, Style]:
        theme, centre = self.grounds.get(at, (self.base, (0., 0.)))
        if entry.get('wall'):
            if roof:
                return ' ', paint(theme.wall_fg, 'ground_black')
            if at in self.signs:
                ch, role = self.signs[at]
                return ch, paint(role, 'ground_black' if paint.tier == '16' else theme.wall_bg)
            return ('█', paint(theme.wall_fg)) if paint.tier == '16' else (' ', paint(theme.wall_fg, theme.wall_bg))
        if entry.get('plain'):
            if paint.tier == '16':
                glyph = '·'
                style = paint('floor')  # UI 2.2 ANSI floor: grey on black.
            else:
                index = stable(*at) if theme.pattern == 'grain' else int(max(abs(at[0] - centre[0]) / 2, abs(at[1] - centre[1])))
                glyph = theme.texture[index % len(theme.texture)]
                style = paint(theme.ground_fg, theme.ground_bg)
            if glyph == ' ' and beside_wall:
                glyph = '·'
            if at in self.marks:
                glyph, role = self.marks[at]
                style = paint(role, 'ground_black' if paint.tier == '16' else theme.ground_bg)
            if glyph == ' ' and beside_wall:
                glyph = '·'  # A painted space cannot erase the wall/floor distinction.
            return glyph, style
        if entry.get('water'):
            role = self.look.get('glint_role') if at in self.glints else entry.get('role', 'water')
            return entry['glyph'], paint(role, 'ground_black' if paint.tier == '16' else theme.ground_bg)
        # Rule glyph and role always win; decoration changes no tile meaning.
        return entry['glyph'], paint(entry.get('role', 'panel_text'), 'ground_black' if paint.tier == '16' else theme.ground_bg, bold=True)


def for_frame(paint: Paint, body: dict[str, Any]) -> Places | None:
    look = body.get('looks')
    if not look:
        return None
    saved = getattr(paint, 'place_cache', None)
    if saved is None or saved.look != look or saved.viewport != body['viewport']:
        saved = Places(look, body['viewport'])
        paint.place_cache = saved
    return saved
