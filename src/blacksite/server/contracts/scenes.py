"""Game 9.3: reconstruct mission-owned bodies from committed objectives."""

from collections import deque
from dataclasses import asdict
from typing import Any

from blacksite.server.contracts.engine import Fact, Instance, Progress
from blacksite.server.npcs.behaviours import step_toward
from blacksite.server.npcs.templates import EVALUATION_TICKS, make_actor
from blacksite.server.world.actors import Actor


class Scenes:
    def __init__(self, owner: Any) -> None:
        self.owner, self.world, self.game = owner, owner.world, owner.game

    @staticmethod
    def unit(instance: Instance, progress: Progress, index: int) -> str:
        return f'{instance.id}:npc:{progress.stage.id}:{progress.attempt}:{index}'

    def checkpoint(self) -> None:
        for actor in self.world.actors.values():
            iid = actor.behaviour.get('mission')
            instance = self.owner.state.engine.instances.get(iid)
            if instance and actor.behaviour.get('contract_target'):
                instance.runtime.setdefault('actors', {})[actor.id] = {
                    'zone': actor.zone, 'tile': actor.position, 'health': actor.health,
                    'shock': actor.shock, 'escort': actor.behaviour.get('escort')}

    def current(self, actor: Actor) -> bool:
        instance = self.owner.state.engine.instances.get(actor.behaviour.get('mission'))
        if not instance or instance.state != 'active':
            return False
        progress = instance.stages[instance.index]
        return (progress.stage.id == actor.behaviour.get('contract_stage')
                and progress.attempt == actor.behaviour.get('contract_attempt')
                and actor.id not in progress.subjects)

    def reconcile(self) -> None:
        # Run after source callbacks, never from the draft installer: NPC
        # death retirement still needs the original body's zone there.
        for actor in tuple(self.world.actors.values()):
            if not actor.behaviour.get('contract_target'):
                continue
            if actor.id in self.game.npcs.pending_deaths:
                continue
            if not self.current(actor):
                self.world.leave(actor)
            else:
                instance = self.owner.state.engine.instances[actor.behaviour['mission']]
                actor.behaviour['mission_roster'] = tuple(p.player for p in instance.roster
                                                         if p.player not in instance.withdrawn)
                if actor.behaviour.get('escort') not in actor.behaviour['mission_roster']:
                    actor.behaviour.pop('escort', None)
        for instance in self.owner.state.engine.instances.values():
            if instance.state != 'active':
                continue
            progress = instance.stages[instance.index]
            if progress.stage.verb not in ('clear', 'escort'):
                continue
            for index, target in enumerate(progress.targets):
                if not target.npc or not target.zone or target.zone not in self.world.zones:
                    continue
                aid = self.unit(instance, progress, index)
                if aid in progress.subjects or aid in self.world.actors:
                    continue
                roster = tuple(p.player for p in instance.roster if p.player not in instance.withdrawn)
                saved = instance.runtime.get('actors', {}).get(aid, {})
                zone = str(saved.get('zone') or target.zone)
                # Bodies sleep with their zone and reappear from the last
                # committed checkpoint; another crew never wakes this scene.
                if not any(pid in self.world.actors and self.world.actors[pid].zone == zone for pid in roster):
                    continue
                origin = target.tile
                if origin is None and target.object in self.world.zones[zone].objects:
                    origin = self.world.zones[zone].objects[target.object].spec.tile
                tile = tuple(saved.get('tile', origin or self.world.zones[zone].template.meta.spawn or (1, 1)))
                actor = make_actor(self.owner.content.npcs[target.npc], aid, {
                    'mission': instance.id, 'mission_roster': roster,
                    'contract_stage': progress.stage.id, 'contract_attempt': progress.attempt,
                    'contract_target': asdict(target), 'willing': progress.stage.verb == 'escort',
                    'home': tile, 'phase': index % EVALUATION_TICKS})
                actor.owner = roster[0] if roster else None
                actor.health = max(1, int(saved.get('health', actor.health)))
                actor.shock = float(saved.get('shock', 0))
                if saved.get('escort') in roster:
                    actor.behaviour['escort'] = saved['escort']
                tile = self.world.free_tile(zone, tile, actor)
                self.world.enter(actor, zone, tile)

    def route(self, source: str, destination: str) -> Any:
        """A willing escort uses ordinary public walking exits."""
        pending = deque([(source, None)])
        seen = {source}
        while pending:
            zone, first = pending.popleft()
            for exit in self.world.zones[zone].template.meta.exits:
                if exit.hidden or exit.requirement or exit.kind == 'tram' or exit.target_zone in seen:
                    continue
                if exit.target_zone == destination:
                    return first or exit
                seen.add(exit.target_zone)
                pending.append((exit.target_zone, first or exit))
        return None

    def escorts(self, tick: int) -> None:
        for actor in tuple(self.world.actors.values()):
            if not actor.behaviour.get('contract_target') or not actor.behaviour.get('willing') or not self.current(actor):
                continue
            instance = self.owner.state.engine.instances[actor.behaviour['mission']]
            progress = instance.stages[instance.index]
            destination = progress.stage.destination
            leader = self.world.actors.get(actor.behaviour.get('escort'))
            if not leader or leader.id in instance.withdrawn:
                continue
            if actor.zone != leader.zone and leader.zone:
                exit = self.route(actor.zone, leader.zone)
                if exit:
                    if actor.position == exit.tile:
                        tile = self.world.free_tile(exit.target_zone, exit.target_tile, actor)
                        self.world.enter(actor, exit.target_zone, tile)
                    else:
                        step_toward(actor, self.world.zones[actor.zone], exit.tile, tick)
            if not destination or destination.zone != actor.zone:
                continue
            tile = destination.tile
            if destination.object:
                obj = self.world.zones[actor.zone].objects.get(destination.object)
                tile = obj.spec.tile if obj else None
            if tile and max(abs(actor.x-tile[0]), abs(actor.y-tile[1])) <= 1:
                if self.owner.commerce.pending:
                    continue
                self.owner.commerce.settle(None, {}, self.owner.commerce.items, self.owner.commerce.caches,
                    self.owner.commerce.serial, lambda success, body=actor: self.world.leave(body) if success else None)
                self.owner.source_fact(self.owner.commerce.outbox[-1], Fact(leader.id, 'escort', 'arrived',
                    progress.stage.target, actor.id, actor.id+':arrived', instance=instance.id,
                    stage=progress.stage.id, attempt=progress.attempt))
