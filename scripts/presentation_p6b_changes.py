"""B3: list only the authorized golden and candidate fingerprint changes.

Updating a test expectation proposes a baseline; it grants no owner gate.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT), str(ROOT/'scripts')]

from blacksite.content.loader import load_content
from p6_cell_diff import cells
from tests.presentation.mechanics import fingerprint
from tests.presentation.snapshots import canonical

BASE = '54adc53c6686eb5b2430f2e90cd457a09332b833'
# Presentation lead's published fixed-post data, signed off on #126.
CONTENT = 'f69541473704f1164cd5b5e8dbd315c2fa811504'
ZONES = ('core-plaza', 'sodium-row', 'vatside-clinics')
# Freeze this B3 exception at its reviewed candidates. A future rebaseline
# needs an explicit update, rather than inheriting a six-file blank cheque.
GOLDEN_SHA256 = {
    '132x50_16': '7940fac0fb30fff556aea4659c4803cc9baf7097b356aa2f1d8fa09cbc5900e5',
    '132x50_256': 'df410386b6ae60a42058adf3bb82435218bee1a210d2b23501ba8ec924e461df',
    '132x50_truecolor': 'c2f7294131f68ec828161bedcb949340ff1a52d844be68a795eb978ec7bd8d59',
    '80x24_16': '72343d9bbf3fa68d9357d5f31c4ce6b3b8898957285bb05a69a576dd31a223da',
    '80x24_256': 'b0fd55109d9b3f7c96a9ca719afe6cbdab72996fcf57d47ccb809686d8b636ef',
    '80x24_truecolor': '44d5a7ab3fa6c371c74ab8c2a5635067e2f260a09f6101d2a7babdd91e41a91b',
}
PINNED_GOLDENS = {f'tests/presentation/golden/p5/zone_{key}.json': value
                  for key,value in GOLDEN_SHA256.items()}
ALLOWED = frozenset(PINNED_GOLDENS)
MECHANICS = 'tests/presentation/mechanics.json'


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', *args], cwd=ROOT)


def report(base: str, content_ref: str, propose: bool) -> dict[str, Any]:
    if not all(re.fullmatch('[0-9a-f]{40}', value) for value in (base, content_ref)):
        raise ValueError('baseline/content refs must be full Git ids')
    git('merge-base','--is-ancestor',content_ref,'HEAD')
    data_changes = git('diff','--name-only',content_ref,'--','src/blacksite/content').decode().splitlines()
    if any(not path.endswith('.py') for path in data_changes):
        raise ValueError('presentation-owned content was modified')
    old = json.loads(git('show',f'{base}:{MECHANICS}'))
    new = json.loads(canonical(fingerprint(load_content(ROOT/'src/blacksite/content'))))
    if {k:v for k,v in old.items() if k not in ('projection','sha256')} != {
            k:v for k,v in new.items() if k not in ('projection','sha256')}:
        raise ValueError('mechanics walk/policy/schema changed')
    before,after = old['projection'],new['projection']
    if {k:v for k,v in before.items() if k!='zones'} != {k:v for k,v in after.items() if k!='zones'}:
        raise ValueError('non-zone mechanics changed')
    if set(before['zones']) != set(after['zones']):
        raise ValueError('zone set changed')
    changed = sorted(zid for zid in before['zones'] if before['zones'][zid]!=after['zones'][zid])
    if changed != list(ZONES):
        raise ValueError(f'fingerprint must move for exactly the three charted zones: {changed}')
    zone_rows = []
    for zid in changed:
        a,b = before['zones'][zid],after['zones'][zid]
        if {k:v for k,v in a.items() if k not in ('charted','public')} != {
                k:v for k,v in b.items() if k not in ('charted','public')}:
            raise ValueError(f'{zid}: mechanics beyond charting changed')
        zone_rows.append({'zone':zid,'fields':['charted','public'],
                          'charted_before':a.get('charted',False),'charted_after':b.get('charted',False),
                          'public_rectangles_before':len(a.get('public',[])),
                          'public_rectangles_after':len(b.get('public',[]))})
    if not propose and json.loads((ROOT/MECHANICS).read_text(encoding='utf-8')) != new:
        raise ValueError('candidate mechanics fixture differs; use --propose-baseline explicitly')
    paths = git('diff','--name-only',base,'--','tests/presentation/golden','tests/door/golden').decode().splitlines()
    if set(paths) != ALLOWED:
        raise ValueError(f'expected exactly the six B3 zone goldens: {paths}')
    goldens = []
    for path in paths:
        a_bytes,b_bytes = git('show',f'{base}:{path}'),(ROOT/path).read_bytes()
        if sha256(b_bytes).hexdigest() != PINNED_GOLDENS[path]:
            raise ValueError(f'{path}: differs from the frozen B3 candidate; rebaseline requires explicit review')
        a,b = json.loads(a_bytes),json.loads(b_bytes)
        if (a['width'],a['height']) != (b['width'],b['height']):
            raise ValueError(f'{path}: dimensions changed')
        changed_cells,rows = 0,[]
        for y in range(a['height']):
            count = sum(old_cell!=new_cell for old_cell,new_cell in zip(cells(a,y),cells(b,y)))
            if count:
                rows.append(y)
                changed_cells += count
        goldens.append({'path':path,'before_sha256':sha256(a_bytes).hexdigest(),
                        'after_sha256':sha256(b_bytes).hexdigest(),
                        'changed_cells':changed_cells,'changed_rows':rows})
    if propose:
        (ROOT/MECHANICS).write_text(canonical(new),encoding='utf-8',newline='\n')
    return {'baseline':base,'content_owner_head':content_ref,'owner_fingerprint_approval':False,
            'h1_granted':False,'s25_layout_approval':False,
            'fingerprint':{'before':old['sha256'],'candidate':new['sha256'],'zones':zone_rows,
                           'geometry_rules_exits_objects_walk':'unchanged'},
            'goldens':goldens,'all_other_goldens':'byte-identical'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',default=BASE)
    parser.add_argument('--content-ref',default=CONTENT)
    parser.add_argument('--propose-baseline',action='store_true',
                        help='Write the candidate fixture; commit it before native acceptance. Grants no owner approval.')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('preserve existing evidence; choose a new output')
    result = report(args.baseline,args.content_ref,args.propose_baseline)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'changed_goldens':len(result['goldens']),
                      'fingerprint_zones':[r['zone'] for r in result['fingerprint']['zones']],
                      'owner_approval':False}))
