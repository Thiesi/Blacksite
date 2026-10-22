"""Game 8.5: installed resonance perception, with no generated XP loops."""

import pytest

from blacksite.server.implants import install
from tests.character_helpers import create, place
from tests.lattice.test_engine import jack, runners
from tests.lattice.test_rig_progression import hardware


@pytest.fixture
def listener(runners):
    game,a,b,c = runners
    client = game.connect({"user_id":4,"handle":"Ear界","node_name":"test"})
    create(game,client,archetype=2,name="Listener",card="none")
    terminal = next(obj for obj in game.core.world.zones["core-plaza"].objects.values() if obj.spec.kind == "terminal")
    place(game,client,"core-plaza",game.core.world.free_tile("core-plaza",terminal.spec.tile))
    player = game.core.characters.players[client.session.player_id]
    player.chits_hand = 50000
    player.standing["choir"] = 20  # Disclosed acquisition fixture; gates are tested separately.
    return game,client,player


def hidden_at_two_links(lat,player):
    return next((sid,hidden,root) for sid,cells in lat.sectors.cells.items()
        for hidden in cells.values() if hidden.access_kind == "hidden" and hidden.id not in lat.found(player,sid)
        for neighbour in hidden.neighbours for root in cells[neighbour].neighbours
        if root != hidden.id and root not in hidden.neighbours and cells[root].access_kind != "hidden")


def test_game_8_5_second_ear_bag_is_inert_then_installed_radius_reveals_once(listener):
    game,client,player = listener
    item = hardware(game,player,"imp_res_second_ear",installed=False)
    presence = jack(game,client)
    lat = game.core.lattice
    sid,hidden,root = hidden_at_two_links(lat,player)
    presence.sector,presence.cell = sid,root
    lat.sense_hidden(presence)
    game.commit_commerce()
    assert hidden.id not in lat.found(player,sid)
    install(player,item,"sablier",game.core.progression.modifiers(player),game.core.commerce.items,
            game.core.loop.content.items,game.clock.now_utc().timestamp(),.5,owned=True)
    xp = player.xp
    lat.sense_hidden(presence)
    lat.sense_hidden(presence)  # Pending reveals must not fill the commerce queue.
    game.commit_commerce()
    assert hidden.id in lat.found(player,sid) and player.xp == xp
    learned = player.skills["listening"]
    assert learned >= .5
    lat.sense_hidden(presence)
    game.commit_commerce()
    assert player.skills["listening"] == learned and player.xp == xp


def test_game_8_5_tenant_ear_discloses_deferred_forecast_and_accepts_event_hook(listener):
    game,client,player = listener
    item = hardware(game,player,"imp_res_tenant_ear",installed=False)
    install(player,item,"sablier",game.core.progression.modifiers(player),game.core.commerce.items,
            game.core.loop.content.items,game.clock.now_utc().timestamp(),.5,owned=True,replace=True)
    slot = game.core.loop.content.items[item.template].implant.slot
    engine = game.core.progression
    rows = engine.sheet(player,0)["rows"]
    cursor = next(i for i,row in enumerate(rows) if row["id"] == "implant:"+slot)
    assert "No effect yet" in engine.sheet(player,cursor)["detail"]
    engine.surge_preview = lambda resident:"Announced variants: Mastiff, Anchor."
    detail = engine.sheet(player,cursor)["detail"]
    assert "Announced variants" in detail and "No effect yet" not in detail
