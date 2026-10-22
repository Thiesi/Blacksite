"""Game 8.6: actual inventory use, committed clocks and resource effects."""

import pytest

from blacksite.server.items import make_item
from blacksite.server.protocol import Frame
from tests.character_helpers import act
from tests.server.test_commerce import caller, execute, game


def give(game, client, tid):
    player = game.core.characters.players[client.session.player_id]
    iid = f"test-origin:item:{game.core.combat.next_serial()+1}"
    item = make_item(iid,game.core.loop.content.items[tid],player.id,game.clock.now_utc().isoformat())
    game.core.commerce.items[iid] = item
    player.inventory.append(iid)
    return iid


@pytest.mark.parametrize("tid", ["drug_sablier_focus", "drug_sablier_calm", "drug_sable_redline",
    "drug_sable_glass", "drug_sable_brick", "drug_sable_deepwater", "drug_ow_static",
    "drug_chapel_hush", "drug_ferry_ringdust", "drug_sable_lullaby", "drug_sable_chrome"])
def test_game_8_6_every_shipped_substance_consumes_through_real_inventory(game,tid):
    client = caller(game)
    player = game.core.characters.players[client.session.player_id]
    iid = give(game,client,tid)
    assert execute(game,client,"inv.use",item=iid)
    assert iid not in player.inventory and iid not in game.core.commerce.items
    assert player.drugs_active[0]["template"] == tid
    assert game.core.characters.me(client.session)["effects"][-1]["template"] == tid


def test_game_8_6_dose_failure_keeps_item_and_third_committed_dose_logs_dependency(game):
    client = caller(game)
    player = game.core.characters.players[client.session.player_id]
    iid = give(game,client,"drug_sable_redline")
    act(game,client,Frame("intent",{"name":"inv.use","args":{"item":iid}}))
    assert not player.drugs_active and iid in player.inventory
    game.commit_commerce(error=True)
    assert not player.drugs_active and iid in player.inventory
    execute(game,client,"inv.use",item=iid)
    for _ in range(2):
        execute(game,client,"inv.use",item=give(game,client,"drug_sable_redline"))
    assert len(player.dependencies) == 1 and len(player.drugs_active) == 1
    assert game.core.progression.modifiers(player).multiplier("weapon_cooldown_multiplier") == pytest.approx(.96)
    lines = [line["text"] for frame in game.frames_for(client) if frame.type == "log" for line in frame.data["lines"]]
    assert any("Dependency takes hold" in line for line in lines)
    game.clock.advance(1400)
    game.core.progression.substances.refresh(player.id)
    game.commit_commerce()
    assert not player.drugs_active and player.dependencies
    assert game.core.progression.modifiers(player).multiplier("weapon_cooldown_multiplier") == 1.2


def test_game_8_6_actual_hot_polls_once_with_transaction_rollback(game):
    client = caller(game)
    player = game.core.characters.players[client.session.player_id]
    actor = game.core.combat.actor(player)
    actor.health = player.health = 50
    execute(game,client,"inv.use",item=give(game,client,"drug_sable_lullaby"))
    game.clock.advance(50)
    game.core.progression.substances.refresh(player.id)
    assert actor.health == 50
    game.commit_commerce(error=True)
    assert actor.health == 50
    game.core.progression.substances.refresh(player.id)
    game.commit_commerce()
    assert actor.health == 65
    game.core.progression.substances.refresh(player.id)
    game.commit_commerce()
    assert actor.health == 65


