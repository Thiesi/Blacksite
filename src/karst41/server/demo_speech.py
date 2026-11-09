"""Demo only (demo/sodium-row-evening, never merged): ambient speech as log lines.

Owner decision Q6 (#143, 2026-10-31) puts the cast live on main later
through its own slice. For the demo, this wakes S27's pure bark scheduler
in Sodium Row and the Tin Halo: a talker NPC with a player within earshot
speaks one of its authored barks, at most once per bark interval for each
talker, through the simulation's ordinary speech path. Players within
earshot hear it as a zone log line, in both presentations.

Installed only when KARST41_DEMO=sodium-row-evening.
"""
from __future__ import annotations

import os
from random import Random
from typing import TYPE_CHECKING

from karst41.server import demo_truce
from karst41.server.clock import TICK_HZ
from karst41.server.dialogue import BarkScheduler

if TYPE_CHECKING:
    from karst41.server.core import Core

ZONES = ('sodium-row', 'sodium-tin-halo')
EARSHOT = 20  # game design 11: say reaches 20 tiles
GAP = int(os.environ.get('KARST41_DEMO_BARK_GAP', '12'))  # seconds between ambient lines per caller


def install(core: Core) -> None:
    if not demo_truce.enabled() or core.dialogue is None:
        return
    Speech(core)


class Speech:
    def __init__(self, core: Core) -> None:
        self.core, self.dialogue = core, core.dialogue
        self.scheduler, self.rng = BarkScheduler(), Random(41)
        self.ready: dict[str, int] = {}  # session id -> first tick it may hear another bark
        original = self.dialogue.tick

        def tick(ctx, original=original):
            original(ctx)
            self.speak(ctx.tick)
        self.dialogue.tick = tick

    def speak(self, tick: int) -> None:
        """At most one ambient line per caller per GAP seconds, nearest talker first.

        A caller who is fighting, targeting or chased hears no barks, so
        ambient lines never push protected danger or combat lines out of
        the log (terminal UI 2.5).
        """
        sim, content = self.dialogue.sim, self.dialogue.content
        busy = {screen.contact.target for screen in self.dialogue.menus.values()}
        open_ears = [(s, sim.avatars[s.user_id].actor) for s in self.core.sessions.active.values()
                     if not s.closed and s.user_id in sim.avatars
                     and self.ready.get(s.id, 0) <= tick and not self.occupied(sim.avatars[s.user_id].actor, tick)]
        for zone_id in ZONES:
            zone = self.dialogue.world.zones.get(zone_id)
            ears = [(s, a) for s, a in open_ears if a.zone == zone_id]
            if zone is None or not ears:
                continue
            talkers = []
            for actor in zone.actors.values():
                if actor.kind == 'player' or actor.stance in ('down', 'dead') or actor.id in busy:
                    continue
                template = content.npcs.get(actor.behaviour.get('template'))
                talker = content.dialogue.get(template.dialogue) if template and template.dialogue else None
                hearers = [(s, a) for s, a in ears if self.near(a.position, actor.position)]
                if talker is not None and hearers:
                    nearest = min(self.distance(a.position, actor.position) for _, a in hearers)
                    talkers.append((nearest, actor.id, actor, talker, hearers))
            for _, _, actor, talker, hearers in sorted(talkers, key=lambda t: (t[0], t[1])):
                bark = self.scheduler.choose(talker, tick, self.rng, nearby=True, interacting=False)
                if bark is None:
                    continue
                for session, _ in hearers:
                    sim.speak(session, actor, bark.text)
                    self.ready[session.id] = tick + GAP * TICK_HZ
                break  # one ambient line per zone per tick

    def occupied(self, actor, tick: int) -> bool:
        if actor.target or actor.cooldowns.get('combat', 0) > tick or actor.cooldowns.get('attacked', 0) > tick:
            return True
        truce = getattr(self.core.combat.hostile_hook, '__self__', None)
        return bool(truce and hasattr(truce, 'engaged') and actor.zone in demo_truce.TRUCE
                    and truce.engaged(actor, actor.zone))

    @staticmethod
    def distance(a: tuple[int, int], b: tuple[int, int]) -> int:
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    @staticmethod
    def near(a: tuple[int, int], b: tuple[int, int]) -> bool:
        return max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= EARSHOT
