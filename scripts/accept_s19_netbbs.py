"""S19 registered native stdio acceptance, with unmodified hub first jobs.

Use the NetBBS interpreter and an installed current Blacksite wheel.
--show forwards the actual ANSI stream to the hosting real terminal.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import deque
import json
from pathlib import Path
import traceback
import time
from typing import Any
from collections.abc import Callable

from accept_s10_netbbs import Connection, wait
from accept_s16_netbbs import commit_key, key, select
from accept_s22_netbbs import CrewProbe


class ContractProbe(CrewProbe):
    async def near(self, connection: Connection, object_id: str) -> None:
        zone = self.service.world.zones[connection.avatar.zone]
        target = zone.objects[object_id].spec.tile
        actor = connection.avatar.actor
        occupied = {other.position for other in zone.actors.values() if other is not actor}
        choices = [(target[0]+dx,target[1]+dy) for dx in (-1,0,1) for dy in (-1,0,1)]
        choices = [tile for tile in choices if tile not in occupied and zone.can_enter(actor,tile)]
        assert choices, object_id
        pending,seen = deque([actor.position]),{actor.position}
        exits = {exit.tile for exit in zone.template.meta.exits}
        while pending:
            tile = pending.popleft()
            if tile in choices:
                await self.walk(connection,tile)
                return
            x,y = tile
            for candidate in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if candidate not in seen and candidate not in exits and candidate not in occupied and zone.can_enter(actor,candidate):
                    seen.add(candidate)
                    pending.append(candidate)
        raise AssertionError('No reachable interaction tile: '+object_id)

    async def route(self, connection: Connection, destination: str) -> None:
        origin = connection.avatar.zone
        pending,paths = deque([origin]),{origin:[]}
        while pending and destination not in paths:
            zone = pending.popleft()
            for exit in self.service.world.zones[zone].template.meta.exits:
                if exit.hidden or exit.requirement or exit.kind == 'tram' or exit.target_zone in paths:
                    continue
                paths[exit.target_zone] = [*paths[zone],exit.target_zone]
                pending.append(exit.target_zone)
        assert destination in paths, (origin,destination)
        for zone in paths[destination]:
            await self.travel(connection,zone)


async def close_jobs(probe: ContractProbe, caller: Connection) -> None:
    await commit_key(probe,caller,b'\x1b',lambda:caller.session.id not in probe.service.core.contracts.panels.menus)


async def objective_key(probe: ContractProbe, caller: Connection, completed: Callable[[], bool]) -> None:
    """A world action has no stale-menu revision and must be sent once.

    Repeating E while a channel finishes can deliver a late key to the
    next objective or an adjacent terminal. Wait for the committed action
    instead of trying to make a timed world interaction a retryable menu.
    """
    await wait(lambda:not probe.commerce.pending and not probe.commerce.waiting)
    await wait(lambda:caller.session.ack_revision==caller.session.view_revision)
    if completed():
        return
    await caller.caller.write(b'e')
    await wait(completed,20)


async def board_row(probe: ContractProbe, caller: Connection, row: str) -> Any:
    owner = probe.service.core.contracts
    await commit_key(probe,caller,b'e',lambda:caller.session.id in owner.panels.menus)
    panel = owner.panels.menus[caller.session.id]
    await select(caller,lambda:owner.panels.rows(caller.session,panel),panel,row)
    return panel


async def encounter_row(probe: ContractProbe, caller: Connection, row: str) -> None:
    encounters = probe.service.core.lattice.encounters
    presence = probe.service.core.lattice.presences[caller.session.player_id]
    await commit_key(probe,caller,b'e',lambda:caller.session.id in encounters.menus)
    screen = encounters.menus[caller.session.id]
    await select(caller,lambda:encounters.rows(presence,screen),screen,row)
    await commit_key(probe,caller,b'\r',lambda:encounters.menus.get(caller.session.id) is not screen)


async def first_job(probe: ContractProbe, width: int, height: int, network: bool) -> dict[str,Any]:
    route = 'network' if network else 'manual'
    caller = await probe.open(width,height,'S19'+route,0 if network else 1,True)
    owner = probe.service.core.contracts
    player = probe.game.players[caller.session.player_id]
    assert any(probe.commerce.items[i].template == 'story_vesper_card' for i in player.inventory)
    await probe.route(caller,'sodium-tin-halo')
    await probe.near(caller,'vesper')
    panel = await board_row(probe,caller,'vesper-first-thing')
    await commit_key(probe,caller,b'a',lambda:panel.confirmation is not None)
    probe.save(caller,f's19-first-terms-{route}-{width}')
    await commit_key(probe,caller,b'y',lambda:any(j.template == 'vesper-first-thing'
        and any(p.player == player.id for p in j.roster) for j in owner.state.engine.instances.values()))
    iid = next(j.id for j in owner.state.engine.instances.values() if j.template == 'vesper-first-thing'
               and any(p.player == player.id for p in j.roster))
    await close_jobs(probe,caller)
    await probe.route(caller,'terraces-blocks')
    await probe.near(caller,'stairwell-c-parcel-hatch')
    await objective_key(probe,caller,lambda:owner.state.engine.instances[iid].index == 1)
    await wait(lambda:'Next:' in caller.caller.screen.screen_text())
    probe.save(caller,f's19-first-objective-{route}-{width}')
    if network:
        await probe.near(caller,'stairwell-c-loan')
        await key(caller,b'j')
        await wait(lambda:player.id in owner.lat.presences)
        presence = owner.lat.presences[player.id]
        assert presence.loaned_rig
        assert presence.cell == 'lat-terraces-c11'
        await encounter_row(probe,caller,'enter:lat-stairwell-c')
        await wait(lambda:presence.core == 'lat-stairwell-c')
        await encounter_row(probe,caller,'control:parcel-release')
        await wait(lambda:owner.state.engine.instances[iid].index == 2)
        assert presence.trace == 0
        probe.save(caller,f's19-loan-release-{width}')
        await key(caller,b'j')
        await wait(lambda:player.id not in owner.lat.presences)
    else:
        start = probe.service.clock.now_tick()
        await objective_key(probe,caller,lambda:owner.state.engine.instances[iid].index == 2)
        assert probe.service.clock.now_tick()-start >= 50
        probe.save(caller,f's19-manual-release-{width}')
    await probe.near(caller,'stairwell-c-parcel')
    await objective_key(probe,caller,lambda:owner.state.engine.instances[iid].index == 3)
    parcel = next(probe.commerce.items[i] for i in player.inventory
                  if probe.commerce.items[i].mission == iid)
    assert parcel.bound and not parcel.secured
    await probe.route(caller,'sodium-tin-halo')
    await probe.near(caller,'vesper')
    await objective_key(probe,caller,lambda:owner.state.engine.instances[iid].state == 'complete')
    panel = await board_row(probe,caller,iid)
    before = player.chits_hand,player.xp,dict(player.standing)
    await commit_key(probe,caller,b't',lambda:panel.confirmation is not None)
    await commit_key(probe,caller,b'y',lambda:owner.state.engine.instances[iid].state == 'turned_in')
    assert player.chits_hand-before[0] == 200 and player.xp-before[1] == 100
    assert all(player.standing[f]-before[2].get(f,0) == 5 for f in owner.content.factions)
    assert parcel.id not in probe.commerce.items
    assert 'stairwell-c-latch-record' in owner.state.journal[player.id]
    await commit_key(probe,caller,b'j',lambda:panel.tab == 'journal')
    await wait(lambda:'Observed:' in caller.caller.screen.screen_text())
    probe.save(caller,f's19-first-journal-{route}-{width}')
    await close_jobs(probe,caller)
    probe.report(f'S19 PASS {width}x{height}: unmodified hub {route} first job, 200 chits / 100 XP / explicit eight-faction +5')
    result = dict(size=[width,height],route=route,chits=200,xp=100,loan_trace=0 if network else None,
                  wide_name=player.name,fixtures=[])
    await probe.leave(caller,f's19-first-left-{route}-{width}')
    return result


async def accept(root: Path, python: Path, show: bool,
                 sizes: tuple[tuple[int,int], ...] = ((80,24),(132,50)),
                 routes: tuple[bool, ...] = (False,True), trace_input: bool = False) -> None:
    probe = ContractProbe(root,python,show)
    await probe.start()
    inputs: deque[dict[str,Any]] = deque(maxlen=512)
    raw: deque[dict[str,Any]] = deque(maxlen=2048)
    from netbbs.doors import runtime as door_runtime
    original_pump = door_runtime._pump_input
    if trace_input:
        class TracedEndpoint:
            def __init__(self, endpoint: Any) -> None:
                self.endpoint = endpoint

            async def write(self, data: bytes) -> None:
                raw.append(dict(at=time.monotonic(),phase='before',bytes=list(data)))
                await self.endpoint.write(data)
                raw.append(dict(at=time.monotonic(),phase='after',bytes=list(data)))

        async def traced_pump(session: Any, endpoint: Any) -> Any:
            return await original_pump(session,TracedEndpoint(endpoint))
        door_runtime._pump_input = traced_pump
    receive = probe.service.core.receive
    def traced_receive(session: Any, frame: Any) -> None:
        if frame.type == 'key':
            inputs.append(dict(session=session.id,tick=probe.service.clock.now_tick(),key=frame.data['k'],at=time.monotonic()))
        receive(session,frame)
    probe.service.core.receive = traced_receive
    try:
        results = [await first_job(probe,w,h,network) for w,h in sizes for network in routes]
        assert not probe.errors and probe.service.failure is None
        (root/'s19-hub-results.json').write_text(json.dumps(dict(passed=True,runs=results,
            transport='NetBBS Telnet -> registered native stdio',fixtures=[]),indent=2)+'\n',encoding='utf-8')
    except BaseException:
        (root/'input-tail.json').write_text(json.dumps(list(inputs),indent=2)+'\n',encoding='utf-8')
        (root/'failure-trace.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
    finally:
        await probe.close()
        door_runtime._pump_input = original_pump
        if trace_input:
            (root/'native-forwarding-tail.json').write_text(json.dumps(list(raw),indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--door-python',type=Path,required=True)
    parser.add_argument('--show',action='store_true')
    parser.add_argument('--size',choices=('both','80x24','132x50'),default='both')
    parser.add_argument('--route',choices=('both','manual','network'),default='both')
    parser.add_argument('--trace-input',action='store_true')
    args = parser.parse_args()
    sizes = ((80,24),(132,50)) if args.size == 'both' else (tuple(map(int,args.size.split('x'))),)
    routes = (False,True) if args.route == 'both' else (args.route == 'network',)
    asyncio.run(accept(args.root,args.door_python,args.show,sizes,routes,args.trace_input))
