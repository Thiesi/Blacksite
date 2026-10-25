"""Server-owned sight, memory and camera for architecture section 5.4."""

from dataclasses import dataclass, field
from copy import deepcopy
from typing import Any

from blacksite.content.loader import ContentTree
from blacksite.content.schema import Tile
from blacksite.server.world.actors import Actor
from blacksite.server.world.sight import sees_actor, visible_tiles, sight_radius, private_visible
from blacksite.server.world.zone import ZoneInstance
from blacksite.server.world.safety import safety_at
from blacksite.server.clock import TICK_HZ
from blacksite.server.npcs.templates import relation
from blacksite.server.views import looks as dressing

SCROLL_MARGIN = 4  # Terminal UI section 2.
MAX_VIEW_CELLS = 4096  # Architecture 5.4: bound large-terminal snapshots.
PARAGRAPH = "\n\n"


@dataclass
class Perception:
    remembered: dict[str, dict[Tile, str]] = field(default_factory=dict)
    viewport: dict[str, int] | None = None
    grid_key: tuple[object, ...] | None = None
    tiles: list[list[int]] = field(default_factory=list)
    memory: list[list[int]] = field(default_factory=list)
    legend: list[dict[str, str]] = field(default_factory=list)
    indices: dict[str, int] = field(default_factory=dict)
    looks: list[list[int]] = field(default_factory=list)


