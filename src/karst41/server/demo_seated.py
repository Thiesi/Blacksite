"""Demo only (demo/sodium-row-evening, never merged): the seated variant.

Round 2's question is whether a Row with only four people moving still feels
inhabited. With KARST41_DEMO_SEATED=1 the bar and Halo drinkers sit in fixed
seats. The street regulars, the Warden, the card court and the fixed cast are
left as they are, so one world can be played both ways. Applied at start-up to
the world's copy of the content; nothing is saved.

`idle` keeps them class `civilian`; `talker` would make them `service`.
"""
from __future__ import annotations

import os
from dataclasses import replace
from typing import TYPE_CHECKING

from karst41.content.schema import Behaviour, Region
from karst41.server import demo_truce

if TYPE_CHECKING:
    from karst41.server.core import Core

# zone -> spawner id -> seats. Doorways and counter fronts stay clear.
SEATS = {
    'sodium-row': {
        'upstairs-halvard': [(12, 6)],
        'upstairs-sablier': [(9, 6)],
        'long-shift-crew': [(27, 4), (30, 3)],
        'quarter-tone-listeners': [(40, 6), (48, 4)],
        'clause-regulars': [(55, 5), (59, 6)],
        'spare-parts-runners': [(73, 5), (80, 4)],
    },
    'sodium-tin-halo': {
        'halo-regular-crew': [(18, 8)],
        'halo-regular-stray': [(28, 8)],
        'halo-regular-runner': [(29, 13)],
    },
}


def enabled() -> bool:
    return demo_truce.enabled() and os.environ.get('KARST41_DEMO_SEATED') == '1'


def install(core: Core) -> None:
    if not enabled() or core.world is None:
        return
    content = core.world.content
    for zone_id, seats in SEATS.items():
        zone = core.world.zones.get(zone_id)
        if zone is None:
            continue
        spawners = []
        for spawner in zone.template.meta.spawners:
            if spawner.id not in seats:
                spawners.append(spawner)
                continue
            content.npcs[spawner.npc] = replace(content.npcs[spawner.npc], behaviours=(Behaviour('idle'),))
            spawners += [replace(spawner, id=f'{spawner.id}-seat{index}', count=1, region=Region(x, y, 1, 1))
                         for index, (x, y) in enumerate(seats[spawner.id])]
        zone.template = replace(zone.template, meta=replace(zone.template.meta, spawners=tuple(spawners)))
