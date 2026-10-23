"""Game 8.5/8.6: installed effects reach actual combat and perception."""

import pytest

from blacksite.content.schema import WeaponBlock, DamageOverTime
from blacksite.server.sessions import QUEUE_LIMIT
from blacksite.server.items import make_item
from blacksite.server.protocol import Frame
from blacksite.server.rules import combat as rules
from tests.character_helpers import place
from tests.combat.test_engine import body, build_duel, count as item_count


def implant(game, client, tid, slot=""):
    player = game.core.characters.players[client.session.player_id]
    template = game.core.loop.content.items[tid]
    iid = f"test-origin:item:{game.core.combat.next_serial()+1}"
    game.core.commerce.items[iid] = make_item(iid, template, player.id, game.clock.now_utc().isoformat())
    player.inventory.append(iid)
    player.implants[slot or template.implant.slot] = iid
    game.core.progression.sync_actor(player)


@pytest.mark.parametrize("pending",[False,True])
def test_game_3_5_full_transfer_queue_never_aborts_combat_or_its_dot(repo_root,monkeypatch,pending):
    game,a,b = build_duel(repo_root)
    combat,commerce = game.core.combat,game.core.commerce
    source,target = body(game,a),body(game,b)
    before = target.health
    # A committing transfer can still have a full waiting queue while its
    # combat callback starts the first new skill write.
    commerce.pending = pending
    commerce.waiting.extend([lambda:None]*QUEUE_LIMIT)
    monkeypatch.setattr(rules,"to_hit",lambda *args:100)
    weapon = WeaponBlock(damage=12,cooldown=1,accuracy=75,damage_type="kinetic",range=6,
                         dot=DamageOverTime(1,3))
    combat.shot(source,target,weapon)
    if pending:
        assert target.health == before and not target.effects
    else:
        assert target.health < before
        assert any(effect.get("kind") == "dot" for effect in target.effects)
    assert len(commerce.waiting) == QUEUE_LIMIT


def test_game_8_5_armour_accuracy_and_rangefinder_affect_actual_shot(repo_root, monkeypatch):
    game, a, b = build_duel(repo_root)
    combat = game.core.combat
    baseline = combat.armour(body(game,b), "kinetic")
    implant(game, b, "imp_sablier_sub_dermal")
    assert combat.armour(body(game,b), "kinetic") == baseline+3
    implant(game, a, "imp_halvard_stabiliser", "arms1")
    implant(game, a, "imp_ostrom_rangefinder")
    place(game,b,"vatside-clinics",(29,3))
    captured = []
    original = rules.to_hit
    def capture(*args):
        captured.append(args)
        return original(*args)
    monkeypatch.setattr(rules,"to_hit",capture)
    weapon = WeaponBlock(damage=10,cooldown=1,accuracy=75,damage_type="kinetic",range=6)
    combat.shot(body(game,a),body(game,b),weapon)
    assert captured[0][0] == 83 and captured[0][-1] == 2.5


def test_game_8_5_reflex_arm_improves_sustained_fire_without_idle_burst(repo_root):
    counts = []
    for installed in (False, True):
        game, a, b = build_duel(repo_root)
        if installed: implant(game,a,"imp_halvard_reflex_arm","arms1")
        actor = body(game,a)
        actor.target = body(game,b).id
        fire = Frame("intent",{"name":"fire","args":{}})
        a.send(fire);game.step();game.step(20)
        count = 0
        for _ in range(70):
            rounds = item_count(game,a,"ammo_9x")
            a.send(fire);game.step()
            game.commit_commerce()
            count += rounds-item_count(game,a,"ammo_9x")
        counts.append(count)
        game.step(100)
        a.send(fire);game.step()
        assert not game.commit_commerce()  # A new exchange warns again.
        game.step(20)
        rounds = item_count(game,a,"ammo_9x")
        a.send(fire);game.step()
        game.commit_commerce()
        assert item_count(game,a,"ammo_9x") == rounds-1
        a.send(fire);game.step()
        assert not game.commit_commerce()
    assert counts[1] > counts[0]


def test_game_8_5_target_lock_retains_health_but_never_authorizes_obscured_fire(repo_root, monkeypatch):
    game, a, b = build_duel(repo_root)
    actor = body(game,a)
    actor.target = body(game,b).id
    implant(game,a,"imp_ostrom_target_lock")
    monkeypatch.setattr(game.core.combat,"visible",lambda observer,target:False)
    target = game.core.combat.target_view(actor)
    assert target["hp"] == body(game,b).health and "Obscured" in target["warning"]
    a.send(Frame("intent",{"name":"fire","args":{}}));game.step()
    assert not game.commit_commerce()


def test_game_8_5_silence_immunity_is_only_for_dissonance_knockdown(repo_root):
    game, a, b = build_duel(repo_root,first_archetype=2)
    implant(game,a,"imp_res_silence")
    target, source = body(game,a), body(game,b)
    target.shock = 90
    game.core.combat.hurt(source,target,1,20,damage_type="dissonance")
    assert target.shock == 99 and "knockdown" not in target.cooldowns
    game.core.combat.hurt(source,target,1,20,damage_type="kinetic")
    assert target.shock == 60 and target.cooldowns["knockdown"] > game.clock.now_tick()


def test_game_8_5_chord_extends_hymn_to_eight_tiles_and_unlocks_both_tiers(repo_root):
    game, a, b = build_duel(repo_root,first_archetype=2)
    implant(game,a,"imp_res_chord")
    combat, content = game.core.combat, game.core.loop.content
    player = game.core.characters.players[a.session.player_id]
    assert all(combat.unlocked(player,h) for h in content.hymns.values() if h.tier <= 2)
    place(game,b,"vatside-clinics",(32,3))
    body(game,b).shock = 50
    crews = game.core.crews
    crews.perform(a.session, 'invite', b.session.player_id)
    crews.perform(b.session, 'accept', next(iter(crews.registry.invites)))
    combat.complete_cast(body(game,a),{"ability":"hymn_steady","target":body(game,a).id})
    assert body(game,b).shock == 30
