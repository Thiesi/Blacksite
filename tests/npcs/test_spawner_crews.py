"""Game 5.5: hostile packs retain outsider targets without infighting."""

from dataclasses import replace
from typing import Any

from blacksite.server.world.actors import Actor
from tests.npcs.test_engine import body, city, spawn


def test_game_5_5_hostile_crew_spares_siblings_and_hunts_outsiders(city: Any) -> None:
    game, caller = city
    templates = game.core.loop.content.npcs
    template = templates['npc-sable-enforcer']
    templates[template.id] = replace(template, behaviours=tuple(replace(behaviour,
        params={**behaviour.params, 'hostile_all': True}) for behaviour in template.behaviours))
    first, sibling = spawn(game, count=2)
    assert first.behaviour['spawner'] == sibling.behaviour['spawner']
    assert not game.core.npcs.hostile(first, sibling)
    assert not game.core.npcs.hostile(sibling, first)
    assert game.core.npcs.hostile(first, body(game, caller))
    outsider = replace(sibling, id='outsider', behaviour={**sibling.behaviour, 'spawner': 'another-crew'})
    assert game.core.npcs.hostile(first, outsider)
    drone = Actor('player-drone', 'Tool', kind='drone', zone=first.zone, owner=caller.session.player_id,
                  behaviour={'player_drone': True})
    assert game.core.npcs.hostile(first, drone)
