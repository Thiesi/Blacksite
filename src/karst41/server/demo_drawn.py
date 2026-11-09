"""Round 4 only: drawn weapons and the keeper's watch (#185).

Installed by the demo launcher, never on main. Uses ticks and existing
combat, visibility and movement; no save, socket or routing policy changes.
Decisions: #185 comments 6735113691, 6750114273, 6749979150.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from karst41.server import demo_truce
from karst41.server.clock import TICK_HZ
from karst41.server.interaction import key_action
from karst41.server.npcs.behaviours import step_toward
from karst41.server.world.actors import Actor
from karst41.server.world.zone import ZoneInstance

if TYPE_CHECKING:
    from karst41.server.core import Core

WARNING_TICKS = 2 * TICK_HZ  # Proposal 3.1 / owner Q1.
AGAIN_TICKS = 120 * TICK_HZ  # Proposal 3.2.
STAND_DOWN_TICKS = 5 * TICK_HZ  # Proposal 3.4.
LOST_TICKS = 20 * TICK_HZ  # Existing guard lost-sight interval.
WATCH_DISTANCE = 3  # Owner Q2, Chebyshev tiles.


@dataclass
class Draw:
    tick: int
    zone: str | None
    witnesses: frozenset[str]
    warned: bool = False


@dataclass
class Watch:
    guard: str
    player: str
    seen: int
    stand_down: int | None = None


def install(core: Core) -> None:
    if demo_truce.enabled() and core.combat and core.npcs:
        core.demo_weapons = Drawn(core)


class Drawn:
    def __init__(self, core: Core) -> None:
        self.core, self.combat, self.npcs = core, core.combat, core.npcs
        self.sim, self.world = self.combat.sim, self.combat.world
        self.draws: dict[str, Draw] = {}
        self.watchers: dict[str, Watch] = {}
        self.last_warning: dict[str, int] = {}
        self._fire, self._warn = self.combat.fire, self.combat.warn
        self.combat.fire, self.combat.warn = self.fire, self.warn
        previous_input = self.combat.input

        def input_(session: Any, frame: Any, tick: int, *, interaction: Any = None) -> bool:
            if key_action(core.keymap, session, frame) != 'draw':
                return previous_input(session, frame, tick, interaction=interaction)
            avatar = self.sim.avatars.get(session.user_id)
            if (not avatar or not self.combat.commerce.ready(session)
                    or session.id in self.sim.external_views or session.pending_prompts):
                return False
            self.toggle(avatar.actor)
            return True
        self.combat.input = input_
        previous_act, previous_tick = self.npcs.act, self.npcs.tick

        def act(actor: Actor, zone: ZoneInstance, tick: int, avoid: set[tuple[int, int]]) -> None:
            if actor.behaviour.get('state') not in ('hunt', 'flee'):
                watch = self.watchers.get(zone.id)
                if watch and watch.guard == actor.id and not actor.target:
                    player = self.world.actors.get(watch.player)
                    if watch.stand_down is not None:
                        if tick < watch.stand_down:
                            return
                    elif player and self.active(player) and self.combat.visible(actor, player):
                        watch.seen = tick
                        if self.distance(actor, player) > WATCH_DISTANCE:
                            step_toward(actor, zone, player.position, tick, avoid=avoid)
                        return
                    elif tick - watch.seen < LOST_TICKS:
                        return  # No last-known-position pursuit in this demo.
                if self.shy(actor, zone, tick, avoid):
                    return
            previous_act(actor, zone, tick, avoid)

        def tick(ctx: Any) -> None:
            self.refresh(ctx.tick)
            previous_tick(ctx)
        self.npcs.act, self.npcs.tick = act, tick
        previous_me, previous_target = self.sim.me_provider, self.sim.target_provider
        self.sim.me_provider = lambda session: {
            **previous_me(session), 'drawn': self.drawn(self.sim.avatars[session.user_id].actor)}

        def target(actor: Actor) -> dict[str, Any] | None:
            view = previous_target(actor) if previous_target else None
            other = self.world.actors.get(actor.target)
            if view and other and other.kind == 'player':
                view['drawn'] = self.drawn(other)
            return view
        self.sim.target_provider = target
        previous_travel = self.sim.travel_refusal

        def travel(session: Any, exit_: Any) -> str | None:
            reason = previous_travel(session, exit_)
            avatar = self.sim.avatars.get(session.user_id)
            if reason:
                return reason
            if exit_.target_zone == demo_truce.HALO and avatar and self.drawn(avatar.actor):
                return 'The bouncer says, "Put it away first. Then the door\'s open."'
            return None
        self.sim.travel_refusal = travel
        previous_attach = core.characters.attach

        def attach(session: Any, player: Any) -> None:
            previous_attach(session, player)
            actor = self.combat.actor(player)
            if actor:
                self.holster(actor, announce=False)
        core.characters.attach = attach
        previous_respawn = self.combat.respawn

        def respawn(player: Any, actor: Actor) -> None:
            self.holster(actor, announce=False)
            previous_respawn(player, actor)
        self.combat.respawn = respawn

    @staticmethod
    def drawn(actor: Actor) -> bool:
        return actor.kind == 'player' and bool(actor.behaviour.get('drawn'))

    def active(self, actor: Actor) -> bool:
        return self.drawn(actor) and actor.zone in self.world.zones and actor.stance == 'normal'

    @staticmethod
    def distance(a: Actor, b: Actor) -> int:
        return max(abs(a.x - b.x), abs(a.y - b.y))

    def toggle(self, actor: Actor) -> None:
        if actor.stance != 'normal' or not actor.zone:
            return
        if self.drawn(actor):
            self.holster(actor)
        else:
            self.draw(actor)

    def draw(self, actor: Actor) -> bool:
        player = self.combat.game.players.get(actor.id)
        if not player or not self.combat.weapon(player):
            self.combat.log(actor, 'Equip a weapon first.')
            return False
        tick = self.combat.clock.now_tick()
        actor.behaviour['drawn'] = True
        witnesses = frozenset(other.id for other in self.world.zones[actor.zone].actors.values()
                              if other is not actor and self.combat.visible(other, actor))
        self.draws[actor.id] = Draw(tick, actor.zone, witnesses)
        self.combat.log(actor, 'You draw your weapon. Fire again after two seconds.', True)
        for session in self.core.sessions.active.values():
            if session.player_id in witnesses:
                session.emit(actor.name + ' draws a weapon.', kind='system', channel='system', role='muted',
                             at=self.combat.clock.now_utc().isoformat())
        self.world.zones[actor.zone].revision += 1
        self.notice(actor, fallback=True)
        self.refresh(tick)
        return True

    def holster(self, actor: Actor, *, announce: bool = True) -> None:
        was = self.drawn(actor)
        actor.behaviour['drawn'] = False
        self.draws.pop(actor.id, None)
        if was and announce:
            self.combat.log(actor, 'You holster your weapon.')
        if actor.zone in self.world.zones:
            self.world.zones[actor.zone].revision += int(was)
        self.refresh(self.combat.clock.now_tick())

    def ensure_zone(self, actor: Actor) -> None:
        draw = self.draws.get(actor.id)
        if draw and draw.zone != actor.zone:
            draw.zone, draw.witnesses, draw.warned = actor.zone, frozenset(), False
            for key in list(self.combat.warnings):
                if key[0] == actor.id:
                    self.combat.warnings.pop(key)

    def fire(self, pid: str, requested: str | None = None) -> None:
        player = self.combat.game.players.get(pid)
        actor = self.combat.actor(player) if player else None
        if not actor or actor.zone is None or actor.stance != 'normal':
            return self._fire(pid, requested)
        truce = bool(self.world.zones[actor.zone].template.meta.truce)
        if not self.drawn(actor):
            if not self.draw(actor):
                return
            if truce:
                return  # First press draws, without attacking or spending ammo.
        self.ensure_zone(actor)
        draw = self.draws.get(actor.id)
        if truce and draw and self.combat.clock.now_tick() - draw.tick < WARNING_TICKS:
            self.combat.log(actor, 'Wait two seconds after drawing before firing.', True)
            return
        self._fire(pid, requested)

    def warn(self, source: Actor, target: Actor, tick: int) -> bool:
        self.ensure_zone(source)
        draw = self.draws.get(source.id)
        zone = self.world.zones.get(source.zone)
        if (draw and self.drawn(source) and zone and zone.template.meta.truce
                and target.id in draw.witnesses and target.zone == draw.zone):
            self.combat.reveal(source, target)
            self.combat.warnings[source.id, target.id] = draw.tick
            return tick >= draw.tick + WARNING_TICKS
        return self._warn(source, target, tick)

    def eligible(self, actor: Actor) -> bool:
        if not self.active(actor):
            return False
        zone = self.world.zones[actor.zone]
        if not (zone.template.meta.truce or zone.id == demo_truce.HALO):
            return False
        target = self.world.actors.get(actor.target)
        if target and (target.marked or self.npcs.hostile(target, actor)):
            return False
        return True

    def guards(self, actor: Actor) -> list[Actor]:
        zone = self.world.zones[actor.zone]
        keeper = zone.template.meta.truce or ('sable' if zone.id == demo_truce.HALO else None)
        return sorted((other for other in zone.actors.values() if other.kind != 'player'
                       and other.faction == keeper and other.stance == 'normal' and not other.target
                       and any(b.kind in ('guard', 'warden') for b in
                               self.npcs.content.npcs[other.behaviour['template']].behaviours)
                       and self.combat.visible(other, actor)), key=lambda other: (self.distance(other, actor), other.id))

    def say(self, guard: Actor, player: Actor, text: str) -> None:
        session = self.combat.session(player.id)
        if session:
            self.sim.speak(session, guard, text)

    def notice(self, actor: Actor, *, fallback: bool = False) -> None:
        draw = self.draws.get(actor.id)
        if not draw or draw.warned or not self.eligible(actor):
            return
        guards = self.guards(actor)
        if guards:
            tick = self.combat.clock.now_tick()
            again = tick - self.last_warning.get(actor.id, -AGAIN_TICKS) < AGAIN_TICKS
            self.say(guards[0], actor, 'Again?' if again else 'I see it. Put it away, or pay for it.')
            self.last_warning[actor.id], draw.warned = tick, True
        elif fallback and actor.zone in demo_truce.TRUCE:
            self.combat.log(actor, "Drawn on the Row. Sable's people will see it.")

    def refresh(self, tick: int) -> None:
        for pid in list(self.draws):
            actor = self.world.actors.get(pid)
            if actor is None or actor.stance in ('down', 'dead', 'sleeper', 'jacked'):
                if actor:
                    actor.behaviour['drawn'] = False
                self.draws.pop(pid, None)
            else:
                self.ensure_zone(actor)
                self.notice(actor)
        for zone in self.world.zones.values():
            candidates = sorted((a for a in zone.actors.values() if self.eligible(a)),
                                key=lambda a: (self.draws.get(a.id, Draw(tick, a.zone, frozenset())).tick, a.id))
            watch = self.watchers.get(zone.id)
            guard = self.world.actors.get(watch.guard) if watch else None
            player = self.world.actors.get(watch.player) if watch else None
            if watch and (not guard or guard.zone != zone.id or guard.stance != 'normal' or guard.target):
                self.watchers.pop(zone.id, None)
                watch = None
            if watch and player and player in candidates and self.combat.visible(guard, player):
                watch.seen, watch.stand_down = tick, None
                continue
            if watch:
                if (player and self.eligible(player) and player.zone == zone.id
                        and not self.combat.visible(guard, player) and tick - watch.seen < LOST_TICKS):
                    continue
                if player and self.drawn(player) and player.zone == zone.id and not self.eligible(player):
                    self.watchers.pop(zone.id, None)
                    continue
                others = [(a, self.guards(a)) for a in candidates if not player or a.id != player.id]
                next_ = next(((a, gs) for a, gs in others if gs), None)
                if player and not self.drawn(player) and watch.stand_down is None:
                    self.say(guard, player, 'Better.')
                if next_:
                    actor, guards = next_
                    chosen = guard if guard in guards else guards[0]
                    self.watchers[zone.id] = Watch(chosen.id, actor.id, tick)
                    continue
                if not player or player.zone != zone.id:
                    self.watchers.pop(zone.id, None)
                elif not self.drawn(player):
                    if watch.stand_down is None:
                        watch.stand_down = tick + STAND_DOWN_TICKS
                    elif tick >= watch.stand_down:
                        self.watchers.pop(zone.id, None)
                elif tick - watch.seen >= LOST_TICKS:
                    self.watchers.pop(zone.id, None)
                continue
            first = next(((a, gs) for a in candidates if (gs := self.guards(a))), None)
            if first:
                actor, guards = first
                self.watchers[zone.id] = Watch(guards[0].id, actor.id, tick)

    def shy(self, actor: Actor, zone: ZoneInstance, tick: int, avoid: set[tuple[int, int]]) -> bool:
        template = self.npcs.content.npcs.get(actor.behaviour.get('template'))
        if not template or template.steady or any(b.kind in ('guard', 'warden', 'talker') for b in template.behaviours):
            return False
        drawers = [a for a in zone.actors.values() if self.active(a) and self.distance(actor, a) <= 3
                   and self.combat.visible(actor, a)]
        if not drawers:
            actor.behaviour.pop('shied_from', None)
            return False
        player = min(drawers, key=lambda a: (self.distance(actor, a), a.id))
        posts = getattr(self.npcs, 'posts', None)
        if posts and posts.shy(actor, zone, tick, player, avoid):
            return True
        # Non-post idle speakers hold. Ordinary wanderers do not acquire
        # an unbudgeted extra movement path; round4 crowds use posts.
        return True
