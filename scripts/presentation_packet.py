"""Build P1 review packets from the existing production-path golden cases."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CASES = ['tests/door/test_display.py::test_golden_screens',
    'tests/door/test_zone_render.py::test_golden_zone_and_wide_name',
    'tests/door/test_wake_render.py::test_wake_golden_wide_name_scroll_and_character_sheet',
    'tests/door/test_lattice_render.py::test_design_ui_3_all_eleven_layouts_no_overlap_and_wide_peer',
    'tests/door/test_encounter_render.py::test_ui_3_encounter_warnings_costs_and_escape_remain_visible']


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--strict-cp437', action='store_true', help='Fail on every non-round-tripping cell, including user text')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('output must be a new or empty directory (preserve prior evidence)')
    output.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PYTHONPATH': str(ROOT/'src')+os.pathsep+str(ROOT)}
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', *CASES,
        '--review-packet', str(output), '--basetemp', str(output/'pytest-temp')], cwd=ROOT, env=env)
    if result.returncode:
        return result.returncode
    contexts = [json.loads(p.read_text(encoding='utf-8')) for p in output.glob('*/*/*/context.json')]
    expected = {(p.stem, tier) for p in (ROOT/'tests/door/golden').glob('*.txt')
                for tier in ('16', '256', 'truecolor')}
    actual = {(c['scenario'], c['colour_tier']) for c in contexts}
    if actual != expected or len(contexts) != len(expected):
        raise RuntimeError('review packet does not cover exactly every existing golden and colour tier')
    failed = [{'scenario': c['scenario'], 'tier': c['colour_tier'],
        'problems': c['cp437_problems']} for c in contexts if not c['cp437_pass']]
    summary = {'schema': 1, 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
        'cases': len(contexts), 'glyph_style_pass': True, 'cp437_pass': not failed,
        'cp437_failures': failed, 'human_approval': False,
        'cp437_policy': 'all rendered cells; no exemptions; existing failures remain visible pending #76'}
    (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'cases': len(contexts), 'cp437_pass': not failed, 'failed_cases': len(failed)}))
    return 2 if args.strict_cp437 and failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
