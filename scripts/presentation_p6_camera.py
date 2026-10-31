"""A7: paired B2 frame/terrain measurements on pinned shipped P6b data.

Both arms run the same P1 frames() method and live seeded population.
Only origin() differs. Instrumented terrain timings are not CPU s/hour.
"""

import argparse
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns, process_time_ns
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]

from blacksite.content.loader import ContentTree, load_content
from blacksite.door.present import zone
from blacksite.door.present.places import Places
from presentation_p6_validation import git, module, snapshot
from tests.presentation import budget

BASE = 'fd4020e7eaa413301145eca969333f2239a6cfcf'
INPUT = '0c4b19db5152c159601fafe63d55743549cc2474'
SOURCE = 'src/blacksite/door/present/zone.py'
STARTS = {'core-plaza':(41,26),'vatside-clinics':(36,17),'sodium-row':(46,14)}


def measure(content: ContentTree, zid: str, tier: str, known: bool, origin: Any) -> dict[str, Any]:
    counts = {'cells':0}
    timings: list[dict[str,float | int]] = []
    origins: list[tuple[int,int]] = []
    callers = []
    original_cell, original_terrain, original_caller = Places.cell, zone.terrain, budget.Caller

    def cell(self: Places, *args: Any, **kwargs: Any) -> Any:
        counts['cells'] += 1
        return original_cell(self,*args,**kwargs)

    def terrain(*args: Any, **kwargs: Any) -> None:
        start, cpu, cells = perf_counter_ns(),process_time_ns(),counts['cells']
        original_terrain(*args,**kwargs)
        timings.append({'cells':counts['cells']-cells,'wall_ms':(perf_counter_ns()-start)/1e6,
                        'cpu_ms':(process_time_ns()-cpu)/1e6})

    def position(*args: Any) -> tuple[int,int]:
        at = origin(*args)
        origins.append(at)
        return at

    class Caller(original_caller):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args,**kwargs)
            callers.append(self)
            counts['cells'] = 0
            timings.clear()
            origins.clear()  # Exclude creation/handshake and initial draw.

    with patch.object(Places,'cell',cell),patch.object(zone,'terrain',terrain),\
            patch.object(zone,'origin',position),patch.object(budget,'Caller',Caller):
        sample = budget.frames(content,132,50,tier,presentation=True,fully_known=known,
                               zone=zid,start=STARTS[zid])
    caller = callers[0]
    return {'frames':sample['summary'],'successful_moves':sample['successful_moves'],
            'end_position':caller.avatar.actor.position,'viewport':caller.avatar.perception.viewport,
            'origin_changes':sum(a!=b for a,b in zip(origins,origins[1:])),
            'terrain_cells':counts['cells'],'terrain_calls':len(timings),
            'terrain_wall_ms':budget.stats([r['wall_ms'] for r in timings]),
            'terrain_cpu_ms':sum(r['cpu_ms'] for r in timings),
            'delta_16kib_pass':sample['delta_16kib_pass'],
            'render_p95_100ms_pass':sample['render_p95_100ms_pass']}


def run(input_ref: str) -> dict[str, Any]:
    if not re.fullmatch('[0-9a-f]{40}',input_ref):
        raise ValueError('input-ref must be a full pinned Git object id')
    old = module('_a7_baseline_zone',git('show',f'{BASE}:{SOURCE}')).origin
    result = {'head':git('rev-parse','HEAD').decode().strip(),'baseline':BASE,'input_ref':input_ref,
              'dirty':bool(git('status','--porcelain').strip()),'platform':platform.platform(),
              'python':sys.version,'size':[132,50],'method':'unchanged P1 frames(), B2 starts, '
              '80 ten-Hz ticks, 40 walking keys, live shipped NPCs, 30 warm-up ticks; '
              'terrain wrapper counts Places.cell calls, excludes initial draw',
              'boundary':'paired Display frames and zone.terrain only; no hourly CPU verdict',
              'cpu_120s_per_hour_verdict':None,'cases':[]}
    with TemporaryDirectory(prefix='blacksite-a7-') as temporary:
        data = Path(temporary)/'content'
        result['input_files_sha256'] = snapshot(data,input_ref)
        content = load_content(data)
        for zid in STARTS:
            for tier in ('16','256','truecolor'):
                for known in (False,True):
                    before = measure(content,zid,tier,known,old)
                    after = measure(content,zid,tier,known,zone.origin)
                    case = {'zone':zid,'tier':tier,'fully_known':known,'start':STARTS[zid],
                            'before':before,'after':after,'matched_walk':all(before[key]==after[key]
                                for key in ('successful_moves','end_position','viewport')),
                            'passed':after['origin_changes']==0 and after['delta_16kib_pass']
                                     and after['render_p95_100ms_pass']}
                    result['cases'].append(case)
                    print(json.dumps({'zone':zid,'tier':tier,'known':known,
                        'delta_max':[r['frames']['delta']['bytes']['max'] for r in (before,after)],
                        'terrain_cells':[r['terrain_cells'] for r in (before,after)]}),flush=True)
    result['platform_reference'] = platform.system()=='Linux' and not result['dirty']
    result['passed'] = all(case['matched_walk'] and case['passed'] for case in result['cases'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-ref',default=INPUT)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('preserve existing evidence; choose a new output')
    result = run(args.input_ref)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    if not result['passed']:
        raise SystemExit('Camera/frame check failed; measurements retained in '+str(args.output))
