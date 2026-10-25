"""Resolve a zone's dressing to per-tile looks (proposal 68).

A look is colour and lettering only: it never changes what a tile does.
The view sends a look only where it already sends the tile (seen now or
remembered), so dressing reveals nothing that sight has not.
"""

import os
from dataclasses import dataclass
from typing import Any

from blacksite.content import schema as s
from blacksite.content.loader import ContentTree

# Trial switches for the presentation playtest. Off in production: D1
# (charted geography) and D5 (ambient lines) are not approved decisions.
TRIAL = os.environ.get("BLACKSITE_PRESENTATION_TRIAL", "") not in ("", "0")


@dataclass(frozen=True)
class ZoneLooks:
    grid: tuple[tuple[int, ...], ...]
    legend: tuple[dict[str, Any], ...]


def stable(x: int, y: int) -> int:
    return (x * 73856093 ^ y * 19349663) & 0xFFFF


def _theme_at(look: s.Look, themes: dict[str, s.Theme], x: int, y: int) -> s.Theme:
    base = themes[look.theme]
    chosen = base
    for region in look.regions:
        if region.rect is not None:
            rx, ry, rw, rh = region.rect
            inside = rx <= x < rx + rw and ry <= y < ry + rh
        elif region.circle is not None:
            cx, cy, r = region.circle
            inside = (x - cx) ** 2 + ((y - cy) * 2) ** 2 <= (r * 2) ** 2
        else:
            inside = False
        if inside and region.theme in themes:
            over = themes[region.theme]
            chosen = s.Theme(ground_bg=over.ground_bg or chosen.ground_bg, ground_fg=over.ground_fg or chosen.ground_fg,
                             texture=over.texture, wall_bg=over.wall_bg or chosen.wall_bg,
                             wall_fg=over.wall_fg or chosen.wall_fg, luma=over.luma, pattern=over.pattern)
    return chosen


def _grain(theme: s.Theme, x: int, y: int, centre: tuple[float, float]) -> str:
    if theme.pattern == "rings":
        ring = int(max(abs(x - centre[0]) / 2, abs(y - centre[1])))
        return theme.texture[ring % len(theme.texture)] if (x + y) % 2 == 0 else " "
    return theme.texture[stable(x, y) % len(theme.texture)]


def resolve(zone: s.Zone, look: s.Look, themes: dict[str, s.Theme]) -> ZoneLooks:
    signs: dict[tuple[int, int], tuple[str, str]] = {}
    for sign in look.signs:
        for i, char in enumerate(sign.text):
            if zone.tile_at((sign.at[0] + i, sign.at[1])) == "wall":
                signs[(sign.at[0] + i, sign.at[1])] = (char, sign.role)
    marks: dict[tuple[int, int], tuple[str, str]] = {}
    for mark in look.marks:
        if mark.line is not None:
            (ax, ay), (bx, by) = mark.line
            cells = [(x, ay) for x in range(min(ax, bx), max(ax, bx) + 1)] if ay == by else \
                    [(ax, y) for y in range(min(ay, by), max(ay, by) + 1)]
            painted = [(cell, mark.glyph) for cell in cells]
        elif mark.at is not None:
            painted = [((mark.at[0] + i, mark.at[1]), char) for i, char in enumerate(mark.text)]
        else:
            painted = []
        for cell, char in painted:
            if zone.tile_at(cell) == "floor":
                marks[cell] = (char, mark.role)
    glints = set(look.glints)
    rings = [r.rect for r in look.regions if r.rect and themes.get(r.theme, s.Theme()).pattern == "rings"]
    centre = ((rings[0][0] + rings[0][2] / 2 - 0.5), (rings[0][1] + rings[0][3] / 2 - 0.5)) if rings else (0.0, 0.0)
    legend: dict[tuple[Any, ...], int] = {}
    grid = []
    for y, row in enumerate(zone.grid):
        out = []
        for x, tile in enumerate(row):
            theme = _theme_at(look, themes, x, y)
            glyph, fg, bg = "", None, theme.ground_bg
            if tile == "wall":
                bg = theme.wall_bg
                glyph, fg = signs.get((x, y), ("", theme.wall_fg))
            elif tile == "floor":
                glyph, fg = marks.get((x, y), (_grain(theme, x, y, centre), theme.ground_fg))
            elif tile == "water":
                fg = look.glint_role if (x, y) in glints and look.glint_role else theme.ground_fg
            key = (glyph, fg, bg, theme.luma)
            if key not in legend:
                legend[key] = len(legend)
            out.append(legend[key])
        grid.append(tuple(out))
    entries = tuple({k: v for k, v in zip(("g", "fg", "bg"), key[:3]) if v} | ({"light": True} if key[3] == "light" else {})
                    for key in legend)
    return ZoneLooks(tuple(grid), entries)


_CACHE: dict[int, tuple[s.Zone, ZoneLooks | None]] = {}


def for_zone(content: ContentTree, zone: s.Zone) -> ZoneLooks | None:
    """The resolved looks of a template, cached while that template lives."""
    cached = _CACHE.get(id(zone))
    if cached is not None and cached[0] is zone:
        return cached[1]
    look = content.looks.get(zone.id)
    themes = content.themes.themes if content.themes else {}
    resolved = resolve(zone, look, themes) if look is not None and look.theme in themes else None
    if len(_CACHE) > 256:
        _CACHE.clear()
    _CACHE[id(zone)] = (zone, resolved)
    return resolved


def charted(content: ContentTree, zone: s.Zone) -> bool:
    look = content.looks.get(zone.id)
    return TRIAL and look is not None and look.charted
