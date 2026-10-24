"""Game 12: saved forecasts and bounded, restart-safe schedules."""

from dataclasses import replace
import json

import pytest

from blacksite.content.schema import Effect, EventTemplate, EventVariant, Route, Waypoint
from blacksite.server.events import Scheduler
from blacksite.server.rules.events import (
    ADVANCE_SECONDS, BEACON_SECONDS, CURFEW_HEAT, EXHALE_RATE,
    MAX_RESERVED, ROLL_SECONDS, SCHEDULES, SURGE_MAGNITUDE, WARNING_SECONDS,
)


def template(name: str = 'ring-fall', where: tuple[str, ...] = ('ring-1',),
             **kwargs: object) -> EventTemplate:
    return EventTemplate(name, name, where, *SCHEDULES[name], **kwargs)


def eligible(event: EventTemplate, where: tuple[str, ...]) -> bool:
    return True


def test_game_12_schedule_numbers() -> None:
    assert (ROLL_SECONDS, ADVANCE_SECONDS, MAX_RESERVED, WARNING_SECONDS, BEACON_SECONDS) == (1200, 3600, 2, 5, 300)
    assert (SURGE_MAGNITUDE, CURFEW_HEAT, EXHALE_RATE) == (1.3, 2, 3)
    assert dict(SCHEDULES) == {
        'ring-fall': (1200, 5400, 5), 'curfew': (3600, 14400, 2),
        'choir-surge': (900, 10800, 2), 'exhale': (1800, 7200, 3),
        'convoy': (1500, 3600, 4),
    }


def test_game_12_seeded_ring_and_variant_survive_json_restart() -> None:
    event = template(where=('ring-1', 'ring-2'), selection='one',
        effects=(Effect('salvage', zone='ring-1'), Effect('salvage', zone='ring-2')),
        variants=(EventVariant('first', (Effect('reveal', zone='ring-1'),)),
                  EventVariant('second', (Effect('reveal', zone='ring-2'),))))
    one, two = Scheduler('origin', {event.id: event}, {}), Scheduler('origin', {event.id: event}, {})
    a, b = one.roll(1200, eligible), two.roll(1200, eligible)
    assert a is not None and b is not None and a == b
    assert len(a.where) == 1 and a.starts_at == 4800 and a.ends_at == 6000
    assert len(a.variant_ids) == 1
    assert all(effect.zone == a.where[0] for effect in one.effects(a))
    saved = json.loads(json.dumps(one.record()))
    restored = Scheduler('origin', {event.id: event}, {}, saved)
    assert restored.record() == one.record()
    assert restored.roll(1201, eligible) is None
    assert restored.plans[a.id].where == a.where
    assert restored.plans[a.id].variant_ids == a.variant_ids


def test_game_12_reservations_include_future_route_and_two_plan_cap() -> None:
    ring = template(where=('ring-1',))
    convoy = template('convoy', ('ring-2',), route='road')
    curfew = template('curfew', ('core',))
    surge = template('choir-surge', ('sector',))
    road = Route('road', (Waypoint('ring-1', (1, 1)), Waypoint('ring-2', (2, 2))), 1)
    scheduler = Scheduler('origin', {e.id: e for e in (ring, convoy, curfew, surge)}, {'road': road})
    scheduler.reserve(ring, 0, 1, eligible)
    with pytest.raises(ValueError, match='scope'):
        scheduler.reserve(convoy, 0, 2, eligible)
    scheduler.reserve(curfew, 0, 3, eligible)
    with pytest.raises(ValueError, match='scope'):
        scheduler.reserve(surge, 0, 4, eligible)
    assert len([p for p in scheduler.plans.values() if p.live]) == 2


def test_game_12_cooldown_begins_at_completion_and_no_reroll_on_restart() -> None:
    event = template()
    scheduler = Scheduler('origin', {event.id: event}, {})
    plan = scheduler.reserve(event, 0, 1, eligible)
    assert not scheduler.cooldowns
    scheduler.advance(plan.ends_at, eligible)
    assert plan.state == 'complete'
    assert scheduler.cooldowns[event.id] == plan.ends_at+event.cooldown_seconds
    restored = Scheduler('origin', {event.id: event}, {}, scheduler.record())
    assert not restored.available(event, plan.ends_at+event.cooldown_seconds-1, eligible)
    assert restored.available(event, plan.ends_at+event.cooldown_seconds, eligible)
    assert restored.plans[plan.id] == plan


def test_game_12_force_warns_then_start_mid_end_once() -> None:
    event = template('curfew', ('core',))
    scheduler = Scheduler('origin', {event.id: event}, {})
    plan = scheduler.reserve(event, 0, 1, eligible, forced=True)
    assert plan.starts_at == 5
    assert [t.kind for t in scheduler.advance(0, eligible)] == ['warning']
    assert not scheduler.advance(4.9, eligible)
    assert [t.kind for t in scheduler.advance(5, eligible)] == ['start']
    assert not scheduler.advance(5, eligible)
    assert [t.kind for t in scheduler.advance(1805, eligible)] == ['mid']
    assert not scheduler.advance(1806, eligible)
    assert [t.kind for t in scheduler.advance(3605, eligible)] == ['end']
    assert not scheduler.advance(3606, eligible)


