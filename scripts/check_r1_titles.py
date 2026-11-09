"""Verify the six explicitly approved P5 title-only golden changes.

Reads the pre-R1 Git objects and the new files. It never writes a golden.
Every other glyph, cell rendition, palette and geometry field must match.
"""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OLD = 'BLACKSITE'  # Historical title, compared under #193/6738034888.
NEW = 'KARST 41'


def expand(row: list[list[int]]) -> list[int]:
    return [style for count, style in row for _ in range(count)]


def pack(row: list[int]) -> list[list[int]]:
    result: list[list[int]] = []
    for style in row:
        if result and result[-1][1] == style:
            result[-1][0] += 1
        else:
            result.append([1, style])
    return result


def check(base: str) -> dict[str, Any]:
    cases = []
    for width, height in ((80, 24), (132, 50)):
        for tier in ('16', '256', 'truecolor'):
            path = f'tests/presentation/golden/p5/title_{width}x{height}_{tier}.json'
            before = subprocess.check_output(['git', 'show', base+':'+path], cwd=ROOT)
            after = (ROOT/path).read_bytes()
            old, actual = json.loads(before), json.loads(after)
            expected = deepcopy(old)
            for y in (0, 1):
                glyphs = old['glyph_rows'][y]
                assert glyphs.count(OLD) == 1, path
                start = glyphs.index(OLD)
                styles = expand(old['style_rows'][y])
                changed = glyphs.replace(OLD, NEW, 1)
                del styles[start+len(OLD)-1]
                if y == 0:
                    old_fill = glyphs.index('═SAFE')+len('═SAFE')
                    fill = changed.index('═SAFE')+len('═SAFE')
                    assert glyphs[old_fill] == '═'
                    style = expand(old['style_rows'][y])[old_fill]
                    changed = changed[:fill]+'═'+changed[fill:]
                else:
                    fill = start+len(NEW)
                    style = expand(old['style_rows'][y])[start+len(OLD)]
                    changed = changed[:fill]+' '+changed[fill:]
                styles.insert(fill, style)
                expected['glyph_rows'][y] = changed
                expected['style_rows'][y] = pack(styles)
            assert expected == actual, f'{path}: difference beyond title and fill'
            cases.append({'file': path, 'before_sha256': sha256(before).hexdigest(),
                'after_sha256': sha256(after).hexdigest(), 'changed_rows': [0, 1],
                'changed_runs': [{'row': y, 'before': old['style_rows'][y],
                                 'after': actual['style_rows'][y]} for y in (0, 1)],
                'title_and_fill_only': True, 'palette_unchanged': True,
                'rectangles_and_other_cells_unchanged': True})
    return {'base': base, 'passed': True, 'cases': cases}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='7597dce6f1263a27421c51ec97cff1b0b91b6f68')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = check(args.base)
    encoded = json.dumps(report, indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded)
