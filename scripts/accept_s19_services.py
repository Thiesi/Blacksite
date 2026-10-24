"""S19 native work orders, personal forks and restart acceptance.

Three future locations and story geography use contracts_fixture; Cold
Chain uses its shipped clinic. No cash, progress, defeat or ICE fixture.
The only time setup is 60 minutes of service uptime to expose faults.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import deque
from dataclasses import asdict
import json
from pathlib import Path
import time
import traceback
from typing import Any

from accept_s10_netbbs import CombatCaller, Connection, wait
from accept_s16_netbbs import commit_key, key, select
from accept_s18_netbbs import get_user_by_id
from accept_s19_netbbs import ContractProbe, board_row, close_jobs, encounter_row, objective_key
from contracts_fixture import build_fixture
from blacksite.server.app import Server


async def reconnect(probe: ContractProbe, previous: Connection, width: int, height: int) -> Connection:
    user=get_user_by_id(probe.db,int(previous.session.door_info['user_id']))
    probe.accounts.append((user,True))
    reader,writer=await asyncio.open_connection('127.0.0.1',probe.node.port)
    async def send(data: bytes) -> None:
        writer.write(data)
        await writer.drain()
    writer.write(b'\xff\xfb\x1f\xff\xfa\x1f'+width.to_bytes(2,'big')+height.to_bytes(2,'big')+b'\xff\xf0')
    writer.write(b'\xff\xfb\x18\xff\xfa\x18\x00xterm-256color\xff\xf0')
    await writer.drain()
    caller=CombatCaller(lambda:reader.read(65536),send,width,height,probe.show)
    caller.display_write=probe.display_write
    await caller.expect('Available doors')
    await caller.write(b'\x1b[B\r')
    await caller.until(lambda:'Chits' in caller.screen.screen_text(),timeout=20)
    async def pump() -> None:
        while chunk:=await reader.read(65536):
            caller.output.extend(chunk)
            caller.replay()
    task=asyncio.create_task(pump())
    session=next(s for s in probe.game.sessions.active.values()
                 if s.player_id==previous.session.player_id and s is not previous.session)
    result=Connection(caller,writer,task,session,probe.game.sim.avatars[session.user_id])
    probe.connections.append(result)
    assert session.caps['tier']=='16'
    return result


async def leave_network(probe: ContractProbe, caller: Connection) -> None:
    lat=probe.service.core.lattice
    if caller.session.player_id in lat.presences:
        await key(caller,b'j')
        await wait(lambda:caller.session.player_id not in lat.presences)
        await wait(lambda:caller.session.id not in lat.transitions)


async def enter_core(probe: ContractProbe, caller: Connection, core: str, descriptor: dict[str,Any]) -> Any:
    lat=probe.service.core.lattice
    if caller.session.player_id not in lat.presences:
        terminal = descriptor.get('terminal') or (
            'cold-chain-loan-terminal' if core == 'lat-relay-cold-chain' else 'fx-loan')
        await probe.near(caller,terminal)
        if core=='lat-relay-cold-chain':
            # Use the authored shelter, not the contested approach that
            # happens to be within interaction range of its terminal.
            await probe.walk(caller,(36,20))
            assert not probe.service.world.zones[caller.avatar.zone].allows_hostile(caller.avatar.actor.position)
        await key(caller,b'j')
        await wait(lambda:caller.session.player_id in lat.presences)
    presence=lat.presences[caller.session.player_id]
    if presence.core != core:
        cells=lat.sectors.cells[presence.sector]
        entrance=next(c.id for c in cells.values() if c.core_id==core)
        pending,paths=deque([presence.cell]),{presence.cell:[]}
        while pending and entrance not in paths:
            cell=pending.popleft()
            for adjacent in cells[cell].neighbours:
                if adjacent not in paths:
                    paths[adjacent]=[*paths[cell],adjacent]
                    pending.append(adjacent)
        for hop in paths[entrance]:
            a,b=cells[presence.cell].pos,cells[hop].pos
            dx,dy=b[0]-a[0],b[1]-a[1]
            value=(b'\x1b[C' if dx>0 else b'\x1b[D') if abs(dx)>=abs(dy) else (b'\x1b[B' if dy>0 else b'\x1b[A')
            await key(caller,value)
            await wait(lambda:presence.cell==hop)
        await encounter_row(probe,caller,'enter:'+core)
        await wait(lambda:presence.core==core)
    return presence


async def neutralize(probe: ContractProbe, caller: Connection, presence: Any) -> None:
    enc=probe.service.core.lattice.encounters
    for ice in list(enc.defenders(presence)):
        await encounter_row(probe,caller,'ice:'+ice.id)
        await commit_key(probe,caller,b'1',lambda:not ice.alive)


async def network_stage(probe: ContractProbe, caller: Connection, target: Any, descriptor: dict[str,Any]) -> None:
    enc=probe.service.core.lattice.encounters
    presence=await enter_core(probe,caller,target.core,descriptor)
    instance=enc.core(presence)
    room=target.room or next(r.id for r in instance.graph.rooms.values()
                             if any(c.id==target.control for c in r.controls))
    while presence.room!=room:
        await neutralize(probe,caller,presence)
        hop=instance.graph.route(presence.room,room)[1]
        a,b=instance.graph.room(presence.room).pos,instance.graph.room(hop).pos
        dx,dy=b[0]-a[0],b[1]-a[1]
        value=(b'\x1b[C' if dx>0 else b'\x1b[D') if abs(dx)>=abs(dy) else (b'\x1b[B' if dy>0 else b'\x1b[A')
        await key(caller,value)
        await wait(lambda:presence.room==hop)
    await neutralize(probe,caller,presence)
    await wait(lambda:enc.idle(presence))
    if target.kind=='core_control':
        row='control:'+target.control
    else:
        data=next(d for d in instance.graph.room(room).data if d.id==target.data)
        source=probe.service.core.lattice.sources.refresh(enc.source(presence,data),data,probe.service.clock.now_tick())
        row=f'lift:{data.id}:{source.generation}'
    await encounter_row(probe,caller,row)


async def escort_stage(probe: ContractProbe, caller: Connection, iid: str, progress: Any) -> None:
    owner=probe.service.core.contracts
    pid=caller.session.player_id
    await probe.route(caller,progress.targets[0].zone)
    # A preceding supply write advances the ledger before the next
    # scene reconciliation creates its NPCs. Do not mistake that frame
    # boundary for an already-recruited/empty group.
    await wait(lambda:len([a for a in owner.world.actors.values()
        if a.behaviour.get('mission')==iid and a.behaviour.get('contract_stage')==progress.stage.id])
        ==len(progress.targets)-len(progress.subjects))
    recruit_deadline=time.monotonic()+120
    while True:
        actors=[a for a in owner.world.actors.values() if a.behaviour.get('mission')==iid
                and a.behaviour.get('contract_target') and a.behaviour.get('escort')!=pid]
        if not actors:
            break
        actor=actors[0]
        zone=owner.world.zones[actor.zone]
        occupied={a.position for a in zone.actors.values() if a.id!=pid}
        choices=[(actor.x+dx,actor.y+dy) for dx in (-1,0,1) for dy in (-1,0,1)
                 if (actor.x+dx,actor.y+dy) not in occupied and zone.can_enter(caller.avatar.actor,(actor.x+dx,actor.y+dy))]
        assert time.monotonic()<recruit_deadline,('escort recruitment timeout',iid)
        if not choices:
            await asyncio.sleep(.2)
            continue
        # A recruited follower can occupy this approach while we walk.
        # Re-read the moving group instead of waiting on that fixed tile.
        try:
            await asyncio.wait_for(probe.walk(caller,min(choices,key=lambda t:abs(t[0]-caller.avatar.actor.x)+abs(t[1]-caller.avatar.actor.y))),5)
        except TimeoutError:
            continue
        await objective_key(probe,caller,lambda:actor.behaviour.get('escort')==pid)
    destination=progress.stage.destination
    await probe.route(caller,destination.zone)
    # Put the worker on the arrival marker so the group's ordinary
    # following distance lies inside the destination's arrival radius.
    # Merely standing beside it can leave followers one tile too far away.
    tile=owner.world.zones[destination.zone].objects[destination.object].spec.tile
    await probe.walk(caller,tile)


async def drive_job(probe: ContractProbe, caller: Connection, iid: str, descriptor: dict[str,Any]) -> None:
    owner=probe.service.core.contracts
    while owner.state.engine.instances[iid].state=='active':
        instance=owner.state.engine.instances[iid]
        index=instance.index
        progress=instance.stages[index]
        target=progress.targets[0]
        if progress.stage.verb=='escort':
            await escort_stage(probe,caller,iid,progress)
        elif target.kind in ('core_room','core_control'):
            await network_stage(probe,caller,target,descriptor)
        else:
            await probe.near(caller,target.object)
            before_objective = descriptor.get('before_objective')
            if before_objective:
                await before_objective(probe, caller)
            await objective_key(probe,caller,lambda:owner.state.engine.instances[iid].index!=index)
        await wait(lambda:owner.state.engine.instances[iid].index!=index)
        await leave_network(probe,caller)


async def reserve(probe: ContractProbe, caller: Connection, sid: str, allocation: str) -> str:
    owner=probe.service.core.contracts
    board='clinic-public-west' if sid=='cold-chain' else 'fx-'+sid+'-board'
    await probe.near(caller,board)
    panel=await board_row(probe,caller,'service:'+sid)
    await commit_key(probe,caller,b'1' if allocation=='common' else b'2',lambda:panel.confirmation is not None)
    await commit_key(probe,caller,b'y',lambda:owner.state.services.nodes[sid].state=='repairing')
    order=owner.state.services.nodes[sid].order
    iid=next(j.id for j in owner.state.engine.instances.values() if j.offer==order)
    await close_jobs(probe,caller)
    return iid


async def settle_story(probe: ContractProbe, caller: Connection, tid: str, board: str,
                       descriptor: dict[str,Any], option: int | None = None) -> str:
    owner=probe.service.core.contracts
    await probe.near(caller,board)
    panel=await board_row(probe,caller,tid)
    await commit_key(probe,caller,b'a',lambda:panel.confirmation is not None)
    await commit_key(probe,caller,b'y',lambda:any(j.template==tid and any(p.player==caller.session.player_id for p in j.roster)
        for j in owner.state.engine.instances.values()))
    iid=next(j.id for j in owner.state.engine.instances.values() if j.template==tid
             and any(p.player==caller.session.player_id for p in j.roster))
    await close_jobs(probe,caller)
    await drive_job(probe,caller,iid,descriptor)
    assert owner.state.engine.instances[iid].state=='complete'
    await probe.near(caller,board)
    panel=await board_row(probe,caller,iid)
    await commit_key(probe,caller,str(option).encode() if option else b't',lambda:panel.confirmation is not None)
    await commit_key(probe,caller,b'y',lambda:owner.state.engine.instances[iid].state=='turned_in')
    await close_jobs(probe,caller)
    return iid


async def run_case(root: Path, python: Path, show: bool, width: int, height: int, allocation: str, stage: str) -> dict[str,Any]:
    shipped=Path(__file__).parents[1]/'src/blacksite/content'
    descriptor=build_fixture(shipped,root/'world/content.local')
    probe=ContractProbe(root,python,show)
    await probe.start()
    try:
        caller=await probe.open(width,height,'S19Svc'+allocation,0,True)
        owner=probe.service.core.contracts
        pid=caller.session.player_id
        player=probe.game.players[pid]
        draft=owner.state.fork()
        draft.services.advance(owner.now(),3600)  # Disclosed uptime fixture only.
        owner.write(draft)
        await wait(lambda:not probe.commerce.pending)
        service_results=[]
        for sid in (() if stage=='forks' else ('sump','depot','relay-zero','cold-chain')):
            destination='vatside-clinics' if sid=='cold-chain' else descriptor['zone']
            await probe.route(caller,destination)
            iid=await reserve(probe,caller,sid,allocation)
            deadline=owner.state.services.nodes[sid].reserved_until
            if sid=='sump':
                await probe.leave(caller,f's19-mid-repair-{width}-{allocation}')
                caller=await reconnect(probe,caller,width,height)
                assert owner.state.engine.instances[iid].offer==owner.state.services.nodes[sid].order
                assert owner.state.services.nodes[sid].reserved_until==deadline
                await probe.route(caller,destination)
            before=player.chits_hand,player.xp
            await drive_job(probe,caller,iid,descriptor)
            assert owner.state.services.nodes[sid].state=='allocated'
            assert player.chits_hand-before[0]==200 and player.xp-before[1]>=100
            if sid=='sump':
                zone=owner.world.zones[descriptor['zone']]
                await wait(lambda:zone.passable(tuple(descriptor['shortcut']))==(allocation=='common'),timeout=8)
                assert zone.passable(tuple(descriptor['niche']))==(allocation=='reserve')
                if allocation=='reserve':
                    await probe.near(caller,'fx-sump-cache')
                    before_units=sum(probe.commerce.items[i].stack for i in player.inventory
                                     if probe.commerce.items[i].template=='slv_power' and not probe.commerce.items[i].mission)
                    await commit_key(probe,caller,b'e',lambda:sum(probe.commerce.items[i].stack for i in player.inventory
                        if probe.commerce.items[i].template=='slv_power' and not probe.commerce.items[i].mission)==before_units+2)
            if sid=='depot':
                assert owner.effects.budget(owner.content.vendors['kestrel-surplus'],descriptor['zone']+':fx-depot-surplus')==(2 if allocation=='common' else 1)
            if sid=='relay-zero':
                presence=await enter_core(probe,caller,descriptor['core'],descriptor)
                if allocation=='common':
                    assert owner.effects.patrols(pid)
                else:
                    await encounter_row(probe,caller,'control:fx-relay-zero-release')
                    await wait(lambda:owner.world.zones[descriptor['zone']].objects['fx-relay-zero-hardware'].open is True)
                await leave_network(probe,caller)
            probe.save(caller,f's19-{sid}-{allocation}-{width}')
            service_results.append(dict(service=sid,allocation=allocation,chits=200,worker_xp=100,
                                        actual_xp=player.xp-before[1],reservation_deadline=deadline))
            probe.report(f'S19 PASS {width}x{height}: {sid} {allocation}, saved allocation and worker reward')
        await probe.route(caller,descriptor['zone'])
        tid='sab-s1-1-retrieval' if allocation=='common' else 'unm-s1-2-vat-nine'
        board='fx-sablier-board' if allocation=='common' else 'fx-unmoored-board'
        before=player.chits_hand
        await settle_story(probe,caller,tid,board,descriptor)
        assert player.chits_hand-before==(400 if allocation=='common' else 200)
        branch='clinic' if allocation=='common' else 'shield'
        assert owner.state.engine.branches[owner.state.engine.branch_key(pid,'walked-templates-s1')]==branch
        before=player.chits_hand
        iid=await settle_story(probe,caller,'kes-s1-2-diversion','fx-kestrel-board',descriptor,1 if allocation=='common' else 2)
        assert player.chits_hand-before==(400 if allocation=='common' else 200)
        balances=player.chits_hand,player.xp,dict(player.standing)
        probe.save(caller,f's19-forks-{allocation}-{width}')
        await probe.leave(caller,f's19-paid-left-{allocation}-{width}')
        await probe.service.stop()
        probe.service=Server(root/'world',tcp=True)
        await probe.service.start()
        probe.game,probe.commerce,probe.combat=probe.service.core.characters,probe.service.core.commerce,probe.service.core.combat
        caller=await reconnect(probe,caller,width,height)
        owner=probe.service.core.contracts
        player=probe.game.players[pid]
        assert (player.chits_hand,player.xp,player.standing)==balances
        assert owner.state.engine.instances[iid].state=='turned_in'
        probe.save(caller,f's19-paid-restart-{allocation}-{width}')
        await probe.leave(caller,f's19-service-left-{allocation}-{width}')
        result=dict(passed=True,size=[width,height],allocation=allocation,stage=stage,services=service_results,
                    forks=True,repair_reconnect=bool(service_results),paid_server_restart=True,**descriptor)
        (root/'s19-service-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        return result
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
    finally:
        await probe.close()


async def accept(root: Path, python: Path, show: bool, size: str, allocation: str, stage: str) -> None:
    sizes=((80,24),(132,50)) if size=='both' else (tuple(map(int,size.split('x'))),)
    allocations=('common','reserve') if allocation=='both' else (allocation,)
    results=[await run_case(root/f'{width}-{mode}',python,show,width,height,mode,stage)
             for width,height in sizes for mode in allocations]
    (root/'s19-service-summary.json').write_text(json.dumps(dict(passed=True,runs=results),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--door-python',type=Path,required=True)
    parser.add_argument('--show',action='store_true')
    parser.add_argument('--size',choices=('both','80x24','132x50'),default='both')
    parser.add_argument('--allocation',choices=('both','common','reserve'),default='both')
    parser.add_argument('--stage',choices=('all','forks'),default='all')
    args=parser.parse_args()
    asyncio.run(accept(args.root,args.door_python,args.show,args.size,args.allocation,args.stage))
