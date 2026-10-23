"""PR 38 / Game 17.2: all five missing programs have usable shipped routes."""

from typing import Any

import pytest

from blacksite.server.clock import TICK_HZ
from tests.character_helpers import place
from tests.lattice.test_engine import runners
from tests.lattice.test_silt_encounters import descend
from tests.npcs.test_engine import city


def test_game_17_2_freelance_caller_can_buy_four_catalog_programs_at_tin_halo(city: tuple[Any, ...]) -> None:
    game, caller = city
    owner, commerce = game.core.contracts, game.core.commerce
    player = owner.game.players[caller.session.player_id]
    owner.lat.season = 1
    place(game, caller, 'sodium-tin-halo', (8,14))
    assert player.faction is None
    # Fixture funds verify real acquisition and debits, not earned income.
    # S19's separate earning report measures natural affordability.
    player.chits_hand = 10000
    programs = ('prg_lance','prg_bunker','prg_signet','prg_anchor')
    for pid in programs:
        commerce.propose(caller.session, 'vendor.buy', {'target':'vesper','item':pid})
        assert commerce.pending and pid not in player.progress['known_programs']
        game.commit_commerce()
        assert pid in player.progress['known_programs']
        game.step(TICK_HZ+1)
    assert 0 < player.chits_hand < 10000
    assert set(player.progress['program_acquisitions']['1']) == set(programs)


def test_game_17_2_shipped_reach_blackout_source_has_identity_custody_and_no_duplicate_acquisition(runners: tuple[Any, ...]) -> None:
    game, caller, _, _ = runners
    owner = game.core.contracts
    owner.lat.season = 1
    presence = descend(game, caller)
    encounters = owner.lat.encounters
    # Isolate acquisition at the actual authored site. S14's scenarios
    # separately exercise traversal and the Reach's unmodified ICE.
    encounters.enter_band(presence, 2)
    instance = encounters.core(presence)
    room = next(r for r in instance.graph.rooms.values()
                if any(d.kind == 'program' and d.asset == 'prg_blackout' for d in r.data))
    data = next(d for d in room.data if d.asset == 'prg_blackout')
    assert data.scope == 'identity' and data.chance == 1
    presence.room = room.id
    for ice in instance.ice.values():
        ice.integrity = 0
    key = encounters.source(presence, data)
    source = owner.lat.sources.refresh(key, data, game.clock.now_tick())
    encounters.start_lift(presence, data.id, source.generation)
    game.step(presence.procedure.until-game.clock.now_tick())
    game.commit_commerce()
    player = owner.game.players[presence.player_id]
    assert 'prg_blackout' in player.progress['known_programs']
    assert player.progress['program_acquisitions']['1'] == ['prg_blackout']
    assert key in owner.game.identity(player.bbs_user_id)['lattice_receipts']
    with pytest.raises(ValueError, match='already know'):
        encounters.start_lift(presence, data.id, source.generation)
    assert not owner.commerce.pending
