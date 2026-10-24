"""Architecture 15.2/game 12: unavailable sources cannot stop the city."""

from typing import Any

import pytest

from blacksite.content.schema import Effect, EventTemplate, ObjectSpec, Region
from blacksite.server.clock import TICK_HZ
from blacksite.server.rules.events import ROLL_SECONDS, SCHEDULES
from blacksite.server.world.zone import ObjectState
from tests.server.test_event_engine import base_content, events_game


def test_arch_15_2_unusable_candidate_saves_roll_boundary_without_publishing_a_forecast(events_game: tuple[Any, ...]) -> None:
    game, caller, player = events_game
    owner = game.core.events
    zone = owner.world.zones['vatside-clinics']
    tile = next(obj.spec.tile for obj in zone.objects.values())
    owner.content.events.clear()
    owner.content.events['exhale'] = EventTemplate('exhale', 'Exhale', (zone.id,), *SCHEDULES['exhale'],
        effects=(Effect('hazard', zone=zone.id, region=Region(*tile, 1, 1), warning_seconds=5),))
    game.clock.advance(ROLL_SECONDS*TICK_HZ)
    game.step()  # A reserved object occupies the only authored candidate.
    assert owner.commerce.pending
    assert not owner.scheduler.reserved()
    game.commit_commerce()
    assert owner.scheduler.last_roll == int(owner.now()//ROLL_SECONDS)
    assert not owner.scheduler.plans
    assert len(owner.diagnostics) == 1 and owner.diagnostics[0]['phase'] == 'reserve'
    game.step(20)
    game.commit_commerce()
    assert len(owner.diagnostics) == 1 and not caller.session.closed


@pytest.mark.parametrize('failed_save', [False, True])
def test_arch_15_2_missing_start_source_cancels_only_after_commit_without_claiming_rewards(events_game: tuple[Any, ...], failed_save: bool) -> None:
    game, caller, player = events_game
    owner = game.core.events
    zone = owner.world.zones['vatside-clinics']
    marker = 'fixture-event-field'
    zone.objects[marker] = ObjectState(ObjectSpec(marker, zone.template.meta.spawn, 'salvage_field', params={'ring': 1}))
    template = EventTemplate('ring-fall', 'Ring-fall', (zone.id,), *SCHEDULES['ring-fall'],
        effects=(Effect('salvage', zone=zone.id, params={'count': 10, 'cap': 40}),))
    owner.content.events[template.id] = template
    draft = owner.scheduler.fork()
    plan = draft.reserve(template, owner.now(), 319, owner.eligible, forced=True)
    owner.effects.allocate(draft, plan)
    owner.jobs.allocate(draft, plan)
    assert owner.write(draft, [])
    game.commit_commerce()
    original = owner.scheduler.record()
    del zone.objects[marker]
    game.clock.advance(6*TICK_HZ)
    game.step()
    assert owner.scheduler.plans[plan.id].state == 'planned'
    game.commit_commerce(error=failed_save)
    if failed_save:
        assert owner.scheduler.record() == original
        game.step(10)
        game.commit_commerce()
    corrected = owner.scheduler.plans[plan.id]
    assert corrected.state == 'cancelled' and corrected.revision > plan.revision
    assert 'site becomes unavailable' in corrected.cancel_reason
    assert not corrected.reward_receipts
    assert not any(node.get('event') == plan.id for field in game.core.salvage.state['zones'].values()
                   for node in field['nodes'].values())
    assert any(row['phase'] == 'start' and row['plan_id'] == plan.id for row in owner.diagnostics)
    game.step(10)
    game.commit_commerce()
    assert not caller.session.closed
