"""S12 numeric rules, transactional transfers and several live sessions."""

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import sqlite3

import pytest

from blacksite.content.loader import load_content
from blacksite.content.schema import Vendor, VendorStock
from blacksite.server.bank import transfer
from blacksite.server.inventory import Inventory
from blacksite.server.items import ItemInstance, make_item
from blacksite.server.players import Player
from blacksite.server.protocol import Frame
from blacksite.server.storage.db import Storage
from blacksite.server.vendors import BUYBACK_BUDGET, VendorBudget, permitted, price
from tests.character_helpers import act, create, place
from tests.harness import HeadlessServer


@pytest.fixture
def game(repo_root: Path) -> HeadlessServer:
    return HeadlessServer(load_content(repo_root / "src/blacksite/content"), character_state={})


def caller(game: HeadlessServer, user: int = 1):
    client = game.connect({"user_id":user,"handle":f"Wide界{user}","node_name":"test"})
    create(game,client,name=f"Wake{user}")
    return client


def execute(game: HeadlessServer, client, name: str, **args):
    act(game,client,Frame("intent",{"name":name,"args":args}))
    effects = game.commit_commerce()
    game.step()
    return effects


def carried(game: HeadlessServer, client, template: str) -> str:
    player = game.core.characters.players[client.session.player_id]
    return next(i for i in player.inventory if game.core.commerce.items[i].template == template)


def test_design_8_1_8_2_prices_budget_and_no_ammo_split_arbitrage() -> None:
    assert price(100,1,80) == 80
    assert price(100,1,-50) == 130
    assert price(100,1,1000) == 80
    assert price(100,1,-1000) == 130
    assert price(100,1,-50,freelance=True) == 100
    assert price(340,1,resale=True) == 136
    assert price(Fraction(25,50),1,resale=True) == 0
    budget = VendorBudget(0)
    assert budget.remaining == BUYBACK_BUDGET == 2000
    budget.remaining = 0
    budget.refill(3599)
    assert budget.remaining == 0
    budget.refill(3600)
    assert budget.remaining == 2000


def test_vendor_server_owned_member_standing_and_archetype_gates() -> None:
    player = Player("p","o","u","handle","name","ghost","2026-01-01")
    vendor = Vendor("v","counter","member",(),faction="choir")
    assert not permitted(player,vendor)
    player.faction="choir"
    assert not permitted(player,vendor,VendorStock("i",standing=20,archetype="cantor"))
    player.archetype="cantor"; player.standing["choir"]=20
    assert permitted(player,vendor,VendorStock("i",standing=20,archetype="cantor"))


def test_inventory_design_5_4_three_secured_slots_and_stack_limits(game) -> None:
    client = caller(game)
    player = game.core.characters.players[client.session.player_id]
    inv = Inventory(game.core.commerce.items,game.core.loop.content.items)
    assert sum(i.secured for i in inv.items.values()) == 2  # Coverall and Vesper's card.
    unsecured = [i for i in player.inventory if not inv.items[i].secured]
    inv.secure(player,unsecured[0])
    with pytest.raises(ValueError,match="three"):
        inv.secure(player,unsecured[1])
    ammo = carried(game,client,"ammo_9x")
    serial = iter(("split1","split2"))
    inv.items[ammo].secured=False
    inv.split(player,ammo,20,lambda:next(serial))
    assert sorted(i.stack for i in inv.items.values() if i.template=="ammo_9x") == [20,30]
    part = inv.remove(player,"split1",20,lambda:next(serial))
    inv.add(player,part)
    assert inv.items[ammo].stack == 50
    with pytest.raises(ValueError): make_item("bad",game.core.loop.content.items["ammo_9x"],player.id,"now",51)


