"""Game 5.3/7.3: controller authority is checked at actual impact."""

import pytest

from blacksite.content.schema import WeaponBlock
from blacksite.server.rules import combat as rules
from tests.character_helpers import place
from tests.combat.test_engine import body
from tests.server.test_drone_ownership import operator
from tests.server.test_substances import give


def deploy(game,client,player,engine,tid="drn_halvard_sentry"):
    iid = give(game,client,tid)
    engine.command(player,iid,"deploy"); game.commit_commerce()
    return engine.actors[iid]


@pytest.mark.parametrize("reason",["grade","pocket","range","offline","detox"])
def test_game_7_3_pet_cannot_bypass_controller_protection_or_authority(operator,reason):
    game,a,b,player,engine = operator
    actor = deploy(game,a,player,engine,"drn_sable_stinger" if reason == "pocket" else "drn_halvard_sentry")
    control_range = game.core.loop.content.items[game.core.commerce.items[actor.behaviour["item"]].template].drone.control_range
    target = body(game,b)
    assert game.core.combat.legal(actor,target)
    if reason == "grade":
        player.grade = 4
    elif reason == "offline":
        game.core.sessions.disconnect(a.session)
    elif reason == "detox":
        player.progress["detox"] = {"until":game.clock.now_utc().timestamp()+600,"zone":player.zone,"tile":list(player.tile)}
    else:
        zone = game.core.world.zones[actor.zone]
        occupied = {other.position for other in zone.actors.values() if other.id != player.id}
        tile = next((x,y) for y in range(zone.template.height) for x in range(zone.template.width)
            if zone.passable((x,y)) and (x,y) not in occupied and (
                zone.safety_at((x,y)) == "pocket" and rules.distance((x,y),actor.position) <= control_range
                if reason == "pocket" else rules.distance((x,y),actor.position) > control_range and zone.allows_hostile((x,y))))
        place(game,a,actor.zone,tile)
    before = target.health
    assert not game.core.combat.legal(actor,target)
    game.core.combat.hurt(actor,target,99)
    game.commit_commerce()
    assert target.health == before


def test_game_7_3_owned_gear_retains_owner_grade_and_marks_neutral_attacker(operator):
    game,a,b,player,engine = operator
    actor = deploy(game,a,player,engine)
    attacker = body(game,b)
    player.grade = 4
    assert not game.core.combat.legal(attacker,actor)
    player.grade = 5
    attacker.target = actor.id
    assert game.core.combat.legal(attacker,actor)
    assert "marks" in game.core.combat.target_view(attacker)["warning"]
    game.core.combat.mark(attacker,actor)
    assert game.core.characters.players[b.session.player_id].marked_until


def test_game_5_3_jacked_online_controller_can_be_guarded_and_pet_hits_learn_drones(operator,monkeypatch):
    game,a,b,player,engine = operator
    actor = deploy(game,a,player,engine)
    body(game,a).stance = "jacked"
    target = body(game,b)
    assert game.core.combat.legal(actor,target)
    monkeypatch.setattr(rules,"to_hit",lambda *args:100)
    template = game.core.loop.content.items[game.core.commerce.items[actor.behaviour["item"]].template]
    before = player.skills["drones"],player.skills["kinetic"]
    game.core.combat.shot(actor,target,template.drone.attack,skill=player.skills["drones"])
    game.commit_commerce()
    assert player.skills["drones"] == before[0]+.1 and player.skills["kinetic"] == before[1]
    assert player.progress["last_exchange"] == game.clock.now_utc().timestamp()
    assert body(game,a).cooldowns["combat"] > game.clock.now_tick()


def test_game_3_5_harmless_support_drone_is_not_an_armed_training_opponent(operator):
    game,a,b,player,engine = operator
    actor = deploy(game,a,player,engine,"drn_kestrel_mule")
    assert not game.core.progression.combat_eligible(body(game,b),actor)


