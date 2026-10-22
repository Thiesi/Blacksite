"""Game 4/6.7: live core rules through the production headless core."""

from dataclasses import replace

import pytest

from tests.character_helpers import place, state
from tests.harness import HeadlessServer
from tests.lattice.test_engine import actor, intent, jack, runners


def enter(game, client, core_id):
    presence = jack(game, client)
    presence.cell = next(c.id for c in game.core.lattice.sectors.records[presence.sector].cells
                         if c.core_id == core_id)
    intent(game, client, "lat.enter", core=core_id)
    assert presence.core == core_id
    return presence


def cast(game, client, program, target=""):
    intent(game, client, "lat.cast", program=program, target=target)
    presence = game.core.lattice.presences[client.session.player_id]
    assert presence.cast
    game.step(presence.cast.until-game.clock.now_tick())


def room(game, client, target):
    intent(game, client, "lat.room", room=target)
    presence = game.core.lattice.presences[client.session.player_id]
    assert presence.room_destination == target
    game.step(presence.move_until-game.clock.now_tick())


def test_game_4_private_training_defeat_lift_and_leave(runners):
    game, a, b, c = runners
    place(game, a, "vatside-wake-hall", (34, 15))
    presence = enter(game, a, "lat-wake-hall")
    encounters = game.core.lattice.encounters
    ice = encounters.defenders(presence)[0]
    assert ice.integrity == 10 and presence.trace == 0
    cast(game, a, "prg_pick", ice.id)
    assert not ice.alive
    data = encounters.core(presence).graph.room(presence.room).data[0]
    source = game.core.lattice.sources.refresh(encounters.source(presence, data), data, game.clock.now_tick())
    intent(game, a, "lat.lift", target=data.id, generation=source.generation)
    game.step(presence.procedure.until-game.clock.now_tick())
    player = game.core.characters.players[presence.player_id]
    assert "lattice-training-record" not in player.progress.get("lattice_records", {})
    effects = game.commit_commerce()
    assert "lattice-training-record" in player.progress["lattice_records"]
    assert effects[0]["lattice_state"]["sources"][encounters.source(presence, data)]["generation"] == 1
    assert presence.trace == 0 and player.xp == 0
    intent(game, a, "interact")
    intent(game, a, "menu_select", row="read:lattice-training-record")
    view = game.core.characters.sim.external_views[a.session.id]
    assert view[0] == "menu" and view[1]["title"] == "YOUR DECANT RECORD"
    assert any("decant" in row["cells"][0] for row in view[1]["rows"])
    intent(game, a, "menu_close")
    intent(game, a, "lat.leave")
    assert presence.instance is None and actor(game, a).stance == "jacked"
    intent(game, a, "lat.jack_out")
    assert actor(game, a).stance == "normal"


def test_game_4_training_instances_and_chat_are_private(runners):
    game, a, b, c = runners
    for client, tile in ((a, (34, 15)), (b, (35, 16))):
        place(game, client, "vatside-wake-hall", tile)
    one, two = enter(game, a, "lat-wake-hall"), enter(game, b, "lat-wake-hall")
    encounters = game.core.lattice.encounters
    assert one.instance != two.instance
    cast(game, a, "prg_pick", encounters.defenders(one)[0].id)
    assert encounters.defenders(two)[0].integrity == 10
    assert not game.core.lattice.view(a.session, one)["presences"]
    assert game.core.lattice.location(a.session) != game.core.lattice.location(b.session)
    game.frames_for(b)
    intent(game, a, "chat", channel="say", text="private lesson")
    assert not any("private lesson" in line["text"] for f in game.frames_for(b)
                   if f.type == "log" for line in f.data["lines"])


def test_game_4_training_cannot_kill_or_create_trace(runners):
    game, a, b, c = runners
    place(game, a, "vatside-wake-hall", (34, 15))
    presence = enter(game, a, "lat-wake-hall")
    hp = actor(game, a).health
    game.step(150)
    assert presence.integrity >= 1 and presence.trace == 0
    assert actor(game, a).health == hp and actor(game, a).stance == "jacked"


