"""Demo only (demo/sodium-row-evening, never merged): a record of door attempts.

Round 1 spent a long time working out what turned a player away at the Halo,
because nothing kept the words. This writes every attempt to use an exit on the
Row or in the Halo to logs/server.log: who, where, what they were told, and
whether they were Marked or being answered. It changes no outcome.

A talker taking E beside an exit is recorded too, because that's what round 1's
refusal most likely was. The alley's locked east door isn't an exit, but it's
recorded as well. Walking into it without pressing E still leaves no record.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from blacksite.content.schema import Exit
from blacksite.server import demo_truce

if TYPE_CHECKING:
    from blacksite.server.core import Core

ZONES = ('sodium-row', 'sodium-tin-halo')


def install(core: Core, record: Callable[..., None]) -> None:
    if not demo_truce.enabled() or not core.characters:
        return
    sim = core.characters.sim
    interact, log = sim.interact, sim.log

    def recorded(session: Any, avatar: Any, tick: int, *, street: bool = False, choice: Any = None) -> None:
        choice = choice or sim.interaction_target(avatar, street=street)
        back_door = getattr(getattr(choice.value, 'spec', None), 'id', '') == demo_truce.BACK_DOOR
        if not (isinstance(choice.value, Exit) or back_door) or avatar.zone not in ZONES:
            interact(session, avatar, tick, street=street, choice=choice)
            return
        said: list[str] = []

        def noting(target: Any, text: str, **fields: Any) -> None:
            said.append(text)
            log(target, text, **fields)

        zone, tile = avatar.zone, avatar.actor.position
        sim.log = noting
        try:
            interact(session, avatar, tick, street=street, choice=choice)
        finally:
            del sim.log  # back to the method, which `log` is bound to
        truce = getattr(core.combat.hostile_hook, '__self__', None) if core.combat else None
        answered = bool(zone in demo_truce.TRUCE and truce and hasattr(truce, 'engaged')
                        and truce.engaged(avatar.actor, zone))
        record('demo door', player=avatar.actor.name, zone=zone, tile=list(tile),
               exit=demo_truce.BACK_DOOR if back_door else choice.value.id,
               outcome='went through' if avatar.travel or avatar.zone != zone else ' '.join(said) or 'nothing said',
               marked=bool(avatar.actor.marked), answered=answered)

    sim.interact = recorded
    if core.dialogue is None:
        return
    show = core.dialogue.show

    def showing(session: Any, contact: Any, text: str, tick: int) -> bool:
        shown = show(session, contact, text, tick)
        avatar = sim.avatars.get(session.user_id)
        zone = sim.world.zones.get(avatar.zone) if avatar else None
        if shown and zone and avatar.zone in ZONES:
            actor = avatar.actor
            beside = [ex.id for ex in zone.template.meta.exits
                      if max(abs(ex.tile[0]-actor.x), abs(ex.tile[1]-actor.y)) <= 1]
            if beside:
                record('demo door', player=actor.name, zone=avatar.zone, tile=list(actor.position), exit=beside[0],
                       outcome=f'a talker took E: {text}', marked=bool(actor.marked), answered=False)
        return shown
    core.dialogue.show = showing
