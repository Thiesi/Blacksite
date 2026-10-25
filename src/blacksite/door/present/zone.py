"""The street: shape is the rule, light and colour are the place.

Draws an authorized ZoneView (spec sections 3 to 5). Everything here is
presentation of fields the server already chose to send: tiles and
memory decide what exists for you, `looks` only colours it.
"""

from typing import Any

from blacksite.door.cells import CellBuffer, display_width, truncate
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


def _light(paint: Paint, role: str, light: bool) -> str:
    return role + "_light" if light and paint.has(role + "_light") else role


def terrain(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint) -> None:
    area, tier = layout.viewport, paint.tier
    legend, memory = body["legend"], body.get("remembered", [])
    looks, looks_legend = body.get("looks", []), body.get("looks_legend", [])
    hazard = {tuple(t) for h in body.get("hazards", []) for t in h.get("tiles", [])}
    vp = body["viewport"]
    for y, row in enumerate(body["tiles"][:area.height]):
        for x, state in enumerate(row[:area.width]):
            if state == -1:
                continue
            now = state >= 0
            index = state if now else memory[y][x] if y < len(memory) and x < len(memory[y]) else -1
            if not 0 <= index < len(legend):
                continue
            entry = legend[index]
            look_index = looks[y][x] if y < len(looks) and x < len(looks[y]) else -1
            look = looks_legend[look_index] if 0 <= look_index < len(looks_legend) else {}
            glyph, style = cell(paint, entry, look, tier)
            if (vp["x"] + x, vp["y"] + y) in hazard and now:
                style = paint("thing_hazard", "hazard_warn", bold=True)
            elif not now:
                style = paint.known(style)
                if tier == "16" and entry["id"] == "floor" and (x + y * 3) % 3:
                    glyph = " "  # known ground, sparse, so seen ground stands out
            buffer.put(area.x + x, area.y + y, glyph, style)


def cell(paint: Paint, entry: dict[str, Any], look: dict[str, Any], tier: str) -> tuple[str, Style]:
    """One terrain cell, fully lit. Shape from the rule tile, light from the look."""
    tile, bg = entry["id"], look.get("bg")
    light = bool(look.get("light"))
    if tile == "wall":
        if look.get("g"):
            return look["g"], paint(look.get("fg", "panel_text"), bg, bold=True)
        if bg and tier != "16":
            return " ", paint(look.get("fg") or "wall", bg)
        return entry["glyph"], paint(look.get("fg") or "wall")
    if tile == "floor":
        if not look:
            return entry["glyph"], paint("floor")
        glyph = look.get("g") or " "
        if tier == "16" and (glyph == " " or glyph in "·∙,'`"):
            glyph = "·"  # 16 colours keep the floor dot: walkable ground stays legible on black
        return glyph, paint(look.get("fg") or "floor", bg)
    if tile == "water":
        return entry["glyph"], paint(look.get("fg") or "water", bg)
    role = _light(paint, TILE_ROLES.get(tile, entry.get("role", "panel_text")), light)
    return entry["glyph"], paint(role if paint.has(role) else entry.get("role", "panel_text"), bg, bold=tile not in ("cover-1", "cover-2", "cover-3"))


def people(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint) -> None:
    area, vp = layout.viewport, body["viewport"]
    looks, looks_legend = body.get("looks", []), body.get("looks_legend", [])
    relation = {n["id"]: n.get("relation", "~") for n in body.get("nearby", [])}
    target = (body.get("target") or {}).get("id")

    def inside(entry: dict[str, Any]) -> tuple[int, int] | None:
        x, y = entry["x"] - vp["x"], entry["y"] - vp["y"]
        if 0 <= x < min(area.width, vp["w"]) and 0 <= y < min(area.height, vp["h"]):
            return x, y
        return None

    def ground(x: int, y: int) -> tuple[str | None, bool]:
        index = looks[y][x] if y < len(looks) and x < len(looks[y]) else -1
        look = looks_legend[index] if 0 <= index < len(looks_legend) else {}
        return look.get("bg"), bool(look.get("light"))

    objects = body.get("objects", [])
    for obj in [o for o in objects if o.get("kind") != "beacon"]:
        at = inside(obj)
        if at is None:
            continue
        bg, light = ground(*at)
        glyph, role = THINGS.get(obj.get("kind", ""), (obj.get("glyph", "?"), "panel_text"))
        if obj.get("glyph") == "*" or obj.get("state", {}).get("dropped_item"):
            glyph, role = "*", "thing_vendor"
        if obj.get("role") == "muted":
            role = "panel_dim"
        elif obj.get("kind") in ("door", "apartment_door", "gate", "shutter") and obj.get("state", {}).get("open") is False:
            glyph = "≡"
        buffer.put(area.x + at[0], area.y + at[1], glyph, paint(_light(paint, role, light), bg, bold=True))
    for entry in body.get("actors", []):
        at = inside(entry)
        if at is None:
            continue
        bg, light = ground(*at)
        if entry.get("role") == "player_self":
            buffer.put(area.x + at[0], area.y + at[1], "@", paint("self_fg", "self_bg", bold=True))
            continue
        kind = entry.get("kind", "npc" if str(entry.get("role", "")).startswith("npc_") else "player")
        glyph = "τ" if kind == "drone" else "☺" if kind == "player" else "☻"
        role = entry.get("role", "npc_neutral")
        hostile = relation.get(entry["id"]) == "!"
        # Hostility is an attribute, not only a hue (spec 7.2): reverse video.
        style = paint(_light(paint, role, light), bg, bold=True, reverse=hostile or entry.get("stance") == "jacked")
        if entry["id"] == target:
            style = Style(style.fg, style.bg, (*style.attrs, 4), style.tier)
        buffer.put(area.x + at[0], area.y + at[1], glyph, style)
    for route in body.get("patrol_routes", []):
        for point in route.get("waypoints", []):
            at = inside(point)
            if at is not None:
                buffer.put(area.x + at[0], area.y + at[1], "°", paint("log_danger"))
    for obj in [o for o in objects if o.get("kind") == "beacon"]:
        at = inside(obj)
        if at is not None:
            buffer.put(area.x + at[0], area.y + at[1], "♦", paint("player_crew", bold=True))


