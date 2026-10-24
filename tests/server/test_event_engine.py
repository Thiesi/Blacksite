"""Game 12: production adapter receipts, Curfew boundaries and forecasts."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from blacksite.content.loader import load_content
from blacksite.content.schema import Effect, EventTemplate
from blacksite.server.clock import ManualClock, TICK_HZ
from blacksite.server.rules.events import ROLL_SECONDS, SCHEDULES
from tests.character_helpers import create, place
from tests.harness import HeadlessServer


@pytest.fixture(scope='module')
def base_content() -> Any:
    return load_content(Path(__file__).parents[2]/'src/blacksite/content')


@pytest.fixture
def events_game(base_content: Any) -> tuple[Any, ...]:
    content = deepcopy(base_content)
    sector = next(iter(content.sectors))
    content.events = {
        'curfew': EventTemplate('curfew', 'Curfew',
            ('core-plaza', 'core-precinct', 'core-tram-hub'), *SCHEDULES['curfew'],
            effects=(Effect('entry_restriction'), Effect('relay_pause'),
                     Effect('heat_multiplier', params={'multiplier': 2}))),
        'choir-surge': EventTemplate('choir-surge', 'Choir Surge',
            (sector,), *SCHEDULES['choir-surge'],
            effects=(Effect('ability_magnitude', params={'multiplier': 1.3}),)),
    }
    clock = ManualClock()
    game = HeadlessServer(content, character_state={
        'events': {'last_roll': int(clock.now_utc().timestamp()//ROLL_SECONDS)}}, clock=clock)
    client = game.connect({'user_id': 1, 'handle': 'Events界', 'node_name': 'test'})
    create(game, client, name='Events界', archetype=3)
    game.commit_commerce()
    player = game.core.characters.players[client.session.player_id]
    return game, client, player


def force(game: Any, event: str, *, error: bool = False) -> tuple[list[Any], list[Any]]:
    result: list[Any] = []
    game.core.events.admin('event.force', {'event': event}, result.append)
    game.step()
    receipts = game.commit_commerce(error=error)
    return result, receipts


def advance(game: Any, seconds: float) -> None:
    game.clock.advance(round(seconds*TICK_HZ))
    game.step()
    game.commit_commerce()


def test_arch_15_2_failed_force_exposes_no_plan_or_effect(events_game: tuple[Any, ...]) -> None:
    game, client, player = events_game
    before = deepcopy(game.core.events.scheduler.record())
    result, receipts = force(game, 'curfew', error=True)
    assert receipts and 'events_state' in receipts[0]
    assert result and not result[0]['ok']
    assert game.core.events.scheduler.record() == before
    assert not game.core.factions.curfew('vatside-clinics')
    assert not game.core.events.active()


def test_game_12_force_receipt_precedes_activation_and_preserves_forecast(events_game: tuple[Any, ...]) -> None:
    game, client, player = events_game
    result, receipts = force(game, 'curfew')
    assert result[0]['ok'] and receipts[0]['events_state']['plans']
    plan = next(iter(game.core.events.scheduler.plans.values()))
    assert plan.state == 'planned' and not game.core.events.active()
    assert plan.starts_at-plan.announced_at >= 5
    before = (plan.id, plan.seed, plan.where, plan.starts_at)
    advance(game, 6)
    assert game.core.factions.curfew('vatside-clinics')
    saved = game.core.events.scheduler.record()
    state = {'events': saved, 'players': [player.record()],
             'items': [item.record() for item in game.core.commerce.items.values()]}
    restored = HeadlessServer(game.core.loop.content, character_state=state, clock=game.clock)
    resumed = restored.core.events.scheduler.plans[plan.id]
    assert (resumed.id, resumed.seed, resumed.where, resumed.starts_at) == before
    assert resumed.state == 'active' and restored.core.factions.curfew('vatside-clinics')


def test_game_12_curfew_blocks_only_inbound_core_and_never_mutates_exit_locks(events_game: tuple[Any, ...]) -> None:
    game, client, player = events_game
    force(game, 'curfew')
    advance(game, 6)
    owner = game.core.events
    baseline = set(game.core.characters.sim.locked_exits)
    internal = next(e for e in game.core.world.zones['core-plaza'].template.meta.exits
                    if e.target_zone.startswith('core-'))
    outside = next(e for e in game.core.world.zones['core-plaza'].template.meta.exits
                   if not e.target_zone.startswith('core-') and e.target_zone in game.core.world.zones)
    plaza = game.core.world.zones['core-plaza']
    tile = game.core.world.free_tile(plaza.id, plaza.template.meta.spawn)
    place(game, client, plaza.id, tile)
    assert owner.travel_refusal(client.session, internal) is None
    assert owner.travel_refusal(client.session, outside) is None
    destination = game.core.world.zones[outside.target_zone]
    inbound = next(e for e in destination.template.meta.exits if e.target_zone.startswith('core-'))
    place(game, client, destination.id, game.core.world.free_tile(destination.id, inbound.tile))
    assert 'inbound Core' in owner.travel_refusal(client.session, inbound)
    assert game.core.characters.sim.locked_exits == baseline
    assert not plaza.allows_hostile(tile)


def test_game_12_surge_provider_changes_only_cantor_beneficial_effects(events_game: tuple[Any, ...]) -> None:
    game, client, player = events_game
    player.archetype = 'cantor'
    hymn = game.core.loop.content.hymns['hymn_steady']
    base = dict(hymn.effect)
    assert game.core.combat.ability_effect(player, hymn) == base
    force(game, 'choir-surge')
    advance(game, 6)
    effect = game.core.combat.ability_effect(player, hymn)
    assert effect['shock'] == pytest.approx(base['shock']*1.3)
    assert hymn.effect == base
    player.archetype = 'ghost'
    assert game.core.combat.ability_effect(player, hymn) == base
    player.archetype = 'cantor'
    damage = next(h for h in game.core.loop.content.hymns.values() if h.kind == 'dissonance')
    assert game.core.combat.ability_effect(player, damage) == damage.effect


def test_game_12_cancel_is_saved_then_removes_only_event_provider(events_game: tuple[Any, ...]) -> None:
    game, client, player = events_game
    force(game, 'curfew')
    advance(game, 6)
    owner = game.core.events
    plan = next(iter(owner.scheduler.plans.values()))
    locks = game.core.characters.sim.locked_exits
    locks.add(('fixture-service-zone', 'fixture-service-exit'))
    result: list[Any] = []
    owner.admin('event.cancel', {'plan': plan.id}, result.append)
    game.step()
    assert owner.curfew('core-plaza')
    game.commit_commerce()
    assert result[0]['ok'] and not owner.curfew('core-plaza')
    assert ('fixture-service-zone', 'fixture-service-exit') in locks
    cancelled = owner.scheduler.plans[plan.id]
    assert cancelled.state == 'cancelled' and cancelled.revision > plan.revision


def test_game_12_preview_never_rolls_and_requires_actual_kin(events_game: tuple[Any, ...]) -> None:
    game, client, player = events_game
    force(game, 'choir-surge')
    before = deepcopy(game.core.events.scheduler.record())
    assert game.core.events.preview(player, 'choir') is None
    player.faction, player.standing['choir'] = 'choir', 90
    offer = game.core.events.preview(player, 'choir')
    assert offer and offer.plan_id in game.core.events.scheduler.plans
    assert offer.revision == game.core.events.scheduler.plans[offer.plan_id].revision
    assert game.core.events.scheduler.record() == before
    player.standing['choir'] = 70
    assert game.core.events.preview(player, 'choir') is None


def test_game_12_slow_commit_cannot_shorten_published_force_warning(events_game: tuple[Any, ...]) -> None:
    game, client, player = events_game
    result: list[Any] = []
    owner = game.core.events
    owner.admin('event.force', {'event': 'curfew'}, result.append)
    game.step()
    game.clock.advance(6*TICK_HZ)  # A deliberately delayed storage acknowledgement.
    game.commit_commerce()
    assert result[0]['ok'] and not owner.curfew('core-plaza')
    advance(game, 4)
    assert not owner.curfew('core-plaza')
    advance(game, 1.1)
    assert owner.curfew('core-plaza')
