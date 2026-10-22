"""Game 7.1: NPC standing belongs to the NPC death receipt."""
from tests.npcs.test_engine import city, spawn, body


def test_game_7_1_npc_kill_explicit_vector_commits_with_respawn_and_loot(city):
    game, caller = city
    p = game.core.characters.players[caller.session.player_id]
    p.update_progression(1500)
    target = spawn(game, "npc-sable-enforcer")[0]
    game.core.npcs.died(body(game, caller), target)
    assert p.standing == {}
    game.commit_commerce(error=True)
    assert p.standing == {} and target.id in game.core.world.actors
    game.core.npcs.died(body(game, caller), target)
    effect = game.commit_commerce()[0]
    assert p.standing["sable"] == -5
    assert p.standing["halvard"] == p.standing["wardens"] == 2
    assert p.standing.get("sablier", 0) == 0  # No secondary propagation.
    assert "npc_state" in effect and target.id not in game.core.world.actors
