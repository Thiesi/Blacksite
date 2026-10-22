"""S15: real caller keys on labelled content/rental fixtures, at both sizes.

No funding, placement, grade or skill fixture. Controls isolate the
interlock with a commissioned Civic core and an explicitly unsafe plaza;
private acceptance supplies an S18 rental and a disclosed Passkey loan.
Actual Gate Nine district geography remains S25's obligation.
"""

import argparse
import asyncio
import json
import time
import traceback
from pathlib import Path
from typing import Any

from accept_s10_netbbs import Connection, NativeProbe, wait
from accept_s13_netbbs import lat_walk
from accept_s14_netbbs import choose, hub, menu, program, room_walk
from blacksite import content as content_package
from blacksite.content.loader import load_content
from blacksite.server.items import make_item


def fixture(probe: NativeProbe, stage: str) -> dict[str, Any]:
    source = Path(content_package.__file__).parent
    local = probe.service.install_dir/'content.local'
    def read(name: str) -> dict[str, Any]:
        return json.loads((source/name).read_text(encoding='utf-8'))
    def write(name: str, value: dict[str, Any]) -> None:
        target = local/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8', newline='\n')
        if name.startswith('zones/'):
            target.with_suffix('.map').write_bytes((source/name).with_suffix('.map').read_bytes())
    if stage == 'controls':
        zone = read('zones/core-plaza.json')
        zone.update(name='S15 LABELLED UNSAFE CONTROL FIXTURE', safety='open', pockets=[])
        door = next(o for o in zone['objects'] if o['id'] == 'civic-ledger-hall-doors')
        door['params'].update(open=False, locked=True)
        write('zones/core-plaza.json', zone)
        core = read('cores/lat-civic-ledger.json')
        core['name'] = 'S15 LABELLED CONTROL FIXTURE'
        core['tier'] = 3
        for room in core['rooms']:
            room['ice'] = []  # S14 tests own encounter combat; no NPCs removed.
        write('cores/lat-civic-ledger.json', core)
        return {}
    content = load_content(source)
    zone = content.zones['terraces-blocks']
    occupied = {o.tile for o in zone.meta.objects} | {e.tile for e in zone.meta.exits}
    floor = [(x, y) for y in range(2, zone.height-2) for x in range(2, zone.width-2)
             if content.tiles[zone.tile_at((x,y))].passable and (x,y) not in occupied][:5]
    record = {'id':'s15-fixture','tier':1,'sector':'lat-terraces','zone':zone.id,
        'cell':next(c.id for c in content.sectors['lat-terraces'].cells
                    if c.access_kind == 'public' and not c.core_id and not c.core_placeholder),
        'hardware':'s15-private-hardware','door':'s15-private-vestibule','light':'s15-private-light'}
    data = read('zones/terraces-blocks.json')
    for index, (kind, oid) in enumerate((('hardware',record['hardware']), ('door',record['door']),
                                      ('light',record['light']), ('apartment_door','s15-resident-menu'))):
        params = {'name':'S15 labelled rental fixture', 'open':kind != 'door'}
        if kind == 'apartment_door':
            params['apartment_id'] = record['id']
        data['objects'].append({'id':oid,'kind':kind,'tile':list(floor[index]),'params':params})
    write('zones/terraces-blocks.json',data)
    record['menu_tile'] = floor[3]
    return record


