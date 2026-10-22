"""Catalog 5: mobile terminals preserve the Lattice's escape contract."""

import pytest

from blacksite.server.protocol import Frame
from tests.character_helpers import act, place
from tests.combat.test_engine import body
from tests.server.test_drone_combat import deploy
from tests.server.test_drone_ownership import operator


def connect(game,client,relay):
    act(game,client,Frame("intent",{"name":"lat.jack_in","args":{"target":relay.id}}))
    game.commit_commerce()
    return game.core.lattice.presences[client.session.player_id]


def test_catalog_5_relay_loans_rig_and_cannot_move_or_recall_connected_runner(operator):
    game,a,b,player,engine = operator
    relay = deploy(game,a,player,engine,"drn_ow_relay")
    presence = connect(game,a,relay)
    assert presence.loaned_rig and presence.jack_source == relay.id and len(presence.rig) == 3
    position = relay.position
    game.step(12)
    assert relay.position == position and body(game,a).stance == "jacked"
    with pytest.raises(ValueError,match="Return to your body"):
        engine.command(player,relay.behaviour["item"],"recall",system=False)
    assert not engine.command(player,relay.behaviour["item"],"recall",system=True)
    game.core.lattice.jack_out(a.session)
    engine.command(player,relay.behaviour["item"],"recall"); game.commit_commerce()
    assert relay.id not in game.core.world.actors


def test_catalog_5_relay_destruction_forces_shock_and_jack_out(operator):
    game,a,b,player,engine = operator
    relay = deploy(game,a,player,engine,"drn_ow_relay")
    presence = connect(game,a,relay)
    relay.health = 0
    game.step()
    assert player.id not in game.core.lattice.presences
    assert body(game,a).stance == "normal" and body(game,a).shock == 100


def test_catalog_5_crew_relay_owner_disconnect_starts_bounded_escape_not_instant_safety(operator):
    game,a,b,player,engine = operator
    relay = deploy(game,a,player,engine,"drn_ow_relay")
    place(game,b,relay.zone,game.core.world.free_tile(relay.zone,relay.position))
    game.core.progression.crew_of = lambda pid:"fixture-crew"
    presence = connect(game,b,relay)
    presence.cell = next(c.id for c in game.core.lattice.sectors.records[presence.sector].cells
                         if c.access_kind == "gated")
    game.core.sessions.disconnect(a.session)
    game.step()
    assert presence.link_failed and presence.escape is not None
    assert presence.player_id in game.core.lattice.presences and relay.id in game.core.world.actors
    end = presence.escape.until_tick
    act(game,b,Frame("intent",{"name":"lat.move","args":{"cell":presence.cell}}))
    assert presence.escape.until_tick == end and presence.destination is None
    game.step(end-game.clock.now_tick()); game.commit_commerce()
    assert presence.player_id not in game.core.lattice.presences
    assert relay.id not in game.core.world.actors


def test_catalog_5_foreign_relay_refuses_without_crew(operator):
    game,a,b,player,engine = operator
    relay = deploy(game,a,player,engine,"drn_ow_relay")
    place(game,b,relay.zone,game.core.world.free_tile(relay.zone,relay.position))
    act(game,b,Frame("intent",{"name":"lat.jack_in","args":{"target":relay.id}}))
    assert b.session.player_id not in game.core.lattice.presences
