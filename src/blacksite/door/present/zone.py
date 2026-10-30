"""P5 zone rule layer, ported from V1 1060c9d with #106 corrections.

Draws only the authorized P4 rule layer. Tiles and memory decide what
exists; live overlays require the current view. Looks, place themes and
charting wait for P6. Geometry and focus remain their shared contracts.
"""

from typing import Any

from blacksite.door.cells import CellBuffer, truncate
from blacksite.door.layout import Layout
from blacksite.door.palette import Style
from blacksite.door.present import chrome
from blacksite.door.present.paint import Paint

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
    """Translate the disclosed viewport once; small axes centre on you.

    Full-size axes keep the server's crop. No camera, focus or world
    coordinate is changed, and every map layer shares this translation.
    """
    area, vp = layout.viewport, body['viewport']
    me = next((entry for entry in body.get('actors', []) if entry.get('role') == 'player_self'), None)
    x, y = area.x, area.y
    if vp['w'] < area.width:
        x += area.width // 2 - (me['x'] - vp['x']) if me else (area.width - vp['w']) // 2
    if vp['h'] < area.height:
        y += area.height // 2 - (me['y'] - vp['y']) if me else (area.height - vp['h']) // 2
    return x, y


def terrain(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint,
            draw_origin: tuple[int, int] | None = None) -> None:
    """Rule layer only. No place records, looks, charting or deep camera."""
    area, vp = layout.viewport, body['viewport']
    ox, oy = draw_origin if draw_origin is not None else origin(body, layout)
    grid, memory, legend = body['tiles'], body.get('remembered', []), body['legend']
    hazards = {tuple(tile) for hazard in body.get('hazards', []) for tile in hazard.get('tiles', [])}

    # Resolve memory/legend indices once. The trial repeated this for every
    # neighbour and dimmed the same style for every remembered floor cell.
    resolved = []
    for y, row in enumerate(grid):
        recall = memory[y] if y < len(memory) else []
        indices = [recall[x] if value == -2 and x < len(recall) else value for x, value in enumerate(row)]
        resolved.append([index if 0 <= index < len(legend) else -1 for index in indices])
    ids = [[legend[index]['id'] if index >= 0 else '' for index in row] for row in resolved]
    open_tiles = frozenset(entry['id'] for entry in legend if entry['id'] not in OPAQUE)
    styles: dict[tuple[int, bool, bool], tuple[str, Style]] = {}

    for y, row in enumerate(grid[:vp['h']]):
        if not area.y <= oy + y < area.bottom:
            continue
        for x, value in enumerate(row[:vp['w']]):
            if not area.x <= ox + x < area.right:
                continue
            index = resolved[y][x]
            if index < 0:
                continue
            entry = legend[index]
            roof = entry['id'] == 'wall' and not _beside(ids, x, y, open_tiles)
            key = index, roof, value < 0
            if key not in styles:
                glyph, style = cell(paint, entry, roof=roof)
                styles[key] = glyph, paint.known(style) if value < 0 else style
            glyph, style = styles[key]
            if value >= 0 and (vp['x'] + x, vp['y'] + y) in hazards:
                style = paint('thing_hazard', 'hazard_warn', bold=True, reverse=paint.tier == '16')
            elif value < 0:
                if (paint.tier == '16' and glyph == '·' and (vp['x'] + x + vp['y'] + y) % 3
                        and not _beside(ids, x, y, OPAQUE)):
                    glyph = ' '
            buffer.put(ox + x, oy + y, glyph, style)


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
        buffer.put(*at, glyph, paint(role, bold=True))
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
    for key in ('focus', 'jack_focus'):
        focus = body.get(key)
        if focus and focus.get('label') and focus['label'] not in names:
            names.append(str(focus['label']))
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
    names.extend({'cover-1': '░ Light cover', 'cover-2': '▒ Cover', 'cover-3': '▓ Heavy cover'}[key]
                 for key in sorted(covers))
    return names


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
            line(name, "panel_text")
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


def head(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint) -> None:
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
    chrome.header(buffer, layout, paint, left, [(me.get('clock', ''), 'head_info')])


def render(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint) -> None:
    draw_origin = origin(body, layout)
    terrain(buffer, body, layout, paint, draw_origin)
    people(buffer, body, layout, paint, draw_origin)
    panel(buffer, body, layout, paint)
    head(buffer, body, layout, paint)
