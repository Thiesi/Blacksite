"""Entities 1.21 and UI 2.2: reject misleading or unreadable dressing."""

from dataclasses import asdict
import re
import unicodedata
from collections.abc import Callable

from blacksite.content import schema as s
from blacksite.content.ids import display_width, valid_id
from blacksite.content.loader import ContentTree
from blacksite.content.places import DEFAULT_THEME, mark_cells, plain, region_tiles, theme_over, wall, water
from blacksite.door.palette import Palette
from blacksite.door.present.paint import BAND_STEP, Paint, light_distance

# UI 2.2: decoration may not masquerade as a thing, actor or warning.
RULE_GLYPHS = frozenset('@☺☻τ§Ω$■+≡☼Θ*♦»‼░▒▓≈█')
GRAIN_GLYPHS = frozenset("·∙,'` ")


def dressing(text: str) -> bool:
    return bool(text) and all(display_width(ch) == 1 and not unicodedata.category(ch).startswith('C')
                              and ch not in RULE_GLYPHS for ch in text)


def validate_places(tree: ContentTree, report: Callable[[str, str, str], None]) -> None:
    themes = tree.themes.themes if tree.themes else {}
    roles = tree.palette.roles if tree.palette else {}

    def role_ok(role: str | None, kind: str, rid: str) -> bool:
        if role not in roles:
            report(kind, rid, f'palette role {role!r} does not exist')
            return False
        return True

    def ansi_backgrounds(theme: s.Theme, kind: str, rid: str) -> None:
        for bg in (theme.ground_bg,theme.wall_bg):
            if bg in roles and any(type(n) is not int or not 0<=n<=7
                                   for n in roles[bg].get('16',{}).values()):
                report(kind,rid,'16-colour background must be 0-7')

    def contrast(theme: s.Theme, kind: str, rid: str) -> None:
        if not tree.palette or not all(r in roles for r in (theme.ground_bg, theme.wall_bg)):
            return
        for tier in s.TIERS:
            for variant in s.VARIANTS:
                paint = Paint(Palette(asdict(tree.palette), tier, variant))
                ground, structure, light = paint.roles_for(theme)
                if tier == '16':
                    # TR-1 rule 7: ANSI uses categories, not numeric L*
                    # distances. Things keep their roles, people use P5's
                    # bright mapping, Halvard stays 7 and jacked bodies 8.
                    if paint.palette.style(structure).fg != 8:
                        report(kind, rid, f'16/{variant}: wall foreground must be grey 8')
                    for role in roles:
                        if not role.startswith(('npc_', 'player_', 'thing_')):
                            continue
                        expected = paint(role)
                        if paint.on_theme(role,theme) != expected:
                            report(kind, rid, f'16/{variant}: categorical role mapping fails for {role!r}')
                        if role.startswith(('npc_', 'player_')) and paint.on_theme(role,theme,jacked=True) != paint.jacked(expected):
                            report(kind, rid, f'16/{variant}: categorical jacked mapping fails for {role!r}')
                    continue
                bands = paint.bands_on(ground, structure)
                if bands.structure < BAND_STEP or bands.things < bands.structure + BAND_STEP:
                    report(kind, rid, f'{tier}/{variant}: structure/things contrast fails against theme ground')
                for role in roles:
                    if not role.startswith(('npc_', 'player_')) or role.endswith('_light'):
                        continue
                    chosen = role + '_light' if light or theme.luma == 'light' else role
                    if chosen not in roles:
                        report(kind, rid, f'light theme requires {chosen!r} in every tier and variant')
                        continue
                    style = paint.on_theme(role, theme)
                    if light_distance(style.fg, bands.ground) < bands.people:
                        report(kind, rid, f'{tier}/{variant}: people contrast fails for {chosen!r} against theme ground')

    for tid, theme in themes.items():
        if not valid_id('themes', tid):
            report('themes', tid, 'theme id must be a slug')
        if not theme.texture or any(ch not in GRAIN_GLYPHS for ch in theme.texture):
            report('themes', tid, 'texture must contain only ground grain glyphs')
        for value in (theme.ground_bg, theme.ground_fg, theme.wall_bg, theme.wall_fg):
            if value is not None:
                role_ok(value, 'themes', tid)
        ansi_backgrounds(theme,'themes',tid)
        if theme.ground_bg is not None and theme.wall_bg is not None:
            contrast(theme_over(DEFAULT_THEME, theme), 'themes', tid)

    for zid, look in tree.looks.items():
        zone = tree.zones.get(zid)
        if zone is None:
            report('looks', zid, 'look zone does not exist')
            continue
        if look.theme not in themes:
            report('looks', zid, f'theme {look.theme!r} does not exist')
            continue
        base = theme_over(DEFAULT_THEME, themes[look.theme])
        effective = [base]
        ground_at: dict[s.Tile, s.Theme] = {}
        for region in look.regions:
            if region.theme not in themes:
                report('looks', zid, f'region theme {region.theme!r} does not exist')
                continue
            if (region.rect is None) == (region.circle is None):
                report('looks', zid, 'region needs exactly one rect or circle')
                continue
            if region.rect is not None and (region.rect[2] <= 0 or region.rect[3] <= 0):
                report('looks', zid, 'region rectangle needs positive dimensions')
                continue
            if region.circle is not None and region.circle[2] <= 0:
                report('looks', zid, 'region circle needs a positive radius')
                continue
            if region.rect is not None:
                x, y, w, h = region.rect
                outside = x < 0 or y < 0 or x + w > zone.width or y + h > zone.height
            else:
                x, y, radius = region.circle
                outside = x - 2 * radius < 0 or y - radius < 0 or x + 2 * radius >= zone.width or y + radius >= zone.height
            if outside:
                report('looks', zid, 'region is outside the map')
                continue
            # Check actual ordered overlaps, without exponential combinations
            # of regions that cannot occur at the same tile.
            for at in region_tiles(region):
                if zone.tile_at(at) is not None:
                    ground_at[at] = theme_over(ground_at.get(at, base), themes[region.theme])
        effective.extend(set(ground_at.values()))
        for theme in set(effective):
            contrast(theme, 'looks', zid)
            ansi_backgrounds(theme,'looks',zid)
            for bg in (theme.ground_bg, theme.wall_bg):
                role_ok(bg,'looks',zid)

        def tile_type(at: s.Tile) -> s.TileType | None:
            return tree.tiles.get(zone.tile_at(at))

        for sign in look.signs:
            good_role = role_ok(sign.role, 'looks', zid)
            if not sign.role.startswith('thing_'):
                report('looks', zid, 'sign letters require a thing-band role')
            if not dressing(sign.text) or any(not (ch.isalnum() or ch in " .,:;'\"-/()") for ch in sign.text):
                report('looks', zid, 'sign uses a rule glyph or non-letter dressing')
            cells = [(sign.at[0] + i, sign.at[1]) for i in range(len(sign.text))]
            for at in cells:
                tile = tile_type(at)
                neighbours = [tile_type((at[0] + dx, at[1] + dy)) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
                if tile is None or not wall(tile) or not any(n and n.passable for n in neighbours):
                    report('looks', zid, 'sign letters must sit on wall-face tiles')
                    break
            if good_role and tree.palette:
                for theme in set(effective):
                    for tier in s.TIERS:
                        for variant in s.VARIANTS:
                            paint = Paint(Palette(asdict(tree.palette), tier, variant))
                            # UI 2.2 mandates a black face behind ANSI letters.
                            bg = 0 if tier == '16' else paint.palette.style(theme.wall_bg).fg
                            if tier == '16':
                                if paint.palette.style(sign.role).fg == bg:
                                    report('looks', zid, f'16/{variant}: sign letters must differ from the black wall background')
                                continue
                            if light_distance(paint.palette.style(sign.role).fg, bg) < BAND_STEP:
                                report('looks', zid, f'{tier}/{variant}: sign contrast fails against wall face')
        for mark in look.marks:
            role_ok(mark.role, 'looks', zid)
            points = [mark.at] if mark.at is not None else list(mark.line or ())
            if any(zone.tile_at(at) is None for at in points):
                report('looks', zid, 'mark is outside the map')
                continue
            if ((mark.at is None) == (mark.line is None) or not mark_cells(mark)
                    or mark.line is not None and (mark.text or len(mark.glyph) != 1)
                    or mark.at is not None and (mark.glyph or not mark.text)):
                report('looks', zid, 'mark needs text at a tile or one straight glyph line')
            for at, ch in mark_cells(mark):
                tile = tile_type(at)
                if ch == ' ' and any((other := tile_type((at[0]+dx, at[1]+dy))) and wall(other)
                                     for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))):
                    report('looks', zid, f'mark space at {at} borders a wall; move that space off wall-adjacent ground')
                if any(ex.hidden and ex.tile == at for ex in zone.meta.exits):
                    report('looks', zid, 'a hidden exit must never carry floor paint')
                if not dressing(ch) or tile is None or not plain(tile):
                    report('looks', zid, 'marks must use dressing glyphs on plain passable floor')
                    break
        if look.glints:
            role_ok(look.glint_role, 'looks', zid)
        for at in look.glints:
            tile = tile_type(at)
            if tile is None or not water(tile):
                report('looks', zid, 'glints must lie on water')
        for tid, name in look.names.items():
            if tid not in tree.tiles or not dressing(name):
                report('looks', zid, 'names must label existing tiles with safe text')
        for line in look.ambient:
            if (not line or len(line) > 200 or '—' in line or any(unicodedata.category(ch).startswith('C') for ch in line)
                    or re.search(r'\b(cyberpunk|hackers?|cyberspace)\b', line, re.I)):
                report('looks', zid, 'ambient violates voice rules (safe text, 200 characters, no em-dash or banned terms)')
