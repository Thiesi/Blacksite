"""Render the authorized ZoneView; no sight, movement or game rules."""

from dataclasses import replace
from typing import Any

from blacksite.door.cells import CellBuffer, display_width, truncate
from blacksite.door.layout import Rect
from blacksite.door.palette import Palette


def render_zone(buffer: CellBuffer, body: dict[str, Any], area: Rect, palette: Palette) -> None:
    viewport = body["viewport"]
    legend = body["legend"]
    memory = body.get("remembered", [])
    for y, row in enumerate(body["tiles"][:area.height]):
        for x, tile in enumerate(row[:area.width]):
            if tile == -1:
                continue
            remembered = tile == -2
            if remembered:
                tile = memory[y][x] if y < len(memory) and x < len(memory[y]) else -1
            if not 0 <= tile < len(legend):
                continue
            entry = legend[tile]
            style = palette.style(entry["role"])
            if remembered:
                style = replace(style, attrs=(*style.attrs, 2))
            buffer.put(area.x + x, area.y + y, entry["glyph"], style)
    objects = body.get('objects', [])
    for entry in [*(o for o in objects if o.get('kind') != 'beacon'), *body.get("actors", []),
                  *(o for o in objects if o.get('kind') == 'beacon')]:
        x, y = entry["x"] - viewport["x"], entry["y"] - viewport["y"]
        if 0 <= x < min(area.width, viewport["w"]) and 0 <= y < min(area.height, viewport["h"]):
            buffer.put(area.x + x, area.y + y, entry["glyph"], palette.style(entry.get("role", "text")))
    me = body["me"]
    header = f"{me['zone_name']}  "
    buffer.put(2, 0, truncate(header, buffer.width - 18), palette.style("title"))
    safety = me["safety"].upper()
    sx = min(buffer.width - len(safety) - (16 if me.get("heat_until") else 10), 2 + display_width(header))
    buffer.put(sx, 0, safety, palette.style("safety_" + me["safety"]))
    if service := body.get('service'):
        start = sx+len(safety)+2
        buffer.put(start, 0, truncate(service.get('summary', ''), max(0, buffer.width-16-start)), palette.style('ui_highlight'))
    buffer.put(buffer.width - 8, 0, me.get("clock", ""), palette.style("title"))
    if me.get("heat_until"):
        buffer.put(buffer.width - 14, 0, "HEAT", palette.style("warning"))
    side_x, side_w = buffer.width - 23, 22
    rows: list[str] = []
    objective = body.get("objective")
    if objective and not (buffer.width < 100 and objective.get('compact_hint')):
        rows += [str(objective.get("next_action", "")), str(objective.get("cost", ""))]
    for hazard in body.get("hazards", [])[:1]:
        rows += [f"WARNING {hazard.get('warning', 0):g}s", "Escape: " + ", ".join(hazard.get("escape", []))]
    target = body.get("target")
    if target:
        filled=max(0,min(8,target["hp_percent"]*8//100))
        health = f"{target['hp']:g}/{target['hp_max']:g}" if "hp" in target else f"{target['hp_percent']}%"
        rows += ["TARGET",target["name"],f"HP {'#'*filled}{'.'*(8-filled)} {health}",
            f"Range {target['range']:g} Cover {target['cover']}",target["faction"],target["relation"]]
        if target.get("warning"): rows.append(target["warning"])
    else:
        rows += ["TARGET", "None"]
    if me.get("weapon") and me["weapon"] != "None":
        rows += ["WEAPON", me["weapon"]]
    rows += ["NEARBY"]
    rows += [f"{entry.get('relation', '~')} {entry.get('name', 'Another Wake')}" for entry in body.get("nearby", [])[:3]]
    crew = body.get('crew', [])
    crew_rows = ['CREW']
    for member in crew:
        suffix = f" {member['hp_pct']}%"
        crew_rows += [('>' if member.get('beacon') else '+' if member.get('leader') else ' ')+
                      truncate(member['name'], side_w-len(suffix)-1)+suffix,
                      str(member['zone'])+(' / '+member['direction'] if member.get('beacon') and member.get('direction') else '')]
    rows += crew_rows if crew else ["CREW", "None"]
    extra = 4 if me.get("grade") is not None else 0
    if crew and len(rows) > max(0, area.height-6-extra):
        # Keep one ally visible on the small terminal; G holds the full roster.
        compact = rows[:rows.index('TARGET')]
        if target:
            compact += [target['name'], f"HP {target['hp_percent']}% / {target['relation']}",
                       f"Range {target['range']:g} Cover {target['cover']}"]
        peers = [m for m in crew if m['name'] != me.get('name')]
        first = peers[0] if peers else crew[0]
        suffix = f" {first['hp_pct']}%"
        compact += ['CREW / G', truncate(first['name'], side_w-len(suffix))+suffix,
                    str(first['zone'])+(' / '+first['direction'] if first.get('beacon') and first.get('direction') else '')]
        rows = compact+([me['weapon']] if me.get('weapon') else [])
    name_roles = {f"{entry.get('relation', '~')} {entry.get('name', 'Another Wake')}": entry.get("role", "text")
                  for entry in body.get("nearby", [])}
    if target:
        name_roles[target["name"]] = target.get("name_role", "text")
    for index, text in enumerate(rows[:max(0, area.height - 6 - extra)]):
        buffer.put(side_x, area.y + index, truncate(text, side_w), palette.style(name_roles.get(text, "text")))
    bottom = area.y + area.height - 5 - extra
    buffer.put(side_x, bottom, truncate(me.get("name", me.get("handle", "")), side_w), palette.style(me.get("name_role", "title")))
    handle_row = int(bool(extra))
    if extra:
        buffer.put(side_x, bottom + 1, truncate("BBS: " + me["handle"], side_w), palette.style())
    for offset, key in ((1, "hp"), (2, "sta")):
        value, maximum = int(me[key]), max(1, int(me[key + "_max"]))
        filled = max(0, min(8, value * 8 // maximum))
        text = f"{key.upper()} {'#' * filled}{'.' * (8 - filled)} {value}/{maximum}"
        buffer.put(side_x, bottom + offset + handle_row, truncate(text, side_w), palette.style("hp_ok" if key == "hp" else "ui_highlight"))
    if extra:
        buffer.put(side_x, bottom + 4, truncate(f"Chits {me['chits']}  Grade {me['grade']}", side_w), palette.style())
        buffer.put(side_x, bottom + 5, truncate(f"Lease days {me['lease_days']}/90", side_w), palette.style())
        buffer.put(side_x, bottom + 6, truncate(f"Discharge XP {me['xp']}/{me['discharge_xp']}", side_w), palette.style())
    buffer.put(side_x, bottom + 3 + extra, truncate(f"Shock {me.get('shock', 0):g}", side_w), palette.style())
    buffer.put(side_x, bottom + 4 + extra, "Ctrl-X leaves", palette.style("hint"))