def test_game_8_6_chrome_expiry_unseats_newest_hardware_only_after_commit(game):
    client = caller(game)  # Ghost: four ordinary tolerance, five with Chrome.
    player = game.core.characters.players[client.session.player_id]
    execute(game,client,"inv.use",item=give(game,client,"drug_sable_chrome"))
    for tid,slot in (("imp_sablier_shock_sink","spine"), ("imp_halvard_reflex_arm","arms1"), ("imp_sablier_adrenal","torso")):
        iid = give(game,client,tid)
        player.implants[slot] = iid
        player.progress.setdefault("implant_order",[]).append(iid)
    newest = player.implants["torso"]
    quality = game.core.commerce.items[newest].quality
    game.clock.advance(12000)
    game.core.progression.substances.refresh(player.id)
    assert player.implants["torso"] == newest
    game.commit_commerce()
    assert "torso" not in player.implants and newest in player.inventory
    assert game.core.commerce.items[newest].quality == quality
    assert game.core.combat.actor(player).shock == 100


def test_game_8_6_ringdust_can_down_a_body_once_and_food_ends_timed_crash(game):
    client = caller(game)
    player = game.core.characters.players[client.session.player_id]
    actor = game.core.combat.actor(player)
    execute(game,client,"inv.use",item=give(game,client,"drug_ferry_ringdust"))
    actor.health = player.health = 1
    game.clock.advance(10)
    game.core.progression.substances.refresh(player.id)
    game.commit_commerce()
    assert actor.health == 0 and actor.stance == "down"
    assert player.progress["combat"]["stage"] == "down"
    assert player.progress["combat"]["killer"] == ""


def test_game_8_6_ration_removes_real_timed_ringdust_crash(game):
    client = caller(game)
    player = game.core.characters.players[client.session.player_id]
    execute(game,client,"inv.use",item=give(game,client,"drug_ferry_ringdust"))
    game.clock.advance(600)
    game.core.progression.substances.refresh(player.id)
    game.commit_commerce()
    assert game.core.progression.modifiers(player).multiplier("stamina_regen_multiplier") == .3
    execute(game,client,"inv.use",item=give(game,client,"con_kestrel_ration"))
    assert game.core.progression.modifiers(player).multiplier("stamina_regen_multiplier") == 1


def test_game_8_5_secure_pocket_increases_actual_inventory_limit(game):
    client = caller(game)
    player = game.core.characters.players[client.session.player_id]
    for iid in player.inventory:
        game.core.commerce.items[iid].secured = False
    player.implants["torso"] = give(game,client,"imp_sablier_secure_pocket")
    patches = [give(game,client,"con_sablier_patch") for _ in range(5)]
    for iid in patches[:4]:
        assert execute(game,client,"inv.secure",item=iid)
    assert not execute(game,client,"inv.secure",item=patches[4])
    assert sum(game.core.commerce.items[iid].secured for iid in player.inventory) == 4


def test_game_8_5_forced_capacity_loss_saves_flags_with_unseating_and_logs_names(game):
    client = caller(game)
    player = game.core.characters.players[client.session.player_id]
    execute(game,client,"inv.use",item=give(game,client,"drug_sable_chrome"))
    for tid,slot in (("imp_sablier_shock_sink","spine"), ("imp_halvard_reflex_arm","arms1"), ("imp_sablier_secure_pocket","torso")):
        iid = give(game,client,tid)
        player.implants[slot] = iid
        player.progress.setdefault("implant_order",[]).append(iid)
    for iid in player.inventory:
        game.core.commerce.items[iid].secured = False
    secured = [give(game,client,"con_sablier_patch") for _ in range(4)]
    for iid in secured:
        game.core.commerce.items[iid].secured = True
    game.clock.advance(12000)
    engine = game.core.progression.substances
    engine.refresh(player.id)
    game.commit_commerce(error=True)
    assert "torso" in player.implants and all(game.core.commerce.items[iid].secured for iid in secured)
    engine.refresh(player.id)
    receipts = game.commit_commerce()
    assert "torso" not in player.implants
    assert all(game.core.commerce.items[iid].secured for iid in secured[:3])
    assert not game.core.commerce.items[secured[-1]].secured
    assert any(item["id"] == secured[-1] and not item["secured"] for item in receipts[0]["items"])
    lines = [line["text"] for frame in game.frames_for(client) if frame.type == "log" for line in frame.data["lines"]]
    assert any("become unsecured" in line and "Patch" in line for line in lines)
