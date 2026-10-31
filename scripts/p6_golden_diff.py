"""Prove the narrow P6a golden exception recorded on #115/6536245124."""

import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def report(base: str) -> dict[str, object]:
    changed = subprocess.check_output(['git', 'diff', '--name-only', base, '--',
        'tests/presentation/golden'], cwd=ROOT, text=True).splitlines()
    expected = {f'tests/presentation/golden/p5/zone_{size}_{tier}.json'
                for size in ('80x24', '132x50') for tier in ('16', '256', 'truecolor')}
    rows = []
    for path in changed:
        if path.startswith('tests/presentation/golden/p6/'):
            continue
        assert path in expected, f'Unapproved existing golden change: {path}'
        before = json.loads(subprocess.check_output(['git', 'show', f'{base}:{path}'], cwd=ROOT))
        after = json.loads((ROOT/path).read_text(encoding='utf-8'))
        assert (before['width'], before['height']) == (after['width'], after['height'])
        def cells(frame, y):
            return [frame['styles'][style] for count, style in frame['style_rows'][y] for _ in range(count)]
        differences = [y for y in range(before['height'])
                       if before['glyph_rows'][y] != after['glyph_rows'][y] or cells(before,y) != cells(after,y)]
        # Existing zone fixtures have no notice and exactly one HERE row.
        assert differences == [2], (path, differences)
        assert before['glyph_rows'][-2] == after['glyph_rows'][-2], 'Hint changed'
        rows.append({'path': path, 'rows_zero_based': differences,
                     'before': before['glyph_rows'][2], 'after': after['glyph_rows'][2]})
    assert {row['path'] for row in rows} == expected
    return {'base': base, 'allowed_by': 'issue 115 comment 6536245124',
            'existing_goldens_changed': rows, 'verdict': 'Only the six HERE rows moved; all other cells and styles unchanged.'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='51cc5dba185662363fe1cf7541a80757ea21ff6d')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    value = report(args.base)
    text = json.dumps(value, ensure_ascii=False, indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8', newline='\n')
    print(text)


if __name__ == '__main__':
    main()
