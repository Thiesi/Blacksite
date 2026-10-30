"""Game 7.5: owned service geometry and narrowly scoped economic effects."""

from blacksite.server.interaction import Interaction, object_interaction
from math import ceil
from copy import deepcopy
from typing import Any, Iterator

from blacksite.content.schema import Effect, StageTarget
from blacksite.server.clock import TICK_HZ
from blacksite.server.contracts.engine import matches
from blacksite.server.contracts.services import ALLOCATION_SECONDS, FAULT_SECONDS, RESERVE_CACHE_UNITS
from blacksite.server.items import make_item
from blacksite.server.inventory import Inventory
from blacksite.server.world.zone import GeometryLayer


class ServiceEffects:
    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.layers: set[tuple[str, str]] = set()
        self.announced: set[tuple[str, str, str]] = set()
        self.status_stamps: dict[str, tuple[Any, ...]] = {}

    def each(self, player: str = '') -> Iterator[tuple[str, Effect]]:
        services = self.owner.state.services
        for sid in services.nodes:
            for effect in services.effects(sid, player, self.owner.now()):
                yield sid, effect

    def fee(self, player: Any, vendor: Any) -> float:
        actor = self.owner.game.combat.actor(player)
        if not actor:
            return 1
        return min((float(effect.params.get('multiplier', 1)) for _, effect in self.each(player.id)
            if effect.type == 'price_modifier' and effect.params.get('service') == 'surgery'
            and effect.zone == actor.zone and effect.params.get('vendor', vendor.id) == vendor.id), default=1)

    def budget(self, vendor: Any, counter: str) -> float:
        zone, _, object_id = counter.partition(':')
        return max((float(effect.params.get('multiplier', 1)) for _, effect in self.each()
            if effect.type == 'price_modifier' and effect.params.get('service') == 'buyback_budget'
            and effect.zone == zone and effect.params.get('vendor', vendor.id) == vendor.id
            and effect.params.get('object', object_id) == object_id), default=1)

    def permits(self, player: str, core: str, control: str) -> bool:
        target = StageTarget('core_control', core=core, control=control)
        return any(effect.type == 'reveal' and effect.params.get('what') == 'credential'
            and effect.binding is not None and matches(effect.binding, target)
            for _, effect in self.each(player))

    def vendor_open(self, zone: str, vendor: str, counter: str) -> bool:
        return not any(effect.type == 'entry_restriction' and effect.zone == zone
            and effect.params.get('service') == 'vendor' and effect.params.get('vendor') == vendor
            and effect.params.get('object', counter) == counter for _, effect in self.each())

    def patrols(self, player: str) -> list[str]:
        """Only committed telemetry reveals authored NPC/ICE routes.

        This never includes player presences, storage or unpublished names.
        The display is a current route, not immunity or a second RNG roll.
        """
        bindings = [effect.binding for _, effect in self.each(player)
                    if effect.type == 'reveal' and effect.params.get('what') == 'patrol_route' and effect.binding]
        for holder in (player, '*'):
            for row in self.owner.state.permits.get(holder, {}).values():
                raw = row['permit']
                if raw['kind'] in ('route', 'patrol_window') and self.owner.now() < row['until'] and raw.get('binding'):
                    from blacksite.server.contracts.engine import target_record
                    bindings.append(target_record(raw['binding']))
        presence = self.owner.lat.presences.get(player)
        body = self.owner.world.actors.get(player)
        lines = []
        for binding in bindings:
            if binding.core and presence and presence.core == binding.core:
                instance = self.owner.lat.encounters.core(presence)
                if not instance:
                    continue
                for ice in instance.ice.values():
                    if not ice.alive:
                        continue
                    rooms = [room for _, room in ice.patrol] or [ice.location[1]]
                    labels = [instance.graph.room(room).label for room in rooms]
                    lines.append(ice.template.name+': '+' -> '.join(labels))
            elif binding.npc and body and body.zone == binding.zone:
                for actor in self.owner.world.zones[body.zone].actors.values():
                    if (actor.kind == 'player' or actor.behaviour.get('mission')
                            or actor.behaviour.get('template') != binding.npc):
                        continue
                    template = self.owner.content.npcs[binding.npc]
                    points = next((b.params.get('waypoints', []) for b in template.behaviours if b.kind == 'patrol'), [])
                    lines.append(template.name+': '+(' -> '.join(str(tuple(p)) for p in points) or str(actor.position)))
        return list(dict.fromkeys(lines))

    def compose(self, tick: int) -> None:
        wanted = set()
        now = self.owner.now()
        for sid, node in self.owner.state.services.nodes.items():
            status_deadline = node.allocation_expires if node.state == 'allocated' else node.fault_expires
            stamp = node.state, node.allocation, node.revision, max(0, ceil(status_deadline-now))
            if self.status_stamps.get(sid) != stamp:
                self.owner.world.zones[self.owner.content.services[sid].zone].revision += 1
                self.status_stamps[sid] = stamp
            if node.state == 'normal':
                continue  # Ordinary geometry is the authored base map.
            deadline = node.allocation_expires if node.state == 'allocated' else node.fault_expires
            started = deadline - (ALLOCATION_SECONDS if node.state == 'allocated' else FAULT_SECONDS)
            for index, effect in enumerate(self.owner.state.services.effects(sid, '', now)):
                layout_id = effect.params.get('layout')
                if not effect.zone or not layout_id:
                    continue
                zone = self.owner.world.zones[effect.zone]
                layout = next(item for item in zone.template.meta.layouts if item.id == layout_id)
                source = f'service:{sid}:{index}'
                starts = tick+ceil((started+effect.warning_seconds-now)*TICK_HZ)
                expires = tick+ceil((deadline-now)*TICK_HZ)
                layer = GeometryLayer(source, layout, starts, expires)
                if zone.layers.get(source) != layer:
                    zone.layers[source] = layer
                    zone.revision += 1
                wanted.add((zone.id, source))
                tag = (sid, node.order or str(node.generation), 'start')
                if now < started+effect.warning_seconds and tag not in self.announced:
                    self.zone_log(zone.id, f'{self.owner.content.services[sid].name}: route changes in '
                        f'{ceil(started+effect.warning_seconds-now)} s. '+self.owner.content.services[sid].safe_return)
                    self.announced.add(tag)
                tag = (sid, node.order or str(node.generation), 'expiry')
                if 0 < deadline-now <= effect.warning_seconds and tag not in self.announced:
                    self.zone_log(zone.id, f'{self.owner.content.services[sid].name}: allocation ends in '
                        f'{ceil(deadline-now)} s. '+self.owner.content.services[sid].safe_return)
                    self.announced.add(tag)
        touched = {zid for zid, _ in self.layers | wanted}
        for zid, source in self.layers-wanted:
            self.owner.world.zones[zid].layers.pop(source, None)
            self.owner.world.zones[zid].revision += 1
        self.layers = wanted
        current = {(sid, node.order or str(node.generation)) for sid, node in self.owner.state.services.nodes.items()}
        self.announced = {tag for tag in self.announced if tag[:2] in current}
        for zid in touched:
            self.owner.world.zones[zid].compose(tick)

    def zone_log(self, zone: str, text: str) -> None:
        for player in self.owner.game.players.values():
            actor = self.owner.game.combat.actor(player)
            if actor and actor.zone == zone:
                self.owner.log(player.id, text)

    def cache_interaction(self, session: Any) -> Interaction | None:
        player = self.owner.game.players[session.player_id]
        actor = self.owner.game.combat.actor(player)
        for sid, effect in self.each(player.id):
            if effect.type != 'cache' or effect.zone != actor.zone:
                continue
            obj = self.owner.world.zones[actor.zone].objects.get(effect.params.get('object'))
            if obj and max(abs(actor.x-obj.spec.tile[0]), abs(actor.y-obj.spec.tile[1])) <= 1:
                choice = object_interaction(obj, 'collect')
                return Interaction(choice.focus, (sid, effect), choice.tile)
        return None

    def cache(self, session: Any, choice: Interaction | None = None) -> bool:
        player = self.owner.game.players[session.player_id]
        actor = self.owner.game.combat.actor(player)
        choice = choice or self.cache_interaction(session)
        if choice:
            sid, effect = choice.value
            if self.owner.commerce.pending:
                raise ValueError('Let the current transfer settle first.')
            draft = self.owner.state.fork()
            node = draft.services.nodes[sid]
            count = draft.services.take_cache(sid, node.order, player.id, RESERVE_CACHE_UNITS, self.owner.now())
            if not count:
                raise ValueError('This work order\'s shared cache is empty or not reserved for you.')
            recipient, items = deepcopy(player), deepcopy(self.owner.commerce.items)
            serial = self.owner.commerce.serial
            inventory = Inventory(items, self.owner.content.items, self.owner.progression.modifiers(player).secured_slots)
            for _ in range(count):
                serial += 1
                inventory.add(recipient, make_item(f'{self.owner.origin}:item:{serial}',
                    self.owner.content.items['slv_power'], player.id, self.owner.clock.now_utc().isoformat()))
            self.owner.write(draft, {player.id: {'inventory': recipient.inventory}}, items=items, serial=serial,
                callback=lambda success: self.owner.log(player.id,
                    f'Workers\' cache: {count} power units.' if success else 'The cache could not be saved. Its stock remains.'))
            return True
        return False