async def controls(probe: NativeProbe, width: int, height: int) -> dict[str, Any]:
    a = await probe.open(width,height,'S15Meat',1,True)
    b = await probe.open(width,height,'S15Wire',1)
    await hub(probe,a)
    await hub(probe,b)
    lattice = probe.service.core.lattice
    interlock, encounters = lattice.interlock, lattice.encounters
    spec = interlock.controls['lat-civic-ledger','hall-doors']
    zone = probe.service.world.zones[spec.target.zone]
    obj = zone.objects[spec.target.object]
    before_tile = next(tile for tile in ((obj.spec.tile[0]-1,obj.spec.tile[1]),
        (obj.spec.tile[0],obj.spec.tile[1]-1)) if zone.passable(tile))
    await probe.walk(a,before_tile)
    await probe.walk(b,(30,5))
    await b.caller.write(b'j')
    await wait(lambda:b.session.player_id in lattice.presences)
    presence = lattice.presences[b.session.player_id]
    entrance = next(c.id for c in lattice.sectors.records[presence.sector].cells if c.core_id == 'lat-civic-ledger')
    await lat_walk(probe,b,entrance)
    await choose(probe,b,'enter:lat-civic-ledger')
    room = next(r.id for r in encounters.core(presence).graph.rooms.values() if any(c.id == 'hall-doors' for c in r.controls))
    await room_walk(probe,b,room)
    assert not obj.open
    probe.save(a,f's15-locked-{width}x{height}')
    started = time.monotonic()
    await choose(probe,b,'control:hall-doors')
    await wait(lambda:obj.open and not probe.commerce.pending)
    elapsed = time.monotonic()-started
    await wait(lambda:any(o['id'] == obj.spec.id and o['state']['open'] for o in (probe.game.sim.views[a.session.id].previous or {}).get('body',{}).get('objects',[])))
    assert any('Nobody touches' in line['text'] for line in a.session.log_ring)
    await probe.walk(a,obj.spec.tile)
    probe.save(a,f's15-open-walked-{width}x{height}')
    (zid, oid), _ = next((key,core) for key,core in interlock.hardware.items() if core == 'lat-civic-ledger')
    probe.report(f"S15 {width}x{height}: flip and physical walking passed; approaching hardware")
    await probe.walk(a,zone.objects[oid].spec.tile)
    probe.report(f"S15 hardware: {a.avatar.actor.position}, stance {a.avatar.actor.stance}")
    await a.caller.write(b'e')
    await wait(lambda:a.session.id in interlock.menus)
    await wait(lambda:'HARDWARE' in a.caller.screen.screen_text())
    await a.caller.write(b'c')
    await wait(lambda:interlock.menus.get(a.session.id,(None,None,False))[2])
    # Closing the confirmation must leave the core running.
    await a.caller.write(b'b')
    await wait(lambda:a.session.id not in interlock.menus)
    assert not interlock.offline('lat-civic-ledger')
    await wait(lambda:'HARDWARE' not in a.caller.screen.screen_text())
    await wait(lambda:a.session.ack_revision == a.session.view_revision)
    await a.caller.write(b'e')
    await wait(lambda:a.session.id in interlock.menus)
    await wait(lambda:'HARDWARE' in a.caller.screen.screen_text())
    await a.caller.write(b'c')
    await wait(lambda:interlock.menus.get(a.session.id,(None,None,False))[2])
    await wait(lambda:'Y confirms' in a.caller.screen.screen_text())
    await a.caller.write(b'y')
    await wait(lambda:a.session.player_id in interlock.cuts)
    cut_started = time.monotonic()
    await wait(lambda:b.session.player_id not in lattice.presences,12)
    cut_elapsed = time.monotonic()-cut_started
    assert b.avatar.actor.shock == 100 and interlock.offline('lat-civic-ledger') > 598
    await wait(lambda:'The floor goes dark' in b.caller.screen.screen_text())
    probe.save(b,f's15-cut-shock-{width}x{height}')
    saved = probe.service.storage.character_state()
    assert next(p for p in saved['players'] if p['id'] == b.session.player_id)['shock'] == 100
    assert saved['interlock']['cores']['lat-civic-ledger']['offline_until'] > interlock.now()
    await b.caller.write(b'j')
    await wait(lambda:b.session.player_id in lattice.presences)
    await lat_walk(probe,b,entrance)
    await choose(probe,b,'enter:lat-civic-ledger',closes=False)
    await wait(lambda:any('core is offline' in line['text'] for line in b.session.log_ring))
    assert lattice.presences[b.session.player_id].core is None
    await b.caller.write(b'b')
    await wait(lambda:b.session.id not in encounters.menus)
    await b.caller.write(b'j')
    await wait(lambda:b.session.player_id not in lattice.presences)
    probe.report(f'PASS S15 controls {width}x{height}: real flip/walk, cancellable confirmation, 5s cut, durable 100 shock/600s offline, real enter refusal')
    await probe.leave(a,f's15-controls-return-a-{width}x{height}')
    await probe.leave(b,f's15-controls-return-b-{width}x{height}')
    return {'stage':'controls','size':[width,height],'flip_seconds':round(elapsed,2),
        'cut_seconds':round(cut_elapsed,2),'transport':'NetBBS Telnet -> native stdio',
        'content_fixture':True,'fixture_tier':3,'placement_fixture':False,'funding_fixture':False,'passed':True}


