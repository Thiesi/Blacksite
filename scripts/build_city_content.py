"""Author S25 geography from the Gazetteer; never imported by the game.

Draft output defaults to .test-tmp/s25-city-draft. Source sketches supply
proportions, not tile counts. Public paths and actual anchors are checked
after scaling. The shipped source is changed only with --output pointing
explicitly at src/blacksite/content.
"""

import argparse
from copy import deepcopy
from collections import deque
from dataclasses import dataclass, field
from heapq import heappop, heappush
import json
from pathlib import Path
import re
import shutil
import sys
import textwrap
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from blacksite.content.validate import door_wall_axis

SHIPPED = ROOT/'src/blacksite/content'
SECTORS = {'spire': 'lat-spire', 'tramyard': 'lat-tramyard', 'sink': 'lat-sink',
           'chapel': 'lat-chapel-ward', 'oldworks': 'lat-old-works',
           'under': 'lat-undercity', 'scour': 'lat-scour'}

# These are physical bearings, not movement shortcuts or engine rules.
BEARINGS: dict[str, dict[str, tuple[int, int]]] = {
    'spire-atrium': {'core-plaza': (30, 27), 'spire-mezzanine': (57, 15)},
    'spire-mezzanine': {'spire-atrium': (47, 12), 'spire-shaft-head': (2, 12)},
    'spire-shaft-head': {'spire-mezzanine': (2, 20), 'under-shaft-foot': (35, 20)},
    'tramyard-depots': {'tramyard-market': (2, 10), 'tramyard-wall-gate': (2, 30), 'oldworks-main': (117, 30)},
    'tramyard-market': {'core-tram-hub': (40, 2), 'tramyard-depots': (2, 25), 'sink-rim': (40, 33)},
    'tramyard-wall-gate': {'tramyard-depots': (2, 10), 'scour-ring-1': (35, 47),
                          'scour-landing': (38, 47)},
    'sink-rim': {'tramyard-market': (2, 15), 'core-tram-hub': (50, 2), 'sink-terraces': (50, 27)},
    'sink-terraces': {'sink-rim': (45, 2), 'sink-floor': (45, 57), 'oldworks-yards': (87, 30)},
    'sink-floor': {'sink-terraces': (35, 2), 'under-caverns': (35, 37)},
    'chapel-towers': {'core-tram-hub': (40, 2), 'chapel-nave': (77, 20),
        'terraces-blocks': (2, 20), 'under-service': (40, 37)},
    'chapel-nave': {'chapel-towers': (25, 27)},
    'oldworks-main': {'tramyard-depots': (2, 17), 'oldworks-yards': (107, 17),
        'oldworks-drop': (55, 2), 'sodium-row': (55, 31)},
    'oldworks-yards': {'oldworks-main': (50, 2), 'sink-terraces': (97, 25), 'under-service': (50, 47)},
    'oldworks-drop': {'oldworks-main': (20, 17)},
    'under-service': {'vatside-vat-row': (20, 2), 'chapel-towers': (80, 2),
        'oldworks-yards': (2, 20), 'under-drowned': (117, 30), 'under-caverns': (60, 47)},
    'under-drowned': {'under-service': (2, 30), 'under-outworks': (97, 30), 'under-caverns': (50, 57)},
    'under-caverns': {'under-service': (40, 2), 'sink-floor': (2, 40),
        'under-drowned': (100, 2), 'under-outworks': (147, 40), 'scour-ring-2': (75, 77)},
    'under-outworks': {'under-drowned': (2, 20), 'under-caverns': (2, 55), 'under-shaft-foot': (117, 35)},
    'under-shaft-foot': {'under-outworks': (2, 30), 'spire-shaft-head': (30, 2)},
    'scour-landing': {'scour-ring-1': (2, 15), 'scour-ring-2': (57, 15),
                      'tramyard-wall-gate': (30, 2)},
    'scour-ring-1': {'tramyard-wall-gate': (2, 40), 'scour-landing': (70, 2), 'scour-ring-2': (157, 40)},
    'scour-ring-2': {'scour-ring-1': (2, 45), 'scour-landing': (60, 2),
        'scour-ring-3': (177, 45), 'under-caverns': (100, 87)},
    'scour-ring-3': {'scour-ring-2': (2, 50), 'scour-ring-4': (197, 50)},
    'scour-ring-4': {'scour-ring-3': (2, 50)},
}

ATMOSPHERE = {
    'spire-atrium': 'You stand on polished stone beneath the glass. Beyond the wall, the Ring catches the light. Security watches the lifts.',
    'spire-mezzanine': 'Your boots sink into dry carpet. The lift closes softly behind you. Office doors stay quiet.',
    'spire-shaft-head': 'You feel warm air against your sleeves. A cage cable hangs over the concrete collar. A camera turns.',
    'tramyard-depots': 'You pass between containers that smell of grain. Cranes move above the ration lanes. A calm voice counts the next load.',
    'tramyard-market': 'You hear prices shouted under patched tarpaulins. A set of scales knocks against a stall. Tram bells cut through the crowd.',
    'tramyard-wall-gate': 'You smell hot engines beneath the wall. Beyond the gate, the road turns pale. A speaker counts the next opening.',
    'sink-rim': 'You look down through layers of washing lines. A cable car rattles below the rail. The long stair stays open.',
    'sink-terraces': 'You walk beneath another street. Water runs down the retaining walls. Market lights mark the next terrace.',
    'sink-floor': 'You hear pumps beneath the water. The public path follows the wall. Warm pipes cross the flooded shortcut.',
    'chapel-towers': 'You feel the towers hum through the soles of your boots. A bell sounds inside the concrete. Drain water runs toward the stairs.',
    'chapel-nave': 'You step into a hall of pillars and cable. Voices settle into a low chord. The light stays warm near the vats.',
    'oldworks-main': 'You smell solder and damp brick. Cables hang over the shop fronts. A patched terminal keeps its screen lit.',
    'oldworks-yards': 'You pass rails buried in rust. A gantry hangs above the work floor. The lamps throw long shadows between the frames.',
    'oldworks-drop': 'You leave the street behind an unmarked door. Cool air moves over the terminals. A recording waits in the quiet.',
    'under-service': 'You follow pipes beneath the city. Most lamps are dark. Warm air moves through the breach ahead.',
    'under-drowned': 'You wade past numbers painted on concrete. The water smells old. A pump hums behind the bulkhead.',
    'under-caverns': 'You hear water beyond the reach of your lamp. Pale growth marks the limestone. The marked fissure leads toward the outworks.',
    'under-outworks': 'You step past a fallen survey marker. Lights wake in separate rooms. The public inner door leads to the shaft.',
    'under-shaft-foot': 'You stand beneath a cage cable. Light falls across the door in the floor. Nine cuts meet a painted Halvard line.',
    'scour-landing': 'You step between walls of hull plate. A dish hangs above the shelters. The smell of cooking reaches the causeway.',
    'scour-ring-1': 'You leave the wall at your back. Tyre tracks cross the pale ground. Metal flashes high above the road.',
    'scour-ring-2': 'You follow a line of beacons through the dust. A camp lamp moves in the wind. The Ring hangs above the ridge.',
    'scour-ring-3': 'You pick a path between broken hulls. The largest wreck hides the next beacon. Loose metal ticks as it cools.',
    'scour-ring-4': 'You keep the mast in sight. Dust buries your footprints. The ground continues beyond every bearing, under the Ring.',
}


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


