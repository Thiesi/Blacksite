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

BASE = 'fd4020e7eaa413301145eca969333f2239a6cfcf'
CONTENT = '0c4b19db5152c159601fafe63d55743549cc2474'
ZONES = ('core-plaza', 'sodium-row', 'vatside-clinics')
ALLOWED = {f'tests/presentation/golden/p5/zone_{size}_{tier}.json'
           for size in ('80x24','132x50') for tier in ('16','256','truecolor')}
MECHANICS = 'tests/presentation/mechanics.json'


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', *args], cwd=ROOT)


def report(base: str, content_ref: str, propose: bool) -> dict[str, Any]:
    if not all(re.fullmatch('[0-9a-f]{40}', value) for value in (base, content_ref)):
        raise ValueError('baseline/content refs must be full Git ids')
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
    if not set(paths) <= ALLOWED:
        raise ValueError(f'unassigned goldens changed: {set(paths)-ALLOWED}')
    goldens = []
    for path in paths:
        a_bytes,b_bytes = git('show',f'{base}:{path}'),(ROOT/path).read_bytes()
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
    parser.add_argument('--propose-baseline',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('preserve existing evidence; choose a new output')
    result = report(args.baseline,args.content_ref,args.propose_baseline)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'changed_goldens':len(result['goldens']),
                      'fingerprint_zones':[r['zone'] for r in result['fingerprint']['zones']],
                      'owner_approval':False}))
