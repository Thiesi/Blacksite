"""S11 real native door: populated streets, refusal, heat and local guards.

The heat interval is actually waited at both sizes. No player teleports,
extra money, faction membership or progression fixtures are needed.
"""

import argparse
import asyncio
import gc
from collections import deque
from dataclasses import asdict
import json
from pathlib import Path
import time
import threading
from typing import Any

from accept_s10_netbbs import Connection, NativeProbe, wait
from karst41.admin.client import request
from karst41.server.loop import TickContext
from karst41.server.world.actors import Actor
from karst41.server.world.sight import line_of_sight
from write_profile import WriteProfile
from minimal_s40_profile import MinimalProfile
from tick_budget import enforce


async def approach(probe: NativeProbe, caller: Connection, target: Actor,
                   *, hostile_tile: bool = True) -> None:
    actor=caller.avatar.actor
    zone=probe.service.world.zones[actor.zone]
    async with asyncio.timeout(20):
        while not probe.combat.visible(target,actor) or (actor.x-target.x)**2+(actor.y-target.y)**2>16:
            # A moving patrol may leave a geometrically close tile behind
            # a wall or another body. Choose a reachable visible approach,
            # then take only one real-key step before planning again.
            occupied={a.position for a in zone.actors.values() if a is not actor}
            exits={e.tile for e in zone.template.meta.exits if e.kind=='street'}
            pending,previous=deque([actor.position]),{actor.position:None}
            while pending:
                x,y=pending.popleft()
                for tile in ((x+1,y),(x,y+1),(x-1,y),(x,y-1)):
                    if tile not in previous and tile not in occupied and tile not in exits and zone.passable(tile):
                        previous[tile]=(x,y);pending.append(tile)
            candidates=[tile for tile in previous if (not hostile_tile or zone.allows_hostile(tile))
                and (tile[0]-target.x)**2+(tile[1]-target.y)**2<=16
                and line_of_sight(zone,tile,target.position)]
            if not candidates:
                await asyncio.sleep(.1)
                continue
            tile=min(candidates,key=lambda p:(p[0]-actor.x)**2+(p[1]-actor.y)**2)
            if tile == actor.position:
                await asyncio.sleep(.1)
                continue
            step=tile
            while previous[step]!=actor.position:
                step=previous[step]
            # A new actor can occupy even that first step after the search.
            try:
                async with asyncio.timeout(1):
                    await probe.walk(caller,step)
            except TimeoutError:
                pass



async def profile(probe: NativeProbe, width: int, height: int) -> float:
    # Only status, sparse commit exits and two loop boundaries are added.
    # Detailed write wrappers/proxies remain in the later diagnostic.
    with (WriteProfile(probe.service, trace_writes=False) as writes_profile,
          MinimalProfile(probe.service) as minimal):
        return await _profile(probe, width, height, writes_profile, minimal)


