"""Game 5.3: ordered and defensive automation keeps the real warning."""

import pytest

from blacksite.server.rules import combat as rules
from tests.character_helpers import place
from tests.combat.test_engine import body
from tests.server.test_drone_combat import deploy
from tests.server.test_drone_ownership import operator


def order(game,player,engine,actor,target):
    engine.command(player,actor.behaviour["item"],"target",target.id)
    game.commit_commerce()


def test_game_5_3_ordered_sentry_warns_two_seconds_then_uses_real_cooldown(operator,monkeypatch):
    game,a,b,player,engine = operator
    actor = deploy(game,a,player,engine)
    target = body(game,b)
    monkeypatch.setattr(rules,"to_hit",lambda *args:100)
    before = target.health
    order(game,player,engine,actor,target)
    game.step()
    game.step(19)
    assert target.health == before and player.marked_until is None
    game.step()
    game.commit_commerce()
    assert target.health < before and player.marked_until
    after = target.health
    game.step(9)
    game.commit_commerce()
    assert target.health == after
    game.step()
    game.commit_commerce()
    assert target.health < after


@pytest.mark.parametrize("tid",["drn_halvard_sentry","drn_sable_stinger","drn_halvard_hound"])
def test_catalog_5_each_combat_tool_executes_its_typed_attack(operator,monkeypatch,tid):
    game,a,b,player,engine = operator
    place(game,b,"vatside-clinics",(29,3))
    actor = deploy(game,a,player,engine,tid)
    target = body(game,b)
    monkeypatch.setattr(rules,"to_hit",lambda *args:100)
    before = target.health
    order(game,player,engine,actor,target)
    game.step(30)
    game.commit_commerce()
    assert target.health < before
    if tid == "drn_halvard_hound":
        assert rules.distance(actor.position,target.position) <= 1.5
    if tid == "drn_sable_stinger":
        assert any(effect.get("damage_type") == "chemical" for effect in target.effects)


def test_game_5_3_idle_unit_ignores_target_selection_but_defends_actual_attack(operator,monkeypatch):
    game,a,b,player,engine = operator
    actor = deploy(game,a,player,engine)
    owner,target = body(game,a),body(game,b)
    target.target = owner.id  # Looking at somebody is not attacking them.
    monkeypatch.setattr(rules,"to_hit",lambda *args:100)
    before = target.health
    game.step(30); game.commit_commerce()
    assert target.health == before
    weapon = game.core.loop.content.items["wpn_kestrel_sidearm"].weapon
    game.core.combat.mark(target,owner)
    game.core.combat.shot(target,owner,weapon)
    game.commit_commerce()
    game.step(21); game.commit_commerce()
    assert target.health < before and player.marked_until is None


def test_game_5_3_order_cannot_continue_autonomous_fire_after_logout(operator,monkeypatch):
    game,a,b,player,engine = operator
    actor = deploy(game,a,player,engine)
    target = body(game,b)
    monkeypatch.setattr(rules,"to_hit",lambda *args:100)
    order(game,player,engine,actor,target)
    game.step()
    before = target.health
    game.core.sessions.disconnect(a.session)
    game.step(30); game.commit_commerce()
    assert target.health == before
