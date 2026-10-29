"""Measure the shipped Display, never the server or terminal emulator.

The V1 provisional mix is a workload, not measured player behaviour.
Wall latency and process CPU are recorded separately. No timing assertions
belong in pytest: P1 records existing misses for subsequent slices.
"""

from collections import Counter
from pathlib import Path
import time
from typing import Any, Callable, TypeVar

from blacksite.content.loader import ContentTree
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from tests.character_helpers import place
from tests.presentation.mechanics import character_game

MIX = {'walking in a scene place': 10, 'walking where there is no scene': 20,
       'standing, a few stops a minute': 15, 'menus, text and help': 15}
KEYS = {'walking in a scene place': ['up']*6+['right']*2+['up']*6+['left']*2,
        'walking where there is no scene': ['right']*8+['left']*8}
T = TypeVar('T')


def stats(values: list[float | int]) -> dict[str, float | int | None]:
    ordered = sorted(values)
    return {'count': len(values), 'p50': ordered[(len(ordered)-1)//2] if values else None,
        'p95': ordered[min(len(ordered)-1, round(.95*(len(ordered)-1)))] if values else None,
        'max': max(values) if values else None}


class Meter:
    def __init__(self) -> None:
        self.cpu_ns = 0
        self.calls: Counter[str] = Counter()

    def call(self, name: str, function: Callable[..., T], *args: Any) -> T:
        started = time.process_time_ns()
        try:
            return function(*args)
        finally:
            self.cpu_ns += time.process_time_ns()-started
            self.calls[name] += 1


class Caller:
    def __init__(self, content: ContentTree, width: int, height: int, tier: str, zone: str) -> None:
        self.game, self.client = character_game(content, width, height, isolate_npcs=False)
        self.avatar = self.game.core.characters.sim.avatars[self.client.session.user_id]
        start = (12, 11) if zone == 'sodium-row' else (4, 10)
        if not self.game.core.world.zones[zone].passable(start):
            raise AssertionError(f'V1 baseline start is not passable: {zone} {start}')
        place(self.game, self.client, zone, start)
        self.game.commit_commerce()
        for _ in range(30):  # V1's activity warm-up, with shipped spawners.
            self.game.step()
            self.game.commit_commerce()
        self.display = Display(DoorInfo(Path('unused'), Path('.'),
            {'handle': 'Verifier\u754c', 'user_id': 1}, width, height, tier, 3600), 'p1-budget')
        self.meter = Meter()
        self.drain(0)
        # character_game completed the wake before this Display existed. Its queued
        # historical prompts have already been answered by create(), not by
        # this Display; start measurement with the settled live zone view.
        self.display.prompt = self.display.key_prompt = None
        self.draw(0)
        self.meter = Meter()  # Character creation and initial handshake are warm-up.
        self.moves = 0

    def drain(self, now: float) -> None:
        for frame in self.game.frames_for(self.client):
            for output in self.meter.call('receive', self.display.receive, frame, now):
                self.client.send(output)

    def key(self, key: str, now: float) -> None:
        for output in self.meter.call('key', self.display.key, key, now):
            self.client.send(output)

    def tick(self, now: float) -> None:
        before = (self.avatar.actor.zone, self.avatar.actor.position)
        self.game.step()
        self.game.commit_commerce()
        self.moves += before != (self.avatar.actor.zone, self.avatar.actor.position)
        self.drain(now)

    def draw(self, now: float) -> dict[str, Any] | None:
        before_cpu = self.meter.cpu_ns
        self.meter.call('update', self.display.update, 10.0, now)
        full = self.display.force_full or self.display.previous is None
        started = time.perf_counter_ns()
        data, ack = self.meter.call('render', self.display.render, now)
        wall = (time.perf_counter_ns()-started)/1e6
        if ack:
            self.client.send(ack)
        if not data:
            return None
        return {'kind': 'full' if full else 'delta', 'bytes': len(data),
            'render_wall_ms': wall, 'update_render_cpu_ms': (self.meter.cpu_ns-before_cpu)/1e6}


def frames(content: ContentTree, width: int, height: int, tier: str) -> dict[str, Any]:
    caller = Caller(content, width, height, tier, 'sodium-row')
    samples = []
    # A real full redraw, then input-driven deltas at five steps a second.
    caller.key('ctrl-l', 1.0)
    samples.append(caller.draw(1.0))
    for tick in range(1, 81):
        now = 1.0+tick*.101  # Avoid float rounding below Display's 100 ms gate.
        if tick % 2 == 0:
            caller.key(KEYS['walking where there is no scene'][(tick//2-1) % 16], now)
        caller.tick(now)
        frame = caller.draw(now)
        if frame:
            samples.append(frame)
    summary = {kind: {field: stats([s[field] for s in samples if s and s['kind'] == kind])
        for field in ('bytes', 'render_wall_ms', 'update_render_cpu_ms')} for kind in ('full', 'delta')}
    if not summary['full']['bytes']['count'] or not summary['delta']['bytes']['count'] or not caller.moves:
        raise AssertionError('baseline must exercise both full and delta output while moving')
    return {'samples': samples, 'summary': summary, 'successful_moves': caller.moves,
        'door_cpu_ms': caller.meter.cpu_ns/1e6, 'calls': dict(caller.meter.calls),
        'delta_16kib_pass': summary['delta']['bytes']['max'] <= 16*1024,
        'render_p95_100ms_pass': all(summary[k]['render_wall_ms']['p95'] <= 100 for k in summary)}


def activity(content: ContentTree, width: int, height: int, tier: str, what: str, seconds: float) -> dict[str, Any]:
    zone = 'sodium-row' if what == 'walking where there is no scene' else 'sodium-tin-halo'
    caller = Caller(content, width, height, tier, zone)
    if what == 'menus, text and help':
        caller.key('?', 1.0)
    keys = KEYS.get(what, [])
    samples = []
    started = last_step = time.monotonic()
    ticks = index = 0
    while time.monotonic()-started < seconds:
        now = time.monotonic()
        caller.tick(now)
        if now-last_step >= (.2 if keys else 20.0):
            last_step = now
            if keys:
                caller.key(keys[index % len(keys)], now)
                index += 1
            elif what == 'standing, a few stops a minute':
                caller.key('up', now)
        frame = caller.draw(now)
        if frame:
            samples.append(frame)
        ticks += 1
        time.sleep(.1)  # Same real-time schedule as V1, outside the CPU meter.
    elapsed = time.monotonic()-started
    return {'zone': zone, 'view': 'shipped map or local help', 'elapsed_s': elapsed,
        'ticks': ticks, 'key_steps': index, 'successful_moves': caller.moves,
        'cpu_s': caller.meter.cpu_ns/1e9, 'cpu_s_per_minute': caller.meter.cpu_ns/1e9/elapsed*60,
        'calls': dict(caller.meter.calls), 'output_frames': len(samples),
        'output_bytes': sum(frame['bytes'] for frame in samples)}


def hourly(activities: dict[str, dict[str, Any]]) -> float:
    return sum(activities[what]['cpu_s_per_minute']*minutes for what, minutes in MIX.items())
