"""S21: real holds and named core control through registered native stdio.

Fixtures are membership, an ICE-free copy of the real tier-two core, a
brief Curfew provider, and +2h UTC for influence settlement. Geometry,
capture duration, caller actions and storage receipts are not bypassed.
"""

import argparse
import asyncio
from datetime import timedelta
import json
from pathlib import Path
import time
import traceback

from accept_s10_netbbs import NativeProbe, Connection, wait
from accept_s13_netbbs import lat_walk
from accept_s14_netbbs import choose, room_walk
from accept_s16_netbbs import key, commit_key, select
from blacksite import content as content_package
from blacksite.admin.client import request


async def card(probe: NativeProbe, connection: Connection) -> None:
    await key(connection,b'e')
    await wait(lambda:connection.session.id in probe.service.core.relays.views.menus)
    await wait(lambda:'Cold Chain' in connection.caller.screen.screen_text())


async def run_size(probe: NativeProbe, width: int, height: int) -> dict:
    owner=probe.service.core.relays
    assert (await request(probe.service.install_dir,'relay.set',{'relay':'cold-chain','faction':'neutral'}))['ok']
    callers=[]
    for label,tile,faction in (('S21Holder',(31,18),'halvard'),
                               ('S21Runner',(33,18),'halvard'),
                               ('S21Rival',(32,19),'choir')):
        connection=await probe.open(width,height,label,1,True)
        await probe.walk(connection,(21,14))
        await key(connection,b'b')
        await wait(lambda:probe.game.players[connection.session.player_id].progress.get('wake_combat')=='skipped')
        await probe.travel(connection,'vatside-clinics')
        p=probe.game.players[connection.session.player_id]
        p.faction=faction
        probe.service.core.factions.refresh(p)
        probe.game.queue('save',p.bbs_user_id,p,immediate=True)
        probe.service._character_writes()
        await probe.walk(connection,tile)
        callers.append(connection)
    a,b,c=callers
    await card(probe,a)
    await commit_key(probe,a,b'h',lambda:any(cl.holder.player==a.session.player_id for cl in owner.claims.active.values()))
    claim=next(cl for cl in owner.claims.active.values() if cl.holder.player==a.session.player_id)
    started=time.monotonic()
    await card(probe,c)
    await commit_key(probe,c,b'h',lambda:len(owner.claims.active)==2)
    await wait(lambda:'contested' in a.caller.screen.screen_text())
    frozen=claim.elapsed
    await asyncio.sleep(1)
    assert claim.elapsed==frozen
    probe.save(a,f's21-contested-{width}')
    await key(c,b'b')
    await wait(lambda:len(owner.claims.active)==1)
    curfew=owner.curfew
    owner.curfew=lambda zone:True
    await asyncio.sleep(.3)
    frozen=claim.elapsed
    await asyncio.sleep(1)
    assert claim.elapsed==frozen
    owner.curfew=curfew
    await card(probe,b)
    screen=owner.views.menus[b.session.id]
    await select(b,lambda:owner.views.body(b.session,screen)['rows'],screen,'claim:'+claim.id)
    await commit_key(probe,b,b's',lambda:b.session.player_id in claim.supporters)
    await probe.walk(b,(36,20))
    lattice=probe.service.core.lattice
    await key(b,b'j')
    await wait(lambda:b.session.player_id in lattice.presences)
    presence=lattice.presences[b.session.player_id]
    entrance=next(cell.id for cell in lattice.sectors.records[presence.sector].cells
                  if cell.core_id=='lat-relay-cold-chain')
    await lat_walk(probe,b,entrance)
    await choose(probe,b,'enter:lat-relay-cold-chain')
    room=next(room.id for room in lattice.encounters.core(presence).graph.rooms.values()
              if any(control.id=='relay_open' for control in room.controls))
    await room_walk(probe,b,room)
    await choose(probe,b,'control:relay_open')
    await wait(lambda:b.session.player_id in claim.hacked and not probe.commerce.pending)
    probe.save(b,f's21-named-control-{width}')
    await wait(lambda:lattice.encounters.idle(presence))
    await room_walk(probe,b,lattice.encounters.core(presence).graph.spec.entry)
    await key(b,b'b')
    await wait(lambda:presence.instance is None)
    await key(b,b'j')
    await wait(lambda:b.session.player_id not in lattice.presences)
    before={conn.session.player_id:probe.game.players[conn.session.player_id].xp for conn in callers}
    next_report=time.monotonic()
    async with asyncio.timeout(210):
        while owner.owner('cold-chain')!='halvard':
            if time.monotonic()>=next_report:
                probe.report(f'S21 {width}x{height}: real hold {claim.elapsed/10:.1f}/180s')
                next_report=time.monotonic()+30
            await asyncio.sleep(.2)
    elapsed=time.monotonic()-started
    await wait(lambda:not probe.commerce.pending)
    assert elapsed>=180
    assert [probe.game.players[conn.session.player_id].xp-before[conn.session.player_id] for conn in callers]==[100,100,0]
    saved=probe.service.storage.character_state()
    fact=saved['relays']['captures'][-1]
    assert fact['relay']=='cold-chain' and len(fact['participants'])==2
    assert saved['interlock']['cores']['lat-relay-cold-chain']['owner_faction']=='halvard'
    probe.save(a,f's21-capture-{width}')
    await key(a,b'b')
    await wait(lambda:not owner.claims.active)
    await card(probe,a)
    await commit_key(probe,a,b'v',lambda:a.session.id in probe.commerce.menus)
    await wait(lambda:'counter' in a.caller.screen.screen_text().lower())
    probe.save(a,f's21-member-counter-{width}')
    await key(a,b'\x1b')
    await wait(lambda:a.session.id not in probe.commerce.menus)
    await card(probe,c)
    await key(c,b'v')
    await wait(lambda:any('current holder' in row['text'] for row in c.session.log_ring))
    assert c.session.id not in probe.commerce.menus
    probe.save(c,f's21-outsider-refused-{width}')
    await key(c,b'\x1b')
    # Only the influence acceptance advances UTC. Native capture used the
    # ordinary injected real clock for the full three-minute hold above.
    previous_utc=probe.service.clock.now_utc
    probe.service.clock.now_utc=lambda:previous_utc()+timedelta(hours=2)
    previous=owner.ledger.state['factions'].get('halvard',{}).get('influence',0)
    draft=owner.ledger.fork()
    draft.settle(owner.rates(),owner.now())
    assert owner.write(draft)
    await wait(lambda:not probe.commerce.pending)
    assert owner.ledger.state['factions']['halvard']['influence']-previous==20
    await key(a,b'\x1b[19~')  # F8, preserving P for the character card.
    await wait(lambda:a.session.id in owner.views.menus)
    await wait(lambda:'Your faction influence:' in a.caller.screen.screen_text())
    probe.save(a,f's21-influence-{width}')
    await key(a,b'\x1b')
    for conn in callers:
        await probe.leave(conn,f's21-return-{conn.session.player_id.replace(":","-")}-{width}')
    probe.report(f'PASS S21 {width}x{height}: contested/Curfew, real {elapsed:.1f}s capture, named control, two rewards, counter and +20 influence')
    return {'size':[width,height],'passed':True,'capture_seconds':round(elapsed,2),
        'contested_pauses':True,'curfew_pauses':True,'named_control_committed':True,
        'capture_xp':[100,100,0],'member_counter':True,'outsider_refused':True,
        'influence_delta':20,'capture_fact':fact}


