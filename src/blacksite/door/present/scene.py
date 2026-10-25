"""Scenes: Karst as places you are in (paradigm prototype B).

You are always somewhere with a name: the stage, the alley behind the
bars, the Tin Halo door. The screen leads with that place (a glimpse at
eye level, its words, who is here, what is in reach) and offers ways
out of it. Choosing one asks the server to walk you there with ordinary
steps in real time (`walk_to`, trial only); any key, a hit or a fight
stops the walk, and any threat hands the screen to the tactical map.
"""

import math
from typing import Any

from blacksite.door.cells import CellBuffer, display_width, truncate
from blacksite.door.layout import Rect
from blacksite.door.present import street
from blacksite.door.present.paint import Paint

COMPASS = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]  # by angle, screen y down; CP437-safe


def wrap(text: str, width: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        if current and display_width(current + " " + word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    return lines + ([current] if current else [])


def me_of(body: dict[str, Any]) -> dict[str, Any] | None:
    return next((a for a in body.get("actors", []) if a.get("role") == "player_self"), None)


def ways(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Where you can go from here: named places and exits you know of,
    nearest first. Shared by the renderer and the door's key handling."""
    me, place = me_of(body), body.get("place") or {}
    if me is None:
        return []
    here = place.get("here")
    out = []
    for spot in place.get("places", []):
        if spot["name"] != here:
            out.append({"name": spot["name"], "at": spot["at"], "kind": "place"})
    for ex in place.get("exits", []):
        out.append({"name": "To " + ex["name"], "at": ex["at"], "kind": "exit"})
    for obj in body.get("objects", []):
        if obj.get("name") and obj.get("kind") not in ("door", "beacon", "light") and \
                max(abs(obj["x"] - me["x"]), abs(obj["y"] - me["y"])) > 1:
            out.append({"name": str(obj["name"]), "at": [obj["x"], obj["y"]], "kind": "thing"})
    for way in out:
        dx, dy = way["at"][0] - me["x"], way["at"][1] - me["y"]
        way["distance"] = max(abs(dx), abs(dy))
        octant = round(math.atan2(dy, dx) / (math.pi / 4)) % 8
        way["direction"] = COMPASS[octant]
    order = {"place": 0, "exit": 1, "thing": 2}
    out.sort(key=lambda w: (order[w["kind"]], w["distance"], w["name"]))
    return out[:12]


def render(buffer: CellBuffer, body: dict[str, Any], area: Rect, paint: Paint, heading: str, cursor: int) -> None:
    me, place = me_of(body), body.get("place") or {}
    if me is None:
        return
    here_name = place.get("here") or body["me"].get("zone_name", "")
    spot = next((p for p in place.get("places", []) if p["name"] == here_name), None)
    text = spot["text"] if spot and spot.get("text") else " ".join(place.get("lore", [])[:1])
    # A glimpse at eye level, the width of the view.
    glimpse_rows = max(5, min(12, area.height // 3))
    street.render(buffer, body, Rect(area.x, area.y, area.width, glimpse_rows), paint, heading, hud=False)
    y = area.y + glimpse_rows
    buffer.put(area.x, y, " " * area.width, paint("panel_text"))
    title = here_name.upper()
    spaced = " ".join(title) if display_width(" ".join(title)) <= area.width - 20 else title
    buffer.put(area.x + 1, y, spaced, paint("head_zone", bold=True))
    district = str(place.get("district", "")).upper()
    buffer.put(area.x + area.width - 1 - display_width(district), y, district, paint("head_district"))
    y += 1
    limit = 4 if area.height >= 30 else 2
    sentences = [part.strip() + "." for part in text.split(".") if part.strip()]
    while sentences and len(wrap(" ".join(sentences), area.width - 4)) > limit:
        sentences.pop()  # whole sentences only; never stop mid-thought
    lines = wrap(" ".join(sentences) if sentences else text, area.width - 4)[:limit]
    for line in lines:
        buffer.put(area.x + 2, y, line, paint("log_place"))
        y += 1
    people = [n for n in body.get("nearby", [])]
    reach = [o for o in body.get("objects", []) if max(abs(o["x"] - me["x"]), abs(o["y"] - me["y"])) <= 1
             and o.get("kind") not in ("beacon",)]
    if people:
        counts: dict[str, int] = {}
        for n in people:
            label = n.get("name", "someone") + (" (hostile)" if n.get("relation") == "!" else "")
            counts[label] = counts.get(label, 0) + 1
        names = [f"{label} x{count}" if count > 1 else label for label, count in counts.items()]
        line = "Here: " + ", ".join(names) + "."
        buffer.put(area.x + 2, y, truncate(line, area.width - 4), paint("panel_text"))
        y += 1
    if reach:
        buffer.put(area.x + 2, y, "E  ", paint("key_cap", bold=True))
        buffer.put(area.x + 5, y, truncate(", ".join(str(o.get("name") or o.get("kind")) for o in reach),
                                           area.width - 7), paint("panel_text"))
        y += 1
    y += 1
    walking = body["me"].get("walking")
    options = ways(body)
    if walking:
        target = next((w["name"] for w in options if w["at"] == walking), "there")
        buffer.put(area.x + 2, y, truncate(f"Walking to {target}. Any key stops.", area.width - 4),
                   paint("panel_strong", bold=True))
        y += 2
    buffer.put(area.x + 1, y, "─ WAYS " + "─" * (area.width - 9), paint("panel_rule"))
    y += 1
    room = area.y + area.height - y
    if not options:
        buffer.put(area.x + 2, y, "Nothing you know of yet. Look around (F7).", paint("panel_dim"))
        return
    cursor = max(0, min(cursor, len(options) - 1))
    first = max(0, min(cursor - room + 1, len(options) - room)) if room > 0 else 0
    for index, way in enumerate(options[first:first + max(0, room)], first):
        selected = index == cursor
        mark = "»" if way["kind"] == "exit" else "·" if way["kind"] == "place" else "∙"
        row = f" {mark} {way['name']}"
        meta = f"{way['distance']:>3} m {way['direction']:<2} "
        style = paint("panel_text", reverse=selected) if selected else paint(
            "thing_exit" if way["kind"] == "exit" else "panel_text" if way["kind"] == "place" else "panel_label")
        buffer.put(area.x + 1, y, (truncate(row, area.width - 4 - len(meta)).ljust(area.width - 2 - len(meta)) + meta),
                   style)
        y += 1