def camera(actor: Actor, zone: ZoneInstance, width: int, height: int,
           old: dict[str, int] | None, deep: bool = False) -> dict[str, int]:
    # UI section 2: borders, divider and 22-column side panel.
    logs = min(8, 3 + max(0, height - 24) * 5 // 16)
    w, h = min(width - 25, zone.template.width), min(height - logs - 4, zone.template.height)
    if deep:
        # Proposal 68 trial: an eye-level view looks as far north and south
        # as east and west. Sight still decides what is in it.
        h, old = min(zone.template.height, max(h, 2 * 24 + 1), MAX_VIEW_CELLS // w), None
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
          width: int, height: int, clock: str, night: bool, tick: int,
          scouted: set[tuple[int,int]] | None = None, scouted_actors: set[str] | None = None,
          deep: bool = False) -> dict[str, Any]:
    radius = sight_radius(actor, zone, night)
    body_visible = visible_tiles(actor, zone, radius)
    visible = body_visible | (scouted or set())
    remembered = perception.remembered.setdefault(zone.id, {})
    viewport = camera(actor, zone, width, height, perception.viewport, deep)
    perception.viewport = viewport
    glyphs = content.glyphs.glyphs if content.glyphs else {}
    if not perception.legend:
        ids = sorted(content.tiles)
        perception.indices = {key: index for index, key in enumerate(ids)}
        perception.legend = [{"id": key, "glyph": glyphs.get(content.tiles[key].glyph, "."), "role": content.tiles[key].colour}
                             for key in ids]
    grid_key = (actor.sight_key, tuple(viewport.values()),frozenset(scouted or ()))
    if perception.grid_key != grid_key:
        for tile in visible:
            remembered[tile] = zone.tile_id(tile)
        tiles: list[list[int]] = []
        memory: list[list[int]] = []
        looked: list[list[int]] = []
        indices = perception.indices
        resolved = dressing.for_zone(content, zone.template)
        # Trial D1: public geography is known on arrival. It is computed per
        # view and never written into the character's sight memory.
        chart = dressing.charted(content, zone.template)
        secret = {ex.tile for ex in zone.template.meta.exits if ex.hidden}
        for y in range(viewport["y"], viewport["y"] + viewport["h"]):
            row, recalled, seen = [], [], []
            for x in range(viewport["x"], viewport["x"] + viewport["w"]):
                tile = x, y
                known = tile in remembered or (chart and tile not in secret)
                row.append(indices[zone.tile_id(tile)] if tile in visible else -2 if known else -1)
                recalled.append(indices[remembered[tile]] if tile in remembered
                                else indices[zone.template.grid[y][x]] if known else -1)
                if resolved is not None:
                    seen.append(resolved.grid[y][x] if row[-1] != -1 else -1)
            tiles.append(row)
            memory.append(recalled)
            looked.append(seen)
        # Replace arrays rather than mutate them: published revisions own the
        # previous arrays, including while their network writer is pending.
        perception.tiles, perception.memory, perception.grid_key = tiles, memory, grid_key
        perception.looks = looked if resolved is not None else []
    actors = []
    for other in sorted(zone.actors.values(), key=lambda a: a.id):
        if not private_visible(actor, other):
            continue
        if other.behaviour.get("training") and other.owner != actor.id:
            continue
        if other is not actor and other.id not in (scouted_actors or ()) and not sees_actor(actor, other, body_visible, radius):
            continue
        entry = {"id": other.id, "x": other.x, "y": other.y,
                 "glyph": glyphs.get("actor-jacked" if other.stance == "jacked" else "actor-self" if other is actor else "actor-drone" if other.kind == "drone" else "actor-npc" if other.kind == "npc" else "actor-player", "@"),
                 "role": "player_self" if other is actor else "npc_"+(other.faction or "neutral") if other.kind != "player" else "player_hostile" if other.marked else content.factions[other.faction].colour if other.faction in content.factions else "player_neutral", "stance": other.stance, "kind": other.kind}
        if other is actor:
            entry["name"] = other.name
            entry["facing"] = other.facing  # Proposal 68 street view, additive.
        actors.append(entry)
    objects = [{"id": obj.spec.id, "x": obj.spec.tile[0], "y": obj.spec.tile[1], "kind": obj.spec.kind,
                "state": {**{key: value for key, value in obj.state.items() if key not in ("actor", "serial")}, "open": obj.open, "in_use": obj.in_use, "progress": obj.progress, **obj.spec.params.get("cache_state",{})},
                "role": "muted" if obj.state.get("enabled") is False else "text",
                "name": str(obj.spec.params.get("name", "")),
                "glyph": glyphs.get("cache" if obj.spec.params.get("dropped_item") else "bank" if obj.spec.kind == "bank" else "vendor" if obj.spec.params.get("vendor") else "locked-door" if obj.open is False else obj.spec.kind if obj.spec.kind in glyphs else content.tiles[zone.tile_id(obj.spec.tile)].glyph, ".")}
               for obj in zone.objects.values() if obj.spec.tile in visible and obj.spec.kind != "salvage_field"]
    hazards = [{"scope": "geometry", "warning": max(0, layer.starts - tick) / TICK_HZ,
                "remaining": max(0, layer.expires - tick) / TICK_HZ,
                "tiles": [list(tile) for tile in layer.layout.warning_tiles if tile in visible],
                "escape": list(layer.layout.alternate_routes)} for layer in zone.layers.values()
               if any(tile in visible for tile in layer.layout.warning_tiles)]
    escapes = [ex.id for ex in zone.template.meta.exits if not ex.hidden and ex.tile in visible]
    nearby = [{"id": entry["id"], "name": zone.actors[entry["id"]].name, "role": entry["role"],
               "relation": "!" if zone.actors[entry["id"]].marked or zone.actors[entry["id"]].target == actor.id or zone.actors[entry["id"]].behaviour.get("training") else {"H":"!","N":"~","A":"+"}[relation(content, actor.faction, zone.actors[entry["id"]].faction)]}
              for entry in actors if entry["id"] != actor.id]
    nearby.sort(key=lambda entry: (entry["relation"] != "!", zone.actors[entry["id"]].kind != "player",
        (zone.actors[entry["id"]].x-actor.x)**2+(zone.actors[entry["id"]].y-actor.y)**2, entry["id"]))
    view = {"viewport": viewport, "tiles": perception.tiles, "remembered": perception.memory, "legend": perception.legend,
            "actors": actors, "objects": objects,
            "me": {"name": actor.name, "handle": actor.handle, "faction": actor.faction, "grade": None,
                   "hp": actor.health, "hp_max": actor.health_max, "sta": actor.stamina, "sta_max": actor.stamina_max,
                   "shock": actor.shock, "chits": None, "marked_until": None, "heat_until": None,
                   "zone": zone.id, "zone_name": zone.template.meta.name, "safety": safety_at(zone, actor.position),
                   "clock": clock, "cooldowns": dict(actor.cooldowns), "effects": deepcopy(actor.effects)},
            "target": None, "nearby": nearby,
            "crew": [], "event": None, "objective": None, "hazards": hazards,
            "service": None, "escape": {"routes": escapes, "action": "Ctrl-X leaves"},
            "hint": "Move: arrows  Shift: sprint  E interact  M map  ? help  Ctrl-X leave"}
    # Proposal 68: additive presentation fields. Clients that ignore them
    # render exactly as before.
    look = content.looks.get(zone.template.id)
    view["place"] = {"district": zone.template.meta.district,
                     "names": dict(look.names) if look else {},
                     "lore": [" ".join(part.split()) for asset in zone.template.meta.lore[:1] if asset in content.text
                              for part in content.text[asset].body.split(PARAGRAPH)[:2]]}
    # Scene navigation: named places and exits, only where the caller knows
    # the ground they stand on, so a list of ways never maps unseen space.
    chart = dressing.charted(content, zone.template)
    known = lambda tile: tile in remembered or tile in visible or (chart and 0 <= tile[1] < zone.template.height
                                                                 and 0 <= tile[0] < zone.template.width)
    places = []
    for spot in (look.places if look else ()):
        x, y, w, h = spot.rect
        anchor = tuple(spot.at) if spot.at else (x + w // 2, y + h // 2)
        if known(anchor):
            places.append({"name": spot.name, "rect": [x, y, w, h], "at": list(anchor), "text": spot.text})
    view["place"]["places"] = places
    view["place"]["here"] = next((p["name"] for p in places if p["rect"][0] <= actor.x < p["rect"][0] + p["rect"][2]
                                  and p["rect"][1] <= actor.y < p["rect"][1] + p["rect"][3]), None)
    view["place"]["exits"] = [{"name": content.zones[ex.target_zone].meta.name if ex.target_zone in content.zones else "Construction",
                               "at": list(ex.tile), "kind": ex.kind}
                              for ex in zone.template.meta.exits if not ex.hidden and known(ex.tile)]
    if perception.looks:
        resolved = dressing.for_zone(content, zone.template)
        assert resolved is not None
        view["looks"], view["looks_legend"] = perception.looks, list(resolved.legend)
    return view
