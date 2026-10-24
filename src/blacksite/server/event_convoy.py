"""Committed Convoy routes use ordinary NPC movement and source receipts."""

from typing import Any

from blacksite.content.schema import Region, Spawner
from blacksite.server.npcs.behaviours import step_toward
from blacksite.server.world.actors import Actor
from blacksite.server.world.zone import ZoneInstance
from blacksite.server.items import ItemInstance
from blacksite.server.sessions import Session


class Convoys:
    def __init__(self, owner: Any) -> None:
        self.owner = owner

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
        from collections import deque
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
        target.allocations['detour'] = {'zone': body.zone, 'tile': list(body.position)}
        target.revision += 1
        if not owner.write(draft, [], lambda success: owner.notify(
                'The public convoy accepts a local detour. Read the updated route.') if success else None, consume=item):
            raise ValueError('The city is busy. Your beacon remains.')
        return True

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
        detour = plan.allocations.get('detour')
        if detour and detour['zone'] == actor.zone:
            tile = tuple(detour['tile'])
            if max(abs(actor.x-tile[0]), abs(actor.y-tile[1])) > 1:
                step_toward(actor, zone, tile, tick, avoid=avoid-{tile})
            elif not owner.commerce.pending:
                draft = owner.scheduler.fork()
                draft.plans[pid].allocations.pop('detour')
                owner.write(draft, [])
            return True
        actor.modifiers['move_ms'] = max(actor.modifiers.get('move_ms', 0), 1000/route.speed)
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
                    step_toward(actor, zone, exit.tile, tick, avoid=avoid-{exit.tile})
            return True
        if max(abs(actor.x-target.tile[0]), abs(actor.y-target.tile[1])) > 1:
            step_toward(actor, zone, target.tile, tick, avoid=avoid-{target.tile})
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
        owner.write(draft, [], facts=facts)
        return True