@dataclass
class Grid:
    rows: list[list[str]]
    reserved: set[tuple[int, int]] = field(default_factory=set)
    private: set[tuple[int, int]] = field(default_factory=set)
    protected: bool = False
    fixed_walls: set[tuple[int, int]] = field(default_factory=set)

    @property
    def width(self) -> int:
        return len(self.rows[0])

    @property
    def height(self) -> int:
        return len(self.rows)

    def inside(self, tile: tuple[int, int]) -> bool:
        return 0 < tile[0] < self.width-1 and 0 < tile[1] < self.height-1

    def safe(self, tile: tuple[int, int]) -> bool:
        return self.inside(tile) and tile not in self.private and self.rows[tile[1]][tile[0]] not in '#=!'

    def mark(self, tile: tuple[int, int], char: str = '.') -> None:
        assert self.inside(tile), tile
        if self.protected:
            return  # S25b never changes S08 terrain; objects render separately.
        if tile in self.fixed_walls and char != '#':
            raise AssertionError(f'route door wall would be cut: {tile}')
        self.rows[tile[1]][tile[0]] = char

    def mark_exit(self, tile: tuple[int, int], hidden: bool) -> None:
        char = '.' if hidden else '>'
        if self.protected:
            assert self.rows[tile[1]][tile[0]] in ('.', '+', '>'), tile
            self.rows[tile[1]][tile[0]] = char  # Marker only; never cut hub walls.
        else:
            self.mark(tile, char)

    def nearest(self, origin: tuple[int, int], *, clear: bool = True) -> tuple[int, int]:
        candidates = ((x, y) for y in range(2, self.height-2) for x in range(2, self.width-2)
                      if (x, y) not in self.reserved | self.private and self.safe((x, y)))
        tile = min(candidates, key=lambda t: (abs(t[0]-origin[0])+abs(t[1]-origin[1]), t))
        if clear:
            self.mark(tile)
        self.reserved.add(tile)
        return tile

    def reachable(self, start: tuple[int, int], avoid: set[tuple[int, int]] | None = None) -> set[tuple[int, int]]:
        found, pending = {start}, deque([start])
        while pending:
            x, y = pending.popleft()
            for tile in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if tile not in found and tile not in (avoid or set()) and self.safe(tile):
                    found.add(tile)
                    pending.append(tile)
        return found

    def connect(self, start: tuple[int, int], target: tuple[int, int],
                avoid: set[tuple[int, int]] | None = None) -> None:
        """Cut the fewest wall/hazard cells only when no safe path exists."""
        if self.protected:
            return
        if not self.safe(start):
            self.mark(start)
        if not self.safe(target):
            self.mark(target)
        if target in self.reachable(start, avoid):
            return
        cost, parent, pending = {start: 0}, {}, [(0, start)]
        while pending:
            amount, tile = heappop(pending)
            if amount != cost[tile]:
                continue
            if tile == target:
                break
            x, y = tile
            for nxt in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if not self.inside(nxt) or nxt in self.private or nxt in self.fixed_walls or nxt in (avoid or set()):
                    continue
                value = amount+(1 if self.safe(nxt) else 1000)
                if value < cost.get(nxt, 10**12):
                    cost[nxt], parent[nxt] = value, tile
                    heappush(pending, (value, nxt))
        assert target in cost, (start, target)
        tile = target
        while tile != start:
            if not self.safe(tile):
                self.mark(tile)
            tile = parent[tile]

    def text(self) -> str:
        return '\n'.join(''.join(row) for row in self.rows)+'\n'


def gazetteer() -> dict[str, dict[str, Any]]:
    source = (ROOT/'docs/world/01-gazetteer.md').read_text(encoding='utf-8')
    pieces = re.split(r'^### `([^`]+)`[^\n]*\n', source, flags=re.M)
    sections = dict(zip(pieces[1::2], pieces[2::2]))
    result = {}
    hubs = set(read(SHIPPED/'bundles/m1-zone-preview.json')['members']['zones'])
    scope = hubs | set(BEARINGS)  # #78: ten S08 hubs plus the 24 S25 zones.
    for line in source.splitlines():
        row = [part.strip() for part in line.split('|')[1:-1]]
        if len(row) != 6 or not row[0].startswith('`') or '×' not in row[-1]:
            continue
        zid = row[0].strip('`')
        if zid not in scope:
            continue  # S26 and planned Warmwater zones belong to later work.
        section = sections[zid]
        pre = re.sub(r'\s+', ' ', section.split('```', 1)[0])
        exits = re.search(r'- \*\*Exits:\*\*(.*?)(?=- \*\*|$)', pre).group(1)
        destinations = re.findall(r'`([^`]+)`', exits)
        sight = int(re.search(r'\*\*Sight:\*\*\s*(\d+)', pre).group(1))
        night = re.search(r'by day,\s*(\d+) by night', pre)
        width, height = map(int, row[-1].split('×'))
        lean = row[4].lower()
        lean = {'red sable': 'sable'}.get(lean, lean)
        if lean not in ('halvard', 'sablier', 'kestrel', 'wardens', 'sable', 'choir', 'unmoored', 'ferrymen'):
            lean = None
        sketch = section.split('```', 2)[1]
        result[zid] = dict(id=zid, name=row[1], district=row[2].removeprefix('The '), safety=row[3],
            width=width, height=height, sight_radius=sight, night=int(night.group(1)) if night else None,
            lean=lean, neighbours=[target for target in destinations if target in scope], sketch=sketch)
    assert set(result) == scope
    return result