async def private(probe: NativeProbe, width: int, height: int, record: dict[str, Any]) -> dict[str, Any]:
    a = await probe.open(width,height,'S15Owner',1,True)
    b = await probe.open(width,height,'S15Visitor',1)
    for connection in (a,b):
        await hub(probe,connection)
        await probe.travel(connection,'core-tram-hub')
    # Board the same scheduled departure from distinct adjacent floor tiles.
    for connection, tile in ((a,(38,14)),(b,(39,13))):
        await probe.walk(connection,tile)
        await connection.caller.write(b'e')
        await wait(lambda:connection.avatar.travel is not None)
    probe.report(f'S15 private {width}x{height}: both callers boarded the scheduled Terraces tram')
    await wait(lambda:all(c.avatar.zone == 'terraces-blocks' for c in (a,b)),150)
    probe.report(f'S15 private {width}x{height}: both physical bodies arrived in the Terraces')
    lattice = probe.service.core.lattice
    interlock, encounters = lattice.interlock, lattice.encounters
    record = {key:value for key,value in record.items() if key != 'menu_tile'}
    record['resident'] = a.session.player_id
    template = interlock.content.items['ammo_9x']
    assert template.stack_max >= 3
    # Disclosed S18 storage fixture: three unsecured units, a secured stack,
    # and an impounded stack. No money, skills, grades or carried items granted.
    items = dict(probe.commerce.items)
    serial = probe.commerce.serial
    record['storage'] = []
    for label, secured, owner in (('unsecured',False,'apartment:'+record['id']),
                                   ('secured',True,'apartment:'+record['id']),
                                   ('impounded',False,'impound:'+record['id'])):
        serial += 1
        iid = f'{probe.game.sessions.origin}:item:{serial}'
        item = make_item(iid,template,owner,interlock.clock.now_utc().isoformat(),3)
        item.secured = secured
        items[iid] = item
        record['storage'].append(iid)
    assert probe.commerce.settle(None,{},items,probe.commerce.caches,serial,lambda success:None)
    await wait(lambda:not probe.commerce.pending)
    interlock.private.register(record)
    await wait(lambda:not probe.commerce.pending)
    player = probe.game.players[b.session.player_id]
    player.progress['known_programs'] = ['prg_passkey']  # Disclosed program loan.
    probe.game.queue('save',player.bbs_user_id,player,immediate=True)
    await b.caller.write(b'j')
    await wait(lambda:player.id in lattice.presences)
    presence = lattice.presences[player.id]
    await wait(lambda:'INTEGRITY' in b.caller.screen.screen_text())
    await b.caller.write(b'r')
    await wait(lambda:b.session.id in encounters.menus)
    await menu(probe,b,'2')
    await wait(lambda:encounters.menus[b.session.id].kind == 'binding')
    await menu(probe,b,'prg_passkey')
    await wait(lambda:presence.rig[2] == 'prg_passkey')
    await b.caller.write(b'b')
    await wait(lambda:b.session.id not in encounters.menus)
    await lat_walk(probe,b,record['cell'])
    await choose(probe,b,'enter:lat-apartment-'+record['id'])
    vestibule = probe.service.world.zones[record['zone']].objects[record['door']]
    await program(probe,b,3,lambda:vestibule.open)
    assert not presence.opened and not interlock.private.manifest(presence)
    await room_walk(probe,b,'index')
    defender = encounters.defenders(presence)[0]
    await choose(probe,b,'ice:'+defender.id)
    await program(probe,b,2,lambda:presence.effects.shield is not None)
    await program(probe,b,1,lambda:not defender.alive)
    assert [i.id for i in interlock.private.manifest(presence)] == [record['storage'][0]]
    await choose(probe,b,'theft:'+record['storage'][0])
    await wait(lambda:bool(interlock.state['apartments'][record['id']]['hack_log']))
    assert probe.commerce.items[record['storage'][0]].stack == 2
    await choose(probe,b,'theft:'+record['storage'][0],closes=False)
    await wait(lambda:any('24 hours' in line['text'] for line in b.session.log_ring))
    assert probe.commerce.items[record['storage'][1]].stack == 3
    assert probe.commerce.items[record['storage'][2]].stack == 3
    await b.caller.write(b'b')
    await wait(lambda:b.session.id not in encounters.menus)
    zone = probe.service.world.zones[record['zone']]
    resident_menu = next(o for o in zone.objects.values() if o.spec.params.get('apartment_id') == record['id'])
    await probe.walk(a,resident_menu.spec.tile)
    await a.caller.write(b'e')
    await wait(lambda:'APARTMENT / CORE LOG' in a.caller.screen.screen_text())
    assert 'Someone was in your core' in a.caller.screen.screen_text()
    probe.save(a,f's15-owner-log-{width}x{height}')
    probe.save(b,f's15-unit-limit-{width}x{height}')
    saved = probe.service.storage.character_state()
    assert len(saved['interlock']['apartments'][record['id']]['hack_log']) == 1
    await a.caller.write(b'b')
    await wait(lambda:a.session.id not in interlock.log_menus)
    await b.caller.write(b'j')
    await wait(lambda:b.session.player_id not in lattice.presences,12)
    probe.report(f'PASS S15 private {width}x{height}: real scheduled tram, Passkey vestibule, Pick/Tripwire, one atomic unit, owner menu log, 24h refusal, secured/impounded hidden')
    await probe.leave(a,f's15-private-return-a-{width}x{height}')
    await probe.leave(b,f's15-private-return-b-{width}x{height}')
    return {'stage':'private','size':[width,height],'transport':'NetBBS Telnet -> native stdio',
        'rental_storage_fixture':True,'program_loan_fixture':'Passkey','funding_fixture':False,
        'placement_fixture':False,'passed':True}