def at_hand(body: dict[str, Any]) -> list[str]:
    """Named things within reach. It does not claim which one E picks:
    that needs the server's E resolver to say so (spec 9, requirement R12)."""
    me = next((a for a in body.get("actors", []) if a.get("role") == "player_self"), None)
    if me is None:
        return []
    names = []
    for obj in body.get("objects", []):
        if max(abs(obj["x"] - me["x"]), abs(obj["y"] - me["y"])) <= 1 and obj.get("kind") != "beacon":
            names.append(str(obj.get("name") or obj.get("kind", "")).strip())
    if body.get("escape", {}).get("routes") and not names:
        vp = body["viewport"]
        for y, row in enumerate(body["tiles"]):
            for x, state in enumerate(row):
                if state >= 0 and body["legend"][state]["id"] == "exit" and \
                        max(abs(vp["x"] + x - me["x"]), abs(vp["y"] + y - me["y"])) <= 1:
                    names.append("an exit")
                    break
    return [n for n in names if n][:3]


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
    limit = vy - 1

    def line(text: str, role: str = "panel_text", indent: int = 1, *, bold: bool = False) -> None:
        nonlocal y
        if y < limit:
            buffer.put(x + indent, y, truncate(text, w - indent), paint(role, bold=bold))
            y += 1

    def section(label: str, role: str = "panel_label") -> None:
        nonlocal y
        if y < limit - 1:
            chrome.rule(buffer, layout, paint, y, label, role)
            y += 1

    for hazard in body.get("hazards", [])[:1]:
        section("DANGER", "log_danger")
        line(f"‼ warning {hazard.get('warning', 0):.1f}s", "log_danger", bold=True)
        line("out: " + ", ".join(hazard.get("escape", [])) if hazard.get("escape") else "move off the marked ground", "panel_text")
    plans = [str(plan["summary"]) for plan in (body.get("event") or {}).get("plans", [])]
    objective = body.get("objective")
    if plans or objective:
        section("NOW")
        for text in plans[:2]:
            line(text, "log_place")
        if objective and not (layout.width < 100 and objective.get("compact_hint") and plans):
            line(str(objective.get("next_action", "")), "panel_strong")
            if objective.get("cost") and layout.height >= 30:
                line(str(objective["cost"]), "panel_label")
    hand = at_hand(body)
    names = (body.get("place") or {}).get("names", {})
    if hand:
        section("HERE")
        for name in hand:
            line(name, "panel_text")
    target = body.get("target")
    section("TARGET")
    if target:
        tag = TAGS.get({"hostile": "!", "allied": "+"}.get(target.get("relation", ""), "~"), "neutral")
        line(target["name"], target.get("name_role", "panel_text"), bold=True)
        if y < limit:
            health = f"{target['hp']:g}" if "hp" in target else f"{target['hp_percent']}%"
            chrome.bar(buffer, paint, x + 1, y, "HP", target["hp_percent"], 100, "bar_hp", health, width=10)
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
        kinds = {a["id"]: a.get("kind", "npc") for a in body.get("actors", [])}
        for entry in nearby:
            if y >= limit:
                break
            glyph = {"drone": "τ", "player": "☺"}.get(kinds.get(entry["id"], "npc"), "☻")
            hostile = entry.get("relation") == "!"
            buffer.put(x + 1, y, glyph, paint(entry.get("role", "npc_neutral"), bold=True, reverse=hostile))
            buffer.put(x + 3, y, truncate(entry.get("name", "Someone"), w - 4), paint("log_danger" if hostile else "panel_text"))
            y += 1
    crew = body.get("crew", [])
    if crew and y < limit - 1:
        section("CREW")
        for member in crew:
            suffix = f" {member['hp_pct']}%"
            mark = "♦" if member.get("beacon") else "+" if member.get("leader") else " "
            line(mark + truncate(member["name"], w - 3 - len(suffix)) + suffix, "player_crew")
            if layout.height >= 30:
                line("  " + str(member["zone"]), "panel_label")
    if me.get("standing_on") in names:
        line(names[me["standing_on"]], "panel_label")
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
    me, place = body["me"], body.get("place") or {}
    safety = me["safety"]
    left = [(str(place.get("district", "")).upper(), "head_district")] if place.get("district") else []
    left += [(me["zone_name"], "head_zone"), (safety.upper(), "word_" + safety)]
    if safety == "contested":
        left.append(("PvP G5+", "head_info"))
    if me.get("heat_until"):
        left.append(("HEAT", "log_danger"))
    if me.get("marked_until"):
        left.append(("MARKED", "log_danger"))
    if service := body.get("service"):
        left.append((str(service.get("summary", "")), "head_info"))
    left = [(f"{text} ·" if index == 0 and len(left) > 1 and role == "head_district" else text, role)
            for index, (text, role) in enumerate(left)]
    chrome.header(buffer, layout, paint, left, [(me.get("clock", ""), "head_info")])


def render(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint) -> None:
    terrain(buffer, body, layout, paint)
    people(buffer, body, layout, paint)
    panel(buffer, body, layout, paint)
    head(buffer, body, layout, paint)