def test_game_12_longer_authored_warning_is_respected() -> None:
    event = template(effects=(Effect('hazard', zone='ring-1', warning_seconds=12),))
    scheduler = Scheduler('origin', {event.id: event}, {})
    plan = scheduler.reserve(event, 10, 1, eligible, forced=True)
    assert plan.starts_at == 22
    assert [t.kind for t in scheduler.advance(10, eligible)] == ['warning']
    assert not scheduler.advance(21, eligible)
    assert [t.kind for t in scheduler.advance(22, eligible)] == ['start']


def test_game_12_restart_past_expiry_never_replays_start_mid_or_rewards() -> None:
    event = template()
    scheduler = Scheduler('origin', {event.id: event}, {})
    plan = scheduler.reserve(event, 0, 1, eligible)
    restored = Scheduler('origin', {event.id: event}, {}, scheduler.record())
    assert [t.kind for t in restored.advance(20000, eligible)] == ['end']
    assert not restored.plans[plan.id].claim('salvage-wave')
    assert not restored.advance(20001, eligible)
    # A late roll reserves one future event, without replaying missed slots.
    future = restored.roll(20000, eligible)
    assert future is not None and future.starts_at == 23600
    assert restored.roll(20001, eligible) is None


def test_game_12_cancel_is_a_revisioned_forecast_correction() -> None:
    event = template()
    scheduler = Scheduler('origin', {event.id: event}, {})
    plan = scheduler.reserve(event, 0, 1, eligible)
    old_scope, old_seed = plan.where, plan.seed
    correction = scheduler.cancel(plan.id, 100, 'Road closed.')
    assert correction.kind == 'cancel' and plan.state == 'cancelled'
    assert plan.revision == 2 and plan.cancel_reason == 'Road closed.'
    assert (plan.where, plan.seed) == (old_scope, old_seed)
    assert event.id not in scheduler.cooldowns
    with pytest.raises(ValueError, match='closed'):
        scheduler.cancel(plan.id, 101, 'Again.')


def test_game_12_active_cancel_uses_actual_completion_time() -> None:
    event = template()
    scheduler = Scheduler('origin', {event.id: event}, {})
    plan = scheduler.reserve(event, 0, 1, eligible, forced=True)
    scheduler.advance(5, eligible)
    scheduler.cancel(plan.id, 25, 'Operator cancellation.')
    assert scheduler.cooldowns[event.id] == 25+event.cooldown_seconds


@pytest.mark.parametrize('change', ['scope', 'variant', 'template'])
def test_game_12_invalidated_content_cancels_without_moving_forecast(change: str) -> None:
    event = template(variants=(EventVariant('pulse', (Effect('reveal', zone='ring-1'),)),))
    templates = {event.id: event}
    scheduler = Scheduler('origin', templates, {})
    plan = scheduler.reserve(event, 0, 1, eligible)
    if change == 'scope':
        templates[event.id] = replace(event, where=('ring-2',))
    elif change == 'variant':
        templates[event.id] = replace(event, variants=())
    else:
        templates.clear()
    assert [t.kind for t in scheduler.advance(5, eligible)] == ['cancel']
    assert plan.where == ('ring-1',) and plan.variant_ids == ('pulse',)
    assert plan.cancel_reason and plan.revision == 2


def test_arch_15_2_failed_proposal_preserves_plan_and_reward_receipts() -> None:
    event = template()
    scheduler = Scheduler('origin', {event.id: event}, {})
    plan = scheduler.reserve(event, 0, 1, eligible, forced=True)
    draft = scheduler.fork()
    draft.advance(5, eligible)
    assert draft.plans[plan.id].claim('salvage-wave')
    assert not draft.plans[plan.id].claim('salvage-wave')
    assert plan.state == 'planned' and not plan.reward_receipts
    committed = draft
    assert committed.plans[plan.id].reward_receipts == ['salvage-wave']
    next_draft = committed.fork()
    next_draft.cancel(plan.id, 10, 'Done.')
    assert committed.plans[plan.id].state == 'active'


def test_game_12_inactive_scopes_are_not_scheduled() -> None:
    ring, curfew = template(), template('curfew', ('core',))
    scheduler = Scheduler('origin', {e.id: e for e in (ring, curfew)}, {})
    plan = scheduler.roll(0, lambda event, where: where == ('core',))
    assert plan is not None and plan.template == 'curfew'
    assert scheduler.last_roll == 0
    assert scheduler.roll(1200, lambda event, where: False) is None
    assert scheduler.last_roll == 1
