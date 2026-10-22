"""Zone registry and physical-body ownership (entity model 3.1/3.2)."""

from collections import deque

from blacksite.content.loader import ContentTree
from blacksite.content.schema import Tile
from blacksite.server.world.actors import Actor
from blacksite.server.world.zone import ZoneInstance
from collections.abc import Callable
from blacksite.content.schema import ObjectSpec


class World:
    def __init__(self, content: ContentTree, seeds: dict[str, int]) -> None:
        self.content = content
        self.zones = {key: ZoneInstance(zone, content.tiles, seeds[key]) for key, zone in content.zones.items()}
        self.actors: dict[str, Actor] = {}
        self.object_access: Callable[[Actor, ObjectSpec], bool] = lambda actor, obj: True

    def free_tile(self, zone_id: str, start: Tile, actor: Actor | None = None) -> Tile:
        zone = self.zones[zone_id]
        pending = deque([start])
        seen = {start}
        occupied = {actor.position for actor in zone.actors.values() if not actor.behaviour.get("training")}
        while pending:
            tile = pending.popleft()
            key = zone.tile_id(tile)
            if zone.passable(tile) and not zone.tiles[key].hazard:
                if tile not in occupied and zone.entry_policy(actor, tile):
                    return tile
                x, y = tile
                for neighbour in ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)):
                    if neighbour not in seen and zone.passable(neighbour):
                        seen.add(neighbour)
                        pending.append(neighbour)
        raise ValueError("zone has no available spawn tile")

    def enter(self, actor: Actor, zone_id: str, tile: Tile) -> None:
        if actor.id in self.actors and self.actors[actor.id] is not actor:
            raise ValueError("actor id is already owned by another body")
        zone = self.zones[zone_id]
        if not zone.can_enter(actor, tile) or any(a.id != actor.id and a.position == tile and not a.behaviour.get("training") for a in zone.actors.values()):
            raise ValueError("entry tile is blocked")
        self.leave(actor)
        actor.zone, (actor.x, actor.y) = zone_id, tile
        zone.actors[actor.id] = actor
        self.actors[actor.id] = actor
        zone.position_update(actor)
        actor.sight_key = None
        zone.revision += 1

    def leave(self, actor: Actor) -> None:
        if actor.zone in self.zones:
            zone = self.zones[actor.zone]
            zone.actors.pop(actor.id, None)
            zone.revision += 1
        self.actors.pop(actor.id, None)
        actor.zone = None
        actor.behaviour.pop("private_owner", None)

    def permits_harm(self, initiator: Actor, body: Actor) -> bool:
        """Use physical bodies at acceptance and again at effect delivery.

        Attribution stays with the initiator for indirect/delayed effects.
        Combat and Lattice consumers implement their actions in later slices.
        """
        return all(actor.zone in self.zones and self.zones[actor.zone].allows_hostile(actor.position)
                   for actor in (initiator, body))
