"""Server-authored map overview; no unvisited terrain or hidden exits."""

from typing import Any

from blacksite.content.loader import ContentTree
from blacksite.server.wake import menu, wrapped


def overview(content: ContentTree, current: str, visited: set[str], cursor: int,
             width: int) -> dict[str, Any]:
    district = content.zones[current].meta.district
    zones = sorted((z for z in content.zones.values() if z.meta.district == district), key=lambda z: z.meta.name)
    rows = [{"id": z.id, "cells": [z.meta.name, z.meta.safety]} for z in zones if z.id in visited]
    cursor = max(0, min(cursor, len(rows) - 1))
    selected = content.zones[rows[cursor]["id"]] if rows else content.zones[current]
    lines = ["DISTRICT: " + district, "", *[f"{z.meta.name}: {z.meta.safety}" for z in zones], "", "KNOWN EXITS"]
    lines.extend(f"{content.zones[e.target_zone].meta.name} ({e.kind})" for e in selected.meta.exits
                 if not e.hidden and e.target_zone in content.zones)
    lines.extend(["", *[content.text[asset].body.strip() for asset in selected.meta.lore if asset in content.text]])
    body = menu("CITY MAP - " + district, rows, cursor, "\n\n".join(lines),
                "Up/Down selects visited zones  Enter reads  Esc/B returns")
    body["columns"] = ["Visited zone", "Class"]
    return body
