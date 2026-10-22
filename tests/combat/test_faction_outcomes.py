"""Game 7.1: standing shares death settlement independently of XP caps."""
from datetime import timedelta
from blacksite.server.storage.db import Storage
from tests.combat.test_engine import duel, body
from tests.combat.test_pvp_progression import kill


def test_game_7_1_marked_reward_is_atomic_with_clone_and_survives_xp_cap(duel, tmp_path):
    game, a, b = duel
    winner = game.core.characters.players[a.session.player_id]
    victim = game.core.characters.players[b.session.player_id]
    victim.faction = "sablier"
    victim.marked_until = (game.clock.now_utc()+timedelta(minutes=15)).isoformat()
    identity = game.core.characters.identities[winner.bbs_user_id]
    identity.setdefault("combat_xp_until", {})[victim.bbs_user_id] = game.clock.now_utc().timestamp()+86400
    before = winner.xp
    kill(game, a, b)
    assert winner.standing.get("wardens", 0) == 0
    game.commit_commerce(error=True)
    assert winner.standing.get("wardens", 0) == 0
    game.step()
    effect = game.core.commerce.outbox.pop(0)
    store = Storage(tmp_path/"factions.db", game.clock)
    try:
        store.commerce_write(game.core.commerce.prepare(effect))
        saved = store.character_state()
        row = next(p for p in saved["players"] if p["id"] == winner.id)
        assert row["standing"]["wardens"] == 5 and row["standing"]["sablier"] == -10
        assert saved["identities"][winner.bbs_user_id]["receipts"]["marked_kills"][victim.bbs_user_id] > game.clock.now_utc().timestamp()
    finally:
        store.close()
    game.core.commerce.committed(effect, True)
    assert winner.xp == before and winner.standing["wardens"] == 5
    game.step(201); game.commit_commerce(); game.step()
    from tests.character_helpers import place
    place(game, b, "vatside-clinics", game.core.world.free_tile("vatside-clinics", (27, 3)))
    kill(game, a, b); game.commit_commerce()
    assert winner.standing["wardens"] == 5 and winner.standing["sablier"] == -20


def test_game_7_3_controlled_turret_attempt_marks_and_lethal_hit_attributes_the_controller(duel):
    from dataclasses import replace
    from blacksite.server.world.actors import Actor
    game, a, b = duel
    source, target = body(game, a), body(game, b)
    combat = game.core.combat
    turret = Actor("fixture:turret", "Turret", kind="npc",
                   behaviour={"interlock_initiator": source.id, "powered": True})
    game.core.world.enter(turret, source.zone, (26, 3))
    weapon = replace(game.core.loop.content.items["wpn_kestrel_sidearm"].weapon, accuracy=0)
    combat.shot(turret, target, weapon)
    p = game.core.characters.players[source.id]
    assert p.marked_until and source.marked
    assert any(e.get("immediate") for e in game.core.characters.outbox if e.get("player", {}).get("id") == p.id)
    combat.hurt(turret, target, 1000)
    assert game.core.characters.players[target.id].progress["combat"]["killer"] == source.id
