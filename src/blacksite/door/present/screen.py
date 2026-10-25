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
from blacksite.door.present import chrome, lattice, zone
from blacksite.door.present.paint import Paint

CARD_SECONDS = 8.0
CARD_MODES = ("entry", "look", "off")
CARD_LABELS = {"entry": "Place cards on entering a zone and on F5.", "look": "Place cards on F5 only.",
               "off": "Place cards off."}


def threatened(body: dict[str, Any]) -> bool:
    me = body.get("me", {})
    return bool(body.get("hazards") or body.get("target") or me.get("in_combat") or me.get("heat_until")
                or any(n.get("relation") == "!" for n in body.get("nearby", [])))


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


def render(buffer: CellBuffer, layout: Layout, paint: Paint, kind: str, body: dict[str, Any],
           logs: list[dict[str, Any]], hint: str, *, show_card: bool, flash: bool) -> None:
    chrome.frame(buffer, layout, paint, safety(kind, body), flash=flash)
    chrome.log(buffer, layout, paint, logs)
    chrome.hints(buffer, layout, paint, hint)
    if kind == "zone":
        zone.render(buffer, body, layout, paint)
        if show_card and body.get("place"):
            card(buffer, body, layout, paint)
    else:
        lattice.render(buffer, body, layout, paint)
