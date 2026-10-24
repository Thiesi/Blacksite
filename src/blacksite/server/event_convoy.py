"""Committed Convoy routes use ordinary NPC movement and source receipts."""

from typing import Any
from collections import deque
from dataclasses import dataclass

from blacksite.content.schema import Region, Spawner
from blacksite.server.world.movement import move as move_actor
from blacksite.server.clock import TICK_HZ
from blacksite.server.rules.events import DETOUR_SECONDS
from blacksite.server.world.actors import Actor
from blacksite.server.world.zone import ZoneInstance
from blacksite.server.items import ItemInstance
from blacksite.server.sessions import Session


@dataclass
class Walk:
    key: tuple[Any, ...]
    origin: tuple[int, int]
    tiles: deque[tuple[int, int]]
    retry: int = 0


class Convoys:
    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.walk: Walk | None = None  # One public Convoy; derived, never authority.

    def use(self, session: Session, item: ItemInstance) -> bool:
        if item.template != 'con_kestrel_beacon':
            return False
        owner = self.owner
        body = owner.world.actors.get(session.player_id)
        if not body or body.stance != 'normal' or any(effect.get('hush') for effect in body.effects):
            raise ValueError('You cannot signal a convoy while hushed or concealed.')
        actor = next((actor for actor in owner.world.actors.values()
            if actor.zone == body.zone and actor.behaviour.get('convoy')
            and owner.world.zones[body.zone].allows_hostile(body.position)), None)
        plan = owner.scheduler.plans.get(actor.behaviour['convoy']) if actor else None
        if (plan is None or plan not in owner.active() or plan.allocations.get('convoy_lost')
                or 'convoy-arrived' in plan.reward_receipts):
            raise ValueError('No travelling public convoy can hear you in this zone. Your beacon remains.')
        receipt = 'beacon:'+str(plan.allocations.get('waypoint', 0))
        if plan.allocations.get('detour') or receipt in plan.reward_receipts:
            raise ValueError('This convoy leg already has a signal. Your beacon remains.')
        # The existing local route finder proves a passable connection first.
        zone = owner.world.zones[body.zone]
        pending, seen = deque([actor.position]), {actor.position}
        while pending and body.position not in seen:
            x, y = pending.popleft()
            for tile in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if tile not in seen and zone.can_enter(actor, tile) and zone.allows_hostile(tile):
                    seen.add(tile)
                    pending.append(tile)
        if body.position not in seen:
            raise ValueError('The convoy cannot reach that signal. Your beacon remains.')
        draft = owner.scheduler.fork()
        target = draft.plans[plan.id]
        target.claim(receipt)
        target.allocations['detour'] = {'zone': body.zone, 'tile': list(body.position),
            'ends_at': owner.now()+DETOUR_SECONDS}
        target.revision += 1
        if not owner.write(draft, [], lambda success: owner.notify(
                'The public convoy accepts a local detour. Read the updated route.') if success else None, consume=item):
            raise ValueError('The city is busy. Your beacon remains.')
        return True

    def follow(self, actor: Actor, zone: ZoneInstance, target: tuple[int, int],
               tick: int, avoid: set[tuple[int, int]], *, exact: bool = False) -> None:
        if tick < actor.cooldowns.get('move', 0):
            return
        blocked = avoid | {other.position for other in zone.actors.values() if other is not actor}
        key = actor.id, zone.id, target, exact, zone.geometry_revision
        path = self.walk
        valid = bool(path and path.key == key and path.origin == actor.position)
        if valid and not path.tiles and tick < path.retry:
            return
        if (not valid or not path.tiles or path.tiles[0] in blocked
                or not zone.can_enter(actor, path.tiles[0])):
            def arrived(tile: tuple[int, int]) -> bool:
                return tile == target if exact else max(abs(tile[0]-target[0]), abs(tile[1]-target[1])) <= 1
            pending, previous = deque([actor.position]), {actor.position: None}
            destination = None
            while pending:
                tile = pending.popleft()
                if arrived(tile):
                    destination = tile
                    break
                x, y = tile
                for adjacent in ((x+1,y),(x,y+1),(x-1,y),(x,y-1)):
                    if adjacent not in previous and adjacent not in blocked and zone.can_enter(actor, adjacent):
                        previous[adjacent] = tile
                        pending.append(adjacent)
            tiles: deque[tuple[int, int]] = deque()
            while destination is not None and destination != actor.position:
                tiles.appendleft(destination)
                destination = previous[destination]
            path = self.walk = Walk(key, actor.position, tiles, tick+TICK_HZ)
        if not path.tiles:
            return
        x, y = path.tiles[0]
        direction = {(1,0):'right',(-1,0):'left',(0,1):'down',(0,-1):'up'}[x-actor.x,y-actor.y]
        if move_actor(actor, zone, direction, tick):
            path.tiles.popleft()
            path.origin = actor.position

    def bind(self) -> None:
        owner = self.owner
        npc = owner.core.npcs
        extra = npc.spawners.extra
        npc.spawners.extra = lambda zone: (*extra(zone), *self.extra(zone))
        spawned = npc.spawners.on_spawn
        def on_spawn(actor: Actor, spec: Spawner) -> None:
            spawned(actor, spec)
            for plan, effect in owner.each('convoy_route'):
                if spec.id != f'event:{plan.id}:convoy':
                    continue
                actor.behaviour.update(event=plan.id, convoy=plan.id)
                actor.health = min(actor.health_max, int(plan.allocations.get('convoy_health', actor.health)))
        npc.spawners.on_spawn = on_spawn
        awake = npc.keep_awake
        npc.keep_awake = lambda zone: awake(zone) or self.awake(zone)
        motion = npc.event_motion
        npc.event_motion = lambda actor, zone, tick, avoid: motion(actor, zone, tick, avoid) or self.move(actor, zone, tick, avoid)

    def extra(self, zone: ZoneInstance) -> tuple[Spawner, ...]:
        owner, result = self.owner, []
        for plan, effect in owner.each('convoy_route'):
            if plan.allocations.get('convoy_lost'):
                continue
            if any(actor.behaviour.get('convoy') == plan.id for actor in owner.world.actors.values()):
                continue
            route = owner.content.routes[plan.allocations['route']]
            position = plan.allocations.get('convoy_position', {
                'zone': route.waypoints[0].zone, 'tile': route.waypoints[0].tile})
            if zone.id != position['zone']:
                continue
            # A killed convoy cannot respawn within this event; its death
            # receipt also closes its shared jobs and records the lost source.
            tile = tuple(position['tile'])
            occupied = {actor.position for actor in zone.actors.values()}
            region = Region(tile[0]-1, tile[1]-1, 3, 3) if tile in (
                owner.core.npcs.spawners.reserved(zone) | occupied) else None
            result.append(Spawner(f'event:{plan.id}:convoy', str(effect.params['npc']), 1,
                int(plan.ends_at-plan.starts_at)+1, tile, region))
        return tuple(result)

    def awake(self, zone: str) -> bool:
        owner = self.owner
        for plan, effect in owner.each('convoy_route'):
            if plan.allocations.get('convoy_lost'):
                continue
            actor = next((actor for actor in owner.world.actors.values()
                          if actor.behaviour.get('convoy') == plan.id), None)
            route = owner.content.routes[plan.allocations['route']]
            current = actor.zone if actor else plan.allocations.get(
                'convoy_position', {'zone': route.waypoints[0].zone})['zone']
            if current == zone:
                return True
        return False

    def move(self, actor: Actor, zone: ZoneInstance, tick: int,
             avoid: set[tuple[int, int]]) -> bool:
        owner = self.owner
        pid = actor.behaviour.get('convoy')
        if not pid:
            return False
        plan = next((plan for plan in owner.active() if plan.id == pid), None)
        if plan is None or plan.allocations.get('convoy_lost'):
            return True
        route = owner.content.routes[plan.allocations['route']]
        index = int(plan.allocations.get('waypoint', 0))
        if index >= len(route.waypoints):
            return True
        target = route.waypoints[index]
        actor.modifiers['move_ms'] = max(actor.modifiers.get('move_ms', 0), 1000/route.speed)
        detour = plan.allocations.get('detour')
        if detour and (detour['zone'] == actor.zone or owner.now() >= detour.get('ends_at', 0)):
            tile = tuple(detour['tile'])
            expired = owner.now() >= detour.get('ends_at', 0)
            if not expired and max(abs(actor.x-tile[0]), abs(actor.y-tile[1])) > 1:
                self.follow(actor, zone, tile, tick, avoid-{tile})
            elif not owner.commerce.pending:
                draft = owner.scheduler.fork()
                draft.plans[pid].allocations.pop('detour')
                draft.plans[pid].revision += 1
                owner.write(draft, [], lambda success: owner.notify(
                    'The public convoy returns to its committed route.') if success else None)
            return True
        if target.zone != actor.zone:
            exit = owner.core.contracts.scenes.route(actor.zone, target.zone)
            if exit:
                if actor.position == exit.tile:
                    try:
                        tile = owner.world.free_tile(exit.target_zone, exit.target_tile, actor)
                    except ValueError:
                        return True
                    owner.world.enter(actor, exit.target_zone, tile)
                else:
                    self.follow(actor, zone, exit.tile, tick, avoid-{exit.tile}, exact=True)
            return True
        if max(abs(actor.x-target.tile[0]), abs(actor.y-target.tile[1])) > 1:
            self.follow(actor, zone, target.tile, tick, avoid-{target.tile})
            return True
        if owner.commerce.pending:
            return True
        draft = owner.scheduler.fork()
        current = draft.plans[pid]
        current.allocations.update(waypoint=index+1,
            convoy_position={'zone': actor.zone, 'tile': list(actor.position)}, convoy_health=actor.health)
        final = index+1 == len(route.waypoints)
        facts = owner.jobs.checkpoint(current, actor, final=final)
        if final:
            current.claim('convoy-arrived')
            current.revision += 1
        owner.write(draft, [], facts=facts)
        return True
