"""Game 3.5: completed real combat actions supply meaningful-use facts."""

import pytest

from blacksite.content.schema import WeaponBlock
from blacksite.server.rules import combat as rules
from tests.combat.test_engine import body, build_duel


def shot(game, a, b, monkeypatch):
    monkeypatch.setattr(rules, "to_hit", lambda *args: 100)
    weapon = WeaponBlock(damage=10, cooldown=1, accuracy=75, damage_type="kinetic", range=6)
    game.core.combat.shot(body(game,a), body(game,b), weapon)
    game.commit_commerce()


def test_game_3_5_hit_and_actual_armour_mitigation_learn(repo_root, monkeypatch):
    game, a, b = build_duel(repo_root)
    attacker = game.core.characters.players[a.session.player_id]
    defender = game.core.characters.players[b.session.player_id]
    before = attacker.skills["kinetic"], defender.skills["armour"]
    assert game.core.combat.armour(body(game,b), "kinetic") > 0
    shot(game,a,b,monkeypatch)
    assert attacker.skills["kinetic"] == before[0]+.2
    assert defender.skills["armour"] == before[1]+.1
    defender.equipment.clear()
    shot(game,a,b,monkeypatch)
    assert defender.skills["armour"] == before[1]+.1  # Nothing absorbed.
    assert attacker.skills["kinetic"] == before[0]+.2  # Unarmed opponent.


@pytest.mark.parametrize("exclusion", ["crew", "training", "denied"])
def test_game_3_5_harmless_or_ineligible_combat_does_not_learn(repo_root, monkeypatch, exclusion):
    game, a, b = build_duel(repo_root)
    attacker = game.core.characters.players[a.session.player_id]
    defender = game.core.characters.players[b.session.player_id]
    if exclusion == "crew":
        game.core.progression.crew_of = lambda pid: "same-crew"
    elif exclusion == "training":
        body(game,b).behaviour["training"] = True
        body(game,b).owner = attacker.id
    else:
        game.core.progression.permit_combat = lambda source, target: False
    before = dict(attacker.skills), dict(defender.skills)
    shot(game,a,b,monkeypatch)
    assert (attacker.skills, defender.skills) == before


def test_game_3_5_miss_and_failed_receipt_do_not_learn(repo_root, monkeypatch):
    game, a, b = build_duel(repo_root)
    attacker = game.core.characters.players[a.session.player_id]
    before = attacker.skills["kinetic"]
    monkeypatch.setattr(rules, "to_hit", lambda *args: 0)
    weapon = WeaponBlock(damage=10, cooldown=1, accuracy=75, damage_type="kinetic", range=6)
    game.core.combat.shot(body(game,a),body(game,b),weapon)
    assert not game.core.commerce.outbox
    monkeypatch.setattr(rules, "to_hit", lambda *args: 100)
    game.core.combat.shot(body(game,a),body(game,b),weapon)
    game.commit_commerce(error=True)
    assert attacker.skills["kinetic"] == before


def test_game_3_5_steady_requires_actual_deficit_and_mend_counts_one_cast(repo_root):
    game, a, b = build_duel(repo_root, first_archetype=2)
    combat, actor = game.core.combat, body(game,a)
    player = game.core.characters.players[a.session.player_id]
    before = player.skills["hymns"]
    combat.complete_cast(actor,{"ability":"hymn_steady","target":actor.id})
    game.commit_commerce()
    assert player.skills["hymns"] == before
    game.clock.advance(1)
    actor.shock = 30
    combat.complete_cast(actor,{"ability":"hymn_steady","target":actor.id})
    game.commit_commerce()
    assert player.skills["hymns"] == before+.15
    game.clock.advance(1)
    combat.complete_cast(actor,{"ability":"hymn_mend","target":actor.id})
    game.commit_commerce()
    assert player.skills["hymns"] == before+.15  # The cast has not healed yet.
    effect = next(e for e in actor.effects if e["kind"] == "hymn_mend")
    actor.health -= 20
    for _ in range(3):
        combat.heal(actor,3,player.id,effect["use_receipt"])
        game.commit_commerce()
    assert player.skills["hymns"] == before+.3
