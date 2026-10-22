"""Game 3.5: defeated identity, clone settlement and winner XP are atomic."""

from copy import deepcopy

from blacksite.server.progression import combat_xp
from blacksite.server.storage.db import Storage
from tests.character_helpers import place
from tests.combat.test_engine import body, duel


def kill(game, source, victim):
    game.core.combat.hurt(body(game,source),body(game,victim),1000)
    game.step(51)
    assert game.core.commerce.pending


def test_game_3_5_pvp_reward_and_both_identities_share_durable_death_receipt(duel, tmp_path):
    game, a, b = duel
    winner = game.core.characters.players[a.session.player_id]
    victim = game.core.characters.players[b.session.player_id]
    expected = combat_xp(winner.grade, victim.grade)
    old_xp = winner.xp
    store = Storage(tmp_path/"pvp.db",game.clock)
    try:
        for player in game.core.characters.players.values():
            store.mark_dirty("players",player.id,player.record())
        for user, identity in game.core.characters.identities.items():
            store.mark_dirty("identities",user,identity)
        for iid, item in game.core.commerce.items.items():
            store.mark_dirty("items",iid,item.record())
        store.flush_now()
        # An old write-behind identity must not overwrite the reward cap.
        store.mark_dirty("identities",winner.bbs_user_id,deepcopy(game.core.characters.identities[winner.bbs_user_id]))
        kill(game,a,b)
        assert winner.xp == old_xp and victim.chits_hand == 200
        effect = game.core.commerce.outbox.pop(0)
        store.commerce_write(game.core.commerce.prepare(effect))
        store.flush_now()
        saved = store.character_state()
        records = {p["id"]:p for p in saved["players"]}
        assert records[winner.id]["xp"] == old_xp+expected
        assert records[victim.id]["chits_hand"] == 140
        assert records[victim.id]["progress"]["combat"]["stage"] == "dead"
        until = saved["identities"][winner.bbs_user_id]["combat_xp_until"][victim.bbs_user_id]
        assert until > game.clock.now_utc().timestamp()+86399
        assert winner.xp == old_xp
        game.core.commerce.committed(effect,True)
        assert winner.xp == old_xp+expected and victim.chits_hand == 140
    finally:
        store.close()


def test_game_3_5_failed_pvp_receipt_keeps_cap_reward_and_clone_charge_retryable(duel):
    game, a, b = duel
    winner = game.core.characters.players[a.session.player_id]
    victim = game.core.characters.players[b.session.player_id]
    old = winner.xp
    kill(game,a,b)
    game.commit_commerce(error=True)
    assert winner.xp == old and victim.chits_hand == 200
    assert "combat_xp_until" not in game.core.characters.identities[winner.bbs_user_id]
    game.step()
    game.commit_commerce()
    assert winner.xp == old+20 and victim.chits_hand == 140


def test_game_3_5_second_defeat_of_same_bbs_identity_pays_no_xp(duel):
    game, a, b = duel
    winner = game.core.characters.players[a.session.player_id]
    kill(game,a,b);game.commit_commerce()
    earned = winner.xp
    game.step(201);game.commit_commerce();game.step()
    place(game,b,"vatside-clinics",(27,3))
    kill(game,a,b);game.commit_commerce()
    assert winner.xp == earned


def test_game_3_5_crew_defeat_never_awards_pvp_xp(duel):
    game, a, b = duel
    game.core.progression.crew_of = lambda pid:"fixture-crew"
    player = game.core.characters.players[a.session.player_id]
    old = player.xp
    kill(game,a,b)
    effects = game.commit_commerce()
    assert player.xp == old and "identities" not in effects[0]