def test_game_6_7_public_entrance_does_not_make_core_escape_immediate(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    intent(game, a, "lat.jack_out")
    assert presence.escape and presence.player_id in game.core.lattice.presences
    game.step(presence.escape.until_tick-game.clock.now_tick())
    assert presence.player_id not in game.core.lattice.presences


def test_game_6_7_turnstile_retreat_and_completed_key(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    # A legitimate learned binding fixture; loading alone grants no opening.
    presence.rig = ("prg_skeleton", "prg_umbrella", None)
    room(game, a, "r-foyer")
    game.core.lattice.encounters.defenders(presence)[0].integrity = 0
    room(game, a, "r-records")
    gate = game.core.lattice.encounters.defenders(presence)[0]
    intent(game, a, "lat.room", room="r-cache")
    assert presence.room_destination is None and gate.id not in presence.opened
    room(game, a, "r-foyer")
    room(game, a, "r-records")
    cast(game, a, "prg_skeleton")
    assert gate.id in presence.opened
    room(game, a, "r-cache")


def test_game_6_7_cash_receipt_failure_retry_and_restart(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    # Isolate the source transaction from traversal/encounter assertions above.
    presence.room = "r-cache"
    encounters = game.core.lattice.encounters
    data = encounters.core(presence).graph.room(presence.room).data[0]
    key = encounters.source(presence, data)
    game.core.lattice.sources.refresh(key, data, game.clock.now_tick())
    player = game.core.characters.players[presence.player_id]
    original = player.chits_hand
    def lift():
        intent(game, a, "lat.lift", target=data.id, generation=0)
        game.step(presence.procedure.until-game.clock.now_tick())
    lift()
    game.commit_commerce(error=True)
    assert player.chits_hand == original
    assert game.core.lattice.sources.sources[key].generation == 0
    lift()
    effects = game.commit_commerce()
    assert player.chits_hand == original+80
    assert game.core.lattice.sources.sources[key].generation == 1
    saved = state(game)
    saved["lattice"] = effects[0]["lattice_state"]
    restored = HeadlessServer(game.core.loop.content, character_state=saved, clock=game.clock)
    assert restored.core.characters.players[player.id].chits_hand == original+80
    assert not restored.core.lattice.sources.refresh(key, data, game.clock.now_tick()).available
    intent(game, a, "lat.lift", target=data.id, generation=0)
    assert presence.procedure is None and player.chits_hand == original+80


def test_game_6_7_cooldown_survives_escape_and_new_presence(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    cast(game, a, "prg_umbrella")
    player = game.core.characters.players[presence.player_id]
    deadline = player.progress["lattice_cooldowns"]["prg_umbrella"]
    intent(game, a, "lat.jack_out")
    presence = jack(game, a)
    intent(game, a, "lat.cast", program="prg_umbrella")
    assert presence.cast is None and presence.effects.shield is None
    assert player.progress["lattice_cooldowns"]["prg_umbrella"] == deadline


def test_game_6_7_refused_shield_downgrade_spends_no_caffeine(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    content = game.core.loop.content
    presence.effects.install(content.programs["prg_bunker"], game.clock.now_tick())
    presence.effects.install(content.programs["prg_caffeine"], game.clock.now_tick())
    intent(game, a, "lat.cast", program="prg_umbrella")
    assert presence.cast is None and presence.effects.has("prg_caffeine", game.clock.now_tick())
    assert presence.effects.shield.budget == 60


def test_ui_3_back_after_menu_close_retreats_even_before_client_context_refresh(runners):
    game, a, b, c = runners
    presence = enter(game, a, 'lat-civic-ledger')
    intent(game, a, 'interact')
    assert a.session.id in game.core.lattice.encounters.menus
    intent(game, a, 'menu_close')
    assert a.session.id not in game.core.lattice.encounters.menus
    intent(game, a, 'menu_close')
    assert presence.instance is None and actor(game, a).stance == 'jacked'
