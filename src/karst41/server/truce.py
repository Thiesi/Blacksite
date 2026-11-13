"""S44: the Row's truce rules after a breach (game design 5.5 and 7.3).

One stored record per player, `Player.keeper_answer` ({keeper, zone,
until}), is the keeper's answer. It is written by `Npcs.keep_truce`,
persisted beside `marked_until`, and cleared by any death. `hunted` reads
only that record, never `Npcs.provocations`, which also holds ordinary
faction reactions to any NPC attack.

The Tin Halo refuses a hunted player, and a player whose Mark came from
breaking a truce (`truce_marked_until`), at every entrance, and shows
such a player out through its street door. Vesper's work closes to any
Mark (`marked_until`). The two differ on purpose (#170).
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from typing import TYPE_CHECKING, Any

from karst41.server.world.exits import schedule

if TYPE_CHECKING:
    from karst41.server.players import Player
    from karst41.server.sessions import Session
    from karst41.server.world.zone import Exit

HALO = 'sodium-tin-halo'  # Gazetteer: the bouncer turns away Sable's answers.
VESPER = 'vesper'  # Her board, counter and talk offers.
SHOW_OUT_TICKS = 10  # Once a second; the Halo's door is never a place to wait.


def stamp(value: str | None) -> float:
    """A stored UTC expiry as a timestamp; 0 when absent or unreadable."""
    try:
        return datetime.fromisoformat(value).timestamp() if value else 0.0
    except (TypeError, ValueError):
        return 0.0


def iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def answer_until(player: Player | None) -> float:
    """The keeper's stored answer's expiry, the only source of `hunted`."""
    record = player.keeper_answer if player else None
    return stamp(record.get('until')) if isinstance(record, dict) else 0.0


def hunted(player: Player | None, now: float) -> bool:
    return answer_until(player) > now


def minutes(seconds: float) -> int:
    """Rounded up, so a refusal never says 0 (terminal UI 2.1)."""
    return max(1, ceil(seconds / 60))


def keeper_name(content: Any, keeper: str) -> str:
    faction = content.factions.get(keeper)
    return faction.short if faction else keeper.title()


def halo_refusal(content: Any, player: Player | None, now: float) -> str | None:
    """The bouncer's line, or None. The longer wait wins; the Mark's on a tie."""
    if player is None:
        return None
    marked, answered = stamp(player.truce_marked_until), answer_until(player)
    if max(marked, answered) <= now:
        return None
    if marked >= answered:
        return f'The bouncer looks at your red name. "Not tonight. Not after the Row. {minutes(marked-now)} min."'
    name = keeper_name(content, str(player.keeper_answer.get('keeper', '')))  # type: ignore[union-attr]
    return f'The bouncer doesn\'t move. "{name}\'s still asking about you. Try me in {minutes(answered-now)} min."'


def vesper_refusal(player: Player | None, now: float) -> str | None:
    """Vesper doesn't work for a red name, whatever earned it."""
    left = stamp(player.marked_until if player else None) - now
    return f'Vesper: "Not with that name. Come back in {minutes(left)} min."' if left > 0 else None


class Truce:
    """Wires the refusals and `me.hunted` into the existing seams."""

    def __init__(self, core: Any) -> None:
        self.core, self.combat, self.sim = core, core.combat, core.characters.sim
        self.game, self.content = core.characters, core.characters.content
        core.truce = self
        previous = self.sim.travel_refusal
        self.sim.travel_refusal = lambda session, exit: previous(session, exit) or self.door(session, exit)
        provider = self.sim.me_provider
        self.sim.me_provider = lambda session: self.me(session, provider(session))
        core.commerce.service_refusal = self.service

    def now(self) -> float:
        return self.combat.now()

    def player(self, session: Session) -> Player | None:
        return self.game.players.get(session.player_id)

    def me(self, session: Session, me: dict[str, Any]) -> dict[str, Any]:
        if hunted(self.player(session), self.now()):
            me['hunted'] = True  # Architecture: additive, absent when false.
        return me

    def door(self, session: Session, exit: Exit) -> str | None:
        if exit.target_zone != HALO:
            return None
        return halo_refusal(self.content, self.player(session), self.now())

    def service(self, session: Session, handler: str) -> str | None:
        return vesper_refusal(self.player(session), self.now()) if handler == VESPER else None

    def talk(self, session: Session, handler: str) -> str | None:
        """S48b: E on a counter's person. The counter's refusal, and inside
        the Halo the bouncer's (a hunted caller is shown out anyway)."""
        if reason := self.service(session, handler):
            return reason
        avatar = self.sim.avatars.get(session.user_id)
        if avatar is not None and avatar.zone == HALO:
            return halo_refusal(self.content, self.player(session), self.now())
        return None

    def tick(self, ctx: Any) -> None:
        """Show out of the Halo anyone it refuses, through its street door."""
        tick = ctx.tick
        if tick % SHOW_OUT_TICKS:
            return
        zone = self.core.world.zones.get(HALO)
        if zone is None:
            return
        street = next((ex for ex in zone.template.meta.exits if ex.id == 'to-sodium-row'), None)
        if street is None:
            return
        for session in tuple(self.game.sessions.active.values()):
            avatar = self.sim.avatars.get(session.user_id)
            if (session.closed or session.role != 'caller' or avatar is None or avatar.zone != HALO
                    or avatar.travel or avatar.actor.id != session.player_id
                    or avatar.actor.stance in ('down', 'dead', 'sleeper', 'jacked')):
                continue
            line = halo_refusal(self.content, self.player(session), self.now())
            if line is None:
                continue
            self.close(session)
            self.sim.log(session, line)
            avatar.travel = schedule(street, self.clock_now())
            self.sim.reset_view(session, avatar)
            self.sim.transition(session, avatar, self.clock_now(), tick)

    def clock_now(self) -> float:
        return self.game.clock.now_utc().timestamp()

    def close(self, session: Session) -> None:
        """Pages over the Halo close with it: talk, board, counter."""
        core = self.core
        if getattr(core, 'dialogue', None) and session.id in core.dialogue.menus:
            core.dialogue.close(session)
        panels = getattr(getattr(core, 'contracts', None), 'panels', None)
        if panels and session.id in panels.menus:
            panels.close(session)
        if session.id in core.commerce.menus:
            core.commerce.close(session)
