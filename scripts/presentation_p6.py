"""P6a charted fixture CPU/frames, using P1's unchanged activity method."""

import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]

from blacksite.content.loader import ContentTree, load_content
from blacksite.content.schema import Region, Zone
from blacksite.content.places import charting_problems
from blacksite.server.protocol import encode
from tests.presentation.budget import Caller, MIX, KEYS, activity, frames, hourly


def fixture_content() -> ContentTree:
    content = load_content(ROOT/'src/blacksite/content', ROOT/'tests/fixtures/p6')
    for zid in ('sodium-row','sodium-tin-halo'):
        template = content.zones[zid]
        width,height = max(120,template.width),max(50,template.height)
        grid = [['wall' if x in (0,width-1) or y in (0,height-1) else 'floor'
                 for x in range(width)] for y in range(height)]
        # Keep the real object/exit bindings, which Interlock resolves even
        # in this benchmark. The fixture only replaces terrain and traffic.
        for obj in template.meta.objects:
            grid[obj.tile[1]][obj.tile[0]] = 'floor'
        for ex in template.meta.exits:
            grid[ex.tile[1]][ex.tile[0]] = 'floor'
        excluded = {obj.tile for obj in template.meta.objects
                    if obj.kind in ('door','gate','shutter','apartment_door')}
        excluded.update(ex.tile for ex in template.meta.exits if ex.requirement is not None)
        for ex in template.meta.exits:
            if ex.hidden:
                excluded.update((ex.tile[0]+dx,ex.tile[1]+dy) for dx in (-1,0,1) for dy in (-1,0,1))
        for obj in template.meta.objects:
            if obj.housing:
                excluded.update(Region(*obj.housing.origin,6,4).tiles())
        public = []
        for y in range(height):
            start = None
            for x in range(width+1):
                if x<width and (x,y) not in excluded:
                    if start is None:
                        start = x
                elif start is not None:
                    public.append(Region(start,y,x-start,1))
                    start = None
        # Explicit benchmark-only geometry, never written to shipped data.
        meta = replace(template.meta, id=zid, name='P6 budget fixture',
                       spawners=(), public=tuple(public), charted=True)
        content.zones[zid] = Zone(meta,tuple(tuple(row) for row in grid))
        assert not list(charting_problems(content.zones[zid],content.tiles))
        content.looks[zid] = replace(content.looks['p6-fixture'], id=zid,
                                    signs=(), marks=(), glints=(), glint_role=None, names={})
    return content


class WireCaller(Caller):
    """Observe actual headless transport frames outside the CPU boundary."""

    def __init__(self, content: ContentTree, width: int, height: int, tier: str, zone: str, *,
                 presentation: bool = False, fully_known: bool = False) -> None:
        self.wire: list[dict[str, Any]] = []
        super().__init__(content, width, height, tier, zone, presentation=presentation, fully_known=fully_known)

    def drain(self, now: float) -> None:
        for frame in self.game.frames_for(self.client):
            look_bytes = 0
            if frame.type == 'view':
                look = frame.data.get('body',{}).get('looks')
                if look:
                    look_bytes = len(json.dumps(look,ensure_ascii=False,separators=(',',':')).encode('utf-8'))
            elif frame.type == 'delta':
                ops = [op for op in frame.data['ops'] if '/looks' in op['path']
                       or isinstance(op.get('value'),dict) and ('looks' in op['value'] or 'looks' in op['value'].get('body',{}))]
                if ops:
                    look_bytes = len(json.dumps(ops,ensure_ascii=False,separators=(',',':')).encode('utf-8'))
            self.wire.append({'kind':frame.type,'bytes':len(encode(frame)), 'look_bytes':look_bytes})
            for output in self.meter.call('receive',self.display.receive,frame,now):
                self.client.send(output)


def wire_walk(content: ContentTree, width: int, height: int, tier: str, fully_known: bool = False) -> dict[str, Any]:
    caller = WireCaller(content,width,height,tier,'sodium-row',presentation=True,fully_known=fully_known)
    first = next(sample['look_bytes'] for sample in caller.wire if sample['kind']=='view' and sample['look_bytes'])
    caller.wire = []
    for tick in range(1,81):
        now = 1.+tick*.101
        if tick%2 == 0:
            caller.key(KEYS['walking where there is no scene'][(tick//2-1)%16],now)
        caller.tick(now)
        caller.draw(now)
    deltas = [sample for sample in caller.wire if sample['kind']=='delta']
    assert deltas and caller.moves
    return {'first_look_payload_bytes':first,'delta_frames':len(deltas),
            'delta_wire_bytes':sum(row['bytes'] for row in deltas),
            'delta_look_bytes':sum(row['look_bytes'] for row in deltas),
            'delta_look_share':sum(row['look_bytes'] for row in deltas)/sum(row['bytes'] for row in deltas),
            'max_delta_wire_bytes':max(row['bytes'] for row in deltas),'successful_moves':caller.moves}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=12.)
    args = parser.parse_args()
    if not 0 < args.seconds <= 600:
        parser.error('seconds must be positive and at most 600')
    content = fixture_content()
    bare = deepcopy(content)
    bare.themes = None
    bare.looks.clear()
    cases = []
    for width,height in ((80,24),(132,50)):
        for tier in ('16','256','truecolor'):
            for fully_known in (False,True) if width==132 else (False,):
                arms = {}
                for label,tree in (('generic',bare),('looks',content)):
                    activities = {what:activity(tree,width,height,tier,what,args.seconds,
                                                presentation=True,fully_known=fully_known) for what in MIX}
                    sample = frames(tree,width,height,tier,presentation=True,fully_known=fully_known)
                    assert sample['delta_16kib_pass'] and sample['render_p95_100ms_pass'], (width,height,tier,label,fully_known,sample)
                    arms[label] = {'activities':activities,'cpu_s_per_hour':hourly(activities),'frames':sample}
                for what in MIX:
                    for field in ('initial_view','final_view','successful_moves'):
                        assert arms['generic']['activities'][what][field] == arms['looks']['activities'][what][field]
                delta = arms['looks']['cpu_s_per_hour']-arms['generic']['cpu_s_per_hour']
                case = {'size':[width,height],'tier':tier,'fully_known':fully_known,'arms':arms,
                        'cpu_delta_s_per_hour':delta,'cpu_120s_per_hour_pass':arms['looks']['cpu_s_per_hour']<=120,
                        'wire':wire_walk(content,width,height,tier,fully_known)}
                cases.append(case)
                print(json.dumps({key:case[key] for key in ('size','tier','fully_known','cpu_delta_s_per_hour','cpu_120s_per_hour_pass','wire')}),flush=True)
    result = {'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'dirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
              'created_utc':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'python':sys.version,
              'cpu_budget_reference':platform.system()=='Linux' and args.seconds==12.,
              'seconds':args.seconds,'mix':'v1-provisional','minutes':MIX,
              'cpu_boundary':'unchanged P1 Meter: Display receive/key/update/render only; server/codecs excluded',
              'fixture':'at least 120x50 charted rectangle; real object/exit bindings, excluded doors/private/hidden cells; dark base plus light region; no spawners',
              'comparison':'generic P5 fallback versus P6 looks on identical charted fixture/knowledge/moves; not the shipped P5 workload',
              'p5_final_shipped_reference':{'run':41126237721,'cpu_132x50_known':[93.3807,87.1260,99.3039]},
              'targets':{'render_p95_ms':100,'delta_bytes':16384,'cpu_s_per_hour':120},'cases':cases}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':
    main()
