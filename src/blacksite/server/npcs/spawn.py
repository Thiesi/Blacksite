"""Bounded spawners. UTC deadlines permit lazy wake and durable death receipts."""

from typing import Any
from collections.abc import Callable

from blacksite.content.schema import Spawner, Tile
from blacksite.server.npcs.templates import EVALUATION_TICKS, make_actor
from blacksite.server.world.actors import Actor
from blacksite.server.world.registry import World
from blacksite.server.world.zone import ZoneInstance


class Spawners:
    def __init__(self, world: World, state: dict[str, Any], origin: str) -> None:
        self.world = world
        self.origin = origin
        self.slots: dict[str, dict[str, Any]] = state.get("slots", {})
        self.serial: int = state.get("serial", 0)
        self.revision = 0
        self.enabled_events: set[str] = set()  # S24 supplies active IDs.
        self.extra: Callable[[ZoneInstance], tuple[Spawner, ...]] = lambda zone: ()
        self.policy: Callable[[ZoneInstance, Spawner], tuple[int, float]] = lambda zone, spawner: (spawner.count, spawner.respawn_seconds)
        self.on_spawn: Callable[[Actor, Spawner], None] = lambda actor, spawner: None

    @staticmethod
    def reserved(zone: ZoneInstance) -> set[Tile]:
        meta = zone.template.meta
        return {ex.tile for ex in meta.exits} | {obj.spec.tile for obj in zone.objects.values()} | ({meta.spawn} if meta.spawn else set())

    def location(self, zone: ZoneInstance, spawner: Spawner) -> Tile | None:
        candidates = spawner.region.tiles() if spawner.region else [spawner.tile]
        occupied = {a.position for a in zone.actors.values() if not a.behaviour.get("training")}
        reserved = self.reserved(zone)
        candidates = [t for t in candidates if t is not None and zone.can_enter(None, t)
                      and not zone.tiles[zone.tile_id(t)].hazard and t not in occupied | reserved]
        return zone.rng.choice(candidates) if candidates else None

    def process(self, zone: ZoneInstance, now: float) -> None:
        for sp in (*zone.template.meta.spawners, *self.extra(zone)):
            if sp.condition == "per_player":
                continue
            if sp.condition and sp.condition.startswith("event:") and sp.condition[6:] not in self.enabled_events:
                continue
            template = self.world.content.npcs[sp.npc]
            count, respawn = self.policy(zone, sp)
            for index in range(count):
                key = f"{zone.id}:{sp.id}:{index}"
                slot = self.slots.setdefault(key, {"until": 0})
                if slot.get("actor") in self.world.actors or now < slot["until"]:
                    continue
                tile = self.location(zone, sp)
                if tile is None:
                    continue
                self.serial += 1
                aid = f"{self.origin}:npc:{self.serial}"
                actor = make_actor(template, aid, {"slot": key, "spawner": sp.id,
                    "home": tile, "region": sp.region, "respawn": respawn,
                    "phase": sum(aid.encode()) % EVALUATION_TICKS})
                slot["actor"] = aid
                self.revision += 1
                self.world.enter(actor, zone.id, tile)
                self.on_spawn(actor, sp)

    def deadline(self, actor: Actor, now: float) -> float:
        zone = self.world.zones[actor.zone]
        spec = next((sp for sp in (*zone.template.meta.spawners, *self.extra(zone))
                     if sp.id == actor.behaviour.get('spawner')), None)
        delay = self.policy(zone, spec)[1] if spec else float(actor.behaviour.get('respawn', 0))
        return now+delay

    def removed(self, actor: Actor, now: float, *, deadline: float | None = None) -> None:
        slot = self.slots.get(str(actor.behaviour.get("slot")))
        if slot is not None:
            slot.update(until=self.deadline(actor, now) if deadline is None else deadline)
            slot.pop("actor", None)
            self.revision += 1

    def record(self) -> dict[str, Any]:
        return {"serial": self.serial, "slots": self.slots}
