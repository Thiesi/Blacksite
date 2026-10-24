"""S24 labelled event sites on hubs; never loaded by production worlds.

This supplies service-composition and event source fixtures, not Scour or
Undercity geography, ordinary earning pace or human play acceptance.
"""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from blacksite.content.loader import load_content
from contracts_fixture import build_fixture as service_fixture


def build_fixture(shipped: Path, local: Path) -> dict[str, Any]:
    descriptor = service_fixture(shipped, local)
    def read(name: str) -> Any:
        return json.loads((shipped/name).read_text(encoding='utf-8'))
    def write(name: str, value: Any) -> None:
        path = local/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    content = load_content(shipped, local)
    zone = content.zones['vatside-clinics']
    reserved = {o.tile for o in zone.meta.objects} | {e.tile for e in zone.meta.exits}
    def clear(tile: tuple[int, int]) -> bool:
        key = zone.tile_at(tile)
        return bool(key in content.tiles and content.tiles[key].passable
            and not content.tiles[key].hazard and tile not in reserved
            and not any(p.contains(tile) for p in zone.meta.pockets))
    tile = next((x,y) for y in range(3,zone.height-3) for x in range(3,zone.width-3)
        if all(clear((x+dx,y+dy)) for dx in range(-2,3) for dy in range(-2,3)))
    region = dict(x=tile[0]-2,y=tile[1]-2,w=5,h=5)
    physical = read('zones/vatside-clinics.json')
    physical['objects'].append(dict(id='fixture-ring-field',kind='salvage_field',tile=list(tile),params={'ring':1}))
    write('zones/vatside-clinics.json', physical)
    (local/'zones/vatside-clinics.map').write_bytes((shipped/'zones/vatside-clinics.map').read_bytes())
    events = {row['id']: deepcopy(row) for row in read('events.json')['events']}
    ring = events['ring-fall']
    ring['where'] = [zone.id]
    ring['effects'] = [dict(type='salvage',zone=zone.id,params={'count':10,'cap':40}),
        dict(type='hazard',zone=zone.id,region=region,warning_seconds=5,params={'radius':1,'seconds':5})]
    exhale = events['exhale']
    exhale['where'] = [zone.id, descriptor['zone']]
    exhale['effects'] = [dict(type='key_drop',zone=zone.id,region=region,params={'item':'key_undercity','count':1}),
        dict(type='spawn_multiplier',zone=zone.id,params={'multiplier':3,'cap':6}),
        dict(type='route_hold',zone=descriptor['zone'],params={'layout':'fixture-event-shortcut'})]
    write('events.json',dict(schema=1,events=[ring,exhale]))
    bundle = read('bundles/s24-future-events.json')
    bundle['members']['events'] = ['convoy']
    write('bundles/s24-future-events.json', bundle)
    bay_path = local/'zones'/(descriptor['zone']+'.json')
    bay = json.loads(bay_path.read_text(encoding='utf-8'))
    bay['layouts'].append(dict(id='fixture-event-shortcut',changes=[dict(tile=[25,12],tile_id='wall')],
        warning_tiles=[],alternate_routes=['return-wake']))
    write('zones/'+descriptor['zone']+'.json',bay)
    core_path = local/'cores'/(descriptor['core']+'.json')
    core = json.loads(core_path.read_text(encoding='utf-8'))
    next(room for room in core['rooms'] if room['id']==core['entry'])['ice'] = ['ice_ticker']
    write('cores/'+descriptor['core']+'.json',core)
    return {**descriptor,'event_zone':zone.id,'event_region':region,
            'event_fixtures':['Ring-fall/Exhale sites on Vatside Clinics',
                              'optional event wall and Ticker in S19 service bay']}
