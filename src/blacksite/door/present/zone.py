"""P5 rule drawing and P6 caller-masked places, with shared geometry.

Tiles, memory and the chart decide known ground. Live overlays require
the current view. Optional looks dress that ground; missing looks retain
the P5 tile drawing. Geometry and focus remain their shared contracts.
"""

from typing import Any

from blacksite.door.cells import CellBuffer, clean_text, display_width, truncate
import re
from blacksite.door.layout import Layout
from blacksite.door.palette import Style
from blacksite.door.present import chrome
from blacksite.door.present.places import for_frame
from blacksite.door.present.paint import Paint
from blacksite.place import CHARTED_GROUND

# Things you can use: one fixed shape and one colour family per kind.
THINGS = {"terminal": ("§", "thing_terminal"), "descent_console": ("§", "thing_terminal"),
          "vendor": ("$", "thing_vendor"), "bank": ("$", "thing_vendor"), "hardware": ("■", "thing_hardware"),
          "door": ("+", "thing_door"), "apartment_door": ("+", "thing_door"), "gate": ("+", "thing_door"),
          "shutter": ("+", "thing_door"), "relay": ("Ω", "thing_terminal"), "light": ("☼", "thing_light"),
          "vat": ("Θ", "thing_vat"), "cache": ("*", "thing_vendor"), "beacon": ("♦", "player_crew"),
          "exit": ("»", "thing_exit"), "hazard": ("‼", "thing_hazard")}
TILE_ROLES = {"wall": "wall", "door": "thing_door", "locked-door": "thing_door", "terminal": "thing_terminal",
              "relay": "thing_terminal", "exit": "thing_exit", "hazard": "thing_hazard", "vendor": "thing_vendor",
              "vat": "thing_vat", "light": "thing_light", "hardware": "thing_hardware",
              "cover-1": "thing_cover", "cover-2": "thing_cover", "cover-3": "thing_cover"}
TAGS = {"!": "hostile", "~": "neutral", "+": "ally"}
OPAQUE = frozenset(('wall', 'locked-door'))  # Shipped opaque rule-tile classes; tested against content.


def _beside(ids: list[list[str]], x: int, y: int, wanted: frozenset[str]) -> bool:
    """Four disclosed neighbours, without repeated memory/legend resolution."""
    return (x > 0 and ids[y][x - 1] in wanted
            or x + 1 < len(ids[y]) and ids[y][x + 1] in wanted
            or y > 0 and x < len(ids[y - 1]) and ids[y - 1][x] in wanted
            or y + 1 < len(ids) and x < len(ids[y + 1]) and ids[y + 1][x] in wanted)