def terrain(definition: dict[str, Any]) -> Grid:
    width, height = definition['width'], definition['height']
    rows = [['#' if x in (0, width-1) or y in (0, height-1) else '.'
             for x in range(width)] for y in range(height)]
    sketch = [re.split(r'\s{2,}', line.strip())[0] for line in definition['sketch'].splitlines()
              if line.lstrip().startswith('#')]
    sw, sh = max(map(len, sketch)), len(sketch)
    for sy, line in enumerate(sketch[1:-1], 1):
        for sx, char in enumerate(line[1:-1], 1):
            if char not in '#%~!':
                continue
            if char == '!' and definition['id'] == 'under-shaft-foot':
                continue  # Gazetteer: the cage lift is a lift, not a hazard.
            if char == '!' and definition['safety'] in ('safe', 'pocket'):
                continue
            for y in range(1+(sy-1)*(height-2)//(sh-2), 1+sy*(height-2)//(sh-2)):
                for x in range(1+(sx-1)*(width-2)//(sw-2), min(width-1, 1+sx*(width-2)//(sw-2))):
                    if char != '%' or (x+y) % 4:
                        rows[y][x] = char
    return Grid(rows)


class City:
    def __init__(self, output: Path) -> None:
        self.output = output
        self.definitions = gazetteer()
        self.hubs = set(read(SHIPPED/'bundles/m1-zone-preview.json')['members']['zones'])
        self.meta: dict[str, dict[str, Any]] = {}
        self.grids: dict[str, Grid] = {}
        self.slots: dict[tuple[str, str], int] = {}
        for zid, definition in self.definitions.items():
            if zid in self.hubs:
                meta = read(SHIPPED/'zones'/(zid+'.json'))
                grid = Grid([list(row) for row in (SHIPPED/'zones'/(zid+'.map')).read_text(encoding='utf-8').splitlines()],
                            protected=True)
            else:
                grid = terrain(definition)
                spawn = (3, definition['height']//2)
                grid.mark(spawn)
                meta = dict(schema=1, id=zid, name=definition['name'], district=definition['district'],
                    safety=definition['safety'], lean=definition['lean'],
                    sight_radius=definition['sight_radius'], sector=SECTORS[zid.split('-')[0]],
                    spawn=list(spawn), exits=[], objects=[], spawners=[], lore=['zone-'+zid])
                if definition['night'] is not None:
                    meta['sight_radius_night'] = definition['night']
            self.meta[zid], self.grids[zid] = meta, grid
            grid.reserved.update(tuple(obj['tile']) for obj in meta['objects'])
            grid.reserved.update(tuple(ex['tile']) for ex in meta['exits'])
            grid.reserved.add(tuple(meta['spawn']))

    def feature(self, zid: str, char: str) -> tuple[int, int]:
        """A semantic sketch anchor, before S25c authors location geometry."""
        sketch = [re.split(r'\s{2,}', line.strip())[0]
                  for line in self.definitions[zid]['sketch'].splitlines() if line.lstrip().startswith('#')]
        points = [(x, y) for y, row in enumerate(sketch) for x, cell in enumerate(row) if cell == char]
        assert points, (zid, char)
        grid = self.grids[zid]
        return (round(sum(x for x, _ in points)/len(points)*(grid.width-1)/(max(map(len, sketch))-1)),
                round(sum(y for _, y in points)/len(points)*(grid.height-1)/(len(sketch)-1)))

    def spot(self, zid: str, kind: str) -> tuple[int, int]:
        definition, grid = self.definitions[zid], self.grids[zid]
        key = zid, kind
        index = self.slots.get(key, 0)
        self.slots[key] = index+1
        letter = {'hardware': 'T', 'relay': 'R', 'vendor': '$', 'vat': 'V', 'light': 'L',
                  'descent_console': 'T'}.get(kind)
        sketch = [re.split(r'\s{2,}', line.strip())[0] for line in definition['sketch'].splitlines()
                  if line.lstrip().startswith('#')]
        points = [(min(grid.width-3, max(2, x*(grid.width-1)//(max(map(len, sketch))-1))),
                   min(grid.height-3, max(2, y*(grid.height-1)//(len(sketch)-1))))
                  for y, row in enumerate(sketch) for x, char in enumerate(row) if letter and char == letter]
        points += [(grid.width*3//4, grid.height//3), (grid.width//4, grid.height*2//3),
                   (grid.width*3//4, grid.height*2//3), (grid.width//4, grid.height//3),
                   (grid.width//2, grid.height//2)]
        origin = points[index % len(points)]
        return grid.nearest(origin)

    def obj(self, zid: str, oid: str, kind: str, name: str, *,
            tile: tuple[int, int] | None = None, essential: bool = False,
            params: dict[str, Any] | None = None) -> dict[str, Any]:
        meta, grid = self.meta[zid], self.grids[zid]
        old = next((obj for obj in meta['objects'] if obj['id'] == oid), None)
        if old:
            if zid in self.hubs and old['kind'] != kind:
                raise AssertionError(f'S08 object kind would change: {zid}/{oid}')
            old['kind'] = kind
            old.setdefault('params', {}).update(params or {})
            if zid not in self.hubs:
                old['params']['name'] = name
            if essential:
                old['essential'] = True
            return old
        point = tile if tile is not None else self.spot(zid, kind)
        grid.mark(point, {'hardware': 'H', 'terminal': 'T', 'relay': 'R', 'vat': 'V',
                          'vendor': '$', 'light': 'L', 'door': '+', 'shutter': '+',
                          'gate': '+', 'lift': '+'}.get(kind, '.'))
        grid.reserved.add(point)
        value = dict(id=oid, tile=list(point), kind=kind,
                     params={'name': name.replace('\u2014', '-').replace('\u2013', '-'), **(params or {})})
        if essential:
            value['essential'] = True
        meta['objects'].append(value)
        return value

    def shelter(self, zid: str, point: tuple[int, int]) -> None:
        if self.meta[zid]['safety'] != 'contested':
            return
        x, y = point
        region = dict(x=max(1, x-1), y=max(1, y-1), w=3, h=3)
        region['w'] = min(region['w'], self.grids[zid].width-1-region['x'])
        region['h'] = min(region['h'], self.grids[zid].height-1-region['y'])
        if region not in self.meta[zid].setdefault('pockets', []):
            self.meta[zid]['pockets'].append(region)
        for yy in range(region['y'], region['y']+region['h']):
            for xx in range(region['x'], region['x']+region['w']):
                if self.grids[zid].rows[yy][xx] in '#=!':
                    self.grids[zid].mark((xx, yy))

    def layout(self, zid: str, name: str, changes: list[dict[str, Any]]) -> None:
        meta = self.meta[zid]
        meta.setdefault('layouts', [])
        meta['layouts'] = [row for row in meta['layouts'] if row['id'] != name]
        meta['layouts'].append(dict(id=name, changes=changes,
            warning_tiles=[row['tile'] for row in changes if row['tile_id'] in ('hazard', 'gantry-hazard')],
            alternate_routes=[ex['id'] for ex in meta['exits'] if not ex.get('hidden')
                              and not ex.get('requirement') and not ex.get('relay')]))

    def hardware(self) -> None:
        for file in sorted((self.output/'cores').glob('*.json')):
            core = read(file)
            if core.get('training') or core.get('template'):
                continue
            for hardware in core.get('hardware', []):
                zid = hardware['zone']
                if zid not in self.meta:
                    continue
                oid = hardware.get('object_id') or core['id'].removeprefix('lat-')+'-hardware'
                point = tuple(hardware['tile']) if hardware.get('tile') else None
                obj = self.obj(zid, oid, 'hardware', hardware['label'], tile=point, params={'core': core['id']})
                hardware.update(tile=obj['tile'], object_id=oid)
            for room in core['rooms']:
                for control in room.get('controls', []):
                    if core['id'] == 'lat-relay-zero' and control['id'] == 'worker_return':
                        continue  # services() authors its fixed corridor and door.
                    target = control['target']
                    if core['id'] == 'lat-halvard-citadel' and control['id'] == 'executive-lift-lockdown':
                        # Lattice 3.1: lockdown closes the inbound public
                        # lift; Gatehouse can restore the same physical panel.
                        target['object'] = 'gatehouse-public-lifts'
                        control.update(action='close', safety_policy='route', alternate_route='to-core-plaza')
                    zid, oid = target.get('zone'), target.get('object')
                    if zid not in self.meta or not oid:
                        continue
                    existing = next((o for o in self.meta[zid]['objects'] if o['id'] == oid), None)
                    if existing:
                        continue
                    label = control['label']
                    if oid.startswith('relay-'):
                        kind = 'relay'
                    elif 'light' in oid:
                        kind = 'light'
                    elif 'camera' in oid:
                        kind = 'camera'
                    elif 'turret' in oid or 'forklift-drones' in oid:
                        kind = 'turret'
                    elif 'pump' in oid or 'cistern' in oid:
                        kind = 'pump'
                    elif 'gantry' in oid:
                        kind = 'gantry'
                    elif 'patrol-' in oid:
                        kind = 'patrol_beacon'
                    elif 'cable-car' in oid:
                        kind = 'cable_car'
                    elif 'lift' in oid or 'maintenance-cage' in oid:
                        kind = 'lift'
                    elif oid == 'gatehouse-east-gate-nine-outbound':
                        kind = 'gate'
                    elif control['action'] == 'call':
                        kind = 'terminal'
                    else:
                        kind = 'door'
                    params: dict[str, Any] = {}
                    tile = None
                    if oid == 'drowned-bulkhead':
                        tile = tuple(next(ex for ex in self.meta[zid]['exits']
                                          if ex['target_zone'] == 'under-outworks')['tile'])
                    if kind in ('door', 'shutter', 'gate'):
                        params.update(open=False, locked=True)
                    if kind in ('lift', 'cable_car', 'gate'):
                        wanted = ('cable',) if kind == 'cable_car' else ('lift', 'gate')
                        params['exits'] = [ex['id'] for ex in self.meta[zid]['exits'] if ex['kind'] in wanted]
                    if kind == 'terminal':
                        params.update(sector=self.meta[zid]['sector'])
                    obj = self.obj(zid, oid, kind, label, tile=tile, params=params)
                    if kind in ('pump', 'gantry'):
                        x, y = obj['tile']
                        name = oid+'-active'
                        # Small side lanes; the permanent public route is separate.
                        tiles = [[xx, min(self.grids[zid].height-3, y+2)]
                                 for xx in range(max(2, x-2), min(self.grids[zid].width-2, x+3))]
                        for point in tiles:
                            self.grids[zid].mark(tuple(point), '~' if kind == 'pump' else '.')
                        changes = [dict(tile=point, tile_id='floor' if kind == 'pump' else 'gantry-hazard') for point in tiles]
                        obj['params']['layout'] = name
                        self.layout(zid, name, changes)
                        control['warning_seconds'] = max(5, control.get('warning_seconds', 0))
            write(file, core)
        tiles = read(self.output/'tiles.json')
        if not any(row['id'] == 'gantry-hazard' for row in tiles['tiles']):
            tiles['tiles'].append(dict(id='gantry-hazard', char='x', glyph='hazard', colour='hazard',
                passable=True, hazard=dict(damage_per_second=5, type='kinetic')))
        write(self.output/'tiles.json', tiles)

    def merchants(self) -> None:
        table = read(self.output/'vendors.json')
        vendors = {row['id']: row for row in table['vendors']}
        extras = [
            dict(id='kestrel-surplus', name='Kestrel surplus counter', faction='kestrel',
                 zone='tramyard-depots', object_id='depot-surplus-counter'),
            dict(id='ferrymen-waystation', name='Ferrymen way-station', faction='ferrymen',
                 zone='under-caverns', object_id='ferrymen-waystation'),
            dict(id='ferrymen-market-buyer', name='Ferrymen salvage scales', faction='ferrymen',
                 zone='tramyard-market', object_id='ferrymen-market-buyer'),
        ]
        for row in extras:
            vendors.setdefault(row['id'], {**row, 'tier': 'list', 'stock': [
                dict(item='con_kestrel_ration'), dict(item='con_ferry_flare_stick')], 'salvage_multiplier': 1})
        for vendor in vendors.values():
            if vendor.get('relay') or vendor.get('zone') not in self.meta:
                continue
            zid = vendor['zone']
            oid = vendor.get('object_id') or vendor['id']+'-counter'
            vendor['object_id'] = oid
            essential = vendor.get('clinic') is not None
            obj = self.obj(zid, oid, 'vendor', vendor['name'], essential=essential,
                           params={'vendor': vendor['id']})
            if essential:
                self.shelter(zid, tuple(obj['tile']))
        table['vendors'] = list(vendors.values())
        write(self.output/'vendors.json', table)
        bundle = read(self.output/'bundles/s25-commerce.json')
        bundle['members']['vendors'] = list(dict.fromkeys([*bundle['members']['vendors'], *(row['id'] for row in extras)]))
        write(self.output/'bundles/s25-commerce.json', bundle)

    def factions(self) -> None:
        table = read(self.output/'faction_sites.json')
        sectors = {file.stem: read(file) for file in (self.output/'sectors').glob('*.json')}
        for site in table['faction_sites']:
            if site['faction'] == 'halvard':
                site['hall'] = 'spire-mezzanine'
            zid = site['hall']
            if not site.get('vat'):
                obj = self.obj(zid, site['faction']+'-hall-vat', 'vat', 'Protected faction vat', essential=True)
                site['vat'] = dict(zone=zid, tile=obj['tile'])
                self.shelter(zid, tuple(obj['tile']))
            else:
                vat = site['vat']
                if not any(obj['kind'] == 'vat' and obj['tile'] == vat['tile']
                           for obj in self.meta[vat['zone']]['objects']):
                    self.obj(vat['zone'], site['faction']+'-hall-vat', 'vat', 'Protected faction vat',
                             tile=tuple(vat['tile']), essential=True)
                self.shelter(vat['zone'], tuple(vat['tile']))
            bank = next((obj for obj in self.meta[zid]['objects'] if obj['kind'] == 'bank'), None)
            if bank is None:
                bank = self.obj(zid, site['faction']+'-hall-bank', 'bank', 'Kestrel bank branch', essential=True)
            self.shelter(zid, tuple(bank['tile']))
            clinic = next((obj for obj in self.meta[zid]['objects']
                           if obj.get('params', {}).get('vendor') == 'sablier-clinic'), None)
            if clinic is None:
                clinic = self.obj(zid, site['faction']+'-public-clinic', 'vendor', 'Public Sablier clinic',
                                  essential=True, params={'vendor': 'sablier-clinic'})
            self.shelter(zid, tuple(clinic['tile']))
            recruiter = site.get('recruiter_zone') or zid
            sector = self.meta[recruiter]['sector']
            terminal = self.obj(recruiter, site['faction']+'-public-board', 'terminal',
                'Public jobs and faction counter', essential=True,
                params={'faction': site['faction'], 'contract_handler': site['faction'],
                        'sector': sector, 'cell': sectors[sector]['entry']})
            self.shelter(recruiter, tuple(terminal['tile']))
        clinic = self.obj('spire-atrium', 'atrium-public-clinic', 'vendor', 'Public Sablier clinic',
                          essential=True, params={'vendor': 'sablier-clinic'})
        self.shelter('spire-atrium', tuple(clinic['tile']))
        for zid in ('tramyard-market', 'spire-atrium'):
            obj = self.obj(zid, 'market-bank' if zid == 'tramyard-market' else 'atrium-bank',
                           'bank', 'Kestrel bank branch', essential=True)
            self.shelter(zid, tuple(obj['tile']))
        write(self.output/'faction_sites.json', table)

    def public_objects(self) -> None:
        counts = {'spire-atrium': 2, 'spire-mezzanine': 1, 'tramyard-market': 2,
                  'sink-rim': 1, 'sink-terraces': 2, 'chapel-towers': 1,
                  'oldworks-main': 2, 'under-service': 2, 'under-caverns': 1,
                  'scour-landing': 1, 'scour-ring-2': 1, 'scour-ring-4': 1}
        for zid, count in counts.items():
            sector = self.meta[zid]['sector']
            entry = read(self.output/'sectors'/(sector+'.json'))['entry']
            for index in range(count):
                obj = self.obj(zid, 'public-uplink-'+str(index+1), 'terminal',
                    'Public Lattice terminal', essential=True, params={'sector': sector, 'cell': entry})
                self.shelter(zid, tuple(obj['tile']))
        for zid, makes in (('tramyard-market', 'any'), ('scour-landing', 'any'),
                           ('oldworks-yards', 'rigs_programs'), ('sink-terraces', 'chemical_melee')):
            self.obj(zid, 'public-workshop', 'workshop', 'Public workshop', params={'makes': makes})
        foot = self.grids['under-shaft-foot']
        season = foot.nearest(self.feature('under-shaft-foot', '>'))
        self.obj('under-shaft-foot', 'season-door', 'descent_console',
                 'The season door is sealed. Depth and expeditions open with the season.',
                 tile=season, params={'season_door': True})
        cage = self.feature('under-shaft-foot', '!')
        self.obj('under-shaft-foot', 'shaft-cage-lift', 'lift', 'Cage lift', tile=cage,
                 params={'exits': ['to-spire-shaft-head']})
        self.obj('terraces-lobby', 'lobby-letting-terminal', 'terminal', 'Residence letting office',
                 essential=True, params={'letting': True})
        self.obj('terraces-blocks', 'letting-office', 'vendor', 'Letting office',
                 essential=True, params={'letting': True})
        lobby = self.meta['terraces-lobby']
        # Existing S08 apartment doors remain until C1/S25c approves its
        # physical residence geometry. Bindings cannot erase those anchors.
        for zid, oid, kind, name in (
            ('under-service', 'unmoored-dead-drop', 'cache', 'Unmoored dead drop'),
            ('under-service', 'choir-shrine', 'cache', 'Choir shrine'),
            ('under-drowned', 'ferrymen-corpse', 'cache', 'Ferrymen corpse and damaged map'),
            ('under-outworks', 'halvard-survey-markers', 'cache', 'Halvard survey markers'),
            ('scour-ring-4', 'season-artifact-west', 'cache', 'Western artifact site'),
            ('scour-ring-4', 'season-artifact-east', 'cache', 'Eastern artifact site'),
            ('under-shaft-foot', 'choir-shrine', 'cache', 'Choir sign beside the season door'),
            ('under-shaft-foot', 'halvard-marker', 'cache', 'Halvard marker beside the season door'),
        ):
            tile = None
            if zid == 'under-shaft-foot' and oid in ('choir-shrine', 'halvard-marker'):
                tile = foot.nearest((season[0]+(1 if oid == 'choir-shrine' else 2), season[1]))
            self.obj(zid, oid, kind, name, tile=tile)
        artifacts = {o['id']: o for o in self.meta['scour-ring-4']['objects']}
        west, east = artifacts['season-artifact-west'], artifacts['season-artifact-east']
        if west['tile'][0] > east['tile'][0]:
            west['tile'], east['tile'] = east['tile'], west['tile']
        for zid, data in self.definitions.items():
            if zid in self.hubs:
                continue
            sketch = data['sketch']
            for index in range(max(1, min(3, sketch.count('L')))):
                self.obj(zid, 'area-light-'+str(index+1), 'light', 'Maintenance lamp')

    def relays(self) -> None:
        vendors = read(self.output/'vendors.json')
        by_id = {vendor['id']: vendor for vendor in vendors['vendors']}
        for relay in read(self.output/'relays.json')['relays']:
            zid, rid = relay['zone'], relay['id']
            terminal = self.obj(zid, relay['terminal'], 'relay', relay['name'],
                                params={'relay': rid, 'vendor': relay['vendor']})
            by_id[relay['vendor']].update(zone=zid, object_id=terminal['id'])
        write(self.output/'vendors.json', vendors)

    def services(self) -> None:
        # Game 7.5: reserve rewards a real optional shortcut. S21's public
        # relay_open remains bound to capture and grants no worker access.
        zid = 'oldworks-main'
        grid = self.grids[zid]
        corridor = {(22, y) for y in range(5, 9)}
        assert not corridor & grid.reserved
        for tile in corridor:
            grid.mark(tile)
        gate = self.obj(zid, 'relay-zero-workers-gate', 'door',
                        'Workers passage', tile=(22, 7),
                        params={'open': False, 'locked': True})
        path = self.output/'cores/lat-relay-zero.json'
        core = read(path)
        for room in core['rooms']:
            room['controls'] = [c for c in room.get('controls', []) if c['id'] != 'worker_return']
        room = next(room for room in core['rooms']
                    if any(c['id'] == 'relay_open' for c in room.get('controls', [])))
        room['controls'].append(dict(id='worker_return', label='Workers passage',
            target=dict(zone=zid, object=gate['id']), action='open',
            reset_seconds=1200, scope='mission', permission='contract', safety_policy='none'))
        write(path, core)
        path = self.output/'services.json'
        services = read(path)
        service = next(node for node in services['services'] if node['id'] == 'relay-zero')
        reserve = next(choice for choice in service['allocations'] if choice['id'] == 'reserve')
        for effect in reserve['effects']:
            if effect.get('params', {}).get('what') == 'credential':
                effect['binding']['control'] = 'worker_return'
        reserve['detail'] = ('Workers may open the shortcut from the relay mast to the public Old Works counter for 20 minutes. '
                             'The public street stays open. ICE remains active.')
        write(path, services)
        self.obj('tramyard-depots', 'depot-surplus-latch', 'door', 'Surplus counter service latch',
                 params={'open': True})
        self.obj('tramyard-depots', 'depot-reserve-cache', 'cache', 'Workers surplus allocation')
        zid = 'sink-floor'
        # Two side lanes have separate allocations; neither is an outward exit.
        shortcut = [(x, 12) for x in range(20, 25)]
        niche = [(x, 26) for x in range(45, 50)]
        grid = self.grids[zid]
        assert not (set(shortcut+niche) & grid.reserved)
        for tile in shortcut+niche:
            grid.mark(tile, '~')
        for name, drain_shortcut, drain_niche in (
                ('sump-common', True, False), ('sump-reserve', False, True),
                ('sump-fault', False, False)):
            self.layout(zid, name, [dict(tile=list(tile), tile_id='floor' if drained else 'water')
                for tiles, drained in ((shortcut, drain_shortcut), (niche, drain_niche)) for tile in tiles])
            # Flooding itself is harmless; warnings identify changed routes.
            self.meta[zid]['layouts'][-1]['warning_tiles'] = [list(tile) for tile in shortcut+niche]
        pump = self.obj(zid, 'sump-pump-regions', 'pump', 'Public shortcut and salvage pumps',
                        params={'layout': 'sump-common', 'work_order_layouts': ['sump-common', 'sump-reserve']})
        self.obj(zid, 'sump-reserve-cache', 'cache', 'Workers salvage niche', tile=(49, 27))
        # The core also operates these exact regions, rather than a decorative lane.
        core_file = self.output/'cores/lat-sump.json'
        core = read(core_file)
        for room in core['rooms']:
            for control in room.get('controls', []):
                if control['target'].get('object') == pump['id']:
                    control['warning_seconds'] = max(5, control.get('warning_seconds', 0))
        write(core_file, core)

    def contract_anchors(self) -> None:
        contracts = read(self.output/'contracts.json')
        def visit(value: Any) -> None:
            if isinstance(value, list):
                for child in value:
                    visit(child)
            elif isinstance(value, dict):
                if value.get('zone') == 'tramyard-gate-nine':
                    value['zone'] = 'tramyard-wall-gate'
                zid, oid = value.get('zone'), value.get('object')
                if zid in self.meta and oid:
                    # These are physical addresses. Their owning story/mission
                    # supplies consent, rewards and durable interaction later.
                    if not any(obj['id'] == oid for obj in self.meta[zid]['objects']):
                        kind = ('cache' if any(word in oid for word in ('cache', 'locker', 'parcel', 'canister'))
                                else 'door' if 'hatch' in oid else 'terminal')
                        self.obj(zid, oid, kind, oid.replace('-', ' ').capitalize(),
                                 params={'letting': True} if oid == 'letting-office' else {})
                for child in value.values():
                    visit(child)
        visit(contracts)
        write(self.output/'contracts.json', contracts)
        # Service orders are local to their zone. Bind this after the
        # story anchors have created the Warm Stack, preserving its site.
        # The Sable hall upstairs cannot expose a Sump order down here.
        board = next(obj for obj in self.meta['sink-floor']['objects'] if obj['id'] == 'warm-stack-1')
        board['params']['contract_handler'] = 'sable'
        board['essential'] = True

    def population(self) -> None:
        table = read(self.output/'npcs.json')
        templates = {row['id']: row for row in table['npcs']}
        attributes = dict(frame=20, nerve=20, cortex=10, resonance=5, vitals=20)
        for role, source, name, faction in (
            ('halvard-staff', 'kestrel-staff', 'Halvard staff', 'halvard'),
            ('freight-crew', 'civilian', 'Freight crew', 'kestrel'),
            ('market-crowd', 'commuter', 'Market visitor', None),
            ('rim-resident', 'civilian', 'Rim resident', None),
            ('choir-pilgrim', 'civilian', 'Choir pilgrim', 'choir'),
            ('chorister', 'kestrel-staff', 'Chorister', 'choir'),
            ('squatter', 'resident', 'Old Works squatter', 'unmoored'),
            ('road-crew', 'civilian', 'Kestrel road crew', 'kestrel'),
        ):
            template = deepcopy(templates['npc-'+source])
            template.update(id='npc-'+role, name=name, faction=faction)
            templates[template['id']] = template
        # Initial profiles: game design 5.5. Numbers are hypotheses for S25
        # native/human pacing acceptance, not claimed field balance.
        profiles: dict[str, dict[str, Any]] = {
            'halvard-guard': dict(name='Halvard security', faction='halvard', grade=3,
                weapon='wpn_halvard_hv7', armour='arm_kestrel_vest'),
            'halvard-heavy': dict(name='Halvard heavy security', faction='halvard', grade=8,
                health=140, weapon='wpn_halvard_hv9', armour='arm_halvard_guard_suit'),
            'kestrel-guard': dict(name='Kestrel security', faction='kestrel', grade=2,
                weapon='wpn_kestrel_sidearm', armour='arm_kestrel_vest'),
            'choir-guard': dict(name='Choir warden', faction='choir', grade=3,
                weapon='wpn_chapel_tuning_fork', armour='arm_chapel_vestment'),
            'unmoored-guard': dict(name='Unmoored runner', faction='unmoored', grade=3,
                weapon='wpn_ow_arcpen', armour='arm_sable_leathers'),
            'ferrymen-guard': dict(name='Ferrymen guard', faction='ferrymen', grade=4,
                weapon='wpn_ferry_slugthrower', armour='arm_ferry_scrap_plate'),
            'scavenger-raider': dict(name='Scavenger raider', grade=6, health=100,
                weapon='wpn_kestrel_sidearm', armour='arm_sable_leathers'),
            'dog': dict(name='Feral dog', grade=1, health=30, attack=dict(
                damage=6, cooldown=1.5, accuracy=60, range=1, damage_type='kinetic')),
            'feral': dict(name='Feral hunter', grade=5, health=75, attack=dict(
                damage=10, cooldown=1.5, accuracy=60, range=1, damage_type='kinetic')),
            'water-hunter': dict(name='Water hunter', grade=7, health=90, attack=dict(
                damage=12, cooldown=1.5, accuracy=65, range=1, damage_type='kinetic')),
            'blind-swarm': dict(name='Blind swarm', grade=6, health=55, attack=dict(
                damage=8, cooldown=1, accuracy=60, range=1, damage_type='chemical')),
            'apex': dict(name='Scour apex hunter', grade=16, health=180, attack=dict(
                damage=20, cooldown=1.5, accuracy=70, range=1, damage_type='kinetic')),
            'old-maintenance': dict(name='Blacksite maintenance drone', grade=10, health=100, attack=dict(
                damage=12, cooldown=1.5, accuracy=65, range=6, damage_type='energy')),
            'custodian-recovery': dict(name='Custodian recovery drone', grade=20, health=200, attack=dict(
                damage=20, cooldown=1.5, accuracy=70, range=8, damage_type='energy')),
        }
        for role, values in profiles.items():
            hostile = values.get('faction') is None
            templates['npc-'+role] = dict(id='npc-'+role, attributes=attributes, xp=20,
                behaviours=[dict(kind='hunt' if hostile and role not in ('old-maintenance', 'custodian-recovery') else 'guard',
                                 params={'hostile_all': True} if hostile else {})], loot=[], **values)
        # Event recovery is its own declared hostile crew, not a harmless
        # courier standing in for the promised encounter.
        recovery = deepcopy(templates['npc-halvard-heavy'])
        recovery.update(id='npc-halvard-recovery', name='Halvard recovery guard',
                        behaviours=[dict(kind='guard', params={'hostile_all': True})])
        templates[recovery['id']] = recovery

        def spawn(zid: str, role: str, count: int, point: tuple[int, int], *, patrol: bool = False) -> str:
            grid = self.grids[zid]
            water_pad = None
            if role == 'water-hunter':
                candidates = [(x, y) for y in range(2, grid.height-3) for x in range(2, grid.width-3)
                    if all(grid.rows[y+dy][x+dx] == '~' and (x+dx, y+dy) not in grid.reserved
                           for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)))]
                tile = min(candidates, key=lambda p: (abs(p[0]-point[0])+abs(p[1]-point[1]), p))
                water_pad = {(tile[0]+dx, tile[1]+dy) for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1))}
            else:
                tile = grid.nearest(point)
            source = templates['npc-'+role]
            npc_id = source['id']
            if patrol:
                npc_id += '-'+zid
                other = grid.nearest((min(grid.width-3, tile[0]+8), tile[1]))
                grid.connect(tile, other)
                template = deepcopy(source)
                template.update(id=npc_id, behaviours=[dict(kind='patrol',
                    params={'waypoints': [list(tile), list(other)], 'bounce': True}), *source['behaviours']])
                templates[npc_id] = template
            sid = role+'-crew'
            # Small authored pads keep every slot off walls, private rooms,
            # clinic pockets and exits. Movement afterwards uses ordinary AI.
            pad = water_pad or {tile}
            if water_pad is None:
                for delta in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                    candidate = tile[0]+delta[0], tile[1]+delta[1]
                    if grid.safe(candidate) and candidate not in grid.reserved:
                        pad.add(candidate)
            assert len(pad) >= count, (zid, role, tile, count)
            x0, y0 = min(x for x, _ in pad), min(y for _, y in pad)
            x1, y1 = max(x for x, _ in pad), max(y for _, y in pad)
            self.meta[zid]['spawners'].append(dict(id=sid, npc=npc_id, count=count,
                respawn_seconds=60, condition='always', region=dict(x=x0, y=y0, w=x1-x0+1, h=y1-y0+1)))
            grid.reserved.update(pad)
            return sid

        placements = {
            'spire-atrium': [('halvard-guard', 2, (15, 8))],
            'spire-mezzanine': [('halvard-guard', 2, (14, 8)), ('halvard-staff', 2, (35, 16))],
            'spire-shaft-head': [('halvard-heavy', 2, (15, 28)), ('maintenance-drone', 1, (29, 30))],
            'tramyard-depots': [('kestrel-guard', 2, (25, 15)), ('freight-crew', 3, (75, 28))],
            'tramyard-market': [('kestrel-guard', 2, (20, 18)), ('market-crowd', 4, (60, 25))],
            'tramyard-wall-gate': [('kestrel-guard', 2, (20, 20)), ('halvard-guard', 2, (50, 30))],
            'sink-rim': [('sable-enforcer', 2, (70, 15)), ('rim-resident', 3, (25, 18))],
            'sink-terraces': [('sable-enforcer', 2, (55, 30)), ('resident', 3, (25, 35)), ('scavenger-raider', 2, (60, 45))],
            'sink-floor': [('feral', 2, (45, 15)), ('dog', 2, (55, 30))],
            'chapel-towers': [('choir-guard', 2, (20, 20)), ('choir-pilgrim', 3, (55, 20))],
            'chapel-nave': [('choir-guard', 2, (15, 20)), ('chorister', 2, (35, 20))],
            'oldworks-main': [('unmoored-guard', 2, (25, 18)), ('squatter', 3, (75, 23))],
            'oldworks-yards': [('unmoored-guard', 2, (20, 25)), ('maintenance-drone', 2, (75, 30))],
            'oldworks-drop': [('unmoored-guard', 2, (12, 9))],
            'under-service': [('maintenance-drone', 2, (25, 35)), ('dog', 2, (75, 35))],
            'under-drowned': [('water-hunter', 2, (65, 35)), ('maintenance-drone', 1, (25, 40))],
            'under-caverns': [('feral', 2, (75, 45)), ('blind-swarm', 1, (100, 25)), ('ferrymen-guard', 2, (25, 20))],
            'under-outworks': [('old-maintenance', 2, (60, 40)), ('unmoored-guard', 2, (25, 30))],
            'under-shaft-foot': [('old-maintenance', 4, (25, 30))],
            'scour-landing': [('ferrymen-guard', 2, (15, 20)), ('dog', 2, (40, 25))],
            'scour-ring-1': [('halvard-guard', 2, (100, 25)), ('dog', 3, (75, 55)), ('road-crew', 2, (35, 40))],
            'scour-ring-2': [('ferrymen-guard', 2, (65, 25)), ('feral', 2, (110, 60)), ('scavenger-raider', 1, (110, 30))],
            'scour-ring-3': [('feral', 3, (100, 65)), ('halvard-heavy', 2, (140, 30)), ('scavenger-raider', 2, (145, 70))],
            'scour-ring-4': [('apex', 2, (75, 35)), ('custodian-recovery', 2, (150, 65))],
        }
        for zid, rows in placements.items():
            for role, count, point in rows:
                spawn(zid, role, count, point, patrol=role in ('halvard-guard', 'halvard-heavy'))
        sid = spawn('under-shaft-foot', 'feral', 2, (40, 40))
        next(sp for sp in self.meta['under-shaft-foot']['spawners'] if sp['id'] == sid)['condition'] = 'event:exhale'
        for zid, meta in self.meta.items():
            for obj in meta['objects']:
                if obj['kind'] not in ('turret', 'patrol_beacon'):
                    continue
                role = ('sable-enforcer' if zid == 'sink-terraces' else
                        'maintenance-drone' if 'forklift' in obj['id'] else 'halvard-guard')
                sid = next((sp['id'] for sp in meta['spawners'] if sp['id'] == role+'-crew'), None)
                if sid is None:
                    x, y = obj['tile']
                    sid = spawn(zid, role, 2, (max(3, x-5), y), patrol=obj['kind'] == 'patrol_beacon')
                obj['params']['spawners'] = [sid]
                if obj['kind'] == 'patrol_beacon':
                    obj['params']['destination'] = list(self.grids[zid].nearest((10, 10)))
        table['npcs'] = list(templates.values())
        write(self.output/'npcs.json', table)

    def events(self) -> None:
        for ring in range(1, 5):
            zid = f'scour-ring-{ring}'
            self.obj(zid, 'salvage-field', 'salvage_field', 'Ring salvage field', params={'ring': ring})
        tiles = read(self.output/'tiles.json')
        if not any(tile['id'] == 'convoy-road' for tile in tiles['tiles']):
            # Game 5.1: visible gravel, ordinary movement, no cover bonus.
            tiles['tiles'].append(dict(id='convoy-road', char='\u00b7', glyph='cover-1',
                                       colour='floor', passable=True))
        write(self.output/'tiles.json', tiles)
        route = read(self.output/'routes.json')['routes'][0]
        for index, waypoint in enumerate(route['waypoints']):
            zid, point = waypoint['zone'], tuple(waypoint['tile'])
            meta, grid = self.meta[zid], self.grids[zid]
            previous = 'tramyard-wall-gate' if index == 0 else route['waypoints'][index-1]['zone']
            start = tuple(next(ex['tile'] for ex in meta['exits'] if ex['target_zone'] == previous))
            end = (tuple(next(ex['tile'] for ex in meta['exits']
                              if ex['target_zone'] == route['waypoints'][index+1]['zone']))
                   if index+1 < len(route['waypoints']) else point)
            for a, b in ((start, point), (point, end)):
                grid.connect(a, b)
                pending, parents = deque([a]), {a: None}
                while pending and b not in parents:
                    x, y = pending.popleft()
                    for nxt in ((x+1, y), (x, y+1), (x-1, y), (x, y-1)):
                        if nxt not in parents and grid.safe(nxt):
                            parents[nxt] = (x, y)
                            pending.append(nxt)
                assert b in parents
                current = b
                while current is not None:
                    if current not in grid.reserved:
                        grid.mark(current, '\u00b7')
                    current = parents[current]
            marker = grid.nearest((point[0], max(2, point[1]-2)))
            self.obj(zid, 'convoy-road-marker', 'cache', 'Convoy road waypoint', tile=marker,
                     params={'route': route['id']})
        table = read(self.output/'events.json')
        footprints = {}
        for ring in range(1, 5):
            zid = f'scour-ring-{ring}'
            grid = self.grids[zid]
            sites = [(x, y) for y in range(5, grid.height-15, 5) for x in range(5, grid.width-25, 5)
                if all(grid.safe((xx, yy)) and (xx, yy) not in grid.reserved
                       and grid.rows[yy][xx] != '\u00b7'
                       for yy in range(y, y+10) for xx in range(x, x+20))]
            x, y = min(sites, key=lambda p: (abs(p[0]-grid.width*3//5)+abs(p[1]-grid.height*3//5), p))
            footprints[zid] = dict(x=x, y=y, w=20, h=10)
        for event in table['events']:
            if event['id'] == 'ring-fall':
                for effect in event['effects']:
                    if effect['type'] in ('hazard', 'npc_spawn'):
                        effect['region'] = footprints[effect['zone']]
                    if effect['type'] == 'npc_spawn':
                        effect['params']['npc'] = 'npc-halvard-recovery'
        write(self.output/'events.json', table)
        zid = 'under-outworks'
        # Exhale opens a side passage. The ordinary Outworks/Shaft route
        # remains available regardless of event timing or key possession.
        # Open an actual wall crossing that saves a measurable detour;
        # do not add a decorative barrier to otherwise open floor.
        grid = self.grids[zid]
        options = []
        for y in range(12, 39):
            a, b = (38, y), (82, y)
            if not grid.safe(a) or not grid.safe(b):
                continue
            line = [(x, y) for x in range(a[0]+1, b[0])]
            walls = [tile for tile in line if grid.rows[tile[1]][tile[0]] == '#']
            if not walls or any(grid.rows[yy][xx] in '=!' for xx, yy in line):
                continue
            distances, pending = {a: 0}, deque([a])
            while pending and b not in distances:
                x0, y0 = pending.popleft()
                for nxt in ((x0+1, y0), (x0-1, y0), (x0, y0+1), (x0, y0-1)):
                    if nxt not in distances and grid.safe(nxt):
                        distances[nxt] = distances[x0, y0]+1
                        pending.append(nxt)
            if b in distances:
                options.append((distances[b]-(b[0]-a[0]), -y, walls))
        saving, _, walls = max(options)
        assert saving >= 8, f'Exhale crossing saves only {saving} tiles'
        changes = [dict(tile=list(tile), tile_id='floor') for tile in walls]
        self.layout(zid, 'exhale-shortcut', changes)

    def commission(self) -> None:
        for name in ('s25-commerce', 's25-cores', 's25-faction-sites', 's25-relays',
                     's19-future-services', 's24-future-events'):
            path = self.output/'bundles'/(name+'.json')
            bundle = read(path)
            bundle['status'] = 'active'
            additional = {'s25-cores': ['s24-future-events'],
                          's25-faction-sites': ['s25-commerce'],
                          's25-relays': ['s25-cores']}.get(name, [])
            bundle['depends'] = list(dict.fromkeys([*bundle.get('depends', []), *additional]))
            write(path, bundle)
        for path in sorted((self.output/'sectors').glob('*.json')):
            sector = read(path)
            for cell in sector['cells']:
                if cell.get('core_placeholder') and cell.get('planned_core'):
                    cid = cell['planned_core']
                    core_path = self.output/'cores'/(cid+'.json')
                    if core_path.exists() and not read(core_path).get('template'):
                        cell['core_id'] = cell.pop('planned_core')
                        cell.pop('core_placeholder')
            write(path, sector)

    def bearing(self, zid: str, target: str, neighbours: list[str]) -> tuple[int, int]:
        meta, grid = self.meta[zid], self.grids[zid]
        if (zid, target) == ('oldworks-main', 'oldworks-drop'):
            return self.feature(zid, '+')
        if (zid, target) == ('under-shaft-foot', 'spire-shaft-head'):
            return self.feature(zid, '!')
        old = next((ex for ex in meta['exits'] if ex['target_zone'] == target), None)
        if old:
            return tuple(old['tile'])
        boundary = next((obj for obj in meta['objects']
                         if obj.get('params', {}).get('unavailable_target') == target), None)
        if boundary:
            return tuple(boundary['tile'])
        if target in BEARINGS.get(zid, {}):
            return BEARINGS[zid][target]
        choices = [(2, grid.height//2), (grid.width-3, grid.height//2),
                   (grid.width//2, 2), (grid.width//2, grid.height-3),
                   (2, grid.height//4), (grid.width-3, grid.height*3//4)]
        return choices[neighbours.index(target)]

    @staticmethod
    def exit_kind(source: str, target: str) -> str:
        pair = {source, target}
        if 'core-tram-hub' in pair:
            return 'tram'
        if pair <= {'spire-atrium', 'spire-mezzanine', 'spire-shaft-head', 'under-shaft-foot'}:
            return 'lift'
        if pair == {'sink-rim', 'sink-terraces'}:
            return 'cable'
        if source == 'tramyard-wall-gate' and target in ('scour-ring-1', 'scour-landing'):
            return 'gate'
        if (source.startswith('under-') or target.startswith('under-')):
            return 'door' if pair in ({'under-drowned', 'under-outworks'},
                                     {'under-outworks', 'under-shaft-foot'}) else 'ladder'
        if 'oldworks-drop' in pair or 'chapel-nave' in pair:
            return 'door'
        return 'street'

    def exits(self) -> None:
        neighbours = {zid: set(d['neighbours']) for zid, d in self.definitions.items()}
        for zid, targets in tuple(neighbours.items()):
            for target in tuple(targets):
                neighbours[target].add(zid)
        positions = {(zid, target): self.bearing(zid, target, sorted(targets))
                     for zid, targets in neighbours.items() for target in targets}
        for zid, targets in neighbours.items():
            meta, grid = self.meta[zid], self.grids[zid]
            for target in sorted(targets):
                if any(ex['target_zone'] == target for ex in meta['exits']):
                    continue
                tile, arrival = positions[zid, target], positions[target, zid]
                if zid == 'under-outworks' and target == 'under-drowned':
                    # Arrive beside the closed bulkhead, on public floor.
                    arrival = arrival[0]-1, arrival[1]
                    self.grids[target].mark(arrival)
                ex: dict[str, Any] = dict(id='to-'+target, tile=list(tile), target_zone=target,
                                         target_tile=list(arrival), kind=self.exit_kind(zid, target))
                if zid == 'spire-atrium' and target == 'spire-mezzanine':
                    ex.update(requirement=dict(kind='faction', ref='halvard', standing=10),
                              alternatives=[dict(kind='pass', ref='key_visitor_pass')],
                              locked_text='The lift needs Halvard standing +10 or a Spire Visitor\'s Pass.')
                elif zid == 'spire-mezzanine' and target == 'spire-shaft-head':
                    ex.update(requirement=dict(kind='member', ref='halvard'),
                              alternatives=[dict(kind='story', ref='halvard-service-lift')],
                              locked_text='The service lift needs Halvard membership or mission authorization.')
                elif {zid, target} == {'spire-shaft-head', 'under-shaft-foot'}:
                    ex.update(requirement=dict(kind='story', ref='shaft-cage'),
                              locked_text='The cage stays sealed until the finale.')
                elif zid == 'under-drowned' and target == 'under-outworks':
                    ex.update(requirement=dict(kind='key', ref='key_undercity'),
                              alternatives=[dict(kind='open', ref=zid, object='drowned-bulkhead')],
                              locked_text='The bulkhead needs an Undercity key or its core latch opened.')
                if (zid == 'oldworks-main' and target == 'oldworks-drop'
                        or {zid, target} == {'under-caverns', 'scour-ring-2'}):
                    ex['hidden'] = True
                if ex['kind'] == 'gate':
                    ex['relay'] = 'gate-nine'
                if ex['kind'] == 'cable':
                    ex['relay'] = 'cable'
                meta['exits'].append(ex)
                grid.mark_exit(tile, bool(ex.get('hidden')))
                grid.reserved.add(tile)
            meta['objects'] = [obj for obj in meta['objects']
                               if obj.get('params', {}).get('unavailable_target') not in self.definitions]
        # A free ladder is independent of cable ownership or payment.
        for source, target in (('sink-rim', 'sink-terraces'), ('sink-terraces', 'sink-rim')):
            tile = positions[source, target]
            arrival = positions[target, source]
            start, end = (tile[0]+3, tile[1]), (arrival[0]+3, arrival[1])
            self.grids[source].mark(start)
            self.grids[source].reserved.add(start)
            self.meta[source]['exits'].append(dict(id='free-ladder-to-'+target,
                tile=list(start), target_zone=target, target_tile=list(end), kind='ladder'))
            for station, x, other_x in (('west', 25 if source == 'sink-rim' else 22,
                                        22 if source == 'sink-rim' else 25),
                                       ('east', 75 if source == 'sink-rim' else 67,
                                        67 if source == 'sink-rim' else 75)):
                local, remote = (x, tile[1]), (other_x, arrival[1])
                self.grids[source].mark(local)
                self.grids[source].reserved.add(local)
                self.meta[source]['exits'].append(dict(id='cable-'+station+'-to-'+target,
                    tile=list(local), target_zone=target, target_tile=list(remote), kind='cable', relay='cable'))

    def base_paths(self) -> None:
        npcs = {npc['id']: npc for npc in read(self.output/'npcs.json')['npcs']}
        # The two Shaft Head heavies share a patrol through this alcove.
        # A single-file doorway lets them seal the public hardware by
        # meeting nose to nose. Leave a maintenance aisle to pass them.
        head = self.grids['spire-shaft-head']
        for y in range(24, 27):
            for x in range(16, 24):
                if head.rows[y][x] == '#':
                    head.mark((x, y))
        for zid, meta in self.meta.items():
            grid = self.grids[zid]
            for point in [*(ex['tile'] for ex in meta['exits']), *(obj['tile'] for obj in meta['objects'])]:
                grid.connect(tuple(meta['spawn']), tuple(point))
            # A passable spawn pad can still lie inside a sealed factory
            # room. Its occupants then make every unrelated core latch
            # wait forever for a public escape. Join all spawn candidates
            # and patrol points to the existing public component without
            # relying on a locked optional shortcut.
            blocked = {tuple(obj['tile']) for obj in meta['objects']
                       if obj.get('params', {}).get('locked')}
            targets: set[tuple[int, int]] = set()
            for spawner in meta['spawners']:
                if region := spawner.get('region'):
                    candidates = [(x, y) for y in range(region['y'], region['y']+region['h'])
                                  for x in range(region['x'], region['x']+region['w'])]
                else:
                    candidates = [tuple(spawner['tile'])] if spawner.get('tile') else []
                targets.update(tile for tile in candidates if grid.safe(tile) and tile not in blocked)
                for behaviour in npcs[spawner['npc']].get('behaviours', []):
                    targets.update(tuple(point) for point in behaviour.get('params', {}).get('waypoints', []))
            for point in sorted(targets):
                grid.connect(tuple(meta['spawn']), point, avoid=blocked)

    def frame_route_doors(self) -> None:
        """Minimum door frames, not S25c's deferred room/identity work."""
        controlled = set()
        for path in sorted((self.output/'cores').glob('*.json')):
            for room in read(path)['rooms']:
                controlled.update((c['target'].get('zone'), c['target'].get('object'))
                                  for c in room.get('controls', []))
        for meta in self.meta.values():
            for ex in meta['exits']:
                for credential in (ex.get('requirement'), *ex.get('alternatives', [])):
                    if credential and credential['kind'] == 'open':
                        controlled.add((credential['ref'], credential.get('object')))
        npcs = {npc['id']: npc for npc in read(self.output/'npcs.json')['npcs']}
        for zid, meta in self.meta.items():
            if zid in self.hubs:
                continue
            grid = self.grids[zid]
            required = {tuple(ex['tile']) for ex in meta['exits']
                        if ex.get('requirement') or ex.get('alternatives')}
            protected = set(grid.reserved) | grid.private
            protected.add(tuple(meta['spawn']))
            protected.update(tuple(ex['target_tile']) for other in self.meta.values()
                             for ex in other['exits'] if ex['target_zone'] == zid)
            for spawner in meta['spawners']:
                if spawner.get('tile'):
                    protected.add(tuple(spawner['tile']))
                for behaviour in npcs[spawner['npc']].get('behaviours', []):
                    protected.update(tuple(p) for p in behaviour.get('params', {}).get('waypoints', []))
            for obj in meta['objects']:
                tile = tuple(obj['tile'])
                if obj['kind'] not in ('door', 'gate', 'shutter') or not (
                        (zid, obj['id']) in controlled or obj.get('params', {}).get('control') or tile in required):
                    continue
                if axis := door_wall_axis(grid.safe, tile):
                    grid.fixed_walls.update(axis)
                    continue
                options = []
                exit_tiles = {tuple(ex['tile']) for ex in meta['exits']}
                candidates = [tile] if tile in exit_tiles else [tile, *(
                    (x, y) for y in range(1, grid.height-1) for x in range(1, grid.width-1)
                    if grid.safe((x, y)) and (x, y) not in protected)]
                for candidate in sorted(candidates, key=lambda p: (abs(p[0]-tile[0])+abs(p[1]-tile[1]), p)):
                    x, y = candidate
                    for flanks, sides in ((((x, y-1), (x, y+1)), ((x-1, y), (x+1, y))),
                                          (((x-1, y), (x+1, y)), ((x, y-1), (x, y+1)))):
                        if not all(grid.inside(p) for p in (*flanks, *sides)) or not all(grid.safe(p) for p in sides):
                            continue
                        changed = {p for p in flanks if grid.rows[p[1]][p[0]] != '#'}
                        regions_fit = all(
                            sum(grid.safe((sx, sy)) and (sx, sy) not in changed
                                for sy in range(region['y'], region['y']+region['h'])
                                for sx in range(region['x'], region['x']+region['w'])) >= spawner['count']
                            for spawner in meta['spawners'] if (region := spawner.get('region')))
                        if not changed & protected and regions_fit:
                            options.append((len(changed), flanks, candidate))
                    if options:
                        break
                assert options, f'No safe route-door frame: {zid}/{obj["id"]} at {tile}'
                _, flanks, candidate = min(options)
                if candidate != tile:
                    grid.mark(tile, '.')
                    obj['tile'] = list(candidate)
                    grid.reserved.add(candidate)
                    grid.mark(candidate, '+')
                    tile = candidate
                for flank in flanks:
                    grid.mark(flank, '#')
                grid.fixed_walls.update(flanks)
                assert door_wall_axis(grid.safe, tile), (zid, obj['id'])

    def save(self) -> None:
        tiles = {tile['id']: tile for tile in read(self.output/'tiles.json')['tiles']}
        for zid, meta in self.meta.items():
            grid = self.grids[zid]
            for tile in [*(tuple(ex['tile']) for ex in meta['exits']),
                         *(tuple(obj['tile']) for obj in meta['objects'])]:
                grid.connect(tuple(meta['spawn']), tile)
            blocked = {tuple(change['tile']) for layout in meta.get('layouts', [])
                       for change in layout.get('changes', []) if not tiles[change['tile_id']]['passable']
                       or tiles[change['tile_id']].get('hazard')}
            blocked.update(tuple(obj['tile']) for obj in meta['objects'] if obj.get('params', {}).get('locked'))
            anchors = [ex['tile'] for ex in meta['exits']]
            anchors.extend(obj['tile'] for obj in meta['objects'] if obj.get('essential') or obj['kind'] in
                           ('hardware', 'vendor', 'bank', 'apartment_door', 'workshop'))
            for point in anchors:
                target = tuple(point)
                if target in blocked:
                    x, y = target
                    target = min((p for p in ((x-1, y), (x+1, y), (x, y-1), (x, y+1))
                                  if grid.inside(p) and p not in grid.private | blocked),
                                 key=lambda p: (abs(p[0]-meta['spawn'][0])+abs(p[1]-meta['spawn'][1]), p))
                grid.connect(tuple(meta['spawn']), target, avoid=blocked)
            for ex in meta['exits']:
                grid.mark_exit(tuple(ex['tile']), bool(ex.get('hidden')))
            write(self.output/'zones'/(zid+'.json'), meta)
            if zid in self.hubs:
                original = [list(row) for row in (SHIPPED/'zones'/(zid+'.map')).read_text(encoding='utf-8').splitlines()]
                for ex in meta['exits']:
                    x, y = ex['tile']
                    original[y][x] = '.' if ex.get('hidden') else '>'
                assert grid.text() == '\n'.join(''.join(row) for row in original)+'\n', zid
            (self.output/'zones'/(zid+'.map')).write_text(grid.text(), encoding='utf-8', newline='\n')
            if zid not in self.hubs:
                (self.output/'text'/('zone-'+zid+'.md')).write_text(
                    textwrap.fill(ATMOSPHERE[zid], width=72)+'\n', encoding='utf-8', newline='\n')
        print('Authored', len(self.meta), 'ordinary maps; finale instance remains S26.')


def build(output: Path) -> None:
    if output.resolve() != SHIPPED.resolve():
        shutil.copytree(SHIPPED, output, dirs_exist_ok=True)
    city = City(output)
    city.exits()
    city.hardware()
    city.merchants()
    city.factions()
    city.public_objects()
    city.relays()
    city.services()
    city.contract_anchors()
    # #78 decision 6491941496: homes and their 48-cell register are C1/S25c.
    city.population()
    city.base_paths()
    city.events()
    city.commission()
    city.frame_route_doors()
    city.save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'.test-tmp/s25-city-draft')
    build(parser.parse_args().output)
