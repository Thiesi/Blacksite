"""Game 8.7: commissioned room blueprints and server-side interior privacy."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from blacksite.content.schema import ApartmentClass, HousingAnchor, ObjectSpec, Region, RoomBlueprint, Tile
from blacksite.server.clock import Clock
from blacksite.server.world.actors import Actor
from blacksite.server.world.registry import World
from blacksite.server.world.zone import ObjectState


@dataclass(frozen=True)
class Unit:
    id: str
    zone: str
    door: str
    anchor: HousingAnchor
    room: RoomBlueprint
    definition: ApartmentClass

    @property
    def region(self) -> Region:
        return Region(*self.anchor.origin, len(self.room.grid[0]), len(self.room.grid))

    def tile(self, local: Tile) -> Tile:
        return self.anchor.origin[0]+local[0], self.anchor.origin[1]+local[1]

    def object_id(self, local: str) -> str:
        return self.door+":"+local


class HousingGeometry:
    def __init__(self, world: World, clock: Clock, saved: dict[str, Any]) -> None:
        self.world, self.clock = world, clock
        self.units: dict[str, Unit] = {}
        self.leases: Callable[[], dict[str, Any]] = lambda: saved.get("apartments", {})
        for zid, zone in world.zones.items():
            if not world.content.active("zones", zid):
                continue
            for obj in tuple(zone.objects.values()):
                anchor = obj.spec.housing
                if anchor is None:
                    continue
                unit = Unit(zid+":"+obj.spec.id, zid, obj.spec.id, anchor,
                    world.content.rooms[anchor.room], world.content.apartments[anchor.class_id])
                self.units[unit.id] = unit
                for local in unit.room.meta.objects:
                    params = {**local.params, "apartment_unit": unit.id}
                    if local.kind == "terminal":
                        params["sector"] = anchor.sector
                    spec = replace(local, id=unit.object_id(local.id), tile=unit.tile(local.tile), params=params)
                    zone.objects[spec.id] = ObjectState(spec)
                meta = replace(zone.template.meta, pockets=(*zone.template.meta.pockets, unit.region))
                zone.template = replace(zone.template, meta=meta)
                obj.spec = replace(obj.spec, params={**obj.spec.params, "open": False})
                obj.open = False
            if any(unit.zone == zid for unit in self.units.values()):
                zone.entry_policy = lambda actor, tile, zid=zid: self.can_enter(actor, zid, tile)
                zone.position_update = self.mark
                zone.escape_origin = self.escape_origin
        world.object_access = self.can_use

    def escape_origin(self, actor: Actor) -> Tile:
        """Game 8.7: an occupant may explicitly leave through a closed door."""
        unit = self.containing(actor.zone, actor.position) if actor.zone else None
        return unit.anchor.doorstep if unit else actor.position

    def mark(self, actor: Actor) -> None:
        unit = self.containing(actor.zone, actor.position) if actor.zone else None
        lease = self.lease(unit) if unit else None
        if unit and lease and actor.position != unit.tile(unit.anchor.vestibule):
            actor.behaviour["private_owner"] = lease["resident"]
        else:
            actor.behaviour.pop("private_owner", None)

    def containing(self, zone: str, tile: Tile) -> Unit | None:
        return next((unit for unit in self.units.values() if unit.zone == zone and unit.region.contains(tile)), None)

    def lease(self, unit: Unit) -> dict[str, Any] | None:
        return next((lease for lease in self.leases().values() if lease.get("unit") == unit.id), None)

    def resident(self, actor: Actor | None, unit: Unit) -> bool:
        lease = self.lease(unit)
        pid = actor.owner if actor and actor.kind == "drone" and actor.behaviour.get("player_drone") else actor.id if actor else None
        return bool(lease and lease["resident"] == pid)

    def can_enter(self, actor: Actor | None, zone: str, tile: Tile) -> bool:
        unit = self.containing(zone, tile)
        if unit is None or self.resident(actor, unit):
            return True
        lease = self.lease(unit)
        return bool(actor and actor.kind == "player" and lease
            and tile == unit.tile(unit.anchor.vestibule)
            and lease.get("vestibule_access_until", {}).get(actor.id, 0) > self.clock.now_utc().timestamp())

    def can_use(self, actor: Actor, obj: ObjectSpec) -> bool:
        unit = self.units.get(str(obj.params.get("apartment_unit", "")))
        return unit is None or bool(actor.zone == unit.zone and unit.region.contains(actor.position)
                                    and self.resident(actor, unit))
