"""Game 3.5: NPC defeat joins XP to loot and spawn retirement."""

from dataclasses import replace

from blacksite.content.schema import LootEntry
from blacksite.server.progression import combat_xp
from blacksite.server.storage.db import Storage
from blacksite.server.world.actors import Actor
from tests.npcs.test_engine import body, city, spawn


def test_game_10_owned_drone_loot_names_controller_for_immediate_recovery(city):
    game, caller = city
    player = game.core.characters.players[caller.session.player_id]
    content = game.core.loop.content
    template = content.npcs['npc-sable-enforcer']
    content.npcs[template.id] = replace(template, loot=(LootEntry('ammo_9x', 1),))
    target = spawn(game)[0]
    tool = Actor('fixture-owned-drone', 'Owned tool', kind='drone', owner=player.id,
                 behaviour={'player_drone': True})
    game.core.npcs.died(tool, target)
    game.commit_commerce()
    cache = next(iter(game.core.commerce.caches.values()))
    assert cache['killer'] == player.id
    assert game.core.crews.cache_permits(player.id, cache, game.clock.now_utc().timestamp())


def test_game_3_5_npc_xp_and_retirement_are_one_durable_receipt(city, tmp_path):
    game, caller = city
    player = game.core.characters.players[caller.session.player_id]
    content = game.core.loop.content
    template = content.npcs["npc-sable-enforcer"]
    assert template.xp > 0
    content.npcs[template.id] = replace(template, loot=(LootEntry("ammo_9x", 1),))
    target = spawn(game)[0]
    old_xp = player.xp
    expected = combat_xp(player.grade, template.grade)
    store = Storage(tmp_path/"xp.db", game.clock)
    try:
        store.mark_dirty("players", player.id, player.record())
        store.mark_dirty("identities", player.bbs_user_id, game.core.characters.identities[player.bbs_user_id])
        for iid, item in game.core.commerce.items.items():
            store.mark_dirty("items", iid, item.record())
        store.flush_now()
        game.core.combat.hurt(body(game,caller), target, 1000)
        assert player.xp == old_xp and target.id in game.core.world.actors
        commerce = game.core.commerce
        effect = commerce.outbox.pop(0)
        prepared = commerce.prepare(effect)
        store.commerce_write(prepared)
        restored = store.character_state()
        row = next(p for p in restored["players"] if p["id"] == player.id)
        assert row["xp"] == old_xp+expected
        assert row["progress"]["reward_receipts"]["combat:"+target.behaviour["slot"]] == target.id
        slot = restored["npcs"]["slots"][target.behaviour["slot"]]
        assert "actor" not in slot and slot["until"] == game.core.combat.now()+60
        assert len(restored["commerce"]["caches"]) == 1
        assert player.xp == old_xp  # Publication still waits for commit.
        commerce.committed(effect, True)
        assert player.xp == old_xp+expected and target.id not in game.core.world.actors
        game.core.npcs.died(body(game,caller), target)
        assert not commerce.outbox
    finally:
        store.close()


def test_game_3_5_failed_npc_reward_keeps_xp_and_source_retryable(city):
    game, caller = city
    target = spawn(game)[0]
    player = game.core.characters.players[caller.session.player_id]
    expected = combat_xp(player.grade, game.core.loop.content.npcs[target.behaviour["template"]].grade)
    old_xp = player.xp
    game.core.combat.hurt(body(game,caller), target, 1000)
    game.core.combat.hurt(body(game,caller), target, 1000)
    assert len(game.core.commerce.outbox) == 1
    game.commit_commerce(error=True)
    assert player.xp == old_xp and target.health == 1
    assert not player.progress.get("reward_receipts")
    game.core.combat.hurt(body(game,caller), target, 1000)
    game.commit_commerce()
    assert player.xp == old_xp+expected and target.zone is None


def test_game_3_5_nonlethal_failure_and_deleting_character_do_not_pay(city):
    game, caller = city
    player = game.core.characters.players[caller.session.player_id]
    target = spawn(game)[0]
    target.behaviour["nonlethal"] = True
    old_xp = player.xp
    game.core.combat.hurt(body(game,caller), target, 1000)
    game.commit_commerce()
    assert player.xp == old_xp
    game.clock.advance(601);game.step()
    target = next(a for a in game.core.world.actors.values() if a.kind == "npc")
    game.core.characters.deleting.add(player.id)
    game.core.combat.hurt(body(game,caller), target, 1000)
    effects = game.commit_commerce()
    assert effects[0]["player"] is None and player.xp == old_xp
