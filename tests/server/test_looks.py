"""Proposal 68 looks: dressing never reveals or changes a rule."""

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.server.views import looks
from tests.harness import HeadlessServer

ROOT = Path(__file__).parents[2]
CONTENT = ROOT / "src/blacksite/content"
CANDIDATE = ROOT / "docs/design/proposals/68-presentation/candidates/sodium-row"
PRESENTATION = ("looks", "looks_legend", "place")


def sim(game: HeadlessServer):
    return game.core.characters.sim if game.core.characters else game.core.simulation


def move(game: HeadlessServer, client, zone_id: str, tile: tuple[int, int]) -> None:
    """Put a preview body on a tile, as tests/character_helpers.place does for characters."""
    avatar, world = sim(game).avatars[client.session.user_id], game.core.world
    if avatar.actor.zone:
        world.zones[avatar.actor.zone].deactivate(client.session.id, game.clock.now_tick())
    world.enter(avatar.actor, zone_id, tile)
    avatar.zone = client.session.subscribed = zone_id
    world.zones[zone_id].activate(client.session.id, game.clock.now_tick())
    game.step()


def walk_views(content, zone: str, tiles: list[tuple[int, int]]):
    game = HeadlessServer(content, zone)
    client = game.connect(width=132, height=50)
    game.step()
    views = []
    for tile in tiles:
        move(game, client, zone, tile)
        game.step()
        views.append(sim(game).views[client.session.id].previous["body"])
    return game, client, views


@pytest.mark.parametrize("zone,tiles", [("core-plaza", [(57, 6), (20, 30), (80, 20)]),
                                        ("sodium-row", [(34, 12), (90, 20)]),
                                        ("vatside-clinics", [(46, 3), (10, 20)])])
def test_looks_exist_exactly_where_tiles_do(zone, tiles) -> None:
    _, _, views = walk_views(load_content(CONTENT), zone, tiles)
    for body in views:
        assert body["looks"], zone
        for tile_row, look_row in zip(body["tiles"], body["looks"], strict=True):
            for tile, look in zip(tile_row, look_row, strict=True):
                assert (tile == -1) == (look == -1)


def test_presentation_fields_leave_every_rule_field_unchanged(monkeypatch) -> None:
    """The mechanics guard: removing all dressing changes nothing else."""
    content = load_content(CONTENT)
    bare = replace(content, looks={}, themes=None)
    route = [(57, 6), (20, 30), (80, 20)]
    _, _, dressed = walk_views(content, "core-plaza", route)
    _, _, plain = walk_views(bare, "core-plaza", route)
    for a, b in zip(dressed, plain, strict=True):
        assert {k: v for k, v in a.items() if k not in PRESENTATION} == \
               {k: v for k, v in b.items() if k not in PRESENTATION}


def test_charted_geography_is_trial_only_and_never_remembered(monkeypatch) -> None:
    content = load_content(CONTENT)
    _, _, (off,) = walk_views(content, "core-plaza", [(57, 6)])
    monkeypatch.setattr(looks, "TRIAL", True)
    game, client, (on,) = walk_views(content, "core-plaza", [(57, 6)])
    known = lambda body: sum(t == -2 for row in body["tiles"] for t in row)
    assert known(on) > known(off) + 500
    avatar = sim(game).avatars[client.session.user_id]
    remembered = avatar.perception.remembered["core-plaza"]
    assert len(remembered) < 1000  # sight memory holds what was seen, not the chart


def test_validator_rejects_dressing_that_would_read_as_a_rule(tmp_path: Path) -> None:
    local = tmp_path / "local"
    (local / "looks").mkdir(parents=True)
    (local / "looks" / "core-plaza.json").write_text("""{
      "schema": 1, "id": "core-plaza", "theme": "core-street",
      "signs": [{"at": [10, 10], "text": "OPEN", "role": "sign_pink"}],
      "marks": [{"at": [2, 1], "text": "§§", "role": "paint"}],
      "glints": [[10, 10]]
    }""", encoding="utf-8")
    (local / "themes.json").write_text("""{"schema": 1, "themes": {"loud": {
      "ground_bg": "sign_pink", "texture": "@"}}}""", encoding="utf-8")
    messages = [p.message for p in validate(load_content(CONTENT, local))]
    assert any("leaves the wall" in m for m in messages)
    assert any("dressing letters only" in m for m in messages)
    assert any("is not on water" in m for m in messages)
    assert any("16-colour values 0-7" in m for m in messages)
    assert any("texture may use only" in m for m in messages)


def test_sodium_row_candidate_overlay_validates(tmp_path: Path) -> None:
    local = tmp_path / "content.local"
    shutil.copytree(CANDIDATE, local)
    tree = load_content(CONTENT, local)
    assert validate(tree) == []
    assert tree.zones["sodium-row"].tile_at((93, 14)) == "door"
