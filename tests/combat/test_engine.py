"""Game design 5.3/5.4/7.3: real Core, deterministic ticks, no sockets."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.content.schema import Faction
from blacksite.server.items import make_item
from blacksite.server.inventory import Inventory
from blacksite.server.protocol import Frame
from blacksite.server.rules import character, combat as rules
from blacksite.server.storage.db import Storage
from tests.character_helpers import act, create, place, state
from tests.harness import HeadlessServer


def build_duel(repo_root: Path, *, first_archetype: int = 0):
    content = load_content(repo_root/"src/blacksite/content")
    # Controlled duel scenarios exclude unrelated city traffic. S11 tests
    # exercise the integrated population and patrol response separately.
    content.zones = {key: replace(zone, meta=replace(zone.meta, spawners=tuple(
        sp for sp in zone.meta.spawners if sp.condition == "per_player"))) for key, zone in content.zones.items()}
    game = HeadlessServer(content,character_state={})
    clients = []
    for uid,pos in ((1,(25,3)),(2,(27,3))):
        client = game.connect({"user_id":uid,"handle":f"Wake界{uid}","node_name":"test"})
        create(game,client,archetype=first_archetype if uid == 1 else 0,name=f"Runner{uid}",card="none")
        player = game.core.characters.players[client.session.player_id]
        player.update_progression(1500)
        actor = game.core.characters.sim.avatars[client.session.user_id].actor
        actor.health = actor.health_max = character.health_max(player.attributes["vitals"])
        place(game,client,"vatside-clinics",pos)
        clients.append(client)
    return game,*clients


@pytest.fixture
def duel(repo_root: Path):
    return build_duel(repo_root)


@pytest.fixture
def cantor_duel(repo_root: Path):
    game, a, b = build_duel(repo_root, first_archetype=2)
    player = game.core.characters.players[a.session.player_id]
    # S10 exercises execution; S16 separately tests acquisition and gates.
    # Use an actual starter Ear and a disclosed installed Throat fixture.
    iid = "test-origin:item:99000"
    game.core.commerce.items[iid] = make_item(iid, game.core.loop.content.items["imp_res_throat"],
        player.id, game.clock.now_utc().isoformat())
    player.inventory.append(iid)
    player.implants["spine"] = iid
    return game, a, b


def body(game,client):
    return game.core.characters.sim.avatars[client.session.user_id].actor


def fire(game,client,other):
    act(game,client,Frame("intent",{"name":"fire","args":{"target":body(game,other).id}}))
    return game.commit_commerce()


def count(game,client,template):
    player = game.core.characters.players[client.session.player_id]
    return sum(game.core.commerce.items[i].stack for i in player.inventory if game.core.commerce.items[i].template==template)


def test_design_5_3_warning_ammo_cooldown_commit_and_marked(duel):
    game,a,b = duel
    assert not fire(game,a,b)
    assert count(game,a,"ammo_9x")==50
    game.step(20)
    assert fire(game,a,b)
    assert count(game,a,"ammo_9x")==49
    assert body(game,a).marked
    assert body(game,a).cooldowns["weapon"]>game.clock.now_tick()
    assert not fire(game,a,b)
    assert count(game,a,"ammo_9x")==49
    assert game.core.characters.me(a.session)["in_combat"]


def test_design_5_3_failed_shot_retains_ammo_and_does_no_damage(duel):
    game,a,b = duel
    fire(game,a,b); game.step(20)
    hp = body(game,b).health
    act(game,a,Frame("intent",{"name":"fire","args":{"target":body(game,b).id}}))
    game.commit_commerce(error=True)
    assert count(game,a,"ammo_9x")==50 and body(game,b).health==hp


def test_design_7_3_under_grade_and_safe_bodies_refuse_in_both_directions(duel):
    game,a,b = duel
    game.core.characters.players[b.session.player_id].grade=4
    assert not fire(game,a,b) and not fire(game,b,a)
    game.core.characters.players[b.session.player_id].grade=5
    place(game,a,"core-plaza",(24,3)); place(game,b,"core-plaza",(26,3))
    assert not fire(game,a,b)
    assert not body(game,a).marked
    assert count(game,a,"ammo_9x")==50


def test_design_5_3_safe_recheck_after_acceptance_and_indirect_damage(duel):
    game,a,b = duel
    fire(game,a,b); game.step(20)
    act(game,a,Frame("intent",{"name":"fire","args":{"target":body(game,b).id}}))
    hp = body(game,b).health
    place(game,b,"core-plaza",(25,3))
    game.commit_commerce()
    assert body(game,b).health==hp
    game.core.combat.hurt(body(game,a),body(game,b),1000)
    assert body(game,b).health==hp


def test_design_5_3_target_selection_visibility_and_verbose_log(duel):
    game,a,b = duel
    act(game,a,Frame("key",{"k":"tab","t":0}))
    assert body(game,a).target==body(game,b).id
    target=game.core.combat.target_view(body(game,a))
    assert target["name"]=="Runner2" and target["hp_percent"]==100 and target["range"]==2
    act(game,a,Frame("intent",{"name":"combat_log_verbose","args":{}}))
    fire(game,a,b); game.step(20); fire(game,a,b)
    assert any("Roll" in line["text"] for line in a.session.log_ring)
    place(game,b,"core-plaza",(25,3))
    assert game.core.combat.target_view(body(game,a)) is None


def test_design_5_4_down_pickup_dead_debt_cache_and_decant(duel):
    game,a,b = duel
    engine=game.core.combat
    victim=game.core.characters.players[b.session.player_id]
    victim.chits_hand=1000;victim.chits_bank=500;victim.xp=1700
    engine.hurt(body(game,a),body(game,b),1000)
    assert body(game,b).stance=="down"
    game.step(49)
    assert body(game,b).stance=="down" and not game.core.commerce.outbox
    game.step(); game.commit_commerce()
    assert body(game,b).stance=="dead" and body(game,b).zone is None
    assert victim.chits_hand==900 and victim.chits_bank==500 and victim.xp==1696
    cache=next(iter(game.core.commerce.caches.values()))
    assert cache["victim"]==victim.id and cache["killer"]==body(game,a).id
    assert all(not game.core.commerce.items[i].secured for i in cache["items"])
    assert all(game.core.commerce.items[i].template!="arm_wake_coverall" for i in cache["items"])
    game.step(199); assert body(game,b).stance=="dead"
    game.step();game.commit_commerce();game.step()
    assert body(game,b).stance=="normal" and victim.zone=="vatside-wake-hall"
    assert body(game,b).health==body(game,b).health_max and body(game,b).shock==0
    loan=[game.core.commerce.items[i] for i in victim.inventory if game.core.commerce.items[i].bound]
    assert any(i.template=="wpn_kestrel_sidearm" for i in loan)
    assert count(game,b,"ammo_9x")==50
    assert victim.legal_at  # Death never removes early discharge.


def test_design_5_4_pickup_neutral_ally_before_timer(duel):
    game,a,b=duel
    engine=game.core.combat
    engine.hurt(body(game,a),body(game,b),1000)
    c=game.connect({"user_id":3,"handle":"Ally界","node_name":"test"})
    create(game,c,name="Ally",card="none")
    place(game,c,"vatside-clinics",(27,4))
    act(game,c,Frame("key",{"k":"e","t":0}))
    assert body(game,b).stance=="normal" and body(game,b).health==35
    assert not game.core.characters.players[b.session.player_id].progress.get("combat")


def test_design_5_4_cache_victim_killer_and_third_party_after_sixty_seconds(duel):
    game,a,b=duel
    game.core.combat.hurt(body(game,a),body(game,b),1000)
    game.step(50);game.commit_commerce()
    cid,cache=next(iter(game.core.commerce.caches.items()))
    c=game.connect({"user_id":3,"handle":"Third","node_name":"test"});create(game,c,name="Third",card="none")
    place(game,c,"vatside-clinics",(27,4))
    item=next(i for i in cache["items"] if game.core.commerce.items[i].template=="con_kestrel_ration")
    act(game,c,Frame("intent",{"name":"inv.pickup","args":{"target":cid,"item":item}}))
    assert not game.commit_commerce()
    game.step(600);game.commit_commerce()
    act(game,c,Frame("intent",{"name":"inv.pickup","args":{"target":cid,"item":item}}))
    assert game.commit_commerce()
    assert count(game,c,"con_kestrel_ration")==3


def test_design_5_4_failed_death_cannot_move_inventory_or_charge(duel):
    game,a,b=duel
    player=game.core.characters.players[b.session.player_id]
    before=list(player.inventory)
    game.core.combat.hurt(body(game,a),body(game,b),1000)
    game.step(50);game.commit_commerce(error=True)
    assert player.inventory==before and player.chits_hand==200 and not game.core.commerce.caches
    game.step();game.commit_commerce()
    assert body(game,b).stance=="dead"


def test_design_5_4_atomic_storage_and_restart_decant(duel,tmp_path):
    game,a,b=duel
    with_storage=Storage(tmp_path/"world.db",game.clock)
    try:
        manager=game.core.characters
        for player in manager.players.values():
            with_storage.character_write({"action":"create","user":player.bbs_user_id,"player":player.record(),
                "identity":manager.identities[player.bbs_user_id],"serial":manager.serial,
                "items":[item.record() for item in manager.items.values() if item.owner==player.id]})
        for effect in game.commit_characters(): with_storage.character_write(effect)
        game.core.combat.hurt(body(game,a),body(game,b),1000)
        game.step(50)
        for effect in game.commit_characters(): with_storage.character_write(effect)
        commerce=game.core.commerce
        proposal=commerce.outbox.pop(0)
        with_storage.commerce_write(commerce.prepare(proposal));commerce.committed(proposal,True)
        saved=with_storage.character_state()
        assert saved["commerce"]["caches"] and next(p for p in saved["players"] if p["id"]==b.session.player_id)["progress"]["combat"]["stage"]=="dead"
        reboot=HeadlessServer(game.core.world.content,character_state=saved,clock=game.clock)
        returning=reboot.connect({"user_id":2,"handle":"Wake界2","node_name":"test"})
        reboot.step()
        assert body(reboot,returning).stance=="dead"
        reboot.step(200);reboot.commit_commerce();reboot.step()
        assert body(reboot,returning).health==body(reboot,returning).health_max
    finally: with_storage.close()


def test_design_5_3_hymn_cast_cooldown_jam_hush_and_safe_delivery(cantor_duel):
    game,a,b=cantor_duel
    player=game.core.characters.players[a.session.player_id]
    actor=body(game,a);actor.shock=50
    actor.cooldowns["last_hit"]=game.clock.now_tick()
    act(game,a,Frame("intent",{"name":"ability","args":{"id":"hymn_steady"}}))
    assert actor.shock==50
    game.step(4)
    assert actor.shock<=30
    assert actor.cooldowns["ability:hymn_steady"]>=game.clock.now_tick()+119
    actor.target=body(game,b).id
    act(game,a,Frame("intent",{"name":"ability","args":{"id":"dis_jam"}}))
    game.step(20)
    act(game,a,Frame("intent",{"name":"ability","args":{"id":"dis_jam"}}))
    game.step(5)
    assert any(e.get("weapon_multiplier")==1.5 for e in body(game,b).effects)
    hp=body(game,b).health
    place(game,b,"core-plaza",(25,3))
    game.core.combat.hurt(actor,body(game,b),999)
    assert body(game,b).health==hp


def test_design_4_training_drone_private_nonlethal_and_completion(duel):
    game,a,b=duel
    place(game,a,"vatside-wake-hall",(21,14))
    game.step()
    drone=next(actor for actor in game.core.world.actors.values() if actor.owner==body(game,a).id)
    assert not game.core.combat.legal(body(game,b),drone)
    assert not game.core.combat.visible(body(game,b),drone)
    game.step(400)
    assert body(game,a).health>=1 and body(game,a).stance!="dead"
    game.core.combat.hurt(body(game,a),drone,100)
    assert drone.id not in game.core.world.actors
    assert game.core.characters.players[a.session.player_id].progress["wake_combat"]=="done"


def test_design_2_combat_logout_settles_after_sixty_seconds_without_banked_loss(duel):
    game,a,b=duel
    player=game.core.characters.players[a.session.player_id]
    player.chits_hand=1000;player.chits_bank=900
    game.core.combat.exchange(body(game,a),body(game,b))
    game.core.sessions.disconnect(a.session)
    game.step(600)
    assert player.zone=="vatside-wake-hall" and player.chits_hand==900 and player.chits_bank==900
    assert player.legal_at


def test_design_5_3_last_energy_charge_preserves_rechargeable_cell(duel):
    game,a,b=duel
    manager=game.core.characters
    player=manager.players[a.session.player_id]
    inventory=Inventory(manager.items,manager.content.items)
    serial=game.core.combat.next_serial()
    for offset,(tid,stack) in enumerate((("wpn_ostrom_pinlight",1),("ammo_cell",1),("con_cell_charger",1)),1):
        if tid not in manager.content.items:
            # The catalog name is intentionally located by its declared effect.
            tid=next(t.id for t in manager.content.items.values() if t.consumable and t.consumable.effects.get("recharge_cell"))
        item=make_item(f"test-origin:item:{serial+offset}",manager.content.items[tid],player.id,"now",stack)
        inventory.add(player,item)
        if tid=="wpn_ostrom_pinlight": inventory.equip(player,item.id,"weapon_main")
        elif tid=="ammo_cell": cell=item
        else: charger=item
    fire(game,a,b);game.step(20);fire(game,a,b)
    assert cell.id in manager.items and manager.items[cell.id].stack==0
    act(game,a,Frame("intent",{"name":"inv.use","args":{"item":charger.id}}));game.commit_commerce()
    assert manager.items[cell.id].stack==30


def test_design_5_3_healing_and_damage_in_one_io_batch_preserve_both(duel):
    game,a,b=duel
    actor=body(game,a);actor.health=50
    player=game.core.characters.players[a.session.player_id]
    patch=next(i for i in player.inventory if game.core.commerce.items[i].template=="con_sablier_patch")
    act(game,a,Frame("intent",{"name":"inv.use","args":{"item":patch}}))
    assert game.core.commerce.pending
    game.core.combat.hurt(body(game,b),actor,10)
    player.progress["combat_cooldowns"]={"ability:hymn_steady":game.clock.now_utc().timestamp()+12}
    actor.cooldowns["ability:hymn_steady"]=game.clock.now_tick()+120
    game.commit_commerce()
    assert actor.health==65  # 50 + patch 25 - hit 10, neither overwritten.
    assert "ability:hymn_steady" in player.progress["combat_cooldowns"]


def test_design_5_3_melee_stamina_shock_knockdown_and_stealth(duel):
    game,a,b=duel
    place(game,b,"vatside-clinics",(26,3))
    player=game.core.characters.players[a.session.player_id]
    player.progress["weapon_slot"]="melee"
    body(game,a).stamina=50
    fire(game,a,b);game.step(20)
    before=body(game,a).stamina
    fire(game,a,b)
    assert body(game,a).stamina==before-6
    assert body(game,a).cooldowns["weapon"]==game.clock.now_tick()+10
    body(game,b).shock=99
    game.core.combat.hurt(body(game,a),body(game,b),4)
    assert body(game,b).shock==60 and body(game,b).cooldowns["knockdown"]==game.clock.now_tick()+20
    player.archetype="ghost"
    act(game,a,Frame("intent",{"name":"stance","args":{"stealth":True}}))
    assert body(game,a).stance=="stealth"
    game.step(20);fire(game,a,b)
    assert body(game,a).stance=="normal"


def test_design_5_3_chemical_dot_rechecks_safe_body(duel):
    game,a,b=duel
    engine=game.core.combat
    target=body(game,b)
    target.effects.append({"kind":"dot","source":body(game,a).id,"damage_type":"chemical","damage":4,
        "until_tick":game.clock.now_tick()+30,"next_tick":game.clock.now_tick()+10})
    before=target.health
    game.step(10)
    assert target.health<before
    place(game,b,"core-plaza",(25,3))
    before=target.health
    game.step(20)
    assert target.health==before


def test_design_5_3_reconnect_restores_cooldown_before_first_input(cantor_duel):
    game,a,b=cantor_duel
    player=game.core.characters.players[a.session.player_id]
    actor=body(game,a);actor.shock=50;actor.cooldowns["last_hit"]=game.clock.now_tick()
    act(game,a,Frame("intent",{"name":"ability","args":{"id":"hymn_steady"}}));game.step(5)
    until=actor.cooldowns["ability:hymn_steady"]
    game.core.sessions.disconnect(a.session)
    returning=game.connect({"user_id":1,"handle":"Wake界1","node_name":"test"})
    assert body(game,returning).cooldowns["ability:hymn_steady"]==until
    act(game,returning,Frame("intent",{"name":"ability","args":{"id":"hymn_steady"}}))
    assert player.id not in game.core.combat.casts


def test_design_5_3_grade5_hv7_documented_model(repo_root: Path):
    tree=load_content(repo_root/"src/blacksite/content")
    weapon=tree.items["wpn_halvard_hv7"].weapon
    armour=tree.items["arm_sable_leathers"].armour.armour.kinetic
    hp=character.health_max(character.attributes("ghost",grade=5)["vitals"])
    chance=rules.to_hit(weapon.accuracy,20,40/3)/100
    hit=rules.damage(weapon.damage,20,armour)
    assert hp==98 and hit==12 and chance==pytest.approx(.5166666667)
    expected_shots=__import__('math').ceil(hp/hit)/chance
    assert 12<=(expected_shots-1)*weapon.cooldown<=20


@pytest.mark.parametrize("relation,marked",[("H",False),("N",True),("A",True)])
def test_design_7_3_faction_matrix_codes_control_marked(duel,relation,marked):
    game,a,b=duel
    tree=game.core.world.content
    tree.factions["halvard"]=Faction("halvard","Halvard","HV","player_neutral",{"unmoored":relation})
    body(game,a).faction="halvard";body(game,b).faction="unmoored"
    game.core.characters.players[a.session.player_id].faction="halvard"
    game.core.characters.players[b.session.player_id].faction="unmoored"
    fire(game,a,b);game.step(20);fire(game,a,b)
    assert body(game,a).marked is marked


def test_design_5_4_full_secured_slots_cannot_block_bound_recovery(duel):
    game,a,b=duel
    player=game.core.characters.players[b.session.player_id]
    inv=Inventory(game.core.commerce.items,game.core.world.content.items)
    for iid in player.inventory:
        if inv.items[iid].template=="con_kestrel_ration": inv.secure(player,iid)
    assert sum(inv.items[i].secured for i in player.inventory)==3
    game.core.combat.hurt(body(game,a),body(game,b),1000)
    game.step(50);game.commit_commerce();game.step(200);game.commit_commerce()
    assert body(game,b).stance=="normal"
    loans=[game.core.commerce.items[i] for i in player.inventory if game.core.commerce.items[i].bound]
    assert any(i.template=="arm_wake_coverall" for i in loans)
    assert all(not i.secured for i in loans)
    assert sum(game.core.commerce.items[i].secured for i in player.inventory)==3


def test_design_5_4_secured_coverall_and_empty_sidearm_still_get_ammo(duel):
    game,a,b=duel
    c=game.connect({"user_id":3,"handle":"Ghost","node_name":"test"});create(game,c,archetype=1,name="Ghost",card="none")
    player=game.core.characters.players[c.session.player_id];player.grade=5
    inv=Inventory(game.core.commerce.items,game.core.world.content.items)
    pistol=next(i for i in player.inventory if inv.items[i].template=="wpn_kestrel_sidearm")
    coverall=next(i for i in player.inventory if inv.items[i].template=="arm_wake_coverall")
    assert inv.items[coverall].secured
    inv.secure(player,pistol)
    place(game,c,"vatside-clinics",(29,3))
    game.core.combat.hurt(body(game,a),body(game,c),1000)
    game.step(50);game.commit_commerce()
    assert coverall in player.inventory and pistol in player.inventory
    assert count(game,c,"ammo_9x")==0
    game.step(200);game.commit_commerce()
    assert body(game,c).stance=="normal" and count(game,c,"ammo_9x")==50


def test_design_5_4_public_vat_recovery_is_bounded_and_requires_proximity(duel):
    game,a,b=duel
    player=game.core.characters.players[a.session.player_id]
    inv=Inventory(game.core.commerce.items,game.core.world.content.items)
    for iid in list(player.inventory):
        if inv.items[iid].template.startswith(("wpn_","ammo_","arm_")):
            player.inventory.remove(iid);inv.items.pop(iid)
    player.equipment.clear()
    act(game,a,Frame("intent",{"name":"recovery","args":{"target":"decant-vat-1"}}))
    assert not game.commit_commerce()
    place(game,a,"vatside-wake-hall",(3,3))
    act(game,a,Frame("key",{"k":"e","t":0}));game.commit_commerce()
    assert count(game,a,"wpn_kestrel_sidearm")==1 and count(game,a,"ammo_9x")==50
    before=list(player.inventory)
    for _ in range(3):
        act(game,a,Frame("key",{"k":"e","t":0}));assert not game.commit_commerce()
    assert player.inventory==before


def test_design_5_3_secondary_targets_obey_pocket_safety(duel):
    from blacksite.content.schema import Region
    game,a,b=duel
    c=game.connect({"user_id":3,"handle":"Safe","node_name":"test"});create(game,c,name="Safe",card="none")
    game.core.characters.players[c.session.player_id].grade=5
    place(game,c,"vatside-clinics",(28,3))
    zone=game.core.world.zones["vatside-clinics"]
    original=zone.template
    zone.template=replace(original,meta=replace(original.meta,pockets=(*original.meta.pockets,Region(28,3,1,1))))
    weapon=game.core.world.content.items["wpn_ostrom_arc_projector"].weapon
    assert game.core.combat.weapon_targets(body(game,a),body(game,b),weapon)==[body(game,b)]
    zone.template=original
    assert game.core.combat.weapon_targets(body(game,a),body(game,b),weapon)==[body(game,b),body(game,c)]


def test_design_5_3_two_sessions_duel_deterministically_then_decant(repo_root: Path):
    results=[]
    for _ in range(2):
        game,a,b=build_duel(repo_root)
        game.core.world.zones["vatside-clinics"].rng.seed(11)
        for client in (a,b): game.core.characters.players[client.session.player_id].skills["kinetic"]=20
        loser=None
        for _ in range(800):
            for client,other in ((a,b),(b,a)):
                client.send(Frame("intent",{"name":"fire","args":{"target":body(game,other).id}}))
            game.step();game.commit_commerce()
            loser=next((c for c in (a,b) if body(game,c).stance=="dead"),None)
            if loser: break
        assert loser is not None
        victim=game.core.characters.players[loser.session.player_id]
        results.append((victim.id,body(game,a).health,body(game,b).health,victim.chits_hand,
            sorted(game.core.commerce.items[i].template for c in game.core.commerce.caches.values() for i in c["items"])))
        game.step(200);game.commit_commerce()
        assert victim.zone=="vatside-wake-hall" and body(game,loser).health==body(game,loser).health_max
    assert results[0]==results[1]


def test_design_5_4_reconnecting_dead_body_cannot_be_charged_again(duel):
    game,a,b=duel
    game.core.combat.hurt(body(game,a),body(game,b),1000)
    game.step(50);game.commit_commerce()
    player=game.core.characters.players[b.session.player_id]
    before=deepcopy(player.progress["combat"]),player.chits_hand,player.clone_debt
    game.core.sessions.disconnect(b.session)
    returning=game.connect({"user_id":2,"handle":"Wake界2","node_name":"test"})
    assert body(game,returning).stance=="dead"
    game.core.combat.hurt(body(game,a),body(game,returning),1000)
    game.step()
    assert (player.progress["combat"],player.chits_hand,player.clone_debt)==before


def test_design_5_3_quick_item_binding_replaces_spell_and_hud_matches_weapon(duel):
    game,a,b=duel
    player=game.core.characters.players[a.session.player_id]
    player.progress["quick_abilities"]={"1":"hymn_steady"}
    inv=Inventory(game.core.commerce.items,game.core.world.content.items)
    patch=next(i for i in player.inventory if inv.items[i].template=="con_sablier_patch")
    inv.equip(player,patch,"quick1")
    assert "1" not in player.progress["quick_abilities"]
    player.progress["weapon_slot"]="melee"
    inv.unequip(player,"melee")
    assert game.core.characters.me(a.session)["weapon"]==game.core.world.content.items[game.core.combat.weapon(player)[0].template].name
