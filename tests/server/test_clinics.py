"""Game 8.5/8.6: actual counters, final confirmation and persisted detox."""

from dataclasses import replace
from math import ceil
from random import Random

import pytest

from blacksite.content.loader import load_content
from blacksite.server.protocol import Frame
from tests.character_helpers import act, place, state
from tests.harness import HeadlessServer
from tests.server.test_commerce import caller, execute
from tests.server.test_substances import give


@pytest.fixture
def clinic(repo_root):
    content = load_content(repo_root/"src/blacksite/content")
    content.zones = {k:replace(z,meta=replace(z.meta,spawners=())) for k,z in content.zones.items()}
    game = HeadlessServer(content,character_state={})
    client = caller(game)
    player = game.core.characters.players[client.session.player_id]
    player.chits_hand = 10000  # Disclosed service funding fixture, no altered catalog price.
    place(game,client,"vatside-clinics",game.core.world.free_tile("vatside-clinics",(10,8)))
    act(game,client,Frame("intent",{"name":"clinic.open","args":{"target":"sablier-main-clinic"}}))
    engine = game.core.progression.clinics
    assert client.session.id in engine.menus
    return game,client,player,engine


def select(game,client,key="enter",request=""):
    body = game.core.characters.sim.external_views[client.session.id][1]
    frame = Frame("intent",{"name":"menu_select","args":{"key":key,
        "row":body["rows"][body["cursor"]]["id"]},"request_id":request or f"clinic-{game.clock.now_tick()}",
        "expected_revision":client.session.view_revision})
    act(game,client,frame)
    return frame


def review(game,client,engine,opid):
    screen = engine.menus[client.session.id]
    index = next(i for i,op in enumerate(engine.options(client.session,screen)) if op.id == opid)
    act(game,client,Frame("intent",{"name":"menu_cursor","args":{"delta":index-screen.cursor}}))
    select(game,client)
    assert screen.confirm == opid
    return screen


def test_game_8_5_owned_install_confirms_full_bill_and_commits_once(clinic):
    game,client,player,engine = clinic
    iid = give(game,client,"imp_halvard_reflex_arm")  # Disclosed owned hardware loan, not a Spire purchase.
    game.core.commerce.items[iid].quality = 1.08
    screen = review(game,client,engine,"install:"+iid+":arms1")
    op = next(op for op in engine.options(client.session,screen) if op.id == screen.confirm)
    bill = engine.quote(player,engine.counter(client.session,screen.target),op)
    body = engine.view(client.session,screen)
    assert any("2%" in cell for row in body["rows"] for cell in row["cells"])
    assert any("2/4" in cell for row in body["rows"] for cell in row["cells"])
    game.core.world.zones["vatside-clinics"].rng = Random(1)
    frame = select(game,client,"y","install-one")
    act(game,client,frame)
    assert "arms1" not in player.implants and player.chits_hand == 10000
    game.commit_commerce()
    assert player.implants["arms1"] == iid and player.chits_hand == 10000-bill.total
    assert game.core.commerce.items[iid].quality == 1.08
    assert game.core.progression.modifiers(player).multiplier("weapon_cooldown_multiplier") == .9
    act(game,client,frame)
    assert not game.core.commerce.outbox


def test_game_8_5_back_and_n_cancel_without_a_charge_or_roll(clinic):
    game,client,player,engine = clinic
    iid = give(game,client,"imp_halvard_reflex_arm")
    rng = game.core.world.zones["vatside-clinics"].rng
    before = rng.getstate()
    review(game,client,engine,"install:"+iid+":arms1")
    select(game,client,"n")
    assert not engine.menus[client.session.id].confirm
    review(game,client,engine,"install:"+iid+":arms1")
    act(game,client,Frame("intent",{"name":"menu_close","args":{}}))
    assert client.session.id not in engine.menus
    assert player.chits_hand == 10000 and iid in player.inventory and rng.getstate() == before


def test_game_8_5_seeded_failed_replacement_keeps_old_quality_and_charges_after_save(clinic):
    game,client,player,engine = clinic
    old = give(game,client,"imp_halvard_stabiliser")
    player.implants["arms1"] = old
    game.core.commerce.items[old].quality = 1.11
    iid = give(game,client,"imp_halvard_reflex_arm")
    screen = review(game,client,engine,"install:"+iid+":arms1")
    op = next(op for op in engine.options(client.session,screen) if op.id == screen.confirm)
    bill = engine.quote(player,engine.counter(client.session,screen.target),op)
    assert bill.removal_price > 0
    game.core.world.zones["vatside-clinics"].rng = Random(31)
    select(game,client,"y")
    assert player.implants["arms1"] == old and iid in player.inventory
    game.commit_commerce()
    assert "arms1" not in player.implants and iid not in player.inventory
    assert old in player.inventory and game.core.commerce.items[old].quality == 1.11
    assert player.chits_hand == 10000-bill.total and game.core.combat.actor(player).shock == 100


def test_game_8_5_save_failure_leaves_chits_hardware_and_installation_untouched(clinic):
    game,client,player,engine = clinic
    iid = give(game,client,"imp_halvard_reflex_arm")
    review(game,client,engine,"install:"+iid+":arms1")
    select(game,client,"y")
    game.commit_commerce(error=True)
    assert player.chits_hand == 10000 and iid in player.inventory and "arms1" not in player.implants


