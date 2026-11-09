"""Issue #187 diagnostic, intentionally red; game design 5.5.

This is outside normal testpaths. Run it explicitly; no production fix.
BLACKSITE_187_SOURCE can select the verified demo checkout, with its src
first on PYTHONPATH. The driver and geometry fixture stay the same.
"""

import os
from collections import deque
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import blacksite.server.npcs.engine as npc_engine
from blacksite.content.formats import parse_map
from blacksite.content.loader import load_content
from blacksite.server.npcs.templates import LOST_SIGHT_SECONDS, make_actor
from blacksite.server.protocol import Frame
from blacksite.server.rules.combat import ticks
from tests.character_helpers import create, place
from tests.harness import HeadlessServer

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get("BLACKSITE_187_SOURCE", ROOT)).resolve()
START = (10, 6)
HIDDEN = (9, 6)
POST = (15, 9)


def advance(game: HeadlessServer, client: Any, count: int = 1) -> None:
    for _ in range(count):
        game.step()
        game.commit_commerce()
        game.frames_for(client)
        client.session.acknowledge(client.session.view_revision)


def scene(*, demo_geometry: bool) -> tuple[Any, ...]:
    assert Path(npc_engine.__file__).resolve().is_relative_to(SOURCE / "src")
    content = load_content(SOURCE / "src/blacksite/content")
    # Exclude unrelated city traffic; retain the actual combat/AI pipeline.
    content.zones = {key: replace(zone, meta=replace(zone.meta, spawners=()))
                     for key, zone in content.zones.items()}
    if demo_geometry:
        grid, problems = parse_map(Path(__file__).with_name("row-demo.map").read_text(encoding="utf-8"),
                                  "d305537 Row fixture", {tile.char: tile.id for tile in content.tiles.values()})
        assert not problems
        content.zones["sodium-row"] = replace(content.zones["sodium-row"], grid=grid)
    game = HeadlessServer(content, character_state={})
    client = game.connect()
    create(game, client, archetype=0, card="none")
    player = game.core.characters.players[client.session.player_id]
    player.progress["wake_combat"] = "skipped"
    # Main's truce suppresses matrix hostility until the shot. The old demo
    # has no truce keeper; this declared affiliation supplies its hostility.
    player.faction = "unmoored"
    place(game, client, "sodium-row", START)
    source = game.core.world.actors[player.id]
    source.faction = "unmoored"
    zone = game.core.world.zones["sodium-row"]
    regular = make_actor(content.npcs["npc-sodium-regular"], "issue187-regular",
                         {"spawner": "issue187-regular", "home": (11, 6), "phase": 0, "pause": 100000})
    template = "npc-row-enforcer" if "npc-row-enforcer" in content.npcs else "npc-sable-enforcer"
    hunter = make_actor(content.npcs[template], "issue187-enforcer",
                        {"spawner": "issue187-enforcer", "home": POST, "phase": 0})
    game.core.world.enter(regular, zone.id, (11, 6))
    game.core.world.enter(hunter, zone.id, POST)
    # A real requested shot, including the ordinary two-second warning and
    # committed ammunition/combat effects. A miss still provokes normally.
    fire = Frame("intent", {"name": "fire", "args": {"target": regular.id}})
    client.send(fire)
    advance(game, client, 22)
    client.send(fire)
    advance(game, client)
    assert source.cooldowns.get("weapon", 0) > game.clock.now_tick()
    for _ in range(40):
        if hunter.cooldowns.get("combat", 0) > game.clock.now_tick():
            break
        advance(game, client)
    # The enforcer has fired while remaining outside the bar.
    assert hunter.position == POST
    assert hunter.cooldowns.get("combat", 0) > game.clock.now_tick()
    assert hunter.target == source.id and hunter.behaviour["state"] == "hunt"
    assert hunter.behaviour["last_position"] == START
    return game, client, source, hunter, zone


def reachable_path(zone: Any, hunter: Any, start: tuple[int, int],
                   target: tuple[int, int], avoid: set[tuple[int, int]]) -> list[tuple[int, int]]:
    """Read-only reachability oracle; never moves or directs the live hunter."""
    queue = deque([start])
    parents = {start: None}
    blocked = {actor.position for actor in zone.actors.values() if actor is not hunter}
    while queue:
        current = queue.popleft()
        if current == target:
            path = []
            while current is not None:
                path.append(current)
                current = parents[current]
            return path[::-1]
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            tile = (current[0] + dx, current[1] + dy)
            if tile not in parents and tile not in avoid | blocked and zone.can_enter(hunter, tile):
                parents[tile] = current
                queue.append(tile)
    return []


def test_shipped_main_row_step_has_no_alcove_occlusion() -> None:
    if SOURCE != ROOT:
        pytest.skip("Control is specifically main's shipped open Row")
    game, client, source, hunter, _ = scene(demo_geometry=False)
    client.send(Frame("intent", {"name": "move", "args": {"dir": "left"}}))
    advance(game, client)
    assert source.position == HIDDEN
    assert game.core.combat.visible(hunter, source)
    assert hunter.target == source.id and hunter.behaviour["state"] == "hunt"


@pytest.mark.parametrize("clear_avoid", [False, True], ids=["ordinary-avoid", "empty-avoid"])
def test_game_5_5_hunter_reaches_bar_trail_before_lost_sight_timeout(
    monkeypatch: pytest.MonkeyPatch, clear_avoid: bool,
) -> None:
    game, client, source, hunter, zone = scene(demo_geometry=True)
    if clear_avoid:
        monkeypatch.setattr(game.core.npcs.spawners, "reserved", lambda zone: set())
    avoid = game.core.npcs.spawners.reserved(zone)
    assert zone.passable((13, 8)) and zone.can_enter(hunter, (13, 8))
    assert (13, 8) not in avoid
    last_seen = hunter.behaviour["last_seen"]
    client.send(Frame("intent", {"name": "move", "args": {"dir": "left"}}))
    advance(game, client)
    assert source.position == HIDDEN
    assert not game.core.combat.visible(hunter, source)
    assert game.core.combat.legal(hunter, source) and game.core.npcs.hostile(hunter, source)
    assert hunter.target == source.id and hunter.behaviour["state"] == "hunt"
    # The old position is now unoccupied. Check the route from the original
    # post without prescribing the production hunter's first step or route.
    path = reachable_path(zone, hunter, POST, START, avoid)
    assert path
    assert len(path) - 1 == 8, path
    trail = [POST, hunter.position]
    reacquired = False
    while game.clock.now_tick() < last_seen + ticks(LOST_SIGHT_SECONDS) + 5:
        if game.core.combat.visible(hunter, source) or hunter.position == START:
            reacquired = True
            break
        if game.clock.now_tick() < last_seen + ticks(LOST_SIGHT_SECONDS):
            assert hunter.target == source.id and hunter.behaviour["state"] == "hunt"
        advance(game, client)
        assert game.core.combat.legal(hunter, source) and game.core.npcs.hostile(hunter, source)
        if hunter.position != trail[-1]:
            trail.append(hunter.position)
    assert reacquired, {"last_seen": last_seen, "tick": game.clock.now_tick(),
                        "target": hunter.target, "state": hunter.behaviour["state"],
                        "last_position": hunter.behaviour["last_position"],
                        "shortest_path": path, "trail": trail[:35]}
