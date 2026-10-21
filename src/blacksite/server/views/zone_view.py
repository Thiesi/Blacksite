"""Server-owned sight, memory and camera for architecture section 5.4."""

from dataclasses import dataclass, field
from copy import deepcopy
from typing import Any

from blacksite.content.loader import ContentTree
from blacksite.content.schema import Tile
from blacksite.server.world.actors import Actor
from blacksite.server.world.sight import sees_actor, visible_tiles
from blacksite.server.world.zone import ZoneInstance
from blacksite.server.world.safety import safety_at
from blacksite.server.clock import TICK_HZ

SCROLL_MARGIN = 4  # Terminal UI section 2.
MAX_VIEW_CELLS = 4096  # Architecture 5.4: bound large-terminal snapshots.


@dataclass
class Perception:
    remembered: dict[str, dict[Tile, str]] = field(default_factory=dict)
    viewport: dict[str, int] | None = None
    grid_key: tuple[object, ...] | None = None
    tiles: list[list[int]] = field(default_factory=list)
    memory: list[list[int]] = field(default_factory=list)
    legend: list[dict[str, str]] = field(default_factory=list)
    indices: dict[str, int] = field(default_factory=dict)


def camera(actor: Actor, zone: ZoneInstance, width: int, height: int,
           old: dict[str, int] | None) -> dict[str, int]:
    # UI section 2: borders, divider and 22-column side panel.
    logs = min(8, 3 + max(0, height - 24) * 5 // 16)
    w, h = min(width - 25, zone.template.width), min(height - logs - 4, zone.template.height)
    # Bound unusually large negotiated terminals to the protocol's local
    # snapshot budget; usual 80x24/132x50 rectangles remain unchanged.
    h = min(h, max(1, MAX_VIEW_CELLS // w))
    if old is None or (old["w"], old["h"]) != (w, h):
        x, y = actor.x - w // 2, actor.y - h // 2
    else:
        x, y = old["x"], old["y"]
        if actor.x - x < SCROLL_MARGIN:
            x = actor.x - SCROLL_MARGIN
        elif actor.x - x >= w - SCROLL_MARGIN:
            x = actor.x - w + SCROLL_MARGIN + 1
        if actor.y - y < SCROLL_MARGIN:
            y = actor.y - SCROLL_MARGIN
        elif actor.y - y >= h - SCROLL_MARGIN:
            y = actor.y - h + SCROLL_MARGIN + 1
    return {"x": max(0, min(zone.template.width - w, x)), "y": max(0, min(zone.template.height - h, y)), "w": w, "h": h}


def build(actor: Actor, zone: ZoneInstance, perception: Perception, content: ContentTree,
          width: int, height: int, clock: str, night: bool, tick: int) -> dict[str, Any]:
    radius = zone.template.meta.sight_radius_night if night else None
    radius = radius or zone.template.meta.sight_radius
    visible = visible_tiles(actor, zone, radius)
    remembered = perception.remembered.setdefault(zone.id, {})
    viewport = camera(actor, zone, width, height, perception.viewport)
    perception.viewport = viewport
    glyphs = content.glyphs.glyphs if content.glyphs else {}
    if not perception.legend:
        ids = sorted(content.tiles)
        perception.indices = {key: index for index, key in enumerate(ids)}
        perception.legend = [{"id": key, "glyph": glyphs.get(content.tiles[key].glyph, "."), "role": content.tiles[key].colour}
                             for key in ids]
    grid_key = (actor.sight_key, tuple(viewport.values()))
    if perception.grid_key != grid_key:
        for tile in visible:
            remembered[tile] = zone.tile_id(tile)
        tiles: list[list[int]] = []
        memory: list[list[int]] = []
        indices = perception.indices
        for y in range(viewport["y"], viewport["y"] + viewport["h"]):
            row, recalled = [], []
            for x in range(viewport["x"], viewport["x"] + viewport["w"]):
                tile = x, y
                row.append(indices[zone.tile_id(tile)] if tile in visible else -2 if tile in remembered else -1)
                recalled.append(indices[remembered[tile]] if tile in remembered else -1)
            tiles.append(row)
            memory.append(recalled)
        # Replace arrays rather than mutate them: published revisions own the
        # previous arrays, including while their network writer is pending.
        perception.tiles, perception.memory, perception.grid_key = tiles, memory, grid_key
    actors = []
    for other in sorted(zone.actors.values(), key=lambda a: a.id):
        if other is not actor and not sees_actor(actor, other, visible, radius):
            continue
        entry = {"id": other.id, "x": other.x, "y": other.y,
                 "glyph": glyphs.get("actor-self" if other is actor else "actor-player", "@"),
                 "role": "player_self" if other is actor else "player_neutral", "stance": other.stance}
        if other is actor:
            entry["name"] = other.name
        actors.append(entry)
    objects = [{"id": obj.spec.id, "x": obj.spec.tile[0], "y": obj.spec.tile[1], "kind": obj.spec.kind,
                "state": {"open": obj.open, "in_use": obj.in_use, "progress": obj.progress},
                "glyph": glyphs.get("locked-door" if obj.open is False else content.tiles[zone.tile_id(obj.spec.tile)].glyph, ".")}
               for obj in zone.objects.values() if obj.spec.tile in visible]
    hazards = [{"scope": "geometry", "warning": max(0, layer.starts - tick) / TICK_HZ,
                "remaining": max(0, layer.expires - tick) / TICK_HZ,
                "tiles": [list(tile) for tile in layer.layout.warning_tiles if tile in visible],
                "escape": list(layer.layout.alternate_routes)} for layer in zone.layers.values()
               if any(tile in visible for tile in layer.layout.warning_tiles)]
    escapes = [ex.id for ex in zone.template.meta.exits if not ex.hidden and ex.tile in visible]
    return {"viewport": viewport, "tiles": perception.tiles, "remembered": perception.memory, "legend": perception.legend,
            "actors": actors, "objects": objects,
            "me": {"name": actor.name, "handle": actor.handle, "faction": actor.faction, "grade": None,
                   "hp": actor.health, "hp_max": actor.health_max, "sta": actor.stamina, "sta_max": actor.stamina_max,
                   "shock": actor.shock, "chits": None, "marked_until": None, "heat_until": None,
                   "zone": zone.id, "zone_name": zone.template.meta.name, "safety": safety_at(zone, actor.position),
                   "clock": clock, "cooldowns": dict(actor.cooldowns), "effects": deepcopy(actor.effects)},
            "target": None, "nearby": [{"id": entry["id"], "name": "Another Wake", "role": entry["role"], "relation": "~"}
                                        for entry in actors if entry["id"] != actor.id],
            "crew": [], "event": None, "objective": None, "hazards": hazards,
            "service": None, "escape": {"routes": escapes, "action": "Ctrl-X leaves"},
            "hint": "Move: arrows  Shift: sprint  E interact  M map  ? help  Ctrl-X leave"}
