"""S19 native acceptance geography; never loaded by a production world.

The extra bay binds the three future service orders and two story forks
to explicit small fixtures. Cold Chain retains its shipped clinic/core.
This proves interactions and state, not S25 travel or human pacing.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any


def build_fixture(shipped: Path, local: Path) -> dict[str,Any]:
    def read(name: str) -> Any:
        return json.loads((shipped/name).read_text('utf-8'))
    def write(name: str, data: Any) -> None:
        path = local/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    zone_id,core_id = 'fixture-service-bay','lat-fixture-service-bay'
    width,height = 52,20
    grid = [['#' if x in (0,width-1) or y in (0,height-1) else '.' for x in range(width)]
            for y in range(height)]
    for y in range(2,18):
        if y != 5:
            grid[y][22]='#'
    for x in range(30,35):
        grid[3][x]=grid[7][x]='#'
    for y in range(3,8):
        grid[y][30]=grid[y][34]='#'
    objects: list[dict[str,Any]] = []
    def obj(id: str, tile: tuple[int,int], kind: str, **params: Any) -> None:
        objects.append(dict(id=id,tile=list(tile),kind=kind,params=params))
    for x,sid,giver in ((6,'sump','sable'),(12,'depot','kestrel'),(18,'relay-zero','unmoored')):
        obj('fx-'+sid+'-board',(x,4),'terminal',name='FIXTURE '+sid+' board',contract_handler=giver)
        obj('fx-'+sid+'-supply',(x,6),'cache',name='FIXTURE bound supplies')
        obj('fx-'+sid+'-hardware',(x,8),'door',name='FIXTURE '+sid+' hardware',open=False)
    obj('fx-loan',(8,10),'terminal',name='FIXTURE public loan terminal',cell='lat-core-c11')
    obj('fx-core-hardware',(9,10),'hardware',name='FIXTURE service cabinet')
    obj('fx-sump-cache',(32,5),'cache',name='FIXTURE Sump workers cache')
    obj('fx-depot-cache',(16,11),'cache',name='FIXTURE Depot workers cache')
    obj('fx-depot-surplus',(16,12),'vendor',name='FIXTURE surplus counter',vendor='kestrel-surplus')
    for id,tile in (('fx-ration-crate',(10,13)),('fx-squat',(37,11)),('fx-shelter',(42,11)),
                    ('fx-clinic-arrival',(37,15)),('fx-shield-socket',(43,12)),('fx-rig-supply',(36,15))):
        obj(id,tile,'cache',name='FIXTURE '+id[3:].replace('-',' '))
    obj('fx-sablier-board',(37,16),'terminal',name='FIXTURE clinic terms',contract_handler='sablier')
    obj('fx-kestrel-board',(12,15),'terminal',name='FIXTURE ration terms',contract_handler='kestrel')
    obj('fx-unmoored-board',(43,16),'terminal',name='FIXTURE shelter terms',contract_handler='unmoored')
    def layout(id: str, shortcut: bool, niche: bool) -> dict[str,Any]:
        return dict(id=id,changes=[dict(tile=[22,5],tile_id='floor' if shortcut else 'wall'),
                                  dict(tile=[30,5],tile_id='floor' if niche else 'wall')],
                    warning_tiles=[[22,5],[30,5]],alternate_routes=['return-wake'])
    zone = dict(schema=1,id=zone_id,name='FIXTURE service bay',district='Core',safety='safe',
                sight_radius=52,spawn=[3,9],sector='lat-core',
                exits=[dict(id='return-wake',tile=[2,9],target_zone='vatside-wake-hall',target_tile=[36,16],kind='street')],
                layouts=[layout('sump-fault',False,False),layout('sump-common',True,False),layout('sump-reserve',False,True)],
                objects=objects,spawners=[])
    write('zones/'+zone_id+'.json',zone)
    (local/'zones'/f'{zone_id}.map').write_text('\n'.join(''.join(row) for row in grid)+'\n',encoding='utf-8',newline='\n')
    wake=read('zones/vatside-wake-hall.json')
    wake['exits'].append(dict(id='fixture-bay',tile=[36,17],target_zone=zone_id,target_tile=[3,9],kind='street'))
    write('zones/vatside-wake-hall.json',wake)
    (local/'zones/vatside-wake-hall.map').write_bytes((shipped/'zones/vatside-wake-hall.map').read_bytes())
    sector=read('sectors/lat-core.json')
    entrance=next(c for c in sector['cells'] if c['id']=='lat-core-c11')
    assert entrance['kind']=='public' and not entrance.get('core_id') and not entrance.get('core_placeholder')
    entrance.update(kind='core_entrance',core_id=core_id,label='FIXTURE service cabinet')
    write('sectors/lat-core.json',sector)
    core=read('cores/lat-stairwell-c.json')
    core.update(id=core_id,name='FIXTURE service cabinet',owner='kestrel',owner_kind='neutral',
                affiliation=None,hardware=[dict(zone=zone_id,object_id='fx-core-hardware',tile=[9,10],label='FIXTURE bay cabinet')])
    entry=core['entry']
    for room in core['rooms']:
        room['controls']=[]
        room['data']=[]
        room['ice']=[]
    main=next(r for r in core['rooms'] if r['id']==entry)
    spare=next(r for r in core['rooms'] if r['id']!=entry)
    spare['ice']=['ice_tripwire']  # Alive authored deployment for published telemetry.
    for sid in ('sump','depot','relay-zero'):
        main['controls'].append(dict(id='fx-'+sid+'-release',label='FIXTURE '+sid+' release',
            target=dict(zone=zone_id,object='fx-'+sid+'-hardware'),action='open',reset_seconds=1200,
            scope='mission',permission='contract',safety_policy='none'))
    for id in ('fx-relay-verification','fx-ration-record'):
        main['data'].append(dict(id=id,label='FIXTURE '+id[3:].replace('-',' '),kind='contract_key',
                                 asset=id,amount=1,scope='mission',respawn_seconds=0))
    write('cores/'+core_id+'.json',core)
    original={j['id']:j for j in read('contracts.json')['contracts']}
    nodes=deepcopy(read('services.json')['services'])
    jobs=[]
    for node in nodes:
        if node['id']=='cold-chain':
            continue
        sid=node['id']
        node.update(zone=zone_id,core=core_id,target_objects=['fx-'+sid+'-hardware'],safe_return='Use the long south passage to the Wake Hall exit.')
        job=deepcopy(original[node['contract']])
        for st in job['stages']:
            target=st['target']
            if target['kind'] in ('zone_object','item'):
                target.update(zone=zone_id,object='fx-'+sid+('-supply' if st['id']=='collect' else '-hardware'))
            elif target['kind']=='core_control':
                target.update(core=core_id,control='fx-'+sid+'-release')
            elif target['kind']=='core_room':
                target.update(core=core_id,room=entry,data='fx-relay-verification')
        jobs.append(job)
        for effect in [*node.get('fault_effects',[]),*(e for a in node['allocations'] for e in a['effects'])]:
            if effect.get('zone'):
                effect['zone']=zone_id
            if effect['params'].get('object'):
                effect['params']['object']='fx-sump-cache' if sid=='sump' else 'fx-depot-cache' if effect['type']=='cache' else 'fx-depot-surplus'
            if effect.get('binding'):
                effect['binding']['core']=core_id
                if effect['binding']['kind']=='core_room':
                    effect['binding']['room']=entry
                else:
                    effect['binding']['control']='fx-relay-zero-release'
    write('services.json',dict(schema=1,services=nodes))
    manifest=read('bundles/s19-future-services.json')
    manifest['members']=dict(services=[],contracts=[])
    write('bundles/s19-future-services.json',manifest)
    vendors=read('vendors.json')['vendors']
    surplus=deepcopy(next(v for v in vendors if v['id']=='wake-outfitter'))
    surplus.update(id='kestrel-surplus',name='FIXTURE surplus',faction='kestrel',stock=[],
                   zone=zone_id,object_id='fx-depot-surplus')
    write('vendors.json',dict(schema=1,vendors=[surplus]))
    # Story copies retain their real rewards/branch groups; only geography,
    # evidence IDs, season availability and prerequisite fixtures change.
    stories=('sab-s1-1-retrieval','unm-s1-2-vat-nine','kes-s1-2-diversion')
    for source in stories:
        id=source
        job=deepcopy(original[source])
        job.update(id=id,season=None,chain=None,unlock_conditions=[])
        for st in job['stages']:
            st['receipt_key']=id+':'+st['id']
            target=st['target']
            if target['kind']=='npc':
                target.update(zone=zone_id,object='fx-squat')
                st['destination']=dict(kind='zone_object',zone=zone_id,object='fx-clinic-arrival' if id=='sab-s1-1-retrieval' else 'fx-shelter')
            elif target['kind']=='core_room':
                target.update(core=core_id,room=entry,data='fx-ration-record')
            else:
                target.update(zone=zone_id,object='fx-ration-crate' if id=='kes-s1-2-diversion' else
                              'fx-rig-supply' if st['id']=='collect' else 'fx-shield-socket')
        if job.get('permit_scope'):
            job['permit_scope']['binding']=dict(kind='core_room',core=core_id,room=entry)
        for option in job.get('publication_options',[]):
            option['permit']['binding']=(dict(kind='core_room',core=core_id,room=entry) if option['audience']=='public'
                                         else dict(kind='core_control',core=core_id,control='fx-depot-release'))
        jobs.append(job)
    write('contracts.json',dict(schema=1,contracts=jobs))
    season=read('bundles/s19-season-one.json')
    evidence={e for source in stories for e in original[source]['evidence_assets']}
    season['members']['contracts']=[c for c in season['members']['contracts'] if c not in stories]
    season['members']['evidence']=[e for e in season['members']['evidence'] if e not in evidence]
    season['members']['text']=[e for e in season['members']['text'] if e not in evidence]
    write('bundles/s19-season-one.json',season)
    return dict(zone=zone_id,core=core_id,entry=entry,shortcut=[22,5],niche=[30,5],
                fixtures=['extra service bay and local cabinet','three future service bindings',
                          'story fork geography/availability copies; real rewards and branch groups retained',
                          'no claimed full-city navigation, faction prerequisites or pacing proof'])
