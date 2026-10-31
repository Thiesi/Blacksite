"""A7: reproduce each baseline/candidate golden with only origin replaced."""

import argparse
import ast
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]

from blacksite.content.loader import load_content
from blacksite.door.cells import CellBuffer
from blacksite.door.palette import Palette
from blacksite.door.present import zone
from blacksite.door.present.paint import Paint
from blacksite.layout import compute
from blacksite.server.protocol import Frame
from p6_cell_diff import cells
from presentation_p6_validation import git, module
from presentation_p6_camera import BASE, SOURCE
from tests.fake_terminal import FakeTerminal
from tests.presentation.snapshots import canonical, snapshot
from tests.presentation.test_client_foundations import display, zone_body
from tests.presentation.test_places import view


def report() -> dict[str, Any]:
    changed_source = git('diff','--name-only',BASE,'--','src').decode().splitlines()
    if changed_source != [SOURCE]:
        raise ValueError(f'only client origin source may change: {changed_source}')
    old_source,new_source = git('show',f'{BASE}:{SOURCE}'),(ROOT/SOURCE).read_bytes()
    def other_functions(source: bytes) -> str:
        tree = ast.parse(source)
        tree.body = [node for node in tree.body if not isinstance(node,ast.FunctionDef) or node.name!='origin']
        return ast.dump(tree,include_attributes=False)
    if other_functions(old_source) != other_functions(new_source):
        raise ValueError('runtime changes outside origin()')
    if git('diff','--name-only',BASE,'--','tests/fixtures').strip():
        raise ValueError('test fixtures changed')
    old_origin = module('_a7_golden_origin',old_source).origin
    shipped = load_content(ROOT/'src/blacksite/content')
    fixture = load_content(ROOT/'src/blacksite/content',ROOT/'tests/fixtures/p6')
    records = []
    for kind in ('p5','dark','light'):
        content = deepcopy(shipped if kind=='p5' else fixture)
        if kind == 'light':
            content.looks['p6-fixture'] = replace(content.looks['p6-fixture'],theme='p6-light')
        for size in ((80,24),(132,50)):
            body = zone_body(content,*size) if kind=='p5' else view(content,*size)[0]
            layout = compute(*size)
            old_at,new_at = old_origin(body,layout),zone.origin(body,layout)
            for tier in ('16','256','truecolor'):
                path = ('tests/presentation/golden/p5/zone_' if kind=='p5' else
                        f'tests/presentation/golden/p6/{kind}_')+f'{size[0]}x{size[1]}_{tier}.json'
                before,after = json.loads(git('show',f'{BASE}:{path}')),json.loads((ROOT/path).read_text())
                for origin,expected in ((old_origin,before),(zone.origin,after)):
                    with patch.object(zone,'origin',origin):
                        terminal = FakeTerminal(*size)
                        if kind == 'p5':
                            model = display(content,*size,tier)
                            model.receive(Frame('view',{'rev':1,'kind':'zone','body':deepcopy(body)}),1)
                            terminal.write(model.render(2)[0])
                        else:
                            buffer = CellBuffer(*size)
                            zone.render(buffer,deepcopy(body),layout,Paint(Palette(asdict(content.palette),tier)))
                            terminal.write(buffer.full())
                    if canonical(snapshot(terminal)) != canonical(expected):
                        raise ValueError(f'{path}: renderer does not reproduce origin-only arm')
                changes = []
                field,vp = layout.viewport,body['viewport']
                for y in range(size[1]):
                    for x,(a,b) in enumerate(zip(cells(before,y),cells(after,y))):
                        if a == b:
                            continue
                        if not (field.x<=x<field.right and field.y<=y<field.bottom) or old_at==new_at:
                            raise ValueError(f'{path}: non-position cell change at {(x,y)}')
                        def world(at: tuple[int,int]) -> list[int] | None:
                            dx,dy = x-at[0],y-at[1]
                            return [vp['x']+dx,vp['y']+dy] if 0<=dx<vp['w'] and 0<=dy<vp['h'] else None
                        changes.append({'cell':[x,y],'cause':'origin translation/clipping only',
                                        'world_before':world(old_at),'world_after':world(new_at),
                                        'before':a,'after':b})
                if changes:
                    records.append({'path':path,'origin_before':old_at,'origin_after':new_at,'cells':changes})
    changed = git('diff','--name-only',BASE,'--','tests/presentation/golden','tests/door/golden').decode().splitlines()
    if set(changed) != {r['path'] for r in records}:
        raise ValueError(f'unassigned or missing golden changes: {changed}')
    return {'baseline':BASE,'allowed_by':'issue115/6542553660; owner merge only',
            'runtime_diff':'origin() only; server camera/disclosure/content unchanged',
            'all_other_goldens':'byte-identical','goldens':records,
            'changed_cells':sum(len(r['cells']) for r in records),'owner_approval':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = report()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,separators=(',',':'))+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'goldens':len(result['goldens']),'changed_cells':result['changed_cells']}))
