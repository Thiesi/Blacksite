"""Game 7.7/12: current commissioned ownership, zero flags and scope."""

from dataclasses import replace
from typing import Any

from blacksite.server.event_relays import Readers
from tests.character_helpers import place
from tests.server.test_event_engine import base_content, events_game, force
from tests.server.test_event_world import author
from tests.server.test_relay_benefits import owned
from tests.server.test_event_convoy import convoy_game
from blacksite.server.clock import TICK_HZ


def relay(game: Any, kind: str) -> None:
    owner = game.core.relays
    current = owner.content.relays['cold-chain']
    owner.content.relays[current.id] = replace(current, benefit=replace(current.benefit,
        kind=kind, amount=300 if kind == 'impact_forecast' else 0, district=None))


def test_game_7_7_beacon_reads_committed_saved_footprint_only_with_current_local_owner(events_game: tuple[Any, ...]) -> None:
    game, caller, player = events_game
    author(game)
    player.faction = 'ferrymen'
    place(game, caller, 'vatside-clinics', (32,18))
    relay(game, 'impact_forecast')
    reader = Readers(game.core.events)
    assert reader.telemetry(player, 'cold-chain') == []
    owned(game, 'cold-chain', 'ferrymen')
    force(game, 'exhale')
    plan = next(iter(game.core.events.scheduler.reserved()))
    lines = reader.telemetry(player, 'cold-chain')
    assert len(lines) == 1
    assert str(tuple(plan.allocations['sites']['0']['tile'])) in lines[0]
    # Key/cache sources must never become false impact predictions.
    assert str(tuple(plan.allocations['sites']['1']['tile'])) not in lines[0] or (
        plan.allocations['sites']['0']['tile'] == plan.allocations['sites']['1']['tile'])
    player.faction = 'halvard'
    assert reader.telemetry(player, 'cold-chain') == []
    player.faction = 'ferrymen'
    place(game, caller, 'vatside-wake-hall', (8,10))
    assert reader.telemetry(player, 'cold-chain') == []


def test_game_7_7_far_zero_flag_reports_local_facts_without_private_history(events_game: tuple[Any, ...]) -> None:
    game, caller, player = events_game
    author(game)
    player.faction = 'ferrymen'
    place(game, caller, 'vatside-clinics', (32,18))
    relay(game, 'long_range_telemetry')
    owned(game, 'cold-chain', 'ferrymen')
    force(game, 'exhale')
    lines = Readers(game.core.events).telemetry(player, 'cold-chain')
    assert any('Exhale' in line for line in lines) and any('Carrier:' in line for line in lines)
    assert not any(player.id in line or player.name in line for line in lines)
    owned(game, 'cold-chain', None)
    assert Readers(game.core.events).telemetry(player, 'cold-chain') == []


def test_game_7_7_beacon_has_no_early_proposal_or_hour_ahead_leak(events_game: tuple[Any, ...]) -> None:
    game, caller, player = events_game
    author(game)
    player.faction = 'ferrymen'
    place(game, caller, 'vatside-clinics', (32,18))
    relay(game, 'impact_forecast')
    owned(game, 'cold-chain', 'ferrymen')
    owner = game.core.events
    draft = owner.scheduler.fork()
    plan = draft.reserve(owner.content.events['exhale'], owner.now(), 91, owner.eligible)
    owner.effects.allocate(draft, plan)
    owner.jobs.allocate(draft, plan)
    reader = Readers(owner)
    assert reader.telemetry(player, 'cold-chain') == []
    assert owner.write(draft, [])
    game.commit_commerce()
    assert reader.telemetry(player, 'cold-chain') == []
    game.clock.advance(3301*TICK_HZ)
    assert reader.telemetry(player, 'cold-chain')


def test_game_7_7_mile_zero_flag_exposes_current_local_route_without_granting_immunity(convoy_game: tuple[Any, ...]) -> None:
    game, callers, players, actor, pid, points = convoy_game
    player = players[0]
    player.faction = 'ferrymen'
    relay(game, 'convoy_patrol')
    owned(game, 'cold-chain', 'ferrymen')
    reader = Readers(game.core.events)
    before = player.record(), actor.health, list(actor.effects), dict(actor.modifiers)
    rows = reader.patrols(player)
    index = game.core.events.scheduler.plans[pid].allocations['waypoint']
    assert rows and rows[0]['waypoints'] == [list(tile) for tile in points[index:]]
    assert (player.record(), actor.health, actor.effects, actor.modifiers) == before
    owned(game, 'cold-chain', None)
    assert reader.patrols(player) == []
