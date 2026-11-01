"""Demo only: the S38 stand-in on demo/sodium-row-evening (never merged)."""

from dataclasses import replace

import pytest

from blacksite.content.loader import load_content
from blacksite.content.schema import Region, Spawner
from blacksite.server import demo_truce
from tests.character_helpers import create, place
from tests.harness import HeadlessServer


def boot(repo_root, monkeypatch, *, demo=True, bouncer=False):
    if demo:
        monkeypatch.setenv("BLACKSITE_DEMO", demo_truce.DEMO)
    else:
        monkeypatch.delenv("BLACKSITE_DEMO", raising=False)
    if bouncer:
        monkeypatch.setenv("BLACKSITE_DEMO_BOUNCER", "1")
    content = load_content(repo_root/"src/blacksite/content")
    content.zones = {key: replace(z, meta=replace(z.meta, spawners=())) for key, z in content.zones.items()}
    game = HeadlessServer(content, character_state={})
    caller = game.connect()
    create(game, caller, card="none")
    game.core.characters.players[caller.session.player_id].progress["wake_combat"] = "skipped"
    return game, caller


def body(game, caller):
    return game.core.characters.sim.avatars[caller.session.user_id].actor


def spawn(game, zone_id, key, tile, group="test-group"):
    zone = game.core.world.zones[zone_id]
    spec = Spawner(group, key, 1, 60, region=Region(tile[0], tile[1], 1, 1), condition="always")
    zone.template = replace(zone.template, meta=replace(zone.template.meta, spawners=zone.template.meta.spawners + (spec,)))
    game.step()
    return next(a for a in zone.actors.values() if a.kind != "player" and a.behaviour.get("spawner") == group)


def lines(game, caller):
    return [line.get("text", "") for line in caller.session.log_ring]


def test_demo_off_installs_nothing(repo_root, monkeypatch):
    game, _ = boot(repo_root, monkeypatch, demo=False)
    assert game.core.npcs.hostile.__func__ is type(game.core.npcs).hostile


def test_row_enforcer_ignores_hostile_faction(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, "sodium-row", (60, 12))
    runner = body(game, caller)
    runner.faction = "kestrel"
    guard = spawn(game, "sodium-row", "npc-sable-enforcer", (64, 12))
    game.step(5)
    assert not game.core.npcs.hostile(guard, runner)
    assert guard.target != runner.id


def test_matrix_still_applies_off_the_row(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, "vatside-clinics", (20, 3))
    runner = body(game, caller)
    runner.faction = "kestrel"
    guard = spawn(game, "vatside-clinics", "npc-sable-enforcer", (24, 3))
    assert game.core.npcs.hostile(guard, runner)


def test_attack_on_any_npc_calls_the_keeper(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, "sodium-row", (60, 12))
    runner = body(game, caller)
    guard = spawn(game, "sodium-row", "npc-sable-enforcer", (70, 12), group="enforcers")
    regular = spawn(game, "sodium-row", "npc-sodium-regular", (62, 12), group="regulars")
    assert not game.core.npcs.hostile(guard, runner)
    game.core.combat.exchange(runner, regular)
    assert game.core.npcs.hostile(guard, runner)
    assert guard.target == runner.id
    assert any("Sable is coming for you." in text for text in lines(game, caller))


def test_returning_fire_at_a_hunter_breaks_nothing(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, "sodium-row", (60, 12))
    runner = body(game, caller)
    guard = spawn(game, "sodium-row", "npc-sable-enforcer", (70, 12), group="enforcers")
    regular = spawn(game, "sodium-row", "npc-sodium-regular", (62, 12), group="regulars")
    regular.target = runner.id  # already after the runner
    truce = game.core.combat.hostile_hook.__self__
    assert not truce.breaks(runner, regular)
    assert not game.core.npcs.hostile(guard, runner)


def test_any_attack_on_a_row_player_would_mark(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    other = game.connect({"user_id": 2, "handle": "Other", "node_name": "test"})
    create(game, other, card="none")
    place(game, caller, "sodium-row", (60, 12))
    place(game, other, "sodium-row", (62, 12))
    a, b = body(game, caller), body(game, other)
    a.faction, b.faction = "halvard", "unmoored"
    combat = game.core.combat
    assert combat.would_mark(a, b)
    b.marked = True
    assert not combat.would_mark(a, b)


def test_bouncer_refuses_a_marked_truce_breaker(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch, bouncer=True)
    place(game, caller, "sodium-row", (60, 12))
    truce = game.core.combat.hostile_hook.__self__
    sim = game.core.characters.sim
    exit = next(e for e in game.core.world.zones["sodium-row"].template.meta.exits if e.target_zone == demo_truce.HALO)
    assert sim.travel_refusal(caller.session, exit) is None
    truce.breakers[caller.session.player_id] = game.core.combat.now() + 900
    assert "Not tonight" in sim.travel_refusal(caller.session, exit)
    truce.breakers[caller.session.player_id] = game.core.combat.now() - 1
    assert sim.travel_refusal(caller.session, exit) is None
