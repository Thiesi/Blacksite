"""S43: current-namespace successor to the 6d6fc30 publisher replay."""
from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import json
from pathlib import Path
import pstats
import statistics
import subprocess
import sys
import time
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def distribution(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {"mean": statistics.mean(values), "median": statistics.median(values),
            "p99": ordered[min(len(ordered)-1, (len(ordered)*99+99)//100-1)],
            "max": max(values)}


def fixture(source: Path, case: str) -> tuple[Any, Any, Any, str]:
    from karst41.content.loader import load_content
    from karst41.server.world.sight import line_of_sight
    from tests.character_helpers import create, place
    from tests.harness import HeadlessServer

    content = load_content(source/'src/karst41/content')
    game = HeadlessServer(content, character_state={})
    client = game.connect({'user_id': 1, 'handle': 'Replay界', 'node_name': 'fixture'}, width=132, height=50)
    create(game, client, archetype=0, name='Replay', card='none')
    place(game, client, 'sodium-row', (16, 5))
    core = game.core
    actor = core.characters.sim.avatars[client.session.user_id].actor
    zone = core.world.zones[actor.zone]
    # Undo the single spawn tick's movement. The authored spawn homes and
    # deterministic zone seed are identical inputs; no simulation follows.
    npcs = [a for a in zone.actors.values() if a.kind == 'npc' and 'home' in a.behaviour]
    for other in npcs:
        core.world.leave(other)
    for other in npcs:
        core.world.enter(other, zone.id, tuple(other.behaviour['home']))
        other.target = None
    warden = next(a for a in zone.actors.values() if a.behaviour.get('template') == 'npc-plainclothes-warden')
    guard = next(a for a in sorted(zone.actors.values(), key=lambda a:a.id)
                 if a.behaviour.get('template') == 'npc-sable-enforcer')

    def near(other: Any) -> None:
        occupied = {a.position for a in zone.actors.values() if a is not other}
        tiles = [(x, y) for x in range(actor.x-3, actor.x+4) for y in range(actor.y-3, actor.y+4)
                 if (x, y) not in occupied and zone.can_enter(other, (x, y))
                 and line_of_sight(zone, actor.position, (x, y))]
        tile = min(tiles, key=lambda p:((p[0]-actor.x)**2+(p[1]-actor.y)**2, p))
        core.world.enter(other, zone.id, tile)

    near(guard)
    if case == 'no_cover':
        core.world.leave(warden)
    else:
        near(warden)
    actor.target = warden.id if case == 'covered_target' else guard.id
    guard.target = actor.id
    core.npcs.provocations[zone.id, str(guard.behaviour['spawner']), actor.id] = core.combat.now()+600
    avatar = core.characters.sim.avatars[client.session.user_id]
    avatar.perception = type(avatar.perception)()
    actor.sight_key = None
    client.session.send_queue.clear()
    client.session.acknowledge(client.session.view_revision)
    rows = [{'id': a.id, 'template': a.behaviour.get('template'), 'spawner': a.behaviour.get('spawner'),
             'position': a.position, 'health': a.health, 'target': a.target, 'faction': a.faction}
            for a in sorted(zone.actors.values(), key=lambda a:a.id)]
    return game, client, actor, digest(rows)


def measure(source: Path, case: str, cache_mode: str, iterations: int, profiled: int, output: Path) -> dict[str, Any]:
    from karst41.server.loop import TickContext

    game, client, actor, fixture_sha = fixture(source, case)
    loop, sim, session = game.core.loop, game.core.characters.sim, client.session
    next_tick = game.clock.now_tick()+100
    wall, cpu = [], []
    profiler = cProfile.Profile()
    phase, iteration = 'warmup', 0
    gc_events: list[dict[str, Any]] = []
    bodies: dict[int, str] = {}

    def gc_event(action: str, info: dict[str, int]) -> None:
        if action == 'stop':
            gc_events.append({'phase': phase, 'iteration': iteration, 'generation': info['generation']})

    def publish(profile: bool = False) -> tuple[float, float]:
        nonlocal next_tick
        next_tick += 1
        # One explicit field change forces the ordinary delta/encoding path.
        # It is declared fixture input, not healing in native acceptance.
        actor.health = actor.health_max-(next_tick % 2)
        session.acknowledge(session.view_revision)
        session.send_queue.clear()
        sim.published.pop(session.id, None)
        if cache_mode == 'invalidate':
            actor.sight_key = None
            sim.avatars[session.user_id].perception.grid_key = None
        revision = session.view_revision
        context = TickContext(next_tick, game.clock, loop.bus, (session,), loop.content)
        if profile:
            profiler.enable()
        started_wall, started_cpu = time.perf_counter_ns(), time.thread_time_ns()
        sim.publish(context)
        elapsed_cpu, elapsed_wall = time.thread_time_ns()-started_cpu, time.perf_counter_ns()-started_wall
        if profile:
            profiler.disable()
        assert session.view_revision == revision+1, 'Replay must publish every invocation'
        body = sim.views[session.id].previous['body']
        assert body['me']['hp'] == actor.health
        # Hash outside both the timing brackets and cProfile. Only two
        # reference documents are needed; later calls retain frozen input.
        if next_tick % 2 not in bodies:
            bodies[next_tick % 2] = digest(body)
        return elapsed_wall/1e6, elapsed_cpu/1e6

    gc.callbacks.append(gc_event)
    try:
        for iteration in range(50):
            publish()
        phase = 'unprofiled'
        for iteration in range(iterations):
            w, c = publish()
            wall.append(w)
            cpu.append(c)
        phase = 'profiled'
        for iteration in range(profiled):
            publish(True)
    finally:
        gc.callbacks.remove(gc_event)
    stats = pstats.Stats(profiler)
    functions = []
    for (file, line, name), (primitive, calls, own, cumulative, callers) in stats.stats.items():
        try:
            file = Path(file).relative_to(source).as_posix()
        except ValueError:
            pass
        functions.append({'file': str(file), 'line': line, 'name': name, 'calls': calls,
                          'self_ms': own*1000, 'cumulative_ms': cumulative*1000})
    output.parent.mkdir(parents=True, exist_ok=True)
    profiler.dump_stats(str(output.with_name(output.stem+'-'+case+'-'+cache_mode+'.pstats')))
    return {'case': case, 'cache_mode': cache_mode, 'fixture_sha256': fixture_sha, 'body_sha256': bodies,
            'nearby_count': len(sim.views[session.id].previous['body']['nearby']),
            'unprofiled_calls': iterations, 'profiled_calls': profiled,
            'publisher_wall_ms': distribution(wall), 'publisher_thread_cpu_ms': distribution(cpu),
            'wall_samples_ms': wall, 'thread_cpu_samples_ms': cpu,
            'gc_events': gc_events, 'functions': sorted(functions, key=lambda f:f['cumulative_ms'], reverse=True)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--iterations', type=int, default=1000)
    parser.add_argument('--profiled', type=int, default=200)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('refuse to overwrite a retained replay arm')
    source = args.source.resolve()
    sys.path[:0] = [str(source/'src'), str(source)]
    import karst41
    import tests.harness
    assert Path(karst41.__file__).is_relative_to(source/'src')
    assert Path(tests.harness.__file__).is_relative_to(source/'tests')
    report = {'label': args.label,
              'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip(),
              'python': sys.version, 'acceptance_credit': False,
              'limits': 'Frozen seeded synthetic Sodium scene; forced per-call view rebuild/delta. No sockets, DB, tick simulation, native S11 rerun or gate comparison. cProfile costs include profiler overhead; outer unprofiled CPU is separate. The replay does not patch product code; source differences are the declared S43 traversal change.',
              'cases': [measure(source, case, mode, args.iterations, args.profiled, args.output)
                        for case in ('sable_target', 'covered_target', 'no_cover')
                        for mode in ('warm', 'invalidate')]}
    args.output.write_bytes((json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps({'label': args.label, 'head': report['head'], 'cases': [
        {'case': c['case'], 'cache_mode': c['cache_mode'], 'cpu_ms': c['publisher_thread_cpu_ms'], 'nearby_count': c['nearby_count']}
        for c in report['cases']]}))


if __name__ == '__main__':
    main()