def test_heavy_requires_hardline_and_equipment_persists(game) -> None:
    client = caller(game)
    player = game.core.characters.players[client.session.player_id]
    commerce = game.core.commerce
    item = make_item("test-origin:item:99999999999",commerce.content.items["wpn_halvard_anvil"],player.id,"now")
    commerce.items[item.id]=item; player.inventory.append(item.id)
    assert not execute(game,client,"inv.equip",item=item.id)
    assert item.id not in player.equipment.values()
    player.archetype="hardline"
    effects=execute(game,client,"inv.equip",item=item.id)
    assert player.equipment["weapon_main"]==item.id
    assert effects[0]["player"]["equipment"]["weapon_main"]==item.id


def test_carry_frame_half_and_double_movement_time(game) -> None:
    client=caller(game)
    player=game.core.characters.players[client.session.player_id]
    template=game.core.commerce.content.items["slv_hull"]
    player.attributes["frame"]=10
    for n in range(2):
        item=make_item(f"test-origin:item:{9999999+n}",template,player.id,"now")
        game.core.commerce.items[item.id]=item; player.inventory.append(item.id)
    game.step()
    actor=game.core.characters.sim.avatars[client.session.user_id].actor
    assert Inventory(game.core.commerce.items,game.core.loop.content.items).weight(player)>player.attributes["frame"]/2
    assert actor.overweight
    from blacksite.server.world.movement import move
    zone=game.core.world.zones[actor.zone]
    actor.cooldowns.clear()
    assert move(actor,zone,"right",100)
    assert actor.cooldowns["move"]==104
    actor.cooldowns.clear()
    assert move(actor,zone,"left",200,sprint=True)
    assert actor.cooldowns["move"]==202


def test_buy_sell_bank_and_no_success_before_commit(game) -> None:
    client=caller(game)
    player=game.core.characters.players[client.session.player_id]
    place(game,client,"vatside-wake-hall",(34,15))
    pistol=carried(game,client,"wpn_kestrel_sidearm")
    act(game,client,Frame("intent",{"name":"vendor.sell","args":{"target":"wake-outfitter","item":pistol}}))
    assert player.chits_hand==200 and pistol in player.inventory
    assert not any("Sold " in str(f.data) for f in game.frames_for(client))
    effects=game.commit_commerce()
    assert player.chits_hand==248 and pistol not in player.inventory
    assert effects[0]["budgets"]["vatside-wake-hall:wake-outfitter"]["remaining"]==1952
    game.step(10)
    execute(game,client,"vendor.buy",target="wake-outfitter",item="wpn_kestrel_sidearm")
    assert player.chits_hand==128
    game.step(10)
    execute(game,client,"vendor.buy",target="wake-outfitter",item="ammo_9x")
    assert player.chits_hand==103
    place(game,client,"core-tram-hub",(12,7))
    execute(game,client,"bank.deposit",target="kestrel-bank",amount=100)
    assert (player.chits_hand,player.chits_bank)==(3,100)
    assert not execute(game,client,"bank.withdraw",target="kestrel-bank",amount=101)
    assert not execute(game,client,"bank.withdraw",target="kestrel-bank",amount=-1)


def test_two_sessions_cannot_pick_up_same_cache_and_expiry_300_seconds(game) -> None:
    a,b=caller(game),caller(game,2)
    place(game,a,"core-plaza",(20,20)); place(game,b,"core-plaza",(21,20))
    iid=carried(game,a,"con_sablier_patch")
    execute(game,a,"inv.drop",item=iid)
    cache_id=next(iter(game.core.commerce.caches))
    assert 299 <= game.core.commerce.caches[cache_id]["expires"]-game.clock.now_utc().timestamp() <= 300
    for client in (a,b):
        client.send(Frame("intent",{"name":"inv.pickup","args":{"target":cache_id,"item":iid}}))
    game.step(); assert len(game.core.commerce.outbox)==1
    game.commit_commerce()
    assert iid in game.core.characters.players[a.session.player_id].inventory
    assert iid not in game.core.characters.players[b.session.player_id].inventory
    execute(game,a,"inv.drop",item=iid)
    game.step(3001); game.commit_commerce()
    assert not game.core.commerce.caches and iid not in game.core.commerce.items