async def _profile(probe: NativeProbe, width: int, height: int,
                   writes_profile: WriteProfile, minimal: MinimalProfile) -> float:
    loop = probe.service.core.loop
    original_subsystems, original_step = loop.subsystems, loop.step
    original_writes = probe.service._character_writes
    original_flush = probe.service.storage._flush
    gc_starts: dict[tuple[int, int], tuple[float, float, int]] = {}
    gc_pauses: list[dict[str, Any]] = []
    flushes: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    sampling_tick, status = -1, {}

    def gc_trace(phase: str, info: dict[str, int]) -> None:
        identity = threading.get_ident(), info['generation']
        if phase == 'start':
            gc_starts[identity] = time.perf_counter(), time.thread_time(), probe.service.clock.now_tick()
        elif phase == 'stop':
            began = gc_starts.pop(identity, None)
            if began:
                gc_pauses.append({'tick': began[2], 'thread': identity[0], 'generation': identity[1],
                    'wall_ms': (time.perf_counter()-began[0])*1000,
                    'cpu_ms': (time.thread_time()-began[1])*1000})

    def flush(*args: Any, **kwargs: Any) -> Any:
        wall, cpu, tick = time.perf_counter(), time.thread_time(), probe.service.clock.now_tick()
        pending = len(probe.service.storage.dirty)
        try:
            return original_flush(*args, **kwargs)
        finally:
            flushes.append({'tick': tick, 'thread': threading.get_ident(), 'pending_rows': pending,
                'wall_ms': (time.perf_counter()-wall)*1000,
                'cpu_ms': (time.thread_time()-cpu)*1000})

    class TimedSubsystem:
        def __init__(self, subsystem: Any, label: str) -> None:
            self.subsystem, self.label = subsystem, label

        def tick(self, ctx: TickContext) -> None:
            wall, cpu = time.perf_counter(), time.thread_time()
            try:
                self.subsystem.tick(ctx)
            finally:
                if current is not None:
                    current['segments'][self.label] = {
                        'wall_ms': (time.perf_counter()-wall)*1000,
                        'cpu_ms': (time.thread_time()-cpu)*1000}

    def step() -> None:
        nonlocal current
        current = {'tick': probe.service.clock.now_tick(), 'segments': {},
                   '_wall': time.perf_counter(), '_cpu': time.thread_time()}
        wall, cpu = time.perf_counter_ns(), time.thread_time()
        try:
            original_step()
        finally:
            ended = time.perf_counter_ns()
            current['tick'] = loop.last_tick
            current['loop_wall_ms'] = (ended-wall)/1_000_000
            current['loop_cpu_ms'] = (time.thread_time()-cpu)*1000
            current.update(minimal.intervals(wall, ended))

    def writes() -> None:
        nonlocal current
        wall, cpu = time.perf_counter(), time.thread_time()
        try:
            original_writes()
        finally:
            if current is not None:
                current['writes_wall_ms'] = (time.perf_counter()-wall)*1000
                current['writes_cpu_ms'] = (time.thread_time()-cpu)*1000
                current['total_wall_ms'] = (time.perf_counter()-current.pop('_wall'))*1000
                current['total_cpu_ms'] = (time.thread_time()-current.pop('_cpu'))*1000
                rows.append(current)
                current = None

    loop.subsystems = [TimedSubsystem(system, f'{index}:{type(system).__name__}')
                       for index, system in enumerate(original_subsystems)]
    loop.step = step
    probe.service._character_writes = writes
    probe.service.storage._flush = flush
    gc.callbacks.append(gc_trace)
    for zone in probe.service.world.zones.values():
        zone.activate("s11-profiling",probe.service.clock.now_tick())
    try:
        await asyncio.sleep(2)
        sampling_tick = probe.service.clock.now_tick()
        loop.timings.clear()
        await asyncio.sleep(10)
        status=await request(probe.service.install_dir,"status")
        count = len(probe.service.world.zones)
        assert status["active_zones"]==count,status
        verdict=enforce(status["tick_p99_ms"],f"S11 admin status {width}x{height}")
        probe.report(f"PASS admin status {width}x{height}: all {count} zones active, p99 {status['tick_p99_ms']:.3f} ms ({verdict})")
        return status["tick_p99_ms"]
    finally:
        loop.subsystems, loop.step = original_subsystems, original_step
        probe.service._character_writes = original_writes
        probe.service.storage._flush = original_flush
        if gc_trace in gc.callbacks:
            gc.callbacks.remove(gc_trace)
        for zone in probe.service.world.zones.values():
            zone.deactivate("s11-profiling",probe.service.clock.now_tick())
        number = len(list(probe.root.glob(f'npc-profile-{width}x{height}-*.json')))+1
        (probe.root/f'npc-profile-{width}x{height}-{number}.json').write_text(json.dumps({
            'status': status, 'sampling_started_tick': sampling_tick,
            'instrumentation': 'wall/thread CPU, GC and storage flush probes; same 10 ms gate including overhead',
            'gc_pauses': gc_pauses, 'storage_flushes': flushes,
            'ticks': rows, 'write_probe': writes_profile.metadata(),
            'commerce_commits': minimal.export(),
            'canonical_observer': {
                'commit': 'Two perf_counter_ns reads around existing SQLite context exit; wall only',
                'loop': 'Two extra perf_counter_ns reads: after inputs, before publishers',
                'limits': 'Commit failure may include SQLite rollback; no thread CPU or rusage; no gate correction'},
            'write_calls': list(writes_profile.calls),
            'gate': writes_profile.gate(status) if status else None}, indent=2)+'\n', encoding='utf-8')


