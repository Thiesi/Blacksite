"""Game 3.5: live sight, elapsed stealth, and persistent encounter caps."""

from tests.combat.test_engine import body, build_duel


def ghost(repo_root):
    game, a, b = build_duel(repo_root,first_archetype=1)
    player = game.core.characters.players[a.session.player_id]
    assert player.archetype == "ghost"
    body(game,a).stance = "stealth"
    body(game,b).marked = True
    # The injected clock clears transient marked state each combat tick;
    # use the rule provider to keep this isolated opponent hostile.
    game.core.combat.relation_provider = lambda source,target: "hostile"
    return game, a, b, player


def test_game_3_5_stealth_requires_elapsed_time_visible_threat_and_commit(repo_root,monkeypatch):
    game, a, b, player = ghost(repo_root)
    before = player.skills["stealth"]
    game.step(9)
    assert player.skills["stealth"] == before
    game.step()
    assert player.skills["stealth"] == before
    game.commit_commerce()
    assert player.skills["stealth"] == before+.05
    monkeypatch.setattr(game.core.combat,"visible",lambda source,target:False)
    game.step(20)
    game.commit_commerce()
    assert player.skills["stealth"] == before+.05


def test_game_3_5_saturated_stealth_encounter_stays_alive_until_quiet(repo_root):
    game, a, b, player = ghost(repo_root)
    before = player.skills["stealth"]
    game.step(200)
    game.commit_commerce()
    assert player.skills["stealth"] == before+1
    original = player.progress["stealth_contact"]["id"]
    for _ in range(7):
        game.step(100)
        game.commit_commerce()
    assert player.progress["stealth_contact"]["id"] == original
    assert player.skills["stealth"] == before+1
    game.core.progression.stealth_ticks.clear()  # Reattachment does not reset persistent contact.
    game.step(10)
    game.commit_commerce()
    assert player.skills["stealth"] == before+1
    body(game,a).stance = "normal"
    game.step(600)
    body(game,a).stance = "stealth"
    game.step(10)
    game.commit_commerce()
    assert player.progress["stealth_contact"]["id"] != original
    assert player.skills["stealth"] == before+1.05


def test_game_3_5_crew_presence_does_not_teach_stealth(repo_root):
    game, a, b, player = ghost(repo_root)
    before = player.skills["stealth"]
    game.core.progression.crew_of = lambda pid:"same-crew"
    game.step(20)
    game.commit_commerce()
    assert player.skills["stealth"] == before and "stealth_contact" not in player.progress
