"""Prove Part A changes only withheld ground and ANSI people in P6 goldens."""

import argparse
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'),str(ROOT)]

from blacksite.content.loader import load_content
from blacksite.door.cells import CellBuffer, display_width
from blacksite.door.palette import Palette
from blacksite.door.present import zone as drawing
from blacksite.door.present.paint import Paint
from blacksite.layout import compute
from blacksite.place import CHARTED_GROUND
from tests.fake_terminal import FakeTerminal
from tests.presentation.snapshots import canonical, snapshot
from tests.presentation.test_places import view


def cells(frame: dict[str,Any], y: int) -> list[tuple[str,dict[str,Any]]]:
    glyphs: list[str] = []
    for ch in frame['glyph_rows'][y]:
        width = display_width(ch)
        if width == 0 and glyphs:
            index = len(glyphs)-1-(not glyphs[-1])
            glyphs[index] += ch
        else:
            glyphs.extend([ch]+['']*(width-1))
    styles = [frame['styles'][index] for count,index in frame['style_rows'][y] for _ in range(count)]
    if len(glyphs)!=frame['width'] or len(styles)!=frame['width']:
        raise ValueError('invalid golden cell dimensions')
    return list(zip(glyphs,styles))


def report(base: str) -> dict[str,Any]:
    changed = subprocess.check_output(['git','diff','--name-only',base,'--','tests/presentation/golden'],
                                     cwd=ROOT,text=True).splitlines()
    if any(not name.startswith('tests/presentation/golden/p6/') for name in changed):
        raise ValueError('P5 and switch-off goldens must remain byte-identical')
    fixture_path = 'tests/fixtures/p6/zones/p6-fixture.map'
    fixture_changes = subprocess.check_output(['git','diff','--name-only',base,'--','tests/fixtures/p6'],
                                              cwd=ROOT,text=True).splitlines()
    if any(path!=fixture_path for path in fixture_changes):
        raise ValueError('only the existing Clinic terminal fixture tile may change')
    old_map = subprocess.check_output(['git','show',f'{base}:{fixture_path}'],cwd=ROOT,text=True).splitlines()
    new_map = (ROOT/fixture_path).read_text(encoding='utf-8').splitlines()
    if len(old_map)!=len(new_map) or any(len(a)!=len(b) for a,b in zip(old_map,new_map)):
        raise ValueError('fixture dimensions changed')
    map_cells = [(x,y,a,b) for y,(old,new) in enumerate(zip(old_map,new_map))
                 for x,(a,b) in enumerate(zip(old,new)) if a!=b]
    if map_cells != [(10,5,'.','T')]:
        raise ValueError(f'only floor -> terminal at the existing Clinic binding is permitted: {map_cells}')
    content = load_content(ROOT/'src/blacksite/content',ROOT/'tests/fixtures/p6')
    rows = []
    for light in (False,True):
        for width,height in ((80,24),(132,50)):
            tree = deepcopy(content)
            if light:
                tree.looks['p6-fixture'] = replace(tree.looks['p6-fixture'],theme='p6-light')
            body,*_ = view(tree,width,height)
            layout = compute(width,height)
            ox,oy = drawing.origin(body,layout)
            vp = body['viewport']
            allowed: dict[tuple[int,int],str] = {}
            for y,row in enumerate(body['tiles']):
                for x,value in enumerate(row):
                    recalled = value==-2 and body['remembered'][y][x]>=0
                    if value<0 and not recalled and body['charted'][y][x]==CHARTED_GROUND:
                        allowed[ox+x,oy+y] = 'withheld ground'
            for tier in ('16','256','truecolor'):
                permitted = dict(allowed)
                if tier=='16':
                    permitted.update({(ox+a['x']-vp['x'],oy+a['y']-vp['y']):'ANSI person'
                                      for a in body['actors']})
                path = f'tests/presentation/golden/p6/{"light" if light else "dark"}_{width}x{height}_{tier}.json'
                before = json.loads(subprocess.check_output(['git','show',f'{base}:{path}'],cwd=ROOT))
                after = json.loads((ROOT/path).read_text(encoding='utf-8'))
                terminal,buffer = FakeTerminal(width,height),CellBuffer(width,height)
                drawing.render(buffer,body,layout,Paint(Palette(asdict(tree.palette),tier)))
                terminal.write(buffer.full())
                if canonical(snapshot(terminal))!=canonical(after):
                    raise ValueError(f'{path}: golden differs from the actual renderer')
                differences = []
                for y in range(height):
                    for x,(old,new) in enumerate(zip(cells(before,y),cells(after,y))):
                        if old==new:
                            continue
                        if (x,y) not in permitted:
                            raise ValueError(f'{path}: unapproved cell change at {(x,y)}')
                        def compact(cell: tuple[str,dict[str,Any]]) -> list[Any]:
                            glyph,style = cell
                            return [glyph,style['foreground'],style['background'],style['attributes']]
                        differences.append({'cell':[x,y],'world':[vp['x']+x-ox,vp['y']+y-oy],
                                            'cause':permitted[x,y],'before':compact(old),'after':compact(new)})
                rows.append({'path':path,'cells':differences})
    return {'base':base,'allowed_by':'issue 115 comments 6538957810 and 6539068401',
            'p5_and_switch_off':'byte-identical',
            'fixture_map_cells':[{'world':[x,y],'before':a,'after':b} for x,y,a,b in map_cells],
            'goldens':rows,
            'changed_cells':sum(len(row['cells']) for row in rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='4e5390b80463b59365cfca38049dee98b0744f91')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    value = report(args.base)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(value,ensure_ascii=False,indent=1)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'changed_cells':value['changed_cells'],'p5_and_switch_off':value['p5_and_switch_off']}))


if __name__=='__main__':
    main()
