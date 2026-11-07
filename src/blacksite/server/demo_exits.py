"""Demo only (demo/sodium-row-evening, never merged): a stand-in for S39.

What you stand on beats what stands beside you: on an exit tile, E and the focus
prompt go to the exit, not to an adjacent talker. S39's real build owns the rule
and its dispatch; this only makes the talker routes stand aside. Vendors aren't
covered, because no Row or Halo counter sits beside an exit.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from blacksite.server import demo_truce

if TYPE_CHECKING:
    from blacksite.server.core import Core


def install(core: Core) -> None:
    if not demo_truce.enabled() or not core.characters:
        return
    sim = core.characters.sim

    def underfoot(session: Any) -> bool:
        avatar = sim.avatars.get(session.user_id)
        zone = sim.world.zones.get(avatar.zone) if avatar else None
        return bool(zone and any(ex.tile == avatar.actor.position for ex in zone.template.meta.exits))

    for owner in (core.dialogue, core.npcs):
        if owner is None:
            continue

        def aside(session: Any, frame: Any, query: Any = owner.interaction, owner: Any = owner) -> Any:
            if session.id not in owner.menus and underfoot(session):
                return None
            return query(session, frame)
        owner.interaction = aside
