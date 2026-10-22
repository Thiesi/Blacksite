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
    for entry in [*body.get("objects", []), *body.get("actors", [])]:
        x, y = entry["x"] - viewport["x"], entry["y"] - viewport["y"]
        if 0 <= x < min(area.width, viewport["w"]) and 0 <= y < min(area.height, viewport["h"]):
            buffer.put(area.x + x, area.y + y, entry["glyph"], palette.style(entry.get("role", "text")))
    me = body["me"]
    header = f"{me['zone_name']}  "
    buffer.put(2, 0, truncate(header, buffer.width - 18), palette.style("title"))
    safety = me["safety"].upper()
    sx = min(buffer.width - len(safety) - (16 if me.get("heat_until") else 10), 2 + display_width(header))
    buffer.put(sx, 0, safety, palette.style("safety_" + me["safety"]))
    buffer.put(buffer.width - 8, 0, me.get("clock", ""), palette.style("title"))
    if me.get("heat_until"):
        buffer.put(buffer.width - 14, 0, "HEAT", palette.style("warning"))
    side_x, side_w = buffer.width - 23, 22
    rows: list[str] = []
    objective = body.get("objective")
    if objective:
        rows += [str(objective.get("next_action", "")), str(objective.get("cost", ""))]
    for hazard in body.get("hazards", [])[:1]:
        rows += [f"WARNING {hazard.get('warning', 0):g}s", "Escape: " + ", ".join(hazard.get("escape", []))]
    service = body.get("service")
    if service:
        rows += [f"SERVICE {service.get('state', '')}", f"Expires {service.get('expiry', '')}"]
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
    rows += ["CREW", "None"]
    extra = 4 if me.get("grade") is not None else 0
    for index, text in enumerate(rows[:max(0, area.height - 6 - extra)]):
        buffer.put(side_x, area.y + index, truncate(text, side_w), palette.style())
    bottom = area.y + area.height - 5 - extra
    buffer.put(side_x, bottom, truncate(me.get("name", me.get("handle", "")), side_w), palette.style("title"))
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
