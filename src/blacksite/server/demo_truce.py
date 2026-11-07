"""Demo only (demo/sodium-row-evening, never merged): a stand-in for S38.

Sodium Row keeps the peace. In a truce zone NPCs are never hostile from
the relations matrix; whoever breaks the peace there (an attack on a
player that Marks, or on an NPC not already after them) is Marked when
the target is a player and is answered by the keeper's guards.

Round 3, the owner's rulings of 2026-11-07 (#170): the Tin Halo refuses a
truce-breaker who is still Marked or whom the keeper is still answering, by any
entrance, and says for how long. Vesper's board and counter close to a Marked
player. The view declares `me.hunted`, and a first arrival gets a one-time
notice with the price.

Installed only when BLACKSITE_DEMO=sodium-row-evening. It wraps existing seams
instead of editing them, so the real slices own the rules.
"""
from __future__ import annotations

import os
from datetime import datetime
from math import ceil
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from blacksite.server.interaction import Focus, Interaction
from blacksite.server.npcs.templates import PROVOCATION_SECONDS

if TYPE_CHECKING:
    from blacksite.server.core import Core
    from blacksite.server.world.actors import Actor

DEMO = 'sodium-row-evening'
TRUCE = {'sodium-row': 'sable'}  # zone -> keeper faction (S38's `truce` field)
KEEPER_NAME = {'sable': 'Sable'}
HALO = 'sodium-tin-halo'
BACK_DOOR = 'row-halo-back-door'  # the alley's east end: locked from this side
BACK_DOOR_TILE = (90, 24)


def enabled() -> bool:
    return os.environ.get('BLACKSITE_DEMO') == DEMO


def install(core: Core) -> None:
    if not enabled() or not (core.combat and core.npcs):
        return
    Truce(core)


def minutes(seconds: float) -> int:
    """Rounded up, so a refusal never says "0 min"."""
    return max(1, ceil(seconds / 60))


