"""Catalog 5: data-backed carrying, scouting, crew medicine and following."""

import pytest

import blacksite.server.views.zone_view as zone_view
from blacksite.server.inventory import Inventory
from blacksite.server.rules import character
from blacksite.server.world.actors import Actor
from tests.character_helpers import create, place
from tests.combat.test_engine import body
from tests.server.test_drone_combat import deploy
from tests.server.test_drone_ownership import operator
from tests.server.test_substances import give


def zone_snapshot(game,client):
    sim = game.core.characters.sim
    game.frames_for(client)
    sim.reset_view(client.session,sim.avatars[client.session.user_id])
    game.step()
    return next(frame.data["body"] for frame in game.frames_for(client)
                if frame.type == "view" and frame.data.get("kind") == "zone")


def test_catalog_5_both_carriers_change_real_encumbrance_and_keep_item_quality(operator):
    game,a,b,player,engine = operator
    mule = deploy(game,a,player,engine,"drn_kestrel_mule")
    lifter = deploy(game,a,player,engine,"drn_ferry_lifter")
    assert game.core.progression.modifiers(player).bonus("carry_kg") == 80
    inventory = Inventory(game.core.commerce.items,game.core.loop.content.items)
    baseline = character.carry_kg(player.attributes["frame"])
    while inventory.weight(player) < baseline+70:
        give(game,a,"wpn_halvard_hv7")
    game.core.progression.sync_actor(player)
    assert not body(game,a).overweight
    engine.command(player,mule.behaviour["item"],"recall"); game.commit_commerce()
    assert game.core.progression.modifiers(player).bonus("carry_kg") == 60
    assert body(game,a).overweight


def test_catalog_5_scout_adds_actual_zone_visibility_and_memory_then_loses_live_feed(operator,monkeypatch):
    game,a,b,player,engine = operator
    place(game,b,"vatside-clinics",(29,3))
    # Darkness fixture isolates the additional viewpoint from ordinary sight.
    monkeypatch.setattr(zone_view,"sight_radius",lambda *args:1)
    before = zone_snapshot(game,a)
    assert body(game,b).id not in {entry["id"] for entry in before["actors"]}
    eye = deploy(game,a,player,engine,"drn_ostrom_eye")
    view = zone_snapshot(game,a)
    assert body(game,b).id in {entry["id"] for entry in view["actors"]}
    remembered = game.core.characters.sim.avatars[a.session.user_id].perception.remembered
    assert body(game,b).position in remembered[eye.zone]
    engine.command(player,eye.behaviour["item"],"recall"); game.commit_commerce()
    view = zone_snapshot(game,a)
    assert body(game,b).id not in {entry["id"] for entry in view["actors"]}
    assert body(game,b).position in remembered[player.zone]


def test_catalog_5_scout_does_not_reveal_other_callers_training_or_extend_stealth_detection(operator,monkeypatch):
    game,a,b,player,engine = operator
    place(game,b,"core-plaza",(33,5))
    caller = game.connect({"user_id":3,"handle":"Hidden界","node_name":"test"})
    create(game,caller,archetype=1,name="Quiet",card="none")
    place(game,caller,"vatside-clinics",(29,3))
    body(game,caller).stance = "stealth"
    eye = deploy(game,a,player,engine,"drn_ostrom_eye")
    # Eye is three tiles away: inside ordinary radius6 but outside stealth's3.
    # Put the observer another tile toward the controller to make separation4.
    game.core.world.enter(eye,eye.zone,(25,4))
    private = Actor("private-training","Private lesson",kind="drone",owner=b.session.player_id,
                    behaviour={"training":True})
    game.core.world.enter(private,eye.zone,(28,3))
    monkeypatch.setattr(zone_view,"sight_radius",lambda *args:1)
    view = zone_snapshot(game,a)
    ids = {entry["id"] for entry in view["actors"]}
    assert body(game,caller).id not in ids and private.id not in ids


def test_catalog_5_medic_restores_real_crew_deficits_once_per_second_without_hymn_gain(operator):
    game,a,b,player,engine = operator
    medic = deploy(game,a,player,engine,"drn_sablier_medic")
    owner,ally = body(game,a),body(game,b)
    game.core.combat.allies_provider = lambda actor:[owner,ally]
    owner.health -= 20; ally.health -= 20
    before = owner.health,ally.health,player.skills["drones"],player.skills["hymns"]
    game.step(); game.commit_commerce()
    assert (owner.health,ally.health) == (before[0]+8,before[1]+8)
    assert player.skills["drones"] == pytest.approx(before[2]+.1) and player.skills["hymns"] == before[3]
    game.step(9); game.commit_commerce()
    assert (owner.health,ally.health) == (before[0]+8,before[1]+8)
    game.step(); game.commit_commerce()
    assert (owner.health,ally.health) == (before[0]+16,before[1]+16)
    owner.health = owner.health_max; ally.health = ally.health_max
    learned = player.skills["drones"]
    game.step(20); game.commit_commerce()
    assert player.skills["drones"] == learned


def test_game_5_3_follow_crosses_with_controller_while_hold_keeps_its_zone_and_health(operator):
    game,a,b,player,engine = operator
    mule = deploy(game,a,player,engine,"drn_kestrel_mule")
    eye = deploy(game,a,player,engine,"drn_ostrom_eye")
    engine.command(player,eye.behaviour["item"],"hold"); game.commit_commerce()
    old_zone = eye.zone
    mule.health = 17
    place(game,a,"core-plaza",game.core.world.free_tile("core-plaza",(30,5)))
    assert mule.zone == old_zone
    game.commit_commerce()
    assert mule.zone == body(game,a).zone == "core-plaza" and mule.health == 17
    assert eye.zone == old_zone


def test_game_3_5_support_objective_learns_on_arrival_and_deduplicates_destination(operator):
    game,a,b,player,engine = operator
    mule = deploy(game,a,player,engine,"drn_kestrel_mule")
    place(game,b,mule.zone,(30,3))
    start = mule.position
    before = player.skills["drones"]
    engine.command(player,mule.behaviour["item"],"target",body(game,b).id)
    game.commit_commerce()
    assert player.skills["drones"] == before
    for _ in range(20):
        game.step(); game.commit_commerce()
    assert mule.behaviour["mode"] == "hold" and player.skills["drones"] == pytest.approx(before+.1)
    game.core.world.enter(mule,mule.zone,start)
    engine.command(player,mule.behaviour["item"],"target",body(game,b).id); game.commit_commerce()
    for _ in range(20):
        game.step(); game.commit_commerce()
    assert mule.behaviour["mode"] == "hold" and player.skills["drones"] == pytest.approx(before+.1)
