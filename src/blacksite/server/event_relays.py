"""Game 7.7/12: commissioned relay readers of committed event sources."""

from typing import Any

from blacksite.server.players import Player
from blacksite.server.rules.events import BEACON_SECONDS


class Readers:
    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def bind(self) -> None:
        benefits = self.owner.core.relays.benefits
        previous = benefits.telemetry
        benefits.telemetry = lambda player, rid: [*previous(player, rid), *self.telemetry(player, rid)]
        patrols = benefits.patrols
        benefits.patrols = lambda player: [*patrols(player), *self.patrols(player)]

    def patrols(self, player: Player) -> list[dict[str, Any]]:
        owner = self.owner
        actor = owner.world.actors.get(player.id)
        if not actor or owner.core.relays.benefit(player, 'convoy_patrol', actor.zone) is None:
            return []
        routes = []
        for plan in owner.active():
            route = owner.content.routes.get(plan.allocations.get('route', ''))
            if route and not plan.allocations.get('convoy_lost'):
                points = [list(point.tile) for point in route.waypoints[int(plan.allocations.get('waypoint', 0)):]
                          if point.zone == actor.zone]
                if points:
                    routes.append({'name': 'Convoy', 'waypoints': points})
        return routes

    def telemetry(self, player: Player, rid: str) -> list[str]:
        owner, relays = self.owner, self.owner.core.relays
        relay = owner.content.relays[rid]
        actor = owner.world.actors.get(player.id)
        if not actor or actor.zone != relay.zone or relays.benefit(player, relay.benefit.kind, actor.zone) is None:
            return []
        if relay.benefit.kind == 'convoy_patrol':
            return [row['name']+': '+' -> '.join(str(tuple(tile)) for tile in row['waypoints'])
                    for row in self.patrols(player)]
        lines = []
        for plan in owner.scheduler.reserved():
            if actor.zone not in plan.where:
                continue
            if relay.benefit.kind == 'impact_forecast':
                if not plan.starts_at-BEACON_SECONDS <= owner.now() < plan.ends_at:
                    continue
                for site in plan.allocations.get('sites', {}).values():
                    if site.get('kind') == 'hazard' and site['zone'] == actor.zone:
                        lines.append('Committed impact '+str(tuple(site['tile']))+' / '+owner.time(plan.starts_at))
            elif relay.benefit.kind == 'long_range_telemetry':
                lines.append(owner.text(plan, detailed=True))
        if relay.benefit.kind == 'long_range_telemetry':
            # The relay's public carrier record is authored, never a caller log.
            lines.append('Carrier: '+relay.name+' / '+owner.place(relay.zone))
        return lines