class Truce:
    def __init__(self, core: Core) -> None:
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
        if sim is not None:
            previous = sim.travel_refusal
            sim.travel_refusal = lambda session, exit: previous(session, exit) or self.door(session, exit)
            provider = sim.me_provider
            sim.me_provider = lambda session: {**provider(session), 'hunted': self.hunted(session.player_id)}
            self.discovering(sim)
            self.back_door(sim)
        self.settling()
        panels = getattr(getattr(core, 'contracts', None), 'panels', None)
        if panels is not None:
            station = panels.station

            def closed(session: Any, target: str) -> str:
                handler = station(session, target)
                if handler == 'vesper':
                    self.vesper_refuses(session.player_id)
                return handler
            panels.station = closed

    def settling(self) -> None:
        """The owner's ruling (#170): any death settles the debt with the keeper.

        It clears the provocation, so the Halo's refusal and `hunted` go with it.
        A Mark isn't settled: its 15 minutes, no Halo and no work are untouched.
        The line comes after the vat's, so a respawn reads in order.
        """
        respawn, log = self.combat.respawn, self.combat.log
        settled: dict[str, str] = {}

        def respawning(player: Any, actor: Any) -> None:
            for zone_id, keeper in TRUCE.items():
                if self.answered_until(player.id, zone_id) > self.combat.now():
                    settled[player.id] = KEEPER_NAME.get(keeper, keeper.title())
                    for group in self.groups(zone_id):
                        self.npcs.provocations.pop((zone_id, group, player.id), None)
            respawn(player, actor)

        def logging(actor: Any, text: str, *args: Any, **fields: Any) -> None:
            log(actor, text, *args, **fields)
            if text.startswith('You wake in the vat') and actor.id in settled:
                log(actor, f'{settled.pop(actor.id)} considers it settled.')
        self.combat.respawn, self.combat.log = respawning, logging

    def back_door(self, sim: Any) -> None:
        """The alley's locked east door says what it is. Its tile can't hold an object."""
        target, interact = sim.interaction_target, sim.interact
        door = SimpleNamespace(spec=SimpleNamespace(id=BACK_DOOR))

        def targeting(avatar: Any, *, street: bool = False) -> Interaction:
            choice = target(avatar, street=street)
            actor = avatar.actor
            if (not street and choice.value is None and avatar.zone == 'sodium-row'
                    and max(abs(BACK_DOOR_TILE[0]-actor.x), abs(BACK_DOOR_TILE[1]-actor.y)) <= 1):
                return Interaction(Focus(BACK_DOOR, "The Halo's back door", 'try'), door, BACK_DOOR_TILE)
            return choice

        def interacting(session: Any, avatar: Any, tick: int, *, street: bool = False, choice: Any = None) -> None:
            choice = choice or sim.interaction_target(avatar, street=street)
            if choice.value is door:
                sim.log(session, 'No handle this side.')
                return
            interact(session, avatar, tick, street=street, choice=choice)
        sim.interaction_target, sim.interact = targeting, interacting

    def discovering(self, sim: Any) -> None:
        discover = sim.discover

        def noticing(session: Any, avatar: Any) -> None:
            first = avatar.zone in TRUCE and avatar.zone not in avatar.seen_zones
            discover(session, avatar)
            if first:
                keeper = KEEPER_NAME.get(TRUCE[avatar.zone], TRUCE[avatar.zone].title())
                session.emit(f'Fire: {keeper} comes, no Halo. At a player: Marked 15m, no work.', kind='notice',
                             channel='system', role='log_danger', at=sim.clock.now_utc().isoformat())
        sim.discover = noticing

    # The one definition of being answered: a live provocation by the keeper's guards.
    def groups(self, zone_id: str) -> set[str]:
        """The keeper's guard spawners, so killing a guard doesn't end the answer."""
        keeper, zone = TRUCE[zone_id], self.combat.world.zones[zone_id]
        found = {str(a.behaviour.get('spawner')) for a in self.guards(zone_id)}
        for spawner in zone.template.meta.spawners:
            template = self.npcs.content.npcs.get(spawner.npc)
            if template and template.faction == keeper and any(b.kind == 'guard' for b in template.behaviours):
                found.add(spawner.id)
        return found

    def answered_until(self, player_id: str, zone_id: str) -> float:
        return max((self.npcs.provocations.get((zone_id, group, player_id), 0) for group in self.groups(zone_id)), default=0)

    def hunted(self, player_id: str) -> bool:
        now = self.combat.now()
        return any(self.answered_until(player_id, zone_id) > now for zone_id in TRUCE)

    def marked_for(self, player_id: str) -> float:
        """Seconds of Mark left, whatever earned it."""
        player = self.combat.game.players.get(player_id)
        if not player or not player.marked_until:
            return 0
        return datetime.fromisoformat(player.marked_until).timestamp() - self.combat.now()

    def vesper_refuses(self, player_id: str) -> None:
        left = self.marked_for(player_id)
        if left > 0:
            raise ValueError(f'Vesper: "Not with that name. Come back in {minutes(left)} min."')

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
        return self.answered_until(responsible.id, zone_id) > self.combat.now()

    def answer(self, source: Actor, zone_id: str, announce: bool = True) -> None:
        responsible = self.controller(source) or source
        keeper = TRUCE[zone_id]
        until = self.combat.now() + PROVOCATION_SECONDS
        for group in self.groups(zone_id):
            self.npcs.provocations[(zone_id, group, responsible.id)] = until
        for actor in self.guards(zone_id):
            if responsible.zone == zone_id:
                actor.target = responsible.id
                self.combat.reveal(actor, responsible)
                actor.behaviour.update(last_seen=self.npcs.clock.now_tick(), last_position=responsible.position, state='hunt')
        if announce:
            name = KEEPER_NAME.get(keeper, keeper.title())
            line = (f'{name} is coming for you.' if responsible.zone == zone_id
                    else f'{name} is waiting for you on {self.zone_name(zone_id)}.')
            self.combat.log(responsible, line, True)

    # Q7 and its extension: Marked for breaking the truce, or still being answered.
    def door(self, session: Any, exit: Any) -> str | None:
        if exit.target_zone != HALO:
            return None
        now = self.combat.now()
        marked = self.breakers.get(session.player_id, 0)
        if marked and marked <= now:
            self.breakers.pop(session.player_id, None)
            marked = 0
        answered = max((self.answered_until(session.player_id, zone_id) for zone_id in TRUCE), default=0)
        if max(marked, answered) <= now:
            return None
        if marked >= answered:  # the longer time wins
            return f'The bouncer looks at your red name. "Not tonight. Not after the Row. {minutes(marked-now)} min."'
        return f'The bouncer doesn\'t move. "Sable\'s still asking about you. Try me in {minutes(answered-now)} min."'

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