def test_failed_transfer_keeps_goods_and_money(game) -> None:
    client=caller(game)
    player=game.core.characters.players[client.session.player_id]
    place(game,client,"vatside-wake-hall",(34,15))
    before=deepcopy(player.record())
    iid=carried(game,client,"wpn_kestrel_baton")
    act(game,client,Frame("intent",{"name":"vendor.sell","args":{"target":"wake-outfitter","item":iid}}))
    game.commit_commerce(error=True)
    assert player.chits_hand==before["chits_hand"] and player.inventory==before["inventory"]
    assert not game.core.commerce.budgets


def test_independent_simultaneous_transfers_both_settle(game) -> None:
    a,b=caller(game),caller(game,2)
    place(game,a,"core-tram-hub",(12,7)); place(game,b,"core-tram-hub",(13,7))
    for client in (a,b):
        client.send(Frame("intent",{"name":"bank.deposit","args":{"target":"kestrel-bank","amount":100}}))
    game.step()
    assert len(game.core.commerce.waiting)==1
    assert len(game.commit_commerce())==2
    assert [game.core.characters.players[c.session.player_id].chits_bank for c in (a,b)]==[100,100]


def test_invalid_queued_action_cannot_break_other_transfers(game) -> None:
    client=caller(game)
    place(game,client,"core-tram-hub",(12,7))
    for name,args in (("bank.deposit",{"target":"kestrel-bank","amount":100}),
                      ("inv.unequip",{"slot":{}}), ("bank.deposit",{"target":"kestrel-bank","amount":10})):
        client.send(Frame("intent",{"name":name,"args":args}))
    game.step();game.commit_commerce()
    assert game.core.characters.players[client.session.player_id].chits_bank==110


def test_patches_and_rations_share_class_cooldown_and_trauma_kit_channels(game) -> None:
    client=caller(game)
    actor=game.core.characters.sim.avatars[client.session.user_id].actor
    actor.health=10
    iid=carried(game,client,"con_sablier_patch")
    execute(game,client,"inv.use",item=iid)
    assert actor.health==35
    other=carried(game,client,"con_sablier_patch")
    assert not execute(game,client,"inv.use",item=other)
    game.step(100)
    execute(game,client,"inv.use",item=other)
    assert actor.health==60


def test_bound_items_cannot_sell_or_drop_and_remote_counters_refuse(game) -> None:
    client=caller(game)
    iid=carried(game,client,"wpn_kestrel_sidearm")
    game.core.commerce.items[iid].bound=True
    assert not execute(game,client,"inv.drop",item=iid)
    assert not execute(game,client,"vendor.buy",target="wake-outfitter",item="wpn_kestrel_sidearm")
    place(game,client,"vatside-wake-hall",(34,15))
    assert not execute(game,client,"vendor.sell",target="wake-outfitter",item=iid)


def test_transfer_does_not_overwrite_a_simultaneous_wake_grant(game) -> None:
    a=caller(game)
    place(game,a,"vatside-wake-hall",(34,15))
    pistol=carried(game,a,"wpn_kestrel_sidearm")
    act(game,a,Frame("intent",{"name":"vendor.sell","args":{"target":"wake-outfitter","item":pistol}}))
    # Creation can commit while the older trade proposal is awaiting I/O.
    b=caller(game,2)
    granted=set(game.core.characters.players[b.session.player_id].inventory)
    game.commit_commerce()
    assert granted <= game.core.commerce.items.keys()
    assert granted.isdisjoint(game.core.commerce.outbox)


