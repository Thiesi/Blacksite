"""Game 8.5/8.6: purchased hardware, integrity and composed Lattice costs."""

import pytest

from blacksite.server.drugs import dose
from blacksite.server.implants import install
from blacksite.server.items import make_item
from tests.character_helpers import create, place
from tests.lattice.test_engine import jack, runners
from tests.lattice.test_encounters import enter


@pytest.fixture
def ghost_link(runners):
    game, a, b, c = runners
    caller = game.connect({"user_id":4,"handle":"Rig\u754c","node_name":"test"})
    create(game,caller,archetype=1,name="Rig\u754c",card="none")
    place(game,caller,"core-plaza",(33,5))
    player = game.core.characters.players[caller.session.player_id]
    player.chits_hand = 50000  # Fixture isolates hardware, not earning time.
    return game, caller, player


def hardware(game, player, tid, *, installed):
    template = game.core.loop.content.items[tid]
    iid = f"test-origin:item:{game.core.combat.next_serial()+1}"
    item = make_item(iid,template,player.id,game.clock.now_utc().isoformat())
    game.core.commerce.items[iid] = item
    player.inventory.append(iid)
    if installed:
        install(player,item,"sablier",game.core.progression.modifiers(player),
            game.core.commerce.items,game.core.loop.content.items,game.clock.now_utc().timestamp(),
            .5,owned=True)
    return item


def test_game_8_5_bag_rig_has_no_installed_slots_or_integrity(ghost_link):
    game, caller, player = ghost_link
    lattice = game.core.lattice
    item = hardware(game,player,"imp_rig_sablier_clinical",installed=False)
    assert lattice.carried_slots(player) == 3 and lattice.integrity_limit(player) == 100
    install(player,item,"sablier",game.core.progression.modifiers(player),
        game.core.commerce.items,game.core.loop.content.items,game.clock.now_utc().timestamp(),.5,owned=True)
    assert lattice.carried_slots(player) == 4 and lattice.integrity_limit(player) == 110
    presence = jack(game,caller)
    assert len(presence.rig) == 4 and presence.integrity == presence.integrity_max == 110
    dose(player,game.core.loop.content.items["drug_ow_static"],game.core.progression.modifiers(player),game.clock.now_utc().timestamp())
    lattice.sync_player_modifiers(player)
    assert presence.integrity_max == 130 and presence.integrity == 110
    assert lattice.view(caller.session,presence)["me"]["integrity_max"] == 130


def test_game_8_6_rig_and_drug_trace_compose_but_fixed_burn_does_not(ghost_link):
    game, caller, player = ghost_link
    hardware(game,player,"imp_rig_ow_jury",installed=True)
    dose(player,game.core.loop.content.items["drug_sable_deepwater"],game.core.progression.modifiers(player),game.clock.now_utc().timestamp())
    presence = enter(game,caller,"lat-civic-ledger")
    before = presence.trace
    game.core.lattice.encounters.trace(presence,10)
    assert presence.trace-before == pytest.approx(13.2)
    before = presence.trace
    game.core.lattice.encounters.trace(presence,15,fixed=True)
    assert presence.trace-before == pytest.approx(15)


def test_game_8_6_deepwater_rig_and_drug_move_effects_both_apply(ghost_link):
    game, caller, player = ghost_link
    hardware(game,player,"imp_rig_ow_deepwater",installed=True)
    dose(player,game.core.loop.content.items["drug_sable_deepwater"],game.core.progression.modifiers(player),game.clock.now_utc().timestamp())
    assert game.core.lattice.carried_slots(player) == 6
    assert game.core.lattice.encounters.move_multiplier(player) == pytest.approx(.56)
    presence = jack(game,caller)
    presence.integrity = 130
    # Expiring Static/other buffers cannot leave integrity over the limit.
    game.core.lattice.sync_player_modifiers(player)
    assert presence.integrity == presence.integrity_max == 100
