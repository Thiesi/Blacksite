"""P8: the one ambient emitter (architecture 5.5.3, game design 13.4).

Two sources share it: talker barks and a zone's authored `looks.ambient`
lines. Each zone instance has its own random stream, derived from the
zone id and a fixed salt, so the simulation's `zone.rng` draws never move
because a place speaks. Everything runs on ticks.

Who pays for a drop: a source's schedule (a talker's interval, a zone's
ambience cadence) and its weighted pick are consumed when it fires,
whether or not any recipient receives the line. The per-caller budget and
suppression are then applied per recipient by `admit`, so a busy spot
thins out instead of bursting when the budget reopens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from random import Random
from typing import Any, Callable, Iterable

from karst41.server.clock import TICK_HZ
from karst41.server.dialogue import BARK_RADIUS, BarkScheduler
from karst41.server.sessions import Session
from karst41.server.world.actors import Actor

STREAM_SALT = b"karst41/P8/ambience/1"
LINE_BUDGET_SECONDS = 20  # N: at most one bark or ambient line per caller per 20 s.
AMBIENT_SECONDS = 60      # A zone's ambience fires at most once a minute...
AMBIENT_JITTER_SECONDS = 30  # ...plus up to 30 s, from the zone's own stream.
DANGER_HOLD_SECONDS = 10  # Terminal UI 2.5: never push danger or combat out of view.
STRIDE = TICK_HZ  # The emitter runs once a second; every number above is whole seconds.


def stream(zone_id: str) -> Random:
    """The zone instance's own stream; never `zone.rng`."""
    return Random(int.from_bytes(sha256(STREAM_SALT + zone_id.encode("utf-8")).digest()[:8], "big"))


@dataclass
class ZoneVoice:
    rng: Random
    ambient_due: int
    barks: BarkScheduler = field(default_factory=BarkScheduler)
    mute: set[str] = field(default_factory=set)
    """NPC instances with no active barking talker; a template never changes."""


class Ambience:
    def __init__(self, world: Any, content: Any, sim: Any, clock: Any, *,
                 threatened: Callable[[Session, Actor], bool],
                 talking: Callable[[str], bool]) -> None:
        self.world, self.content, self.sim, self.clock = world, content, sim, clock
        self.threatened, self.talking = threatened, talking
        self.zones: dict[str, ZoneVoice] = {}

    # --- the shared per-caller gate (S48's runner may call it) -------------

    def admit(self, session: Session, tick: int) -> bool:
        """Budget and suppression for one recipient, at emit time.

        True spends the caller's budget. Suppressed: travelling, threatened
        (the declared danger inputs), or within ten seconds of a danger or
        combat line sent to this caller, so no renderer has an ambient
        line pushing one out of view. The hold and the budget live on the
        session (carried across a reconnect), so a menu or a reconnect
        never resets them.
        """
        avatar = self.sim.avatars.get(session.user_id)
        if avatar is None or avatar.travel is not None:
            return False
        if session.danger_at is not None and (
                self.clock.now_utc() - datetime.fromisoformat(session.danger_at)).total_seconds() < DANGER_HOLD_SECONDS:
            return False
        if session.voice_tick is not None and tick - session.voice_tick < LINE_BUDGET_SECONDS * TICK_HZ:
            return False
        if self.threatened(session, avatar.actor):
            return False
        session.voice_tick = tick
        return True

    # --- the tick ------------------------------------------------------------

    def tick(self, tick: int, sessions: Iterable[Session], playing: Callable[[Session], bool]) -> None:
        if tick % STRIDE:
            return  # Cost: once a second, not every tick (PR notes give the figures).
        present: dict[str, list[tuple[Session, Actor]]] = {}
        for session in sessions:
            if session.closed or session.role != "caller" or not playing(session):
                continue
            avatar = self.sim.avatars.get(session.user_id)
            if avatar is None or not avatar.actor.zone:
                continue
            present.setdefault(avatar.actor.zone, []).append((session, avatar.actor))
        for zone_id, callers in present.items():
            zone = self.world.zones.get(zone_id)
            if zone is None:
                continue
            voice = self.zones.get(zone_id)
            if voice is None:
                rng = stream(zone_id)
                voice = self.zones[zone_id] = ZoneVoice(rng, tick + self._ambient_gap(rng))
            self._barks(zone, voice, callers, tick)
            self._ambient(zone, voice, callers, tick)

    def _ambient_gap(self, rng: Random) -> int:
        return (AMBIENT_SECONDS + rng.randint(0, AMBIENT_JITTER_SECONDS)) * TICK_HZ

    def _ambient(self, zone: Any, voice: ZoneVoice, callers: list[tuple[Session, Actor]], tick: int) -> None:
        look = self.content.looks.get(zone.id)
        if look is None or not look.ambient or tick < voice.ambient_due:
            return
        text = voice.rng.choice(look.ambient)
        voice.ambient_due = tick + self._ambient_gap(voice.rng)
        at = self.clock.now_utc().isoformat()
        for session, _ in callers:
            if self.admit(session, tick):
                session.emit(text, kind="ambient", channel="zone", role="log_ambient", at=at, replay=False)

    def _barks(self, zone: Any, voice: ZoneVoice, callers: list[tuple[Session, Actor]], tick: int) -> None:
        if len(voice.mute) + len(voice.barks.next_due) > 4 * len(zone.actors) + 64:
            # Bounded memory: forget instances that left the zone.
            voice.mute &= zone.actors.keys()
            voice.barks.next_due = {k: v for k, v in voice.barks.next_due.items() if k in zone.actors}
        for actor in tuple(zone.actors.values()):
            if actor.id in voice.mute or tick < voice.barks.next_due.get(actor.id, 0):
                continue
            if actor.kind != "npc":
                voice.mute.add(actor.id)
                continue
            if actor.health <= 0 or actor.stance in ("down", "dead"):
                continue
            template = self.content.npcs.get(actor.behaviour.get("template"))
            talker = self.content.dialogue.get(template.dialogue) if template and template.dialogue else None
            if (talker is None or not talker.barks or talker.machine_mind
                    or not self.content.active("dialogue", talker.id)):
                voice.mute.add(actor.id)
                continue
            audience = [(session, viewer) for session, viewer in callers
                        if max(abs(viewer.x - actor.x), abs(viewer.y - actor.y)) <= BARK_RADIUS]
            bark = voice.barks.choose(talker, tick, voice.rng, nearby=bool(audience),
                                      interacting=self.talking(actor.id), key=actor.id)
            if bark is None:
                continue
            for session, _ in audience:
                if self.admit(session, tick):
                    self.sim.speak(session, actor, bark.text, replay=False)
