"""Server-owned sight, memory and camera for architecture section 5.4."""

from dataclasses import dataclass, field
from copy import deepcopy
from typing import Any

from blacksite.layout import compute as screen_layout
from blacksite.content.loader import ContentTree
from blacksite.content.schema import Tile, Zone
from blacksite.server.world.actors import Actor
from blacksite.server.world.sight import sees_actor, visible_tiles, sight_radius, private_visible
from blacksite.server.world.zone import ZoneInstance
from blacksite.server.world.safety import safety_at
from blacksite.server.clock import TICK_HZ
from blacksite.server.npcs.templates import relation
from blacksite.server.views import presentation
from blacksite.server.views import looks
from blacksite.content.places import public_tiles, wall, water, plain
from blacksite.place import CHARTED_GROUND

SCROLL_MARGIN = 4  # Terminal UI section 2.
MAX_VIEW_CELLS = 4096  # Architecture 5.4: bound large-terminal snapshots.


@dataclass
class Perception:
    remembered: dict[str, dict[Tile, str]] = field(default_factory=dict)
    viewport: dict[str, int] | None = None
    grid_key: tuple[object, ...] | None = None
    grid_revision: int = 0
    tiles: list[list[int]] = field(default_factory=list)
    memory: list[list[int]] = field(default_factory=list)
    legend: list[dict[str, str]] = field(default_factory=list)
    indices: dict[str, int] = field(default_factory=dict)
    public_template: Zone | None = None
    public: set[Tile] = field(default_factory=set)
    ground_only: set[Tile] = field(default_factory=set)
    chart_key: tuple[object, ...] | None = None
    charted: list[list[int]] = field(default_factory=list)
    look_key: tuple[object, ...] | None = None
    looks: dict[str, Any] | None = None