def test_budget_runs_out_but_essential_purchases_stay_available(game) -> None:
    client=caller(game)
    place(game,client,"vatside-wake-hall",(34,15))
    player=game.core.characters.players[client.session.player_id]
    commerce=game.core.commerce
    for n in range(40):
        iid=f"test-origin:item:{9999999999+n}"
        commerce.items[iid]=make_item(iid,commerce.content.items["wpn_halvard_hv7"],player.id,"now")
        player.inventory.append(iid)
        execute(game,client,"vendor.sell",target="wake-outfitter",item=iid)
        game.step(10)
    assert player.chits_hand==200+14*136
    assert next(iter(commerce.budgets.values())).remaining==96
    execute(game,client,"vendor.buy",target="wake-outfitter",item="con_sablier_patch")
    assert player.chits_hand==200+14*136-40


def test_clinic_branches_share_stock_but_have_independent_budgets(game) -> None:
    client=caller(game)
    place(game,client,"vatside-clinics",(10,8))
    execute(game,client,"vendor.sell",target="sablier-main-clinic",item=carried(game,client,"wpn_kestrel_baton"))
    game.step(10)
    place(game,client,"core-precinct",(15,6))
    execute(game,client,"vendor.sell",target="precinct-clinic",item=carried(game,client,"wpn_kestrel_sidearm"))
    assert game.core.commerce.budgets["vatside-clinics:sablier-main-clinic"].remaining==1984
    assert game.core.commerce.budgets["core-precinct:precinct-clinic"].remaining==1952


def test_trauma_kit_uses_two_seconds_and_cancels_on_movement(game) -> None:
    client=caller(game)
    player=game.core.characters.players[client.session.player_id]
    commerce=game.core.commerce
    iid="test-origin:item:99999999999"
    commerce.items[iid]=make_item(iid,commerce.content.items["con_sablier_trauma_kit"],player.id,"now")
    player.inventory.append(iid)
    av=game.core.characters.sim.avatars[client.session.user_id]
    av.actor.health=10
    execute(game,client,"inv.use",item=iid)
    assert av.actor.health==10 and iid in player.inventory
    game.step(20);game.commit_commerce()
    assert av.actor.health==70 and iid not in player.inventory


@pytest.mark.parametrize("quality",[.84,1.16])
def test_design_8_4_quality_bounds(quality) -> None:
    with pytest.raises(ValueError):ItemInstance("i","t","p",quality=quality)


def test_storage_transfer_atomic_and_restart_keeps_inventory_budget_and_bank(game,tmp_path) -> None:
    client=game.connect()
    creation=create(game,client)
    with_storage=Storage(tmp_path/"world.db",game.clock)
    try:
        for effect in creation: with_storage.character_write(effect)
        place(game,client,"vatside-wake-hall",(34,15))
        iid=carried(game,client,"wpn_kestrel_baton")
        act(game,client,Frame("intent",{"name":"vendor.sell","args":{"target":"wake-outfitter","item":iid}}))
        commerce=game.core.commerce
        effect=commerce.outbox.pop(0)
        with_storage.commerce_write(commerce.prepare(effect)); commerce.committed(effect,True)
        saved=with_storage.character_state()
        assert saved["players"][0]["chits_hand"]==216
        assert iid not in {i["id"] for i in saved["items"]}
        assert next(iter(saved["commerce"]["budgets"].values()))["remaining"]==1984
        restored=HeadlessServer(game.core.loop.content,character_state=saved,clock=game.clock)
        assert next(iter(restored.core.commerce.budgets.values())).remaining==1984
        game.step(10)
        with_storage.db.execute("CREATE TRIGGER reject_trade BEFORE UPDATE ON players BEGIN SELECT RAISE(ABORT,'probe'); END")
        iid=carried(game,client,"wpn_kestrel_sidearm")
        act(game,client,Frame("intent",{"name":"vendor.sell","args":{"target":"wake-outfitter","item":iid}}))
        effect=commerce.outbox.pop(0)
        with pytest.raises(sqlite3.IntegrityError): with_storage.commerce_write(commerce.prepare(effect))
        commerce.committed(effect,False)
        assert with_storage.character_state()["players"][0]["chits_hand"]==216
        assert iid in game.core.characters.players[client.session.player_id].inventory
    finally: with_storage.close()
