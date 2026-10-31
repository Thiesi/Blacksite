"""B2 causal control changes origin only and restores it on failure."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from blacksite.door.present import zone
from scripts import presentation_p6b as b2


def test_control_matches_activity_workload_and_restores_origin(monkeypatch) -> None:
    original = zone.origin
    old = object()
    content = object()
    row = {'cpu_s_per_minute': 1., 'initial_view': {}, 'final_view': {},
           'successful_moves': 4, 'ticks': 120, 'key_steps': 4}
    current = {'activities': {what: deepcopy(row) for what in b2.MIX}, 'cpu_s_per_hour': 70.}
    monkeypatch.setattr(b2.subprocess, 'check_output', lambda *a, **k: b'baseline')
    monkeypatch.setattr(b2, 'module', lambda *a: SimpleNamespace(origin=old))
    def activity(tree, width, height, tier, what, seconds, **kwargs):
        assert zone.origin is old and tree is content
        assert (width, height, tier, seconds) == (132, 50, '256', 12.)
        assert kwargs == {'presentation': True, 'fully_known': True,
                          'zone': 'vatside-clinics', 'start': (36, 17)}
        return deepcopy(row)
    monkeypatch.setattr(b2, 'activity', activity)
    report = b2.origin_control(content, 'vatside-clinics', (36, 17), (132, 50), '256', 12., current)
    assert report['matched_workloads'] and report['a7_minus_old_s_per_hour'] == 10.
    assert zone.origin is original
    def fail(*args, **kwargs):
        raise RuntimeError('measurement interrupted')
    monkeypatch.setattr(b2, 'activity', fail)
    with pytest.raises(RuntimeError, match='measurement interrupted'):
        b2.origin_control(content, 'vatside-clinics', (36, 17), (132, 50), '256', 12., current)
    assert zone.origin is original