async def write_diagnostic(probe: NativeProbe, width: int, height: int) -> None:
    """Collect detailed all-hub writes after the canonical result is saved."""
    loop = probe.service.core.loop
    # Model the NPC armour-learning receipt after the canonical result is
    # saved. This is a current snapshot, not the stalled receipt's payload.
    game, commerce = probe.service.core.characters, probe.service.core.commerce
    records = [player.record() for player in game.players.values()]
    player = max(records, key=lambda row: len(json.dumps(row).encode('utf-8')))
    shape = {'basis': 'Post-result largest current player; record_use player-only receipt',
             'tick': loop.last_tick, 'not_captured_stalled_payload': True,
             'effect': {'player': player, 'players': [], 'items': [], 'delete_items': [],
                        'budgets': {key: asdict(value) for key, value in commerce.budgets.items()},
                        'caches': commerce.caches, 'serial': commerce.serial}}
    (probe.root/'disk-baseline-shape.json').write_text(
        json.dumps(shape, ensure_ascii=False)+'\n', encoding='utf-8')
    began_tick, began = loop.last_tick, time.perf_counter()
    for zone in probe.service.world.zones.values():
        zone.activate('s40-write-diagnostic', probe.service.clock.now_tick())
    trace = WriteProfile(probe.service)
    try:
        with trace:
            await asyncio.sleep(120)
    finally:
        try:
            path = probe.root/f'npc-write-diagnostic-{width}x{height}.json'
            manifest = trace.export_trace(path, {
                'diagnostic_only': True, 'phase': 'after_final_canonical_gate',
                'began_tick': began_tick, 'ended_tick': loop.last_tick,
                'all_hub_zones': len(probe.service.world.zones),
                'requested_seconds': 120, 'elapsed_seconds': time.perf_counter()-began,
                'retention': 'Latest calls only, bounded by loop.timings.maxlen',
                'limits': 'Detailed probe overhead is included here; these are not gate samples.'})
            (probe.root/f'npc-write-shape-{width}x{height}.json').write_text(
                json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
            probe.report(f"S40 DIAGNOSTIC {width}x{height}: {manifest['exported_calls']} calls, "
                         f"{manifest['trace_bytes']} bytes, export {manifest['export_seconds']:.3f}s; not a gate")
        finally:
            for zone in probe.service.world.zones.values():
                zone.deactivate('s40-write-diagnostic', probe.service.clock.now_tick())
            del trace


async def sodium_response(probe: NativeProbe, caller: Connection, width: int, height: int) -> None:
    actor=caller.avatar.actor
    await probe.walk(caller,(16,5))
    sodium=probe.service.world.zones[actor.zone]
    guards=[a for a in sodium.actors.values() if a.behaviour.get("template")=="npc-sable-enforcer"]
    assert len(guards)>=2 and all(a.faction=="sable" for a in guards)
    victim=min(guards,key=lambda a:(a.x-actor.x)**2+(a.y-actor.y)**2)
    responders=[a for a in guards if a.id!=victim.id]
    # #147 makes regulars unaffiliated: Sable no longer answers their attacks.
    # Provoke a real Sable peer and require another enforcer to answer.
    # Keep using real movement/fire keys if the victim leaves weapon range.
    async with asyncio.timeout(30):
        while not any(a.target==actor.id for a in responders):
            if (victim.x-actor.x)**2+(victim.y-actor.y)**2>16:
                occupied={a.position for a in sodium.actors.values()}
                candidates=[(x,y) for x in range(victim.x-1,victim.x+2) for y in range(victim.y-1,victim.y+2)
                    if sodium.passable((x,y)) and (x,y) not in occupied]
                tile=min(candidates,key=lambda p:(p[0]-actor.x)**2+(p[1]-actor.y)**2)
                await probe.walk(caller,tile)
            await probe.target(caller,victim.id)
            await caller.caller.write(b"f")
            await asyncio.sleep(.25)
    assert not any(a.faction=="wardens" and a.target==actor.id for a in sodium.actors.values())
    probe.save(caller,f"s11-sodium-{width}x{height}")
    probe.report(f"PASS local response {width}x{height}: another Sable enforcer answers an attack on a Sable peer, no Wardens")


async def accept(root: Path, door_python: Path, show: bool,
                 sizes: tuple[tuple[int, int], ...] = ((80,24),(132,50))) -> None:
    probe=NativeProbe(root,door_python,show)
    await probe.start()
    results=[]
    try:
        for width,height in sizes:
            caller=await probe.open(width,height,"NpcRunner",0,True)
            actor=caller.avatar.actor
            await probe.walk(caller,(21,14))
            await caller.caller.write(b"b")
            await wait(lambda:probe.game.players[actor.id].progress.get("wake_combat")=="skipped")
            await probe.travel(caller,"vatside-clinics")
            await probe.travel(caller,"core-plaza")
            await probe.walk(caller,(20,6))
            plaza=probe.service.world.zones["core-plaza"]
            before={a.id:a.position for a in plaza.actors.values() if a.kind!="player"}
            moved=set()
            for _ in range(30):
                await asyncio.sleep(.1)
                moved.update(a.behaviour.get("template") for a in plaza.actors.values()
                             if a.id in before and a.position!=before[a.id])
            assert {"npc-civilian","npc-warden-patrol","npc-courier"} <= moved,moved
            await wait(lambda:"~" in caller.caller.screen.screen_text())
            await profile(probe,width,height)
            # Profiling leaves the simulation running: civilians can walk
            # out of sight. Approach a real civilian instead of assuming
            # one is still visible from the earlier observation point.
            target=min((a for a in plaza.actors.values() if a.behaviour.get("template")=="npc-civilian"),
                       key=lambda a:(a.x-actor.x)**2+(a.y-actor.y)**2)
            await approach(probe,caller,target,hostile_tile=False)
            await probe.target(caller,target.id)
            hp=actor.health;target_hp=target.health
            started=time.monotonic()
            await caller.caller.write(b"f")
            await wait(lambda:probe.game.players[actor.id].warden_heat_until is not None,2)
            response=time.monotonic()-started
            assert len([a for a in plaza.actors.values() if a.behaviour.get("response")==actor.id])==2
            for _ in range(3):
                await caller.caller.write(b"f");await asyncio.sleep(.2)
            assert (actor.health,target.health)==(hp,target_hp)
            await wait(lambda:"HEAT" in caller.caller.screen.screen_text().splitlines()[0])
            probe.save(caller,f"s11-plaza-{width}x{height}")
            probe.report(f"PASS NPC plaza {width}x{height}: patrol, wander, courier, relation glyph, warning {response:.2f}s, two responders, safe HP")
            await probe.travel(caller,"vatside-clinics")
            await probe.walk(caller,(44,3))
            patrol=next(a for a in probe.service.world.zones[actor.zone].actors.values() if a.behaviour.get("template")=="npc-warden-patrol")
            await approach(probe,caller,patrol)
            await wait(lambda:patrol.target==actor.id,3)
            probe.report(f"PASS heat pursuit {width}x{height}: Clinic Row patrol targets caller after visible warning")
            # Retreat to the real public-clinic pocket before waiting out heat.
            clinic=next(o for o in probe.service.world.zones[actor.zone].objects.values() if o.spec.essential and o.spec.params.get("vendor"))
            await probe.walk(caller,clinic.spec.tile)
            assert not probe.service.world.zones[actor.zone].allows_hostile(actor.position)
            await wait(lambda:patrol.target is None,3)
            safe_hp=actor.health
            until=probe.game.players[actor.id].warden_heat_until
            from datetime import datetime
            while probe.combat.now()<datetime.fromisoformat(until).timestamp():
                await asyncio.sleep(min(30,datetime.fromisoformat(until).timestamp()-probe.combat.now()))
                probe.report(f"WAIT heat {width}x{height}: {max(0,datetime.fromisoformat(until).timestamp()-probe.combat.now()):.0f}s remain in protected clinic")
                assert actor.health==safe_hp
            await probe.walk(caller,(44,3))
            await approach(probe,caller,patrol)
            await asyncio.sleep(3)
            assert patrol.target is None
            assert not probe.game.me(caller.session)["heat_until"]
            probe.report(f"PASS actual ten-minute heat expiry {width}x{height}: patrol ignores Freelance again")
            await probe.travel(caller,"core-plaza")
            await probe.travel(caller,"sodium-row")
            await sodium_response(probe,caller,width,height)
            try:
                p99=await profile(probe,width,height)
            except AssertionError:
                probe.report(f"S40 DIAGNOSTIC {width}x{height}: final canonical gate FAILED; preserving result before detailed capture")
                await write_diagnostic(probe,width,height)
                raise
            # With both sizes in one service, leave every canonical window
            # ahead of detailed collection. CI uses one service per size.
            if (width, height) == sizes[-1]:
                probe.report(f"S40 DIAGNOSTIC {width}x{height}: final canonical gate passed; collecting supplementary evidence")
                await write_diagnostic(probe,width,height)
            await probe.leave(caller,f"s11-complete-{width}x{height}")
            results.append({"size":[width,height],"warning_seconds":response,"heat_wait":"actual 600-second deadline",
                "safe_damage":False,"local_guards":True,"all_hub_p99_ms":p99})
        assert not probe.errors,probe.errors
        (probe.root/"result.json").write_text(json.dumps({"passed":True,"transport":"NetBBS Telnet native stdio",
            "teleports":False,"human_playtest":False,"runs":results},indent=2),encoding="utf-8")
    finally:
        await probe.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--door-python",type=Path,required=True)
    parser.add_argument("--show",action="store_true")
    parser.add_argument("--size", choices=("80x24", "132x50"),
                        help="Run one profile; the default runs both sizes.")
    args=parser.parse_args()
    sizes = (tuple(map(int,args.size.split("x"))),) if args.size else ((80,24),(132,50))
    asyncio.run(accept(args.root,args.door_python,args.show,sizes))