async def accept(root: Path, python: Path, show: bool, size: tuple[int,int], stage: str) -> None:
    probe = NativeProbe(root,python,show)
    record = fixture(probe,stage)
    await probe.start()
    try:
        if stage == 'controls':
            result = await controls(probe,*size)
        else:
            result = await private(probe,*size,record)
        assert not probe.errors and probe.service.failure is None
        (probe.root/'s15-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    except BaseException:
        (probe.root/"failure-trace.txt").write_text(traceback.format_exc(),encoding="utf-8")
        for i,connection in enumerate(probe.connections):
            probe.save(connection,f's15-failed-{i}')
        (probe.root/'failure-state.json').write_text(json.dumps([{
            'player':c.session.player_id,'zone':c.avatar.zone if c.avatar else None,
            'tile':c.avatar.actor.position if c.avatar else None,
            'stance':c.avatar.actor.stance if c.avatar else None,
            'menu':probe.service.core.lattice.interlock.menus.get(c.session.id),
            'overlay':probe.game.sim.external_views.get(c.session.id,(None,))[0],
            'logs':[line['text'] for line in list(c.session.log_ring)[-12:]]}
            for c in probe.connections],indent=2)+'\n',encoding='utf-8')
        raise
    finally:
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--door-python',type=Path,required=True)
    parser.add_argument('--show',action='store_true')
    parser.add_argument('--stage',choices=('controls','private'),default='controls')
    parser.add_argument('--size',choices=('both','80','132'),default='both')
    args = parser.parse_args()
    sizes = ((80,24),(132,50)) if args.size == 'both' else ((80,24),) if args.size == '80' else ((132,50),)
    for size in sizes:
        asyncio.run(accept(args.root/f'{size[0]}x{size[1]}',args.door_python,args.show,size,args.stage))
