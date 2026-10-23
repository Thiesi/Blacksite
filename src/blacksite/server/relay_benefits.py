"""Game 7.7 consumers; ownership changes never manufacture source rolls."""

from typing import Any

from blacksite.server.lattice.cores import CoreGraph
from blacksite.server.lattice.ice import Ice
from blacksite.server.players import Player


class Benefits:
    def __init__(self, owner: Any) -> None:
        self.owner = owner
        core = owner.core
        clinic_fee = owner.progression.clinics.service_multiplier
        def fee(player: Player, vendor: Any) -> float:
            actor = owner.world.actors.get(player.id)
            relay = owner.benefit(player, 'surgery_fee', actor.zone) if actor and actor.zone else None
            return min(clinic_fee(player, vendor), relay if relay is not None else 1)
        owner.progression.clinics.service_multiplier = fee
        period = owner.commerce.budget_period
        def budget_period(vendor: Any, counter: str) -> int:
            return min(period(vendor, counter), min((int(relay.benefit.amount)
                for rid, relay in owner.content.relays.items() if owner.active(rid)
                and relay.benefit.kind == 'vendor_refresh' and vendor.faction
                and owner.owner(rid) == vendor.faction), default=period(vendor, counter)))
        owner.commerce.budget_period = budget_period
        quality = core.fabrication.quality_bonus
        core.fabrication.quality_bonus = lambda player, zone: quality(player, zone)+(owner.benefit(
            player, 'fabrication_quality', zone) or 0)
        crash = core.salvage.crash_relay_bonus
        core.salvage.crash_relay_bonus = lambda zone: crash(zone) or any(
            owner.active(rid) and owner.owner(rid) is not None and relay.zone == zone
            and relay.benefit.kind == 'salvage_grade' for rid, relay in owner.content.relays.items())
        rent = core.apartments.rent_modifier
        core.apartments.rent_modifier = lambda player, due: min(rent(player, due),
            owner.benefit(player, 'rent_and_ice', at=due) or 1)
        extra = core.apartments.private_core_ice_slots
        core.apartments.private_core_ice_slots = lambda player: extra(player)+int(
            owner.benefit(player, 'rent_and_ice') is not None)
        before = core.factions.before_membership_change
        def membership(player: Player) -> bool:
            if not before(player):
                return False
            if not core.apartments.ensure_rent(player.id):
                owner.log(player.id, 'Your due rent quote is being saved. Membership waits for that receipt; retry if saving fails.')
                return False
            return True
        core.factions.before_membership_change = membership
        refresh = core.factions.refresh
        def membership_changed(player: Player) -> None:
            refresh(player)
            self.refresh_cores(player.id)
        core.factions.refresh = membership_changed
        trace = owner.lat.encounters.trace
        def gain(presence: Any, amount: float, *, fixed: bool = False, entered: bool = False) -> None:
            player = owner.game.players[presence.player_id]
            district = owner.lat.sectors.records[presence.sector].district
            if amount > 0 and not fixed and any(owner.active(rid) and player.faction
                    and owner.owner(rid) == player.faction and relay.benefit.kind == 'trace_gain'
                    and relay.benefit.district == district for rid, relay in owner.content.relays.items()):
                amount *= next(float(relay.benefit.amount) for rid, relay in owner.content.relays.items()
                    if owner.active(rid) and owner.owner(rid) == player.faction
                    and relay.benefit.kind == 'trace_gain' and relay.benefit.district == district)
            trace(presence, amount, fixed=fixed, entered=entered)
        owner.lat.encounters.trace = gain

    def layers(self, player: Player) -> list[dict[str, float]]:
        actor = self.owner.world.actors.get(player.id)
        radius = self.owner.benefit(player, 'hymn_radius', actor.zone) if actor and actor.zone else None
        return [{'hymn_radius_bonus': radius}] if radius is not None else []

    def refresh_cores(self, pid: str | None = None) -> None:
        owner = self.owner
        private = owner.lat.interlock.private
        for record in owner.lat.interlock.state['apartments'].values():
            if (record.get('unit') not in owner.core.apartments.geometry.units
                    or pid is not None and record['resident'] != pid):
                continue
            cid = private.core_id(record)
            old = owner.content.cores.get(cid)
            private.install(record)
            spec = owner.content.cores[cid]
            if old and tuple(r.ice for r in old.rooms) == tuple(r.ice for r in spec.rooms):
                continue
            for instance in owner.lat.encounters.instances.values():
                if instance.graph.spec.id != cid:
                    continue
                expected = {f'{instance.id}:{room.id}:{index}': (room.id, template)
                            for room in spec.rooms for index, template in enumerate(room.ice)}
                removed = set(instance.ice)-set(expected)
                for iid in removed:
                    instance.ice.pop(iid)
                for iid, (room, template) in expected.items():
                    if iid not in instance.ice:
                        instance.ice[iid] = Ice.spawn(iid, owner.content.ice[template],
                            (instance.id, room), spec.tier, owner.clock.now_tick())
                instance.graph = CoreGraph(spec)
                for presence in owner.lat.presences.values():
                    if presence.instance == instance.id and presence.target in removed:
                        presence.target = None

    def refresh(self) -> None:
        self.refresh_cores()
        for player in self.owner.game.players.values():
            self.owner.progression.sync_actor(player)

    def patrols(self, player: Player) -> list[dict[str, Any]]:
        """Publish authored waypoints, without exposing unseen actors or tiles."""
        owner = self.owner
        actor = owner.world.actors.get(player.id)
        if not actor or owner.benefit(player, 'patrol_overlay', actor.zone) is None:
            return []
        routes = []
        for npc in owner.world.zones[actor.zone].actors.values():
            if npc.kind != 'npc' or npc.behaviour.get('mission'):
                continue
            template = owner.content.npcs.get(npc.behaviour.get('template'))
            if template:
                waypoints = next((b.params.get('waypoints', []) for b in template.behaviours
                                  if b.kind == 'patrol'), [])
                if waypoints:
                    routes.append({'name': template.name, 'waypoints': waypoints})
        return routes

    def telemetry(self, player: Player, rid: str) -> list[str]:
        owner = self.owner
        relay = owner.content.relays[rid]
        if not owner.active(rid) or not player.faction or owner.owner(rid) != player.faction:
            return []
        if relay.benefit.kind == 'pump_telemetry':
            return [f'{service.name}: {node.state} / {node.allocation or "no allocation"}'
                for sid, service in owner.content.services.items()
                if service.zone == relay.zone and owner.content.active('services', sid)
                and (node := owner.core.contracts.state.services.nodes.get(sid))]
        if relay.benefit.kind == 'patrol_overlay':
            actor = owner.world.actors.get(player.id)
            if not actor or actor.zone != relay.zone:
                return []
            lines = []
            for npc in owner.world.zones[relay.zone].actors.values():
                if npc.kind != 'npc' or npc.behaviour.get('mission'):
                    continue
                template = owner.content.npcs.get(npc.behaviour.get('template'))
                if template:
                    route = next((b.params.get('waypoints', []) for b in template.behaviours if b.kind == 'patrol'), [])
                    if route:
                        lines.append(template.name+': '+' -> '.join(str(tuple(tile)) for tile in route))
            return lines
        return []
