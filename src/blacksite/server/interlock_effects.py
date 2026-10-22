"""Typed physical effects of committed core controls (game 6.4/7.5).

Effects compose with event geometry; expiry removes only this subsystem's
layer. Attribution is checked again when a hazard or powered actor hits.
"""

from math import ceil
from typing import TYPE_CHECKING, Any

from blacksite.server.clock import TICK_HZ
from blacksite.server.world.zone import GeometryLayer
from blacksite.server.rules import combat as combat_rules

if TYPE_CHECKING:
    from blacksite.server.interlock import Interlock

PATROL_DIVERSION_SECONDS = 900  # S15 / world Lattice patrol beacon.
DARK_SIGHT_RADIUS = 5  # Game 5.2/6.4: unlit local area.


def lighting_radius(actor: Any, zone: Any, base: int) -> int:
    dark = any(obj.spec.kind == "light" and obj.state.get("enabled") is False
        and (actor.x-obj.spec.tile[0])**2+(actor.y-obj.spec.tile[1])**2 <= zone.template.meta.sight_radius**2
        for obj in zone.objects.values())
    return min(base, DARK_SIGHT_RADIUS) if dark else base


class PhysicalEffects:
    def __init__(self, interlock: "Interlock") -> None:
        self.interlock = interlock
        self.layout_layers: set[tuple[str, str]] = set()
        self.exit_locks: set[tuple[str, str]] = set()
        self.powered: set[str] = set()
        self.damage_remainders: dict[str, float] = {}
        self.pending_damage: dict[tuple[str, str, str], int] = {}

    def flush_hits(self) -> None:
        if self.interlock.commerce.pending:
            return
        pending, self.pending_damage = self.pending_damage, {}
        world = self.interlock.game.world
        for (aid, source_id, zid), amount in pending.items():
            if self.interlock.commerce.pending:
                key = aid, source_id, zid
                self.pending_damage[key] = self.pending_damage.get(key, 0)+amount
                continue
            actor, source = world.actors.get(aid), world.actors.get(source_id)
            if not actor or not source or actor.zone != zid or actor.stance in ("down", "dead"):
                continue
            allowed = (world.permits_harm(source, actor) if source is actor
                       else self.interlock.combat.permits_indirect(source, actor))
            if allowed:
                self.interlock.combat._apply_damage(source, actor, amount, 0,
                    source.id, "Controlled machinery", False)

    def compose(self) -> None:
        interlock = self.interlock
        now, tick = interlock.now(), interlock.clock.now_tick()
        wanted_layers: set[tuple[str, str]] = set()
        wanted_locks: set[tuple[str, str]] = set()
        powered: set[str] = set()
        for key, effect in interlock.state["effects"].items():
            control = interlock.controls.get((effect["core"], effect["control"]))
            if not control or effect.get("revision") != control.revision or effect["expires"] is not None and effect["expires"] <= now:
                continue
            zone = interlock.game.world.zones[control.target.zone]
            obj = zone.objects[control.target.object]
            kind, params = obj.spec.kind, obj.spec.params
            geometry = kind in ("pump", "gantry") or control.safety_policy == "hazard"
            if not geometry and (effect["serial"] != obj.state.get("serial") or obj.state.get("pending")):
                continue
            if geometry:
                layout_id = effect.get("layout", params.get("layout"))
                layout = next((layout for layout in zone.template.meta.layouts if layout.id == layout_id), None)
                if layout:
                    source = "interlock:"+key
                    starts = tick+ceil((effect["starts"]-now)*TICK_HZ)
                    expires = tick+ceil((effect["expires"]-now)*TICK_HZ)
                    zone.layers[source] = GeometryLayer(source, layout, starts, expires)
                    wanted_layers.add((zone.id, source))
            if kind in ("cable_car", "lift", "gate", "shutter") and not effect["enabled"]:
                wanted_locks.update((zone.id, ex.id) for ex in zone.template.meta.exits
                                    if ex.id in params.get("exits", ()) and ex.id != control.alternate_route)
            if kind == "turret":
                for actor in zone.actors.values():
                    if actor.kind == "player" or actor.behaviour.get("spawner") not in params.get("spawners", ()):
                        continue
                    actor.behaviour["powered"] = effect["enabled"]
                    actor.behaviour["interlock_initiator"] = effect["actor"]
                    powered.add(actor.id)
            if kind == "patrol_beacon" and now < effect.get("divert_until", effect["starts"]+PATROL_DIVERSION_SECONDS):
                for actor in zone.actors.values():
                    if actor.behaviour.get("spawner") in params.get("spawners", ()):
                        actor.behaviour["interlock_diversion"] = tuple(params.get("destination", actor.behaviour.get("home", actor.position)))
                        powered.add(actor.id)
        touched = {zid for zid, source in self.layout_layers | wanted_layers}
        for zid, source in self.layout_layers-wanted_layers:
            interlock.game.world.zones[zid].layers.pop(source, None)
        self.layout_layers = wanted_layers
        interlock.sim.locked_exits -= self.exit_locks
        interlock.sim.locked_exits |= wanted_locks
        self.exit_locks = wanted_locks
        for aid in self.powered-powered:
            actor = interlock.game.world.actors.get(aid)
            if actor:
                actor.behaviour.pop("powered", None)
                actor.behaviour.pop("interlock_initiator", None)
                actor.behaviour.pop("interlock_diversion", None)
        self.powered = powered
        for zid in touched:
            zone = interlock.game.world.zones[zid]
            zone.wake(tick)
            zone.compose(tick)

    def hazards(self) -> None:
        interlock = self.interlock
        active: set[str] = set()
        for zone in interlock.game.world.zones.values():
            for actor in tuple(zone.actors.values()):
                if actor.stance in ("down", "dead"):
                    continue
                hazardous = [(source, layer) for source, layer in zone.layers.items()
                    if source.startswith("interlock:") and layer.starts <= interlock.clock.now_tick() < layer.expires
                    and any(c.tile == actor.position and zone.tiles[c.tile_id].hazard
                            and zone.tile_id(c.tile) == c.tile_id for c in layer.layout.changes)]
                if not hazardous:
                    continue
                source, layer = sorted(hazardous)[-1]
                effect = interlock.state["effects"][source[len("interlock:"):]]
                initiator = interlock.game.world.actors.get(effect["actor"])
                if not initiator or not zone.allows_hostile(actor.position):
                    continue
                allowed = (interlock.game.world.permits_harm(initiator, actor) if initiator is actor
                           else interlock.combat.permits_indirect(initiator, actor))
                if not allowed:
                    continue
                active.add(actor.id)
                hazard = zone.tiles[zone.tile_id(actor.position)].hazard
                # Hazard rates are per second. Mitigate each second's dose,
                # rather than subtracting armour from each fractional tick.
                accumulated = self.damage_remainders.get(actor.id, 0)+1/TICK_HZ
                pulses = int(accumulated+1e-8)
                self.damage_remainders[actor.id] = accumulated-pulses
                if pulses:
                    amount = pulses*combat_rules.damage(float(hazard.damage_per_second), 0,
                        interlock.combat.armour(actor, hazard.type), False)
                    key = actor.id, initiator.id, actor.zone
                    self.pending_damage[key] = self.pending_damage.get(key, 0)+amount
        self.damage_remainders = {aid: value for aid, value in self.damage_remainders.items() if aid in active}
        self.flush_hits()
