"""A4: isolate looks.masked cost on the presentation lead's real geometry."""

import argparse
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'),str(ROOT)]

from blacksite.content import schema as s
from blacksite.content.formats import decode
from blacksite.content.loader import ContentTree, load_content
from blacksite.content.places import region_tiles, theme_over, DEFAULT_THEME
from blacksite.layout import compute
from blacksite.server.views.looks import masked
from tests.presentation.budget import stats


def geometry() -> tuple[ContentTree,dict[str,Any]]:
    fixture = json.loads((ROOT/'tests/fixtures/p6-mask-geometry.json').read_text(encoding='utf-8'))
    content = load_content(ROOT/'src/blacksite/content')
    content.themes = decode(s.ThemeTable,fixture['themes'])
    for zid,record in fixture['zones'].items():
        zone = content.zones[zid]
        if [zone.width,zone.height]!=record['size']:
            raise ValueError(f'{zid}: map dimensions differ from the supplied geometry')
        data = (ROOT/f'src/blacksite/content/zones/{zid}.map').read_bytes().replace(b'\r\n',b'\n')
        if sha256(data).hexdigest()!=record['map_sha256']:
            raise ValueError(f'{zid}: shipped map differs from the pinned author input')
        content.looks[zid] = decode(s.Look,{'id':zid,'theme':record['theme'],'regions':record['regions']})
    return content,fixture['source']


def measure(repeats: int) -> dict[str,Any]:
    content,source = geometry()
    bare = deepcopy(content)
    for zid,look in bare.looks.items():
        bare.looks[zid] = replace(look,regions=())
    cases = []
    for zid in ('core-plaza','sodium-row'):
        zone,look = content.zones[zid],content.looks[zid]
        themes = content.themes.themes
        base = theme_over(DEFAULT_THEME,themes[look.theme])
        for width,height in ((80,24),(132,50)):
            layout = compute(width,height)
            w,h = min(layout.viewport.width,zone.width),min(layout.viewport.height,zone.height)
            for partial in (False,True):
                whole = {(x,y) for y in range(zone.height) for x in range(zone.width)
                         if not partial or x<zone.width//2}
                windows = []
                for step in range(60):
                    ox,oy = step%max(1,zone.width-w+1),step%max(1,zone.height-h+1)
                    windows.append({(x,y) for y in range(oy,oy+h) for x in range(ox,ox+w)} & whole)
                arms = {}
                for name,tree in (('no_regions',bare),('authored_regions',content)):
                    for known in windows[:5]:
                        masked(tree,zone,known,set(),known_at=whole.__contains__)
                    samples,cpu,peak_pieces,peak_bytes = [],0,0,0
                    for step in range(repeats):
                        known = windows[step%len(windows)]
                        started,process = time.perf_counter_ns(),time.process_time_ns()
                        body = masked(tree,zone,known,set(),known_at=whole.__contains__)
                        cpu += time.process_time_ns()-process
                        samples.append((time.perf_counter_ns()-started)/1e6)
                        peak_pieces = max(peak_pieces,len(body['regions']))
                        peak_bytes = max(peak_bytes,len(json.dumps(body,separators=(',',':')).encode('utf-8')))
                        for region in body['regions']:
                            if region['theme']['pattern']=='rings':
                                shape = s.LookRegion('',rect=tuple(region['rect']) if 'rect' in region else None,
                                                     circle=tuple(region['circle']) if 'circle' in region else None)
                                if not region_tiles(shape)<=whole:
                                    raise ValueError('a whole-only region disclosed an unknown tile')
                    arms[name] = {'calls':repeats,'wall_ms':stats(samples),'cpu_ms':cpu/1e6,
                                  'peak_regions':peak_pieces,'peak_payload_bytes':peak_bytes}
                cases.append({'zone':zid,'map_size':[zone.width,zone.height],'terminal':[width,height],
                    'knowledge':'partly known' if partial else 'wholly known',
                    'regions':len(look.regions),'circles':sum(r.circle is not None for r in look.regions),
                    'whole_only':sum(theme_over(base,themes[r.theme]).pattern=='rings' for r in look.regions),
                    'arms':arms,'added_cpu_ms_per_call':(arms['authored_regions']['cpu_ms']-arms['no_regions']['cpu_ms'])/repeats})
    return {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
        'platform':platform.platform(),'source':source,
        'boundary':'looks.masked only, geometry-only; excludes view construction, codecs and door CPU',
        'method':'60 moving viewports; five warmups; paired no-region/authored-region calls; no wall-clock sleeps',
        'cpu_120s_per_hour_verdict':None,'cases':cases}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats',type=int,default=200)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if not 20<=args.repeats<=10000:
        parser.error('repeats must be between 20 and 10000')
    result = measure(args.repeats)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'cases':len(result['cases']),
        'worst_authored_mask_p95_ms':max(c['arms']['authored_regions']['wall_ms']['p95'] for c in result['cases'])}))


if __name__=='__main__':
    main()
