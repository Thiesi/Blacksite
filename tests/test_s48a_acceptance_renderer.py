"""S48a: every NetBBS acceptance results file names the renderer that ran."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from acceptance_renderer import stamp  # noqa: E402


def test_s48a_result_and_results_files_are_stamped(tmp_path):
    (tmp_path / 'result.json').write_text(json.dumps({'passed': True}), encoding='utf-8')
    (tmp_path / 's44-results.json').write_text(json.dumps({'passed': True}), encoding='utf-8')
    (tmp_path / 'native-client.json').write_text(json.dumps({'version': 'x'}), encoding='utf-8')
    assert {p.name for p in stamp(tmp_path, 'legacy', 0)} == {'result.json', 's44-results.json'}
    assert json.loads((tmp_path / 'result.json').read_text(encoding='utf-8'))['renderer_ran'] == 'legacy'
    assert 'renderer_ran' not in json.loads((tmp_path / 'native-client.json').read_text(encoding='utf-8'))


def test_s48a_a_stamp_already_there_is_kept(tmp_path):
    (tmp_path / 'p8-results.json').write_text(json.dumps({'renderer_ran': 'present'}), encoding='utf-8')
    assert stamp(tmp_path, 'legacy', 0) == []
    assert json.loads((tmp_path / 'p8-results.json').read_text(encoding='utf-8'))['renderer_ran'] == 'present'


def test_s48a_a_half_written_file_is_skipped_not_raised(tmp_path):
    (tmp_path / 'result.json').write_text('{"passed": tr', encoding='utf-8')
    (tmp_path / 'x-results.json').write_text(json.dumps({'passed': True}), encoding='utf-8')
    assert [p.name for p in stamp(tmp_path, 'present', 0)] == ['x-results.json']


def test_s48a_a_file_from_an_earlier_run_is_not_stamped(tmp_path):
    import os
    old = tmp_path / 'result.json'
    old.write_text(json.dumps({'passed': True}), encoding='utf-8')
    os.utime(old, (1000, 1000))
    new = tmp_path / 's44-results.json'
    new.write_text(json.dumps({'passed': True}), encoding='utf-8')
    assert [p.name for p in stamp(tmp_path, 'present', 2000)] == ['s44-results.json']
    assert 'renderer_ran' not in json.loads(old.read_text(encoding='utf-8'))
