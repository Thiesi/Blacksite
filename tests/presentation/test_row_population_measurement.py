"""Fixture and accounting checks; no real-time benchmark in pytest."""

from copy import deepcopy
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from scripts.measure_row_population import Group, EXTRA_TEMPLATE, fixture_content
from scripts.summarize_row_population import summarize
from tests.presentation.budget import KEYS


@pytest.mark.parametrize('callers', [1, 4])
def test_visible_stationary_extras_and_one_shared_tick(repo_root: Path, callers: int) -> None:
    content = load_content(repo_root/'src/blacksite/content')
    original = content.zones['sodium-row'].meta.spawners
    group = Group(content, 80, 12, callers, '16')
    assert all(c.game is group.game for c in group.callers)
    assert content.zones['sodium-row'].meta.spawners == original
    before = group.game.clock.now_tick()
    group.tick(1.0)
    assert group.game.clock.now_tick() == before+1
    assert group.server.calls['step'] == 1
    assert len(group.fixed_positions) == 80
    assert group.meter.cpu_ns == sum(c.meter.cpu_ns for c in group.callers)
    assert group.initial['extra_positions'] == group.fixed_positions
    if callers == 4:
        # Exercise one full P1 route without sleeps or performance sampling.
        for tick in range(1, 35):
            group.tick(1.0+tick*.101)
            if tick % 2 == 0 and tick <= 32:
                group.key(KEYS['walking where there is no scene'][tick//2-1],
                          1.0+tick*.101)
            group.draw(1.0+tick*.101)
        assert all(c.moves == 16 for c in group.callers)
        assert sum(group.moving_changes.values()) > 0


def test_nested_population_fixture_keeps_authored_posts(repo_root: Path) -> None:
    content = load_content(repo_root/'src/blacksite/content')
    fixture = fixture_content(content, 12)
    assert fixture.npcs[EXTRA_TEMPLATE].behaviours[0].kind == 'talker'
    assert fixture.npcs[EXTRA_TEMPLATE].behaviours[0].params['anchor']
    assert EXTRA_TEMPLATE not in content.npcs
    expected = [s for s in content.zones['sodium-row'].meta.spawners if s.id != 'sodium-regular']
    assert [s for s in fixture.zones['sodium-row'].meta.spawners if s.id != 'sodium-regular'] == expected


def reports() -> list[dict]:
    result = []
    for callers in (1, 4):
        for tier in ('16', '256', 'truecolor'):
            rows = []
            for stationary in (0, 20, 40, 80):
                for moving in (4, 8, 12):
                    cost = 30+stationary*.5+moving*2
                    rows.append({'stationary': stationary, 'moving': moving, 'fully_known': False,
                        'door_total_cpu_s_per_hour': callers*cost,
                        'door_mean_cpu_s_per_hour': cost, 'door_max_cpu_s_per_hour': cost,
                        'server_cpu_s_per_hour': stationary+moving*3, 'within_108': cost <= 108})
            result.append({'head': 'a'*40, 'complete': True, 'cpu_budget_reference': True,
                'seconds': 12, 'callers': callers, 'tier': tier, 'cases': rows})
    return result


def test_marginals_are_per_added_npc_per_caller_and_keep_negative_samples() -> None:
    data = reports()
    result = summarize(data)
    assert result['required_cells'] == 72
    assert {r['door_cpu_s_per_hour_per_added_npc_per_caller']
            for r in result['marginals'] if r['axis'] == 'stationary'} == {.5}
    assert {r['door_cpu_s_per_hour_per_added_npc_per_caller']
            for r in result['marginals'] if r['axis'] == 'moving'} == {2.}
    data[0]['cases'][3]['door_total_cpu_s_per_hour'] = 0
    assert any(r['door_cpu_s_per_hour_per_added_npc_per_caller'] < 0
               for r in summarize(data)['marginals'])


@pytest.mark.parametrize('problem', ['missing', 'duplicate', 'dirty', 'head'])
def test_summary_rejects_incomplete_or_mixed_evidence(problem: str) -> None:
    data = deepcopy(reports())
    if problem == 'missing':
        data[0]['cases'].pop()
    elif problem == 'duplicate':
        data[0]['cases'].append(data[0]['cases'][0])
    elif problem == 'dirty':
        data[0]['cpu_budget_reference'] = False
    else:
        data[0]['head'] = 'b'*40
    with pytest.raises(ValueError):
        summarize(data)
