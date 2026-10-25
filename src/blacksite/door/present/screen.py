"""Compose a whole proposal 68 screen: frame, header, view, panel, log, hint.

Also owns the place card, the D8 trial of contextual interludes: on first
sight of a zone (or on F5) the map area shows where you are, in words and
light, until any key. A card never appears while anything threatens you,
and it closes the moment something does (spec section 10).
"""

from collections import Counter
from typing import Any

from blacksite.door.cells import CellBuffer, display_width, truncate
from blacksite.door.layout import Layout
from dataclasses import replace

from blacksite.door.layout import Rect
from blacksite.door.present import chrome, lattice, lit, scene, street, zone
from blacksite.door.present.paint import Paint

CARD_SECONDS = 8.0
CARD_MODES = ("entry", "look", "off")
CARD_LABELS = {"entry": "Place cards on entering a zone and on F5.", "look": "Place cards on F5 only.",
               "off": "Place cards off."}


def threats(body: dict[str, Any]) -> list[str]:
    """What makes this moment dangerous, in plain words; empty when calm."""
    me, target = body.get("me", {}), body.get("target")
    found = [f"hostile {n.get('name', '?')}" for n in body.get("nearby", []) if n.get("relation") == "!"]
    if body.get("hazards"):
        found.append("hazard")
    if target:
        found.append(f"target {target.get('name', '?')}" if isinstance(target, dict) else "target")
    if me.get("in_combat"):
        found.append("combat")
    if me.get("heat_until"):
        found.append("heat")
    return found


def threatened(body: dict[str, Any]) -> bool:
    return bool(threats(body))


def safety(kind: str, body: dict[str, Any]) -> str:
    value = body.get("me", {}).get("safety") if kind == "zone" else body.get("body_safety")
    return value if value in ("safe", "pocket", "contested", "open") else "contested"


def wrap(text: str, width: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        if current and display_width(current + " " + word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    return lines + ([current] if current else [])


def card(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint) -> None:
    """The place, before the street takes over: district, name, how it feels."""
    area, me, place = layout.viewport, body["me"], body.get("place") or {}
    width = min(64, area.width - 4)
    text = [line for paragraph in place.get("lore", []) for line in wrap(paragraph, width - 6) + [""]][:-1]
    height = min(area.height - 2, 7 + len(text))
    x0, y0 = area.x + (area.width - width) // 2, area.y + max(1, (area.height - height) // 3)
    # The card is lit by the place: its most common ground colour.
    grounds = Counter(e.get("bg") for row in body.get("looks", []) for i in row if i >= 0
                      for e in [body["looks_legend"][i]] if e.get("bg"))
    ground = grounds.most_common(1)[0][0] if grounds else None
    fill = paint("panel_text", ground)
    for y in range(y0, y0 + height):
        buffer.put(x0, y, " " * width, fill)
    edge = paint("word_" + me.get("safety", "contested"), ground, bold=True)
    buffer.put(x0, y0, "╔" + "═" * (width - 2) + "╗", edge)
    for y in range(y0 + 1, y0 + height - 1):
        buffer.put(x0, y, "║", edge)
        buffer.put(x0 + width - 1, y, "║", edge)
    buffer.put(x0, y0 + height - 1, "╚" + "═" * (width - 2) + "╝", edge)
    district = str(place.get("district", "")).upper()
    buffer.put(x0 + 3, y0 + 1, truncate(" ".join(district), width - 6), paint("head_district", ground))
    name = str(me.get("zone_name", "")).upper()
    spaced = " ".join(name) if display_width(" ".join(name)) <= width - 6 else name
    buffer.put(x0 + 3, y0 + 2, truncate(spaced, width - 6), paint("head_zone", ground, bold=True))
    word = me.get("safety", "").upper()
    buffer.put(x0 + width - 3 - len(word), y0 + 1, word, paint("word_" + me.get("safety", "contested"), ground, bold=True))
    for index, line in enumerate(text[:height - 6]):
        buffer.put(x0 + 3, y0 + 4 + index, line, paint("log_place", ground))
    buffer.put(x0 + 3, y0 + height - 2, truncate("Any key: the street.  F5 shows this again.", width - 6), paint("key_text", ground))


MODES = ("map", "street", "scene", "auto")
HINTS = {"street": "Up forward  Down back  Left/Right turn  E use  Tab target  F7 view",
         "scene": "Arrows step  , . choose a way  Space go  E use  Tab target  F7 view",
         "look": "Any key returns  F5 look again  F7 view"}


def render(buffer: CellBuffer, layout: Layout, paint: Paint, kind: str, body: dict[str, Any],
           logs: list[dict[str, Any]], hint: str, *, show_card: bool, flash: bool, mode: str = "map",
           heading: str = "up", cursor: int = 0, tag: str | None = None) -> None:
    """`tag` is set by the auto view, which has already chosen `mode`."""
    tactical = tag == "TACTICAL" if tag else mode != "map" and kind == "zone" and threatened(body)
    immersive = mode in ("street", "scene") and kind == "zone" and not tactical
    chrome.frame(buffer, layout, paint, safety(kind, body), flash=flash)
    chrome.log(buffer, layout, paint, logs)
    shown_hint = HINTS["look" if tag == "LOOK" else mode] if immersive else hint
    chrome.hints(buffer, layout, paint, hint if hint.startswith(("Leave", "Weapon")) else shown_hint)
    if kind != "zone":
        lattice.render(buffer, body, layout, paint)
        return
    label = f" {tag or ('TACTICAL' if tactical else '')} ".replace("  ", "")
    if not immersive:
        zone.render(buffer, body, layout, paint)
        if show_card and body.get("place") and not tactical:
            card(buffer, body, layout, paint)
    else:
        side = layout.side
        rows = 7 if layout.height < 30 else 13
        street.radar(buffer, body, Rect(side.x, side.y, side.width, rows), paint, heading if mode == "street" else None)
        zone.panel(buffer, body, replace(layout, side=Rect(side.x, side.y + rows, side.width, side.height - rows)), paint)
        zone.head(buffer, body, layout, paint)
        if mode == "street":
            if not lit.render(buffer, body, layout.viewport, paint, heading):
                street.render(buffer, body, layout.viewport, paint, heading)
        else:
            scene.render(buffer, body, layout.viewport, paint, heading, cursor)
    if label.strip():
        # The view names itself; danger says so loudest.
        buffer.put(layout.side.x - 2 - len(label), 0, label,
                   paint("log_danger", bold=True, reverse=True) if tactical else paint("panel_label", reverse=True))
