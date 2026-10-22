"""S16 manual spending: real drafts, rollback, revision and replay gates."""

from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.server.progression_engine import ProgressionEngine
from blacksite.server.progression import Grant
from blacksite.server.skills import Use
from blacksite.server.protocol import Frame
from tests.character_helpers import act, create
from tests.harness import HeadlessServer


@pytest.fixture
def skills_game(repo_root: Path):
    game = HeadlessServer(load_content(repo_root/"src/blacksite/content"), character_state={})
    client = game.connect()
    create(game, client, archetype=0)
    engine = game.core.progression
    player = game.core.characters.players[client.session.player_id]
    player.update_progression(1500)
    engine.open_skills(client.session)
    return game, client, player, engine


def select(client, *, request="spend-one", revision=None, row="kinetic"):
    return Frame("intent", {"name": "menu_select", "request_id": request,
        "expected_revision": client.session.view_revision if revision is None else revision,
        "args": {"row": row, "key": "+"}})


def test_game_3_5_spending_only_publishes_after_commit_and_replays_once(skills_game):
    game, client, player, engine = skills_game
    request = select(client)
    assert engine.input(client.session, request, 0)
    assert player.skills["kinetic"] == 0 and player.progress["points"] == 12
    engine.input(client.session, request, 0)
    assert len(game.core.commerce.outbox) == 1
    game.commit_commerce()
    assert player.skills["kinetic"] == 1 and player.progress["points"] == 11
    engine.input(client.session, request, 0)
    assert not game.core.commerce.outbox


def test_game_3_5_failed_skill_receipt_keeps_point_and_can_retry(skills_game):
    game, client, player, engine = skills_game
    engine.input(client.session, select(client), 0)
    game.commit_commerce(error=True)
    assert player.skills["kinetic"] == 0 and player.progress["points"] == 12
    engine.input(client.session, select(client, request="retry"), 0)
    game.commit_commerce()
    assert player.skills["kinetic"] == 1 and player.progress["points"] == 11


def test_game_3_5_stale_menu_or_wrong_selected_line_cannot_spend(skills_game):
    game, client, player, engine = skills_game
    engine.input(client.session, select(client, revision=client.session.view_revision-1), 0)
    engine.input(client.session, select(client, row="programs"), 0)
    assert not game.core.commerce.outbox and player.progress["points"] == 12
    engine.input(client.session, Frame("intent", {"name": "menu_close", "args": {}}), 0)
    assert client.session.id not in engine.menus
    assert game.core.characters.screens[client.session.id] == ("sheet", 0)


def test_game_3_3_group_attribute_and_actor_pool_update_on_spend_commit(skills_game):
    game, client, player, engine = skills_game
    player.skills["kinetic"] = 9
    before = player.attributes["frame"]
    engine.input(client.session, select(client), 0)
    game.commit_commerce()
    assert player.attributes["frame"] == before+1
    actor = game.core.combat.actor(player)
    assert actor.health_max == engine.modifiers(player).health_max(player)
    assert player.skills["kinetic"] == 10


def test_game_3_5_source_owner_can_join_reward_without_any_live_payment(skills_game):
    game, client, player, engine = skills_game
    old = player.xp
    patch, identity, result = engine.reward_patch(player,
        Grant("run", "core-unit:1", True, tier=3, core="lat-core"))
    assert patch["xp"] == old+120 and player.xp == old
    assert "run_xp_days" not in game.core.characters.identities[player.bbs_user_id]
    assert identity["run_xp_days"]["lat-core"] == game.clock.now_utc().date().isoformat()
    assert game.core.commerce.settle(player, patch, game.core.commerce.items,
        game.core.commerce.caches, game.core.commerce.serial,
        lambda success: engine.notify_reward(player, result) if success else None, identity)
    game.commit_commerce(error=True)
    assert player.xp == old and "run_xp_days" not in game.core.characters.identities[player.bbs_user_id]


def test_ui_4_live_core_character_sheet_opens_skills_and_commits_selected_point(skills_game):
    game, client, player, engine = skills_game
    engine.close_skills(client.session)
    game.step()
    act(game, client, Frame("intent", {"name": "menu_select", "args": {"key": "s", "row": "grade"}}))
    assert client.session.id in engine.menus
    act(game, client, Frame("intent", {"name": "menu_select", "args": {"key": "+", "row": "kinetic"}}))
    assert player.skills["kinetic"] == 0
    game.commit_commerce()
    assert player.skills["kinetic"] == 1 and player.progress["points"] == 11
    act(game, client, Frame("intent", {"name": "menu_close", "args": {}}))
    assert game.core.characters.screens[client.session.id] == ("sheet", 0)


def test_ui_4_downed_caller_keeps_combat_screen_when_skills_menu_closes(skills_game):
    game, client, player, engine = skills_game
    actor = game.core.combat.actor(player)
    actor.health = player.health = 0
    player.progress["combat"] = {"stage": "down", "until": game.clock.now_utc().timestamp()+5, "killer": "npc"}
    game.step()
    assert client.session.id not in engine.menus
    assert client.session.id not in game.core.characters.screens
    assert game.core.characters.sim.external_views[client.session.id][0] == "dead"


def test_game_3_5_use_gain_serializes_caps_and_refreshes_older_queued_save(skills_game):
    game, client, player, engine = skills_game
    game.core.characters.outbox.clear()
    use = Use("weapon_hit", "kinetic", "actual-hit:one", True, threat=True)
    engine.record_use(player.id, use)
    # Combat callbacks can checkpoint before the later skill write commits.
    game.core.characters.queue("save", player.bbs_user_id, player, immediate=True)
    assert player.skills["kinetic"] == 0
    engine.record_use(player.id, use)
    game.commit_commerce()
    assert player.skills["kinetic"] == .2
    assert game.core.characters.outbox[-1]["player"]["skills"]["kinetic"] == .2
    assert len(game.core.commerce.outbox) == 0


def test_game_3_5_failed_use_receipt_does_not_spend_daily_budget(skills_game):
    game, client, player, engine = skills_game
    engine.record_use(player.id, Use("weapon_hit", "kinetic", "failed-hit", True, threat=True))
    game.commit_commerce(error=True)
    assert player.skills["kinetic"] == 0 and "skill_use" not in player.progress
