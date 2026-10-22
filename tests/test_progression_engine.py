"""S16 manual spending: real drafts, rollback, revision and replay gates."""

from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.server.progression_engine import ProgressionEngine
from blacksite.server.protocol import Frame
from tests.character_helpers import create
from tests.harness import HeadlessServer


@pytest.fixture
def skills_game(repo_root: Path):
    game = HeadlessServer(load_content(repo_root/"src/blacksite/content"), character_state={})
    client = game.connect()
    create(game, client, archetype=0)
    engine = ProgressionEngine(game.core.commerce)
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