def test_game_5_3_npc_retaliates_against_actual_pet_and_controller_not_foreign_mission(operator,monkeypatch):
    game,a,b,player,engine = operator
    actor = deploy(game,a,player,engine)
    template = next(n for n in game.core.loop.content.npcs.values() if n.weapon and not n.training)
    zone = game.core.world.zones[actor.zone]
    target = game.core.npcs.spawn_mission(body(game,a),"pet-retaliation",template.id,
        game.core.world.free_tile(actor.zone,(actor.x,actor.y+1)))
    monkeypatch.setattr(rules,"to_hit",lambda *args:100)
    arm = game.core.loop.content.items[game.core.commerce.items[actor.behaviour["item"]].template].drone.attack
    game.core.combat.shot(actor,target,arm)
    game.commit_commerce()
    assert target.target == actor.id
    assert game.core.npcs.hostile(target,actor) and game.core.npcs.hostile(target,body(game,a))
    target.owner = body(game,b).id
    assert not game.core.combat.legal(actor,target)
    assert not game.core.combat.legal(target,actor)


def test_game_3_5_pet_down_stores_controller_and_pvp_death_rewards_owner_atomically(operator):
    game,a,b,player,engine = operator
    actor = deploy(game,a,player,engine)
    victim = game.core.characters.players[b.session.player_id]
    before = player.xp
    game.core.combat.hurt(actor,body(game,b),999)
    assert victim.progress["combat"]["killer"] == player.id
    game.core.combat.die(victim,body(game,b))
    assert player.xp == before
    receipts = game.commit_commerce()
    assert player.xp == before+20
    assert receipts[0]["identities"][player.bbs_user_id]["combat_xp_until"][victim.bbs_user_id]


@pytest.mark.parametrize("change",["range","visibility"])
def test_game_5_3_queued_shot_rechecks_impact_range_and_visibility(operator,monkeypatch,change):
    game,a,b,player,engine = operator
    combat = game.core.combat
    monkeypatch.setattr(rules,"to_hit",lambda *args:100)
    weapon = WeaponBlock(damage=10,cooldown=1,accuracy=75,damage_type="kinetic",range=2)
    combat.commerce.settle(player,{},combat.commerce.items,combat.commerce.caches,combat.commerce.serial,lambda success:None)
    combat.shot(body(game,a),body(game,b),weapon)
    health = body(game,b).health
    if change == "range":
        place(game,b,"vatside-clinics",(29,3))
    else:
        monkeypatch.setattr(combat,"visible",lambda source,target:False)
    game.commit_commerce()
    assert body(game,b).health == health


def test_game_5_3_queued_pet_hit_rechecks_controller_online_at_delivery(operator,monkeypatch):
    game,a,b,player,engine = operator
    actor = deploy(game,a,player,engine)
    combat = game.core.combat
    monkeypatch.setattr(rules,"to_hit",lambda *args:100)
    weapon = game.core.loop.content.items[game.core.commerce.items[actor.behaviour["item"]].template].drone.attack
    combat.commerce.settle(player,{},combat.commerce.items,combat.commerce.caches,combat.commerce.serial,lambda success:None)
    combat.shot(actor,body(game,b),weapon)
    before = body(game,b).health
    game.core.sessions.disconnect(a.session)
    game.commit_commerce()
    assert body(game,b).health == before


def test_game_5_3_chemical_pet_dot_stops_when_controller_disconnects(operator,monkeypatch):
    game,a,b,player,engine = operator
    actor = deploy(game,a,player,engine,"drn_sable_stinger")
    combat = game.core.combat
    monkeypatch.setattr(rules,"to_hit",lambda *args:100)
    weapon = game.core.loop.content.items[game.core.commerce.items[actor.behaviour["item"]].template].drone.attack
    combat.shot(actor,body(game,b),weapon)
    game.commit_commerce()
    assert any(effect.get("kind") == "dot" for effect in body(game,b).effects)
    before = body(game,b).health
    game.core.sessions.disconnect(a.session)
    game.step(10)
    game.commit_commerce()
    assert body(game,b).health == before
