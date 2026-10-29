"""Draft-only subset decisions must fail closed for broader changes."""

from pathlib import Path
import re

import pytest

from scripts.presentation_scope import full_native
from tests.presentation.budget import MIX, hourly, stats
from tests.presentation.budget import frames
from blacksite.content.loader import load_content


@pytest.mark.parametrize('paths', [
    ['src/blacksite/door/model.py'],
    ['src/blacksite/content/palette.json', 'tests/door/test_display.py'],
    ['src/blacksite/content/text/help.json'],
    ['src/blacksite/content/art/title.ans'],
])
def test_draft_presentation_subset_and_ready_full(paths: list[str]) -> None:
    assert full_native(paths, True)[0] is False
    assert full_native(paths, False)[0] is True


@pytest.mark.parametrize('paths', [[], ['tests/door/test_display.py'],
    ['src/blacksite/door/model.py', 'src/blacksite/server/world/zone.py'],
    ['src/blacksite/content/zones/sodium-row.json'],
    ['src/blacksite/door/model.py', '.github/workflows/service-acceptance.yml'],
    ['src/blacksite/door/../../server/core.py'], ['docs/design/03-terminal-ui.md']])
def test_uncertain_or_mixed_changes_keep_full_matrix(paths: list[str]) -> None:
    assert full_native(paths, True)[0] is True


def test_all_native_jobs_use_scope_and_ready_transition_runs(repo_root: Path) -> None:
    source = (repo_root/'.github/workflows/service-acceptance.yml').read_text(encoding='utf-8')
    assert 'ready_for_review' in source and 'converted_to_draft' in source
    assert "base+':scripts/presentation_scope.py'" in source
    jobs = re.split(r'^  ([a-z0-9-]+):\n', source.split('jobs:\n', 1)[1], flags=re.M)
    for name, body in zip(jobs[1::2], jobs[2::2]):
        if name != 'native-scope':
            assert 'needs: native-scope' in body
            expected = 'false' if name == 'door-subset-netbbs' else 'true'
            assert f"if: needs.native-scope.outputs.full == '{expected}'" in body


def test_budget_aggregation_uses_minutes_without_rounding() -> None:
    assert sum(MIX.values()) == 60
    assert hourly({what: {'cpu_s_per_minute': .12345} for what in MIX}) == pytest.approx(7.407)
    assert stats([1, 2, 3]) == {'count': 3, 'p50': 2, 'p95': 3, 'max': 3}
    assert stats([])['p95'] is None


def test_frame_measurement_exercises_live_input_and_both_output_classes(repo_root: Path) -> None:
    result = frames(load_content(repo_root/'src/blacksite/content'), 80, 24, '256')
    assert result['successful_moves'] > 0
    assert result['summary']['full']['bytes']['count'] > 0
    assert result['summary']['delta']['bytes']['count'] > 0
    assert all(result['calls'][method] > 0 for method in ('receive', 'key', 'update', 'render'))