def test_game_8_5_removal_returns_quality_and_rejects_occupied_secured_bonus(clinic):
    game,client,player,engine = clinic
    iid = give(game,client,"imp_sablier_secure_pocket")
    game.core.commerce.items[iid].quality = .94
    player.implants["torso"] = iid
    for carried in player.inventory:
        game.core.commerce.items[carried].secured = False
    secured = [give(game,client,"con_sablier_patch") for _ in range(4)]
    for carried in secured:
        game.core.commerce.items[carried].secured = True
    review(game,client,engine,"remove:torso")
    select(game,client,"y")
    assert not game.core.commerce.outbox and player.implants["torso"] == iid and player.chits_hand == 10000
    game.core.commerce.items[secured[-1]].secured = False
    select(game,client,"y")
    game.commit_commerce()
    assert "torso" not in player.implants and iid in player.inventory
    assert game.core.commerce.items[iid].quality == .94


def test_game_8_5_real_vendor_hotkey_opens_clinic_and_remote_counter_refuses(clinic):
    game,client,player,engine = clinic
    engine.close(client.session)
    act(game,client,Frame("key",{"k":"e","t":0}))
    vendor = game.core.commerce.menus[client.session.id]
    assert vendor.target == "sablier-main-clinic"
    select(game,client,"c")
    assert client.session.id in engine.menus
    engine.close(client.session)
    place(game,client,"core-plaza",(30,5))
    act(game,client,Frame("intent",{"name":"clinic.open","args":{"target":"sablier-main-clinic"}}))
    assert client.session.id not in engine.menus


def test_game_8_6_confirmed_detox_blocks_actions_and_completes_after_offline_time(clinic):
    game,client,player,engine = clinic
    engine.close(client.session)
    for _ in range(3):
        execute(game,client,"inv.use",item=give(game,client,"drug_sable_redline"))
    assert player.dependencies
    act(game,client,Frame("intent",{"name":"clinic.open","args":{"target":"sablier-main-clinic"}}))
    review(game,client,engine,"detox")
    select(game,client,"y")
    assert player.chits_hand == 10000 and "detox" not in player.progress
    game.commit_commerce()
    assert player.chits_hand == 9600
    actor = game.core.combat.actor(player)
    before = actor.position
    act(game,client,Frame("intent",{"name":"move","args":{"dir":"down"}}))
    assert actor.position == before
    iid = give(game,client,"drug_sable_redline")
    execute(game,client,"inv.use",item=iid)
    assert iid in player.inventory and not player.drugs_active
    saved = state(game)
    restored = HeadlessServer(game.core.loop.content,character_state=saved,clock=game.clock)
    returning = restored.connect({"user_id":1,"handle":"Wide界1","node_name":"test"})
    resident = restored.core.characters.players[player.id]
    position = restored.core.combat.actor(resident).position
    act(restored,returning,Frame("intent",{"name":"move","args":{"dir":"down"}}))
    assert restored.core.combat.actor(resident).position == position
    restored.clock.advance(6010)
    restored.core.progression.substances.refresh(resident.id)
    restored.commit_commerce()
    assert not resident.dependencies and not resident.drugs_active and "detox" not in resident.progress
    assert resident.chits_hand == 9600


def test_game_8_5_clinic_stock_purchase_installs_a_new_owned_instance(clinic):
    game,client,player,engine = clinic
    screen = engine.menus[client.session.id]
    op = next(op for op in engine.options(client.session,screen) if op.action == "install" and not op.owned
              and game.core.loop.content.items[op.item].class_ == "implant")
    review(game,client,engine,op.id)
    bill = engine.quote(player,engine.counter(client.session,screen.target),op)
    template = game.core.loop.content.items[op.item]
    assert bill.total == template.base_price+ceil(template.base_price*.2)
    before = set(player.inventory)
    game.core.world.zones["vatside-clinics"].rng = Random(1)
    select(game,client,"y")
    game.commit_commerce()
    assert player.chits_hand == 10000-bill.total
    assert player.implants[op.slot] in set(player.inventory)-before
    assert game.core.commerce.items[player.implants[op.slot]].template == template.id


def test_game_8_5_typed_black_tariff_uses_fifteen_percent_seeded_failure(clinic):
    game,client,player,engine = clinic
    # Adapter fixture only: the real Sink counter remains deferred to S25.
    vendor = game.core.loop.content.vendors["sablier-clinic"]
    game.core.loop.content.vendors[vendor.id] = replace(vendor,clinic="black")
    iid = give(game,client,"imp_halvard_reflex_arm")
    screen = review(game,client,engine,"install:"+iid+":arms1")
    op = next(op for op in engine.options(client.session,screen) if op.id == screen.confirm)
    bill = engine.quote(player,engine.counter(client.session,screen.target),op)
    assert bill.failure == .15 and bill.total == ceil(game.core.loop.content.items["imp_halvard_reflex_arm"].base_price*.12)
    game.core.world.zones["vatside-clinics"].rng = Random(1)  # 0.134: black fails, Sablier succeeds.
    select(game,client,"y")
    game.commit_commerce()
    assert "arms1" not in player.implants and iid not in player.inventory
    assert player.chits_hand == 10000-bill.total


def test_game_8_6_failed_detox_save_does_not_charge_or_lock_the_caller(clinic):
    game,client,player,engine = clinic
    player.dependencies.append({"template":"drug_sable_redline","since":game.clock.now_utc().timestamp()})
    review(game,client,engine,"detox")
    select(game,client,"y")
    game.commit_commerce(error=True)
    assert player.chits_hand == 10000 and player.dependencies and "detox" not in player.progress
