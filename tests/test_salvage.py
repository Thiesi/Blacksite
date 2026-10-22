"""Game 8.4: deterministic ring generation, shared nodes and restart clocks."""

from copy import deepcopy
from dataclasses import replace
from random import Random

import pytest

from blacksite.content.schema import ObjectSpec
from blacksite.server.clock import TICK_HZ
from blacksite.server.world.zone import ObjectState
from blacksite.server.salvage import Salvage
from blacksite.server.storage.db import Storage
from tests.test_fabrication import content, game, caller, grant
from tests.character_helpers import place


def node(game, client, units=3):
    salvage = game.core.salvage
    actor = game.core.characters.sim.avatars[client.session.user_id].actor
    salvage.state["zones"][actor.zone] = {"ring": 1, "nodes": {
        "fixture-node": {"tile": list(actor.position), "grade": "hull", "units": units}},
        "respawn_at": salvage.uptime+600, "rng": Random(42).getstate()}
    salvage.sync()
    return actor.zone


def test_game_8_4_ring_weights_bounds_and_intact_only_ring_four(content):
    rules = content.salvage
    assert (rules.minimum_nodes, rules.maximum_nodes, rules.minimum_units, rules.maximum_units) == (2, 6, 1, 6)
    assert (rules.respawn_seconds, rules.harvest_seconds, rules.craft_seconds) == (600, 2, 3)
    assert rules.weights == {"1": {"hull": 90, "optics": 10},
        "2": {"hull": 55, "optics": 25, "power": 20},
        "3": {"hull": 35, "optics": 25, "power": 25, "compute": 15},
        "4": {"hull": 20, "optics": 20, "power": 25, "compute": 30, "intact": 5}}


def test_game_8_4_harvest_repeats_two_seconds_and_cancel_keeps_completed_units(game):
    client, player = caller(game)
    zid = node(game, client)
    fab = game.core.fabrication
    fab.start(client.session, "fixture-node")
    game.step(2*TICK_HZ-1)
    assert not fab.amounts(player)
    game.step()
    effect = game.commit_commerce()[-1]
    assert fab.amounts(player) == {"hull": 1}
    assert effect["salvage_state"]["zones"][zid]["nodes"]["fixture-node"]["units"] == 2
    game.step(TICK_HZ)
    fab.stop(client.session)
    game.step(3*TICK_HZ)
    game.commit_commerce()
    assert fab.amounts(player) == {"hull": 1}


def test_game_8_4_two_callers_split_one_node_without_duplicate_units(game):
    first, p1 = caller(game)
    second, p2 = caller(game, 2)
    zid = node(game, first, units=3)
    actor = game.core.characters.sim.avatars[first.session.user_id].actor
    adjacent = game.core.world.free_tile(zid, actor.position)
    place(game, second, zid, adjacent)
    fab = game.core.fabrication
    fab.start(first.session, "fixture-node")
    fab.start(second.session, "fixture-node")
    for _ in range(5):
        game.step(2*TICK_HZ)
        game.commit_commerce()
    assert sum(fab.amounts(player).get("hull", 0) for player in (p1, p2)) == 3
    assert all(fab.amounts(player).get("hull", 0) >= 1 for player in (p1, p2))
    assert "fixture-node" not in game.core.world.zones[zid].objects


def test_game_8_4_failed_harvest_save_does_not_remove_node_unit(game):
    client, player = caller(game)
    zid = node(game, client)
    fab = game.core.fabrication
    fab.start(client.session, "fixture-node")
    game.step(2*TICK_HZ)
    game.commit_commerce(error=True)
    assert not fab.amounts(player)
    assert game.core.salvage.state["zones"][zid]["nodes"]["fixture-node"]["units"] == 3


def test_game_8_4_lazy_respawn_counts_uptime_without_downtime(game, tmp_path):
    client, player = caller(game)
    zid = node(game, client, units=2)
    salvage = game.core.salvage
    zone = game.core.world.zones[zid]
    zone.objects["fixture-field"] = ObjectState(ObjectSpec("fixture-field", (1, 1), "salvage_field", params={"ring": 1}))
    game.clock.advance(599*TICK_HZ)
    salvage.tick()
    assert not game.core.commerce.outbox
    game.clock.advance(TICK_HZ)
    salvage.tick()
    effects = game.commit_commerce()
    assert len(salvage.state["zones"][zid]["nodes"]) == 2
    game.clock.advance(200*TICK_HZ)
    saved = salvage.record()
    storage = Storage(tmp_path/"world.db", game.clock)
    try:
        storage.commerce_write(effects[-1])
        storage.mark_dirty("meta", "salvage_state", saved)
        storage.flush_now()
        persisted = storage.character_state()["salvage"]
    finally:
        storage.close()
    # Arbitrarily long process downtime does not count toward ring uptime.
    game.clock.advance(86400*TICK_HZ)
    restored = Salvage(game.core.commerce, persisted)
    restored.tick()
    assert not game.core.commerce.outbox
    game.clock.advance(399*TICK_HZ)
    restored.tick()
    assert not game.core.commerce.outbox
    game.clock.advance(TICK_HZ)
    restored.tick()
    game.commit_commerce()
    assert len(restored.state["zones"][zid]["nodes"]) == 3
    assert restored.state["zones"][zid]["nodes"]["fixture-node"]["units"] == 2


def test_game_8_4_restart_keeps_rng_and_crash_bonus_cannot_create_intact(game):
    client, player = caller(game)
    zid = node(game, client)
    salvage = game.core.salvage
    salvage.state["zones"][zid]["ring"] = 3
    salvage.rules = replace(salvage.rules, weights={**salvage.rules.weights, "3": {"compute": 100}})
    salvage.crash_relay_bonus = lambda zone: True
    proposal = deepcopy(salvage.state)
    rng = salvage.rng(zid, proposal)
    for _ in range(10):
        assert salvage.spawn(zid, proposal, rng)
    assert {row["grade"] for key, row in proposal["zones"][zid]["nodes"].items() if key != "fixture-node"} == {"compute"}
    proposal["zones"][zid]["rng"] = rng.getstate()
    salvage.state = proposal
    import json
    persisted = json.loads(json.dumps(salvage.record()))
    restored = Salvage(game.core.commerce, persisted)
    assert restored.rng(zid, restored.state).random() == salvage.rng(zid, salvage.state).random()


def test_game_8_4_landing_salvage_price_and_intact_vendor_exclusion(game):
    client, player = caller(game)
    hull = grant(game, player, "slv_hull")
    vendor = next(row for row in game.core.loop.content.vendors.values() if row.salvage_multiplier == 1.2)
    assert game.core.commerce.resale(vendor, hull, 1) == 18
    assert game.core.loop.content.items["slv_intact"].no_vendor_sale
