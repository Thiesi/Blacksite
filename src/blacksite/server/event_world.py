"""Game 12 physical sources and layers, proposed through commerce."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from random import Random
from typing import Any

from blacksite.content.schema import Effect, Spawner, TileChange, ZoneLayout
from blacksite.server.clock import TICK_HZ
from blacksite.server.event_effects import compatible, swap
from blacksite.server.events import Plan, Scheduler, Transition
from blacksite.server.items import ItemInstance, make_item
from blacksite.server.rules.events import EXHALE_RATE, WARNING_SECONDS
from blacksite.server.world.actors import Actor
from blacksite.server.world.zone import GeometryLayer, ZoneInstance


@dataclass
class Proposal:
    items: dict[str, ItemInstance]
    caches: dict[str, dict[str, Any]]
    serial: int
    salvage: dict[str, Any] | None = None


class WorldEffects:
    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.layers: set[tuple[str, str]] = set()
        self.originals: dict[str, str] = {}
        self.warnings: dict[tuple[str, str], int] = {}

    @staticmethod
    def pass_valid(item: ItemInstance, now: float) -> bool:
        # Catalog key_curfew_pass: seven days from its actual acquisition.
        return bool(item.created_at and 0 <= now-datetime.fromisoformat(item.created_at).timestamp() < 7*86400)

    def allocate(self, scheduler: Scheduler, plan: Plan) -> None:
        """Freeze source sites before a paid/free preview can name them."""
        owner = self.owner
        sites = {}
        for index, effect in enumerate(scheduler.effects(plan)):
            if effect.type not in ('hazard', 'key_drop', 'npc_spawn') or not effect.zone:
                continue
            zone = owner.world.zones[effect.zone]
            candidates = effect.region.tiles() if effect.region else [zone.template.meta.spawn]
            reserved = {exit.tile for exit in zone.template.meta.exits}
            reserved.update(obj.spec.tile for obj in zone.objects.values())
            candidates = [tile for tile in candidates if tile and tile not in reserved
                          and zone.passable(tile) and zone.allows_hostile(tile)]
            if not candidates:
                raise ValueError('That event has no safe, authored source site.')
            tile = Random(plan.seed+index).choice(sorted(candidates))
            site = {'zone': effect.zone, 'tile': list(tile), 'kind': effect.type}
            if effect.type == 'hazard':
                radius = int(effect.params.get('radius', 0))
                site['tiles'] = [list(cell) for cell in sorted(candidates)
                    if sum((a-b)**2 for a, b in zip(cell, tile)) <= radius**2]
            sites[str(index)] = site
        plan.allocations['sites'] = sites
        plan.allocations['definition'] = owner.definition(plan)
        template = owner.content.events[plan.template]
        if template.route:
            plan.allocations['route'] = template.route
            plan.allocations['waypoint'] = 0

    def stage(self, scheduler: Scheduler, transitions: list[Transition]) -> Proposal:
        owner = self.owner
        proposal = Proposal(deepcopy(owner.commerce.items), deepcopy(owner.commerce.caches), owner.commerce.serial)
        for transition in transitions:
            plan = scheduler.plans[transition.plan]
            if transition.kind == 'start':
                for index, effect in enumerate(scheduler.effects(plan)):
                    source = f'{effect.type}:{index}'
                    if effect.type == 'salvage' and plan.claim(source):
                        self.salvage(proposal, plan, effect)
                    elif effect.type == 'key_drop' and plan.claim(source):
                        site = plan.allocations['sites'][str(index)]
                        template = owner.content.items[str(effect.params['item'])]
                        cache = f'{plan.id}:key:{index}'
                        ids = []
                        for _ in range(int(effect.params.get('count', 1))):
                            proposal.serial += 1
                            iid = f'{owner.core.sessions.origin}:item:{proposal.serial}'
                            proposal.items[iid] = make_item(iid, template, cache, owner.clock.now_utc().isoformat())
                            ids.append(iid)
                        proposal.caches[cache] = {'zone': site['zone'], 'tile': site['tile'],
                            'items': ids, 'expires': plan.ends_at, 'event': plan.id}
            elif transition.kind in ('end', 'cancel'):
                if proposal.salvage is None and any(
                        node.get('event') == plan.id for field in owner.core.salvage.state['zones'].values()
                        for node in field['nodes'].values()):
                    proposal.salvage = owner.core.salvage.record()
                if proposal.salvage is not None:
                    for field in proposal.salvage['zones'].values():
                        field['nodes'] = {key: node for key, node in field['nodes'].items()
                                          if node.get('event') != plan.id}
                expired = {key for key, cache in proposal.caches.items() if cache.get('event') == plan.id}
                proposal.caches = {key: cache for key, cache in proposal.caches.items() if key not in expired}
                proposal.items = {key: item for key, item in proposal.items.items() if item.owner not in expired}
        return proposal

    def salvage(self, proposal: Proposal, plan: Plan, effect: Effect) -> None:
        owner = self.owner
        engine = owner.core.salvage
        zone = owner.world.zones[effect.zone]
        marker = next((obj for obj in zone.objects.values() if obj.spec.kind == 'salvage_field'), None)
        if marker is None:
            raise ValueError('Ring-fall needs a commissioned salvage field.')
        if proposal.salvage is None:
            proposal.salvage = engine.record()
        state = proposal.salvage
        if effect.zone not in state['zones']:
            state['zones'][effect.zone] = {'ring': marker.spec.params['ring'], 'nodes': {},
                'respawn_at': engine.uptime+engine.rules.respawn_seconds}
            baseline = engine.rng(effect.zone, state)
            for _ in range(baseline.randint(engine.rules.minimum_nodes, engine.rules.maximum_nodes)):
                engine.spawn(effect.zone, state, baseline)
            state['zones'][effect.zone]['rng'] = baseline.getstate()
        field = state['zones'][effect.zone]
        rng = Random(plan.seed)
        count = int(effect.params['count'])
        count = min(count, max(0, int(effect.params['cap'])-len(field['nodes'])))
        for _ in range(count):
            before = set(field['nodes'])
            if engine.spawn(effect.zone, state, rng):
                for key in set(field['nodes'])-before:
                    field['nodes'][key]['event'] = plan.id

    def install(self, proposal: Proposal) -> None:
        if proposal.salvage is not None:
            self.owner.core.salvage.state = proposal.salvage
            self.owner.core.salvage.sync()

    def bind(self) -> None:
        owner = self.owner
        spawners = owner.core.npcs.spawners
        extra = spawners.extra
        spawners.extra = lambda zone: (*extra(zone), *self.extra(zone))
        policy = spawners.policy
        def composed(zone: ZoneInstance, spec: Spawner) -> tuple[int, float]:
            count, delay = policy(zone, spec)
            for plan, effect in owner.each('spawn_multiplier'):
                if effect.zone != zone.id or (effect.params.get('spawner') and effect.params['spawner'] != spec.id):
                    continue
                rate = owner.number(plan.template, 'spawn_rate', float(effect.params['multiplier']), 1, EXHALE_RATE)
                bonus = int(owner.number(plan.template, 'wave_cap_bonus', 0, 0, 2))
                count = min(int(effect.params['cap'])+bonus, count+bonus)
                delay /= rate
            return count, delay
        spawners.policy = composed
        spawned = spawners.on_spawn
        def on_spawn(actor: Actor, spec: Spawner) -> None:
            spawned(actor, spec)
            for plan in owner.active():
                if spec.id.startswith(f'event:{plan.id}:'):
                    actor.behaviour['event'] = plan.id
        spawners.on_spawn = on_spawn

    def extra(self, zone: ZoneInstance) -> tuple[Spawner, ...]:
        owner = self.owner
        result = []
        for plan in owner.active():
            for index, effect in enumerate(owner.scheduler.effects(plan)):
                if effect.type != 'npc_spawn' or effect.zone != zone.id:
                    continue
                site = plan.allocations['sites'][str(index)]
                result.append(Spawner(f'event:{plan.id}:{index}', str(effect.params['npc']),
                    int(effect.params['count']), int(effect.params['respawn_seconds']),
                    tuple(site['tile']), effect.region))
        return tuple(result)

    def geometry(self) -> None:
        owner = self.owner
        now, tick = owner.now(), owner.clock.now_tick()
        wanted = set()
        for plan in owner.scheduler.reserved():
            if (not plan.live or now >= plan.ends_at or 'warning' not in plan.milestones
                    or plan.template not in owner.content.events
                    or not owner.eligible(owner.content.events[plan.template], plan.where)):
                continue
            for index, effect in enumerate(owner.scheduler.effects(plan)):
                if effect.type not in ('hazard', 'route_hold') or not effect.zone:
                    continue
                zone = owner.world.zones[effect.zone]
                until = min(plan.ends_at, plan.starts_at+float(effect.params.get('seconds', plan.ends_at-plan.starts_at)))
                if now >= until:
                    continue
                source = f'event:{plan.id}:{index}'
                key = zone.id, source
                if key not in self.layers:
                    if effect.type == 'hazard':
                        tiles = tuple(tuple(tile) for tile in plan.allocations['sites'][str(index)]['tiles'])
                        changes = tuple(TileChange(tile, 'hazard') for tile in tiles)
                        layout = ZoneLayout(source, changes, tiles,
                            tuple(exit.id for exit in zone.template.meta.exits if not exit.hidden))
                    else:
                        if 'layout' not in effect.params:
                            continue  # Exit predicates are composed at departure.
                        layout = next(layout for layout in zone.template.meta.layouts
                                      if layout.id == effect.params['layout'])
                    starts = tick+max(0, int((plan.starts_at-now)*TICK_HZ))
                    starts = max(starts, owner.warning_until.get(plan.id, 0))
                    if now >= plan.starts_at and effect.type == 'hazard':
                        # Returning after downtime never takes an offline strike.
                        starts = tick+WARNING_SECONDS*TICK_HZ
                    expires = tick+max(0, int((until-now)*TICK_HZ))
                    if starts >= expires:
                        continue
                    zone.layers[source] = GeometryLayer(source, layout, starts, expires)
                    zone.revision += 1
                wanted.add(key)
        for zid, source in self.layers-wanted:
            zone = owner.world.zones[zid]
            zone.layers.pop(source, None)
            zone.revision += 1
        touched = {zid for zid, _ in self.layers | wanted}
        for zid in touched:
            owner.world.zones[zid].compose(tick)
        self.layers = wanted

    def ice(self) -> None:
        owner = self.owner
        tick = owner.clock.now_tick()
        active = {plan.id for plan in owner.active()}
        swaps = [(plan, effect) for plan in owner.scheduler.reserved()
                 if plan.live and plan.ends_at > owner.now() and 'warning' in plan.milestones
                 and plan.template in owner.content.events
                 for effect in owner.scheduler.effects(plan) if effect.type == 'ice_variant']
        live_ids = set()
        for instance in owner.lat.encounters.instances.values():
            if instance.graph.spec.training or instance.graph.spec.owner_kind == 'private':
                continue
            presences = [p for p in owner.lat.presences.values() if p.instance == instance.id]
            sectors = {p.sector for p in presences}
            for ice in instance.ice.values():
                live_ids.add(ice.id)
                base = owner.content.ice[self.originals.get(ice.id, ice.template.id)]
                chosen = None
                for plan, effect in swaps:
                    if (effect.sector and effect.sector not in sectors
                            or effect.params['from'] != base.id
                            or owner.tuning(plan.template, 'surge_variants') is False):
                        continue
                    variant = owner.content.ice[str(effect.params['to'])]
                    if not compatible(base, variant):
                        continue
                    key = ice.id, plan.id
                    if key not in self.warnings:
                        self.warnings[key] = tick+WARNING_SECONDS*TICK_HZ
                        for presence in presences:
                            owner.lat.encounters.log(presence,
                                f'{variant.name}: {variant.counter_label}. Surge changes this defender in 5s.', True)
                    if tick >= self.warnings[key] and plan.id in active:
                        chosen = variant
                target = chosen or base
                if ice.template.id != target.id:
                    self.originals.setdefault(ice.id, base.id)
                    swap(ice, target, instance.graph.spec.tier, tick)
        self.originals = {iid: base for iid, base in self.originals.items() if iid in live_ids}
        live = {plan.id for plan in owner.scheduler.reserved()}
        self.warnings = {key: until for key, until in self.warnings.items()
                         if key[0] in live_ids and key[1] in live}

    def refresh(self) -> None:
        self.geometry()
        self.ice()
        self.reveal()
        live = {plan.id for plan in self.owner.active()}
        for actor in tuple(self.owner.world.actors.values()):
            if (actor.behaviour.get('event') and actor.behaviour['event'] not in live
                    and actor.id not in self.owner.core.npcs.pending_deaths):
                self.owner.world.leave(actor)

    def reveal(self) -> None:
        owner = self.owner
        for plan, effect in owner.each('reveal'):
            if effect.params.get('what') != 'silt_band':
                continue
            for presence in owner.lat.presences.values():
                if not presence.descent or effect.sector and effect.sector != presence.sector:
                    continue
                graph = owner.lat.encounters.core(presence).graph
                # Knowledge belongs only to the current instantiated band.
                # It pays no skill/XP and contains no future seed or identity.
                presence.found_silt.setdefault(presence.instance, set()).update(
                    cell.id for cell in graph.band.cells)