def camera(actor: Actor, zone: ZoneInstance, width: int, height: int,
           old: dict[str, int] | None) -> dict[str, int]:
    layout = screen_layout(width, height)
    w, h = min(layout.viewport.width, zone.template.width), min(layout.viewport.height, zone.template.height)
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
          scouted: set[tuple[int,int]] | None = None, scouted_actors: set[str] | None = None) -> dict[str, Any]:
    radius = sight_radius(actor, zone, night)
    body_visible = visible_tiles(actor, zone, radius)
    visible = body_visible | (scouted or set())
    remembered = perception.remembered.setdefault(zone.id, {})
    viewport = camera(actor, zone, width, height, perception.viewport)
    perception.viewport = viewport
    glyphs = content.glyphs.glyphs if content.glyphs else {}
    if not perception.legend:
        ids = sorted(content.tiles)
        perception.indices = {key: index for index, key in enumerate(ids)}
        perception.legend = [{"id": key, "glyph": glyphs.get(content.tiles[key].glyph, "."), "role": content.tiles[key].colour}
                             for key in ids]
        for entry in perception.legend:
            modern = content.glyphs.modern.get(content.tiles[entry["id"]].glyph) if content.glyphs else None
            if modern:
                entry["glyph_modern"] = modern
    grid_key = (actor.sight_key, tuple(viewport.values()),frozenset(scouted or ()))
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
        perception.grid_revision += 1
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
                 "role": "player_self" if other is actor else "npc_"+(other.faction or "neutral") if other.kind != "player" else "player_hostile" if other.marked else content.factions[other.faction].colour if other.faction in content.factions else "player_neutral", "stance": other.stance}
        if other is actor:
            entry["name"] = other.name
        entry.update({"class": presentation.presented_class(other, actor, content),
                      "jacked": other.stance == "jacked"})
        entry["glyph_id"] = "actor-self" if other is actor else "actor-drone" if other.kind == "drone" else "actor-npc" if other.kind == "npc" else "actor-player"
        if other.kind == "drone" and other.stance != "jacked" and other is not actor:
            entry["glyph"] = "@"  # Current renderer's historical fallback; D6 draws later.
        entry["role"] = presentation.role(other, actor, content, entry["role"])
        actors.append(entry)
    objects = [{"id": obj.spec.id, "x": obj.spec.tile[0], "y": obj.spec.tile[1], "kind": obj.spec.kind,
                "state": {**{key: value for key, value in obj.state.items() if key not in ("actor", "serial")}, "open": obj.open, "in_use": obj.in_use, "progress": obj.progress, **obj.spec.params.get("cache_state",{})},
                "role": presentation.object_role(obj.spec.kind, obj.spec.params),
                "legacy_role": "muted" if obj.state.get("enabled") is False else "text",
                "glyph": glyphs.get("cache" if obj.spec.params.get("dropped_item") else "bank" if obj.spec.kind == "bank" else "vendor" if obj.spec.params.get("vendor") else "locked-door" if obj.open is False else obj.spec.kind if obj.spec.kind in glyphs else content.tiles[zone.tile_id(obj.spec.tile)].glyph, ".")}
               for obj in zone.objects.values() if obj.spec.tile in visible and obj.spec.kind != "salvage_field"]
    hazards = [{"scope": "geometry", "warning": max(0, layer.starts - tick) / TICK_HZ,
                "remaining": max(0, layer.expires - tick) / TICK_HZ,
                "tiles": [list(tile) for tile in layer.layout.warning_tiles if tile in visible],
                "escape": list(layer.layout.alternate_routes)} for layer in zone.layers.values()
               if any(tile in visible for tile in layer.layout.warning_tiles)]
    escapes = [ex.id for ex in zone.template.meta.exits if not ex.hidden and ex.tile in visible]
    nearby = [{"id": entry["id"], "name": presentation.name(zone.actors[entry["id"]], actor, content), "role": entry["role"],
               "class": entry["class"], "jacked": entry["jacked"],
               "relation": "~" if presentation.covered(zone.actors[entry["id"]], actor, content) else "!" if zone.actors[entry["id"]].marked or zone.actors[entry["id"]].target == actor.id or zone.actors[entry["id"]].behaviour.get("training") else {"H":"!","N":"~","A":"+"}[relation(content, actor.faction, zone.actors[entry["id"]].faction)]}
              for entry in actors if entry["id"] != actor.id]
    nearby.sort(key=lambda entry: (entry["relation"] != "!", zone.actors[entry["id"]].kind != "player",
        (zone.actors[entry["id"]].x-actor.x)**2+(zone.actors[entry["id"]].y-actor.y)**2, entry["id"]))
    result = {"viewport": viewport, "tiles": perception.tiles, "remembered": perception.memory, "legend": perception.legend,
            "actors": actors, "objects": objects,
            "me": {"name": actor.name, "handle": actor.handle, "faction": actor.faction, "grade": None,
                   "hp": actor.health, "hp_max": actor.health_max, "sta": actor.stamina, "sta_max": actor.stamina_max,
                   "shock": actor.shock, "chits": None, "marked_until": None, "heat_until": None,
                   "zone": zone.id, "zone_name": zone.template.meta.name, "safety": safety_at(zone, actor.position),
                   "district": zone.template.meta.district,
                   "pvp": safety_at(zone, actor.position) == "open",
                   "clock": clock, "cooldowns": dict(actor.cooldowns), "effects": deepcopy(actor.effects)},
            "target": None, "nearby": nearby, "focus": None, "jack_focus": None,
            "crew": [], "event": None, "objective": None, "hazards": hazards,
            "service": None, "escape": {"routes": escapes, "action": "Ctrl-X leaves"},
            "hint": "Move: arrows  Shift: sprint  E interact  M map  ? help  Ctrl-X leave"}
    if perception.public_template is not zone.template:
        perception.public_template = zone.template
        perception.public = public_tiles(zone.template)
        object_tiles = {obj.tile for obj in zone.template.meta.objects}
        perception.ground_only = {at for at in perception.public
                                 if at in object_tiles or (kind := content.tiles[zone.template.tile_at(at)]).hazard
                                 or kind.interaction}
        perception.chart_key = None
    public = perception.public
    if public:
        # Static template terrain only. Withheld classes share one marker;
        # a chart never publishes live state, hazards, actors or memory.
        chart_key = id(zone.template), tuple(viewport.values())
        if perception.chart_key != chart_key:
            hidden = {ex.tile for ex in zone.template.meta.exits if ex.hidden}
            def chart_index(tile: Tile) -> int:
                kind = content.tiles[zone.template.tile_at(tile)]
                if tile not in public or tile in hidden:
                    return -1
                if tile in perception.ground_only:
                    return CHARTED_GROUND
                return perception.indices[kind.id]
            perception.charted = [[chart_index((x, y)) for x in range(viewport['x'], viewport['x'] + viewport['w'])]
                                 for y in range(viewport['y'], viewport['y'] + viewport['h'])]
            perception.chart_key = chart_key
        result['charted'] = perception.charted
    if zone.id in content.looks:
        # The grid revision records sight/scout/viewport rebuilds, including
        # explicit memory restoration with unchanged coordinates. Inspect
        # the bounded grid on a miss; never enumerate whole-map memory.
        look_key = id(zone.template), id(content.looks[zone.id]), perception.grid_revision, perception.chart_key
        if perception.look_key != look_key:
            chart = perception.charted if public else []
            known = {(viewport['x'] + x, viewport['y'] + y)
                     for y, row in enumerate(perception.tiles) for x, index in enumerate(row)
                     if index >= 0 or index == -2 and perception.memory[y][x] >= 0
                     or y < len(chart) and (chart[y][x] >= 0 or chart[y][x] == CHARTED_GROUND)}
            hidden = {ex.tile for ex in zone.template.meta.exits if ex.hidden}
            def known_at(tile: Tile) -> bool:
                if tile in visible or tile in remembered:
                    return True
                return tile in public and tile not in hidden
            def ground_only_at(tile: Tile) -> bool:
                return tile in perception.ground_only and tile not in visible and tile not in remembered
            perception.looks = looks.masked(content, zone.template, known, visible,
                                            known_at=known_at, ground_only_at=ground_only_at)
            perception.look_key = look_key
        result['looks'] = perception.looks
        # Add class metadata only for the new place layer. The old no-look
        # legend and switch-off rendering retain their bytes.
        result['legend'] = [{**entry, 'wall': wall(content.tiles[entry['id']]),
                             'water': water(content.tiles[entry['id']]),
                             'plain': plain(content.tiles[entry['id']])}
                            for entry in perception.legend]
    return result
