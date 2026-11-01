"""Demo only (demo/sodium-row-evening, never merged): ambient speech as log lines.

Owner decision Q6 (#143, 2026-10-31) puts the cast live on main later
through its own slice. For the demo, this wakes S27's pure bark scheduler
in Sodium Row and the Tin Halo: a talker NPC with a player within earshot
speaks one of its authored barks, at most once per bark interval for each
talker, through the simulation's ordinary speech path. Players within
earshot hear it as a zone log line, in both presentations.

Installed only when BLACKSITE_DEMO=sodium-row-evening.
"""
from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

from blacksite.server import demo_truce
from blacksite.server.dialogue import BarkScheduler

if TYPE_CHECKING:
    from blacksite.server.core import Core

ZONES = ('sodium-row', 'sodium-tin-halo')
EARSHOT = 20  # game design 11: say reaches 20 tiles


def install(core: Core) -> None:
    if not demo_truce.enabled() or core.dialogue is None:
        return
    Speech(core)


class Speech:
    def __init__(self, core: Core) -> None:
        self.core, self.dialogue = core, core.dialogue
        self.scheduler, self.rng = BarkScheduler(), Random(41)
        original = self.dialogue.tick

        def tick(ctx, original=original):
            original(ctx)
            self.speak(ctx.tick)
        self.dialogue.tick = tick

    def speak(self, tick: int) -> None:
        sim, content = self.dialogue.sim, self.dialogue.content
        listeners = [(s, sim.avatars[s.user_id].actor) for s in self.core.sessions.active.values()
                     if not s.closed and s.user_id in sim.avatars]
        busy = {screen.contact.target for screen in self.dialogue.menus.values()}
        for zone_id in ZONES:
            zone = self.dialogue.world.zones.get(zone_id)
            if zone is None:
                continue
            here = [(s, a) for s, a in listeners if a.zone == zone_id]
            if not here:
                continue
            for actor in list(zone.actors.values()):
                if actor.kind == 'player' or actor.stance in ('down', 'dead'):
                    continue
                template = content.npcs.get(actor.behaviour.get('template'))
                talker = content.dialogue.get(template.dialogue) if template and template.dialogue else None
                if talker is None:
                    continue
                hearers = [(s, a) for s, a in here if self.near(a.position, actor.position)]
                bark = self.scheduler.choose(talker, tick, self.rng, nearby=bool(hearers),
                                             interacting=actor.id in busy)
                if bark is None:
                    continue
                for session, _ in hearers:
                    sim.speak(session, actor, bark.text)

    @staticmethod
    def near(a: tuple[int, int], b: tuple[int, int]) -> bool:
        return max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= EARSHOT