async def accept(root: Path, python: Path, show: bool, size: tuple[int,int]) -> None:
    probe=NativeProbe(root,python,show)
    source=Path(content_package.__file__).parent/'cores/lat-relay-cold-chain.json'
    core=json.loads(source.read_text(encoding='utf-8'))
    for room in core['rooms']:
        room['ice']=[]
    target=probe.service.install_dir/'content.local/cores/lat-relay-cold-chain.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(core,indent=2)+'\n',encoding='utf-8',newline='\n')
    await probe.start()
    try:
        probe.report('S21 fixtures: membership, ICE-free real tier2 core, brief Curfew flag, +2h UTC after capture. No geometry, placement or capture-clock fixture.')
        result=await run_size(probe,*size)
        assert not probe.errors and probe.service.failure is None
        (root/'s21-results.json').write_text(json.dumps({'passed':True,'run':result,
            'transport':'NetBBS Telnet -> registered native stdio',
            'fixtures':['membership','ICE-free real tier2 core','brief Curfew provider','+2h UTC after capture'],
            'capture_clock_fixture':False,'placement_fixture':False,
            'future_geography':'S25','human_full_city_pacing':'S25/S26 pending'},indent=2)+'\n',encoding='utf-8')
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
    finally:
        await probe.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--door-python',type=Path,required=True)
    parser.add_argument('--show',action='store_true')
    parser.add_argument('--size',choices=('80x24','132x50'),required=True)
    args=parser.parse_args()
    asyncio.run(accept(args.root,args.door_python,args.show,tuple(map(int,args.size.split('x')))))