def origin(body: dict[str, Any], layout: Layout) -> tuple[int, int]:
    """Centre fitting axes once; keep the server's crop on larger axes.

    UI section 2: the server camera already owns the four-tile scroll
    margin and edge clamps. A fitting zone stays still while you walk.
    Every map layer shares this translation; disclosure stays unchanged.
    """
    area, vp = layout.viewport, body['viewport']
    return (area.x + max(0, (area.width - vp['w']) // 2),
            area.y + max(0, (area.height - vp['h']) // 2))


def terrain(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint,
            draw_origin: tuple[int, int] | None = None) -> None:
    """Draw known terrain, optional dressing and currently visible warnings."""
    area, vp = layout.viewport, body['viewport']
    ox, oy = draw_origin if draw_origin is not None else origin(body, layout)
    grid, memory, legend = body['tiles'], body.get('remembered', []), body['legend']
    charted = body.get('charted', [])
    places = for_frame(paint, body)
    target = buffer
    if places:
        geometry = (buffer.width, buffer.height, ox, oy, area.x, area.y, area.width, area.height)
        if places.terrain_geometry != geometry:
            places.terrain_buffer = CellBuffer(buffer.width, buffer.height)
            places.terrain_states.clear()
            places.terrain_geometry = geometry
        target = places.terrain_buffer
    hazards = {tuple(tile) for hazard in body.get('hazards', []) for tile in hazard.get('tiles', [])}

    # Resolve memory/legend indices once. The trial repeated this for every
    # neighbour and dimmed the same style for every remembered floor cell.
    resolved = []
    for y, row in enumerate(grid):
        recall = memory[y] if y < len(memory) else []
        chart = charted[y] if y < len(charted) else []
        indices = [recall[x] if value == -2 and x < len(recall) and recall[x] >= 0 else
                   chart[x] if value < 0 and x < len(chart) else value for x, value in enumerate(row)]
        resolved.append([index if 0 <= index < len(legend) or index == CHARTED_GROUND else -1 for index in indices])
    ids = [[legend[index]['id'] if index >= 0 else '' for index in row] for row in resolved]
    opaque = frozenset(entry['id'] for entry in legend if entry.get('wall', entry['id'] in OPAQUE))
    open_tiles = frozenset(entry['id'] for entry in legend if entry['id'] not in opaque)
    near_walls = {(x + dx, y + dy) for y, row in enumerate(ids) for x, tile in enumerate(row)
                  if tile in opaque for dx, dy in ((-1,0),(1,0),(0,-1),(0,1))} if places else set()
    styles: dict[tuple[int, bool, bool], tuple[str, Style]] = {}

    for y, row in enumerate(grid[:vp['h']]):
        if not area.y <= oy + y < area.bottom:
            continue
        for x, value in enumerate(row[:vp['w']]):
            if not area.x <= ox + x < area.right:
                continue
            index = resolved[y][x]
            beside_wall = (x,y) in near_walls if places else False
            roof = index >= 0 and legend[index].get('wall', legend[index]['id'] == 'wall') and not _beside(ids, x, y, open_tiles)
            warned = value >= 0 and (vp['x'] + x, vp['y'] + y) in hazards
            if places:
                state = index, roof, value < 0, warned, beside_wall
                if places.terrain_states.get((x,y)) == state:
                    continue
                places.terrain_states[x,y] = state
            if index < 0 and index != CHARTED_GROUND:
                if places:
                    target.put(ox+x,oy+y,' ')
                continue
            # Ground-only carries no tile class or rule shape. It also makes
            # no claim about passability for the neighbouring roof test.
            entry = ({'id': ':charted-ground', 'plain': True, 'ground_only': True}
                     if index == CHARTED_GROUND else legend[index])
            key = index, roof, value < 0
            if key not in styles:
                glyph, style = cell(paint, {'id':'floor'} if index == CHARTED_GROUND else entry, roof=roof)
                styles[key] = glyph, paint.known(style) if value < 0 else style
            glyph, style = styles[key]
            if places:
                glyph, style = places.cell(paint, entry, (vp['x'] + x, vp['y'] + y),
                                           roof=roof, beside_wall=beside_wall, live=value >= 0)
            if warned:
                style = paint('thing_hazard', 'hazard_warn', bold=True, reverse=paint.tier == '16')
            elif value < 0:
                if (paint.tier == '16' and glyph == '·' and (vp['x'] + x + vp['y'] + y) % 3
                        and not (beside_wall if places else _beside(ids, x, y, opaque))):
                    glyph = ' '
            target.put(ox + x, oy + y, glyph, style)
    if places:
        buffer.copy_from(target, area.x, area.y, area.width, area.height)


def cell(paint: Paint, entry: dict[str, Any], *, roof: bool = False) -> tuple[str, Style]:
    """UI 2.2. P5 uses generic ground; authored place themes belong to P6."""
    tile = entry['id']
    if tile == 'wall':
        return (' ', paint('wall', 'ground_black')) if roof else (
            ('█', paint('wall')) if paint.tier == '16' else (' ', paint('wall', 'wall_face')))
    if tile == 'floor':
        return '·', paint('floor')
    role = TILE_ROLES.get(tile, entry.get('role', 'panel_text'))
    glyph = '≡' if tile == 'locked-door' else entry['glyph']
    return glyph, paint(role, bold=tile not in ('cover-1', 'cover-2', 'cover-3', 'water'))


def people(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint,
           draw_origin: tuple[int, int] | None = None) -> None:
    area, vp = layout.viewport, body['viewport']
    ox, oy = draw_origin if draw_origin is not None else origin(body, layout)
    relation = {n['id']: n.get('relation', '~') for n in body.get('nearby', [])}
    places = for_frame(paint, body)
    target = (body.get('target') or {}).get('id')

    def inside(entry: dict[str, Any]) -> tuple[int, int] | None:
        x, y = entry['x'] - vp['x'], entry['y'] - vp['y']
        if (0 <= x < vp['w'] and 0 <= y < vp['h']
                and area.x <= ox + x < area.right and area.y <= oy + y < area.bottom):
            return ox + x, oy + y
        return None

    objects = body.get('objects', [])
    for obj in [o for o in objects if o.get('kind') != 'beacon']:
        at = inside(obj)
        if at is None:
            continue
        glyph, role = THINGS.get(obj.get('kind', ''), (obj.get('glyph', '?'), obj.get('role', 'panel_text')))
        state = obj.get('state', {})
        if obj.get('glyph') == '*' or state.get('dropped_item'):
            glyph, role = '*', 'thing_vendor'
        if state.get('enabled') is False:
            role = 'panel_dim'
        elif obj.get('kind') in ('door', 'apartment_door', 'gate', 'shutter') and state.get('open') is False:
            glyph = '≡'
        theme = places.theme((obj['x'], obj['y'])) if places else None
        buffer.put(*at, glyph, paint.on_theme(role, theme, bold=True) if theme else paint(role, bold=True))
    shapes = {'actor-self': '@', 'actor-player': '☺', 'actor-npc': '☻', 'actor-drone': 'τ'}
    for entry in body.get('actors', []):
        at = inside(entry)
        if at is None:
            continue
        self = entry.get('role') == 'player_self'
        glyph_id = entry.get('glyph_id', 'actor-self' if self else 'actor-drone' if entry.get('class') == 'drone'
                             else 'actor-player' if entry.get('class') == 'caller' else 'actor-npc')
        glyph = shapes.get(glyph_id, entry.get('glyph', '?'))
        jacked = entry.get('jacked', False)
        role = entry.get('role', 'npc_neutral')
        style = paint(role, bold=True, reverse=self or relation.get(entry['id']) == '!')
        if jacked:
            style = paint.jacked(paint(role))  # Jacked beats hostile/self: never reverse.
        if places:
            theme = places.theme((entry['x'], entry['y']))
            style = paint.on_theme(role, theme, bold=True, reverse=self or relation.get(entry['id']) == '!', jacked=jacked)
        if entry['id'] == target:
            style = Style(style.fg, style.bg, (*style.attrs, 4), style.tier)
        buffer.put(*at, glyph, style)
    occupied = {(a['x'], a['y']) for a in body.get('actors', [])} | {(o['x'], o['y']) for o in objects}
    occupied.update(tuple(tile) for hazard in body.get('hazards', []) for tile in hazard.get('tiles', []))
    for route in body.get('patrol_routes', []):
        for point in route.get('waypoints', []):
            at = inside(point)
            if at is not None and (point['x'], point['y']) not in occupied:
                buffer.put(*at, '°', paint('log_danger'))
    for obj in [o for o in objects if o.get('kind') == 'beacon']:
        if (at := inside(obj)) is not None:
            buffer.put(*at, '♦', paint('player_crew', bold=True))


def at_hand(body: dict[str, Any]) -> list[str]:
    """#106: P3 focus plus visible adjacent cover only. Never scan objects/exits."""
    names = []
    labels = set()
    for key in ('focus', 'jack_focus'):
        focus = body.get(key)
        if focus and focus.get('label') and focus['label'] not in labels:
            labels.add(focus['label'])
            obj = next((obj for obj in body.get('objects', []) if obj['id'] == focus.get('id')), None)
            if obj:
                shape = THINGS.get(obj.get('kind'), (obj.get('glyph', '■'), ''))[0]
                if obj.get('state', {}).get('open') is False and obj.get('kind') in ('door', 'gate', 'shutter', 'apartment_door'):
                    shape = '≡'
            else:
                shape = '§' if key == 'jack_focus' else '»' if focus.get('id') in body.get('escape', {}).get('routes', []) else '■'
            names.append(shape + ' ' + str(focus['label']))
    me = next((a for a in body.get('actors', []) if a.get('role') == 'player_self'), None)
    if me is None:
        return names
    vp, grid, legend = body['viewport'], body['tiles'], body['legend']
    x, y = me['x'] - vp['x'], me['y'] - vp['y']
    covers = set()
    for cy in range(max(0, y - 1), min(len(grid), y + 2)):
        for cx in range(max(0, x - 1), min(len(grid[cy]), x + 2)):
            value = grid[cy][cx]
            if 0 <= value < len(legend) and legend[value]['id'] in ('cover-1', 'cover-2', 'cover-3'):
                covers.add(legend[value]['id'])
    authored = (body.get('looks') or {}).get('names', {})
    generic = {'cover-1': ('░', 'Light cover'), 'cover-2': ('▒', 'Cover'), 'cover-3': ('▓', 'Heavy cover')}
    names.extend(generic[key][0] + ' ' + authored.get(key, generic[key][1]) for key in sorted(covers))
    return names


def fit_here(text: str, width: int) -> str:
    """Keep the distinguishing suffix when a HERE entry cannot fit (#114).

    Shape and space are retained. Parenthetical place names take priority
    over generic prefixes such as Public terminal; otherwise elide the
    middle so the start and the distinguishing end both survive.
    """
    text = clean_text(text)
    if display_width(text) <= width:
        return text
    shape, _, label = text.partition(' ')
    budget = max(0, width - display_width(shape) - 1)
    match = re.match(r'^(.*?)\s*(\([^)]*\))$', label)
    if match and display_width(match[2]) <= budget:
        suffix = match[2]
        room = budget - display_width(suffix) - 1
        prefix = truncate(match[1], max(0, room))
        return truncate(shape + ' ' + (prefix + ' ' if prefix else '') + suffix, width)
    if budget <= 3:
        return truncate(text, width)
    # Slice by measured cells, including wide-character names.
    tail = ''
    tail_room = (budget - 3 + 1) // 2
    for ch in reversed(label):
        if display_width(ch + tail) > tail_room:
            break
        tail = ch + tail
    return shape + ' ' + truncate(label, budget - display_width(tail) - 3, ellipsis=False) + '...' + tail


def panel(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint) -> None:
    """HERE, TARGET, NEARBY, CREW; vitals pinned to the bottom (spec 6.2)."""
    x, w = layout.side.x, layout.side.width
    top, bottom = layout.side.y, layout.side.y + layout.side.height - 1
    me = body["me"]
    wide = layout.height >= 40
    has_sheet = me.get("grade") is not None
    vitals = (6 if wide else 5) if has_sheet else 4
    vy = bottom - vitals + 1
    y = top
    crew = body.get('crew', [])
    # UI 2: reserve a target and one crew member before optional nearby rows.
    crew_reserve = 3 if crew else 0
    target_reserve = 4 if body.get('target') else 2
    limit = vy - 1 - crew_reserve - target_reserve
    active = False

    def line(text: str, role: str = "panel_text", indent: int = 1, *, bold: bool = False) -> None:
        nonlocal y
        if active and y < limit:
            buffer.put(x + indent, y, truncate(text, w - indent), paint(role, bold=bold))
            y += 1

    def section(label: str, role: str = "panel_label") -> None:
        nonlocal y, active
        active = y < limit - 1
        if active:
            chrome.rule(buffer, layout, paint, y, label, role)
            y += 1

    for hazard in body.get("hazards", [])[:1]:
        section("DANGER", "log_danger")
        line(f"‼ warning {hazard.get('warning', 0):.1f}s", "log_danger", bold=True)
        line("out: " + ", ".join(hazard.get("escape", [])) if hazard.get("escape") else "move off the marked ground", "panel_text")
    plans = [str(plan["summary"]) for plan in (body.get("event") or {}).get("plans", [])]
    objective = body.get("objective")
    if plans or objective and layout.wide:
        section("NOW")
        for text in plans[:2]:
            line(text, "log_place")
        if objective and layout.wide:
            line(str(objective.get("next_action", "")), "panel_strong")
            if objective.get("cost") and layout.height >= 30:
                line(str(objective["cost"]), "panel_label")
    hand = at_hand(body)
    if hand:
        section("HERE")
        for name in hand:
            line(fit_here(name, w - 1), "panel_text")
    limit += target_reserve
    target = body.get("target")
    section("TARGET")
    if target:
        tag = TAGS.get({"hostile": "!", "allied": "+"}.get(target.get("relation", ""), "~"), "neutral")
        line(target["name"], target.get("name_role", "panel_text"), bold=True)
        if y < limit:
            health = f"{target['hp']:g}" if "hp" in target else f"{target.get('hp_percent', target.get('hp_pct', 0))}%"
            chrome.bar(buffer, paint, x + 1, y, "HP", target.get("hp_percent", target.get("hp_pct", 0)), 100, "bar_hp", health, width=10)
            y += 1
        cover = {0: "open", 1: "light cover", 2: "cover", 3: "heavy cover"}.get(target.get("cover", 0), "cover")
        line(f"{target['range']:g} m  {cover}  {tag}", "panel_label")
        if target.get("warning"):
            line(target["warning"], "log_danger")
        if me.get("weapon") and me["weapon"] != "None":
            line("with " + me["weapon"], "panel_label")
    else:
        line("none   Tab picks", "panel_dim")
    nearby = body.get("nearby", [])
    if nearby and y < limit - 2:
        section("NEARBY")
        actors = {a['id']: a for a in body.get('actors', [])}
        for entry in nearby:
            if y >= limit:
                break
            actor = actors.get(entry['id'], {})
            glyph = {'actor-drone': 'τ', 'actor-player': '☺'}.get(actor.get('glyph_id'), '☻')
            hostile = entry.get("relation") == "!"
            jacked = entry.get('jacked', False)
            style = paint(entry.get('role', 'npc_neutral'), bold=True, reverse=hostile and not jacked)
            if jacked:
                style = paint.jacked(paint(entry.get('role', 'npc_neutral')))
            buffer.put(x + 1, y, glyph, style)
            relation = entry.get('relation', '~')
            relation = relation if relation in TAGS else '~'
            suffix = (' jacked' if jacked else '') + ' ' + relation
            label = truncate(entry.get('name', 'Someone'), w - 4 - len(suffix)) + suffix
            buffer.put(x + 3, y, label, paint("log_danger" if hostile else "panel_text"))
            y += 1
    limit = vy - 1
    if crew and y < limit - 1:
        section("CREW")
        for member in crew:
            suffix = f" {member['hp_pct']}%" + (' jacked' if member.get('jacked') else '')
            mark = "♦" if member.get("beacon") else "+" if member.get("leader") else " "
            line(mark + truncate(member["name"], w - 3 - len(suffix)) + suffix, "player_crew")
            line("  " + str(member["zone"]), "panel_label")
    chrome.rule(buffer, layout, paint, vy - 1)
    name = me.get("name", me.get("handle", ""))
    if me.get("handle") and me["handle"] != name and wide:
        name = f"{name} · {me['handle']}"
    buffer.put(x + 1, vy, truncate(name, w - 6), paint(me.get("name_role", "panel_strong") if paint.has(me.get("name_role", "")) else "panel_strong", bold=True))
    if has_sheet:
        buffer.put(x + w - 4, vy, f"G{me['grade']}", paint("panel_label"))
    chrome.bar(buffer, paint, x + 1, vy + 1, "HP", me["hp"], me["hp_max"], "bar_hp" if me["hp"] > me["hp_max"] // 3 else "bar_trace", f"{int(me['hp'])}")
    chrome.bar(buffer, paint, x + 1, vy + 2, "STA", me["sta"], me["sta_max"], "bar_sta", f"{int(me['sta'])}")
    chrome.bar(buffer, paint, x + 1, vy + 3, "SHK", me.get("shock", 0), 100, "bar_shock", f"{me.get('shock', 0):g}")
    if has_sheet:
        buffer.put(x + 1, vy + 4, truncate(f"{me['chits']} ch", 9), paint("panel_text"))
        buffer.put(x + 10, vy + 4, f"lease {me['lease_days']}/90", paint("panel_label"))
        if wide:
            buffer.put(x + 1, vy + 5, truncate(f"discharge {me['xp']}/{me['discharge_xp']}", w - 1), paint("panel_label"))


def head(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint, *,
         notice: tuple[str, str, float] | None = None) -> None:
    me = body['me']
    safety = me['safety']
    left = [(me['zone_name'], 'head_zone'), (safety.upper(), 'word_' + safety)]
    if safety == 'contested':
        left.append(('PvP G5+', 'head_info'))
    if me.get('heat_until'):
        left.append(('HEAT', 'log_danger'))
    if me.get('marked_until'):
        left.append(('MARKED', 'log_danger'))
    if me.get('district'):
        left.append((str(me['district']).upper(), 'head_district'))
    if service := body.get('service'):
        left.append((str(service.get('summary', '')), 'head_info'))
    chrome.header(buffer, layout, paint, left, [(me.get('clock', ''), 'head_info')], notice=notice)


def render(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint, *,
           notice: tuple[str, str, float] | None = None) -> None:
    draw_origin = origin(body, layout)
    terrain(buffer, body, layout, paint, draw_origin)
    people(buffer, body, layout, paint, draw_origin)
    panel(buffer, body, layout, paint)
    head(buffer, body, layout, paint, notice=notice)
