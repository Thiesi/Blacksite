"""Demo only (demo/sodium-row-evening, never merged): a stand-in for S38.

Sodium Row keeps the peace. In a truce zone NPCs are never hostile from
the relations matrix; whoever breaks the peace there (an attack on a
player that Marks, or on an NPC not already after them) is Marked when
the target is a player and is answered by the keeper's guards. With
BLACKSITE_DEMO_BOUNCER=1 the Tin Halo also refuses a truce-breaker who
is still Marked (owner question Q7, #143), by any entrance.

Installed only when BLACKSITE_DEMO=sodium-row-evening. It wraps four
existing seams instead of editing them, so S38's real build owns the rule.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

from blacksite.server.npcs.templates import PROVOCATION_SECONDS

if TYPE_CHECKING:
    from blacksite.server.core import Core
    from blacksite.server.world.actors import Actor

DEMO = 'sodium-row-evening'
TRUCE = {'sodium-row': 'sable'}  # zone -> keeper faction (S38's `truce` field)
KEEPER_NAME = {'sable': 'Sable'}
HALO = 'sodium-tin-halo'


def enabled() -> bool:
    return os.environ.get('BLACKSITE_DEMO') == DEMO


def install(core: Core) -> None:
    if not enabled() or not (core.combat and core.npcs):
        return
    Truce(core, bouncer=os.environ.get('BLACKSITE_DEMO_BOUNCER') == '1')


class Truce:
    def __init__(self, core: Core, bouncer: bool) -> None:
        self.core, self.combat, self.npcs = core, core.combat, core.npcs
        self.breakers: dict[str, float] = {}  # player id -> Mark expiry, truce breaks only
        self._hostile, self._would_mark = self.npcs.hostile, self.combat.would_mark
        self._provoked, self._mark = self.combat.hostile_hook, self.combat.mark
        self._mark_indirect, self._target_view = self.combat.mark_indirect, self.combat.target_view
        self.npcs.hostile = self.hostile
        self.combat.would_mark = self.would_mark
        self.combat.hostile_hook = self.provoked
        self.combat.mark = self.mark
        self.combat.mark_indirect = self.mark_indirect
        self.combat.target_view = self.target_view
        view_field()
        sim = core.characters.sim if core.characters else core.simulation
        if bouncer and sim is not None:
            previous = sim.travel_refusal
            sim.travel_refusal = lambda session, exit: previous(session, exit) or self.door(session, exit)

    # NPC hostility: provocation and Warden rules only, never the matrix.
    def hostile(self, actor: Actor, other: Actor) -> bool:
        if actor.zone not in TRUCE or actor.kind == 'player' or actor.zone != other.zone:
            return self._hostile(actor, other)
        if actor.behaviour.get('training'):
            return actor.owner == other.id
        group = actor.behaviour.get('spawner')
        if group and group == other.behaviour.get('spawner'):
            return False
        if self.npcs.provocations.get((actor.zone, str(group), other.id), 0) > self.combat.now():
            return True
        player = self.combat.game.players.get(other.id)
        if actor.faction == 'wardens' and player:
            heat = player.warden_heat_until and datetime.fromisoformat(player.warden_heat_until).timestamp() > self.combat.now()
            return bool(other.marked or heat)
        return False

    # Marking: the hostile-faction exemption does not apply to a target on the Row.
    def would_mark(self, source: Actor, target: Actor, indirect: bool = False) -> bool:
        if (target.zone in TRUCE and source.kind == 'player' and target.kind == 'player'
                and not target.marked and not self.combat.crew_together(source.id, target.id)):
            return True
        return self._would_mark(source, target, indirect)

    def mark(self, source: Actor, target: Actor) -> None:
        self.marking(source, target, self._mark, indirect=False)

    def mark_indirect(self, source: Actor, target: Actor) -> None:
        self.marking(source, target, self._mark_indirect, indirect=True)

    def marking(self, source: Actor, target: Actor, original: Any, indirect: bool) -> None:
        breaking = (target.zone in TRUCE and source.kind == 'player' and not source.marked
                    and self.would_mark(source, target, indirect))
        if breaking:  # the truce line comes before the Mark line
            self.combat.log(source, f"You break {self.zone_name(target.zone)}'s truce.", True)
        original(source, target)
        if breaking and source.marked:
            player = self.combat.game.players.get(source.id)
            if player and player.marked_until:
                self.breakers[source.id] = datetime.fromisoformat(player.marked_until).timestamp()

    # TARGET panel: warn from the truce rules, not the relations matrix.
    def target_view(self, actor: Actor) -> dict[str, Any] | None:
        view = self._target_view(actor)
        target = self.combat.world.actors.get(actor.target) if view else None
        if not view or target is None or target.zone not in TRUCE or view.get('warning') in ('Protected', 'Obscured; no clear shot'):
            return view
        responsible = self.controller(actor) or actor
        if target.kind == 'player' or target.behaviour.get('player_drone'):
            view['warning'] = 'Firing marks you' if self.would_mark(responsible, target) else ''
        elif self.breaks(actor, target):
            name = KEEPER_NAME.get(TRUCE[target.zone], TRUCE[target.zone].title())
            line = f'Truce: {name} answers'
            view['warning'] = line if len(line) <= 21 else f'{name} answers'
        return view

    # Provocation: breaking the peace also calls the keeper's guards.
    def provoked(self, source: Actor, target: Actor) -> None:
        breaks = self.breaks(source, target)
        responsible = self.controller(source) or source
        engaged = breaks and self.engaged(responsible, target.zone)
        self._provoked(source, target)
        if breaks:
            self.answer(source, target.zone, announce=not engaged)

    def breaks(self, source: Actor, target: Actor) -> bool:
        if target.zone not in TRUCE:
            return False
        responsible = self.controller(source)
        if responsible is None:
            return False
        if target.kind == 'player':
            return self.would_mark(responsible, target)
        return not self.hostile(target, responsible) and target.target != responsible.id

    def controller(self, source: Actor) -> Actor | None:
        if source.kind == 'player':
            return source
        if source.behaviour.get('player_drone'):
            return self.combat.game.progression.controller(source)
        return None

    def guards(self, zone_id: str) -> list[Actor]:
        keeper = TRUCE[zone_id]
        found = []
        for actor in self.combat.world.zones[zone_id].actors.values():
            if actor.kind == 'player' or actor.faction != keeper:
                continue
            template = self.npcs.content.npcs.get(actor.behaviour.get('template'))
            if template and any(b.kind == 'guard' for b in template.behaviours):
                found.append(actor)
        return found

    def engaged(self, responsible: Actor, zone_id: str) -> bool:
        now = self.combat.now()
        return any(self.npcs.provocations.get((zone_id, str(a.behaviour.get('spawner')), responsible.id), 0) > now
                   for a in self.guards(zone_id))

    def answer(self, source: Actor, zone_id: str, announce: bool = True) -> None:
        responsible = self.controller(source) or source
        keeper = TRUCE[zone_id]
        until = self.combat.now() + PROVOCATION_SECONDS
        for actor in self.guards(zone_id):
            key = (zone_id, str(actor.behaviour.get('spawner')), responsible.id)
            self.npcs.provocations[key] = until
            if responsible.zone == zone_id:
                actor.target = responsible.id
                self.combat.reveal(actor, responsible)
                actor.behaviour.update(last_seen=self.npcs.clock.now_tick(), last_position=responsible.position, state='hunt')
        if announce:
            name = KEEPER_NAME.get(keeper, keeper.title())
            line = (f'{name} is coming for you.' if responsible.zone == zone_id
                    else f'{name} is waiting for you on {self.zone_name(zone_id)}.')
            self.combat.log(responsible, line, True)

    # Q7: the Halo refuses a truce-breaker who is still Marked, whatever the door.
    def door(self, session: Any, exit: Any) -> str | None:
        if exit.target_zone != HALO:
            return None
        until = self.breakers.get(session.player_id)
        if until is None:
            return None
        if until <= self.combat.now():
            self.breakers.pop(session.player_id, None)
            return None
        return 'The bouncer looks at your red name. "Not tonight. Not after the Row."'

    def zone_name(self, zone_id: str) -> str:
        zone = self.combat.world.zones.get(zone_id)
        meta = getattr(getattr(zone, 'template', None), 'meta', None)
        return getattr(meta, 'name', None) or zone_id


def view_field() -> None:
    """The zone view carries `me.truce` (the keeper) for the client's TRUCE header.

    The simulation imported `build` by name, so its module reference is
    wrapped once per process; the wrapper checks the switch on every call.
    """
    from blacksite.server.world import simulation
    if getattr(simulation.build, 'demo_truce', False):
        return
    original = simulation.build

    def build(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        me = result.get('me') if isinstance(result, dict) else None
        if enabled() and me and me.get('zone') in TRUCE:
            me['truce'] = TRUCE[me['zone']]
        return result
    build.demo_truce = True  # type: ignore[attr-defined]
    simulation.build = build
