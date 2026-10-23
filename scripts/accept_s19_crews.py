"""S19 native frozen-roster clear and late-join acceptance.

Mission drones use a disclosed one-HP/delayed-attack fixture to isolate
contract accounting. Crew consent, movement, targeting, fire and payment
use actual keys through the registered NetBBS stdio door.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import traceback
from typing import Any

from accept_s10_netbbs import Connection, wait
from accept_s16_netbbs import commit_key, key, select
from accept_s19_netbbs import ContractProbe, board_row, close_jobs
from accept_s22_netbbs import crew_menu, close_menu


async def invite(probe: ContractProbe, leader: Connection, member: Connection) -> None:
    crews=probe.service.core.crews
    pid=member.session.player_id
    await crew_menu(probe,leader,pid)
    await commit_key(probe,leader,b'i',lambda:any(i.target==pid for i in crews.registry.invites.values()))
    await close_menu(probe,leader)
    invitation=next(i for i in crews.registry.invites.values() if i.target==pid)
    await crew_menu(probe,member,invitation.id)
    await commit_key(probe,member,b'a',lambda:crews.crew_id(pid) is not None)
    await close_menu(probe,member)


async def jobs(probe: ContractProbe, caller: Connection, row: str) -> Any:
    owner=probe.service.core.contracts
    await key(caller,b'q')
    await wait(lambda:caller.session.id in owner.panels.menus)
    panel=owner.panels.menus[caller.session.id]
    await select(caller,lambda:owner.panels.rows(caller.session,panel),panel,row)
    return panel


async def run_size(probe: ContractProbe, width: int, height: int) -> dict[str,Any]:
    a=await probe.open(width,height,'S19Ghost',1,True)
    await probe.walk(a,(12,10))
    b=await probe.open(width,height,'S19Operator',3,True)
    await probe.walk(b,(14,10))
    await invite(probe,a,b)
    owner=probe.service.core.contracts
    players=[probe.game.players[c.session.player_id] for c in (a,b)]
    await probe.route(a,'core-precinct')
    await probe.near(a,'warden-contract-handler')
    offer=next(o for o in owner.state.engine.board('wardens',owner.now())
               if o.template=='wardens-commission-clear')
    await board_row(probe,a,offer.id)
    await commit_key(probe,a,b'c',lambda:bool(owner.proposals))
    proposal=next(p for p in owner.proposals.values() if p.creator==players[0].id)
    assert proposal.roster==(players[0].id,players[1].id)
    await close_jobs(probe,a)
    await jobs(probe,b,proposal.id)
    await commit_key(probe,b,b'a',lambda:players[1].id in proposal.consent)
    await close_jobs(probe,b)
    panel=await jobs(probe,a,proposal.id)
    await commit_key(probe,a,b's',lambda:panel.confirmation is not None)
    await commit_key(probe,a,b'y',lambda:any(j.offer==offer.id and j.roster[0].player==players[0].id
        for j in owner.state.engine.instances.values()))
    iid=next(j.id for j in owner.state.engine.instances.values()
             if j.offer==offer.id and j.roster[0].player==players[0].id)
    assert len(owner.state.engine.instances[iid].stages[0].targets)==6
    probe.save(a,f's19-six-target-terms-{width}')
    await close_jobs(probe,a)
    await probe.route(a,'terraces-blocks')
    await wait(lambda:len([n for n in owner.world.actors.values() if n.behaviour.get('mission')==iid])==6)
    drones=[n for n in owner.world.actors.values() if n.behaviour.get('mission')==iid]
    for drone in drones:
        drone.health=drone.health_max=1
        drone.cooldowns['weapon']=probe.service.clock.now_tick()+6000
        drone.cooldowns['move']=probe.service.clock.now_tick()+6000
    await probe.near(a,'letting-office')
    await probe.route(b,'terraces-blocks')
    await probe.near(b,'letting-office')
    for index,drone in enumerate(drones):
        caller=(a,b)[index%2]
        assert drone.id in owner.world.actors, ('target retired before caller action',drone.id)
        zone=owner.world.zones[drone.zone]
        occupied={n.position for n in zone.actors.values() if n is not caller.avatar.actor}
        adjacent=[(drone.x+dx,drone.y+dy) for dx in (-1,0,1) for dy in (-1,0,1)
                  if (drone.x+dx,drone.y+dy) not in occupied
                  and zone.can_enter(caller.avatar.actor,(drone.x+dx,drone.y+dy))]
        await probe.walk(caller,min(adjacent,key=lambda t:abs(t[0]-caller.avatar.actor.x)+abs(t[1]-caller.avatar.actor.y)))
        await probe.target(caller,drone.id)
        await commit_key(probe,caller,b'f',lambda:drone.id not in owner.world.actors)
    await wait(lambda:owner.state.engine.instances[iid].state=='complete')
    late=await probe.open(width,height,'S19Late',0,True)
    await invite(probe,a,late)
    assert len(probe.service.core.crews.registry.crew_of(players[0].id).members)==3
    assert len(owner.state.engine.instances[iid].roster)==2
    await probe.route(a,'core-precinct')
    await probe.near(a,'warden-contract-handler')
    panel=await board_row(probe,a,iid)
    late_player=probe.game.players[late.session.player_id]
    before=[(p.chits_hand,p.xp) for p in (*players,late_player)]
    await commit_key(probe,a,b't',lambda:panel.confirmation is not None)
    await commit_key(probe,a,b'y',lambda:owner.state.engine.instances[iid].state=='turned_in')
    payouts=[dict(chits=p.chits_hand-before[i][0],xp=p.xp-before[i][1]) for i,p in enumerate((*players,late_player))]
    assert payouts==[dict(chits=250,xp=250),dict(chits=275,xp=250),dict(chits=0,xp=0)],payouts
    probe.save(a,f's19-frozen-roster-paid-{width}')
    await close_jobs(probe,a)
    probe.report(f'S19 PASS {width}x{height}: four scaled to six, consent, useful actions, 250/275 chits; late join zero')
    for caller in (late,b,a):
        await probe.leave(caller,f's19-crew-left-{caller.session.player_id[-8:]}-{width}')
    return dict(size=[width,height],required_targets=6,payouts=payouts,
                fixtures=['mission drones one HP with delayed attacks/movement; combat pacing not measured'])


async def accept(root: Path, python: Path, show: bool, size: str) -> None:
    probe=ContractProbe(root,python,show)
    await probe.start()
    try:
        sizes=((80,24),(132,50)) if size=='both' else (tuple(map(int,size.split('x'))),)
        results=[await run_size(probe,w,h) for w,h in sizes]
        (root/'s19-crew-results.json').write_text(json.dumps(dict(passed=True,runs=results),indent=2)+'\n',encoding='utf-8')
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
    parser.add_argument('--size',choices=('both','80x24','132x50'),default='both')
    args=parser.parse_args()
    asyncio.run(accept(args.root,args.door_python,args.show,args.size))
