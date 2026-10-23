"""Labelled S21 passage fixtures in real hub zones; not S25 geography proof."""

from copy import deepcopy
import json
from pathlib import Path


def build_passage_fixture(shipped: Path, local: Path) -> tuple[str, str]:
    def read(name: str) -> dict:
        return json.loads((shipped/name).read_text('utf-8'))
    def write(name: str, value: dict) -> None:
        target=local/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    table=read('relays.json')
    overrides=[]
    exits=[]
    for rid,kind in (('cold-chain','cable_ride'),('block','fast_gate')):
        relay=deepcopy(next(row for row in table['relays'] if row['id']==rid))
        relay['benefit']={'kind':kind,'amount':0}
        overrides.append(relay)
        zone=read('zones/'+relay['zone']+'.json')
        route=next(ex for ex in zone['exits'] if (shipped/('zones/'+ex['target_zone']+'.json')).exists())
        if kind=='cable_ride':
            free=deepcopy(route)
            free.update(id='zz-s21-free-stairs',kind='ladder')
            zone['exits'].append(free)
        route.update(kind='cable' if kind=='cable_ride' else 'gate',relay=rid)
        zone['name']='S21 passage fixture'
        write('zones/'+relay['zone']+'.json',zone)
        (local/'zones'/f"{relay['zone']}.map").write_bytes((shipped/'zones'/f"{relay['zone']}.map").read_bytes())
        exits.append(route['id'])
    write('relays.json',{'schema':1,'relays':overrides})
    return exits[0],exits[1]
