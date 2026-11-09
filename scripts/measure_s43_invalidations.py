"""S43 step 1: count cache work without editing or timing runtime code.

Fresh paired runs must have identical encoded frames and bodies. The
observer is test-only; counts are not S11 timings or acceptance credit.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from types import FrameType
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]

from karst41.content.loader import load_content
from karst41.server.protocol import Frame, encode
from karst41.server.views import looks, zone_view
from karst41.server.world import sight
from karst41.server.world.actors import Actor
from karst41.server.world.zone import ZoneInstance
from tests.character_helpers import create, place
from tests.harness import HeadlessServer


def sight_changes(old: tuple[Any, ...] | None, new: tuple[Any, ...]) -> str:
    if old is None:
        return 'cold_or_explicit_clear'
    return '+'.join(name for index, name in enumerate(('zone', 'origin', 'radius', 'geometry'))
                    if old[index] != new[index]) or 'unchanged'


class Observer:
    def __init__(self, game: HeadlessServer) -> None:
        self.game = game
        self.rows: dict[str, Counter[str]] = defaultdict(Counter)
        self.pending: dict[int, Any] = {}
        self.perception_zones = {id(a.perception): a.zone for a in game.core.characters.sim.avatars.values()}
        self.tick = 0
        self.events: dict[int, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))

    def count(self, zone: str, kind: str, amount: int = 1) -> None:
        self.rows[zone][kind] += amount
        self.events[self.tick][zone][kind] += amount

    def write(self, obj: Any, name: str, old: Any, new: Any, caller: str) -> None:
        if isinstance(obj, ZoneInstance) and name in ('revision', 'geometry_revision') and old != new:
            self.count(obj.id, name+':'+caller)
        elif isinstance(obj, Actor) and name == 'sight_key' and new is None:
            self.count(obj.zone or '<unplaced>', ('sight_clear:' if old is not None else 'redundant_sight_clear:')+caller)
        elif isinstance(obj, zone_view.Perception) and name == 'grid_key' and new is None and old is not None:
            self.count(self.perception_zones.get(id(obj), '<unknown>'), 'grid_clear:'+caller)

    def profile(self, frame: FrameType, event: str, arg: Any) -> None:
        code = frame.f_code
        if event == 'call':
            values = frame.f_locals
            if code is sight.visible_tiles.__code__:
                actor, zone, radius = (values[k] for k in ('actor', 'zone', 'radius'))
                expected = (zone.id, actor.position, radius, zone.geometry_revision)
                caller = frame.f_back.f_code.co_qualname
                self.count(zone.id, 'sight_query:'+actor.kind)
                self.count(zone.id, 'sight_consumer:'+caller)
                miss = actor.sight_key != expected
                self.count(zone.id, ('sight_rebuild:' if miss else 'sight_hit:')+actor.kind)
                if miss:
                    self.count(zone.id, 'sight_reason:'+sight_changes(actor.sight_key, expected))
            elif code is sight.line_of_sight.__code__:
                caller = frame.f_back.f_code.co_qualname
                self.count(values['zone'].id, 'line_of_sight:'+('visible_tiles' if 'visible_tiles' in caller else caller))
            elif code is zone_view.build.__code__:
                perception, actor = values['perception'], values['actor']
                self.perception_zones[id(perception)] = actor.zone
                self.pending[id(frame)] = perception.grid_revision, perception.grid_key
                self.count(actor.zone, 'grid_query')
            elif code is looks.masked.__code__:
                self.count(values['zone'].id, 'looks_rebuild')
        elif event == 'return' and code is zone_view.build.__code__:
            previous_revision, previous_key = self.pending.pop(id(frame))
            p, zone = frame.f_locals['perception'], frame.f_locals['zone']
            changed = p.grid_revision != previous_revision
            self.count(zone.id, 'grid_rebuild' if changed else 'grid_hit')
            if changed:
                if previous_key is None:
                    reason = 'cold_or_explicit_clear'
                else:
                    parts = []
                    if previous_key[0] != p.grid_key[0]:
                        parts.append('sight_'+sight_changes(previous_key[0], p.grid_key[0]))
                    if previous_key[1] != p.grid_key[1]:
                        parts.append('viewport')
                    if previous_key[2] != p.grid_key[2]:
                        parts.append('scouted')
                    reason = '+'.join(parts)
                    assert reason, 'Unattributed grid rebuild'
                self.count(zone.id, 'grid_reason:'+reason)

    def __enter__(self) -> Observer:
        self.stack = ExitStack()
        for cls in (Actor, ZoneInstance, zone_view.Perception):
            original = cls.__setattr__

            def write(obj: Any, name: str, value: Any, original: Any = original) -> None:
                old = obj.__dict__.get(name)
                original(obj, name, value)
                self.write(obj, name, old, value, sys._getframe(1).f_code.co_qualname)

            self.stack.enter_context(patch.object(cls, '__setattr__', write))
        self.previous_profile = sys.getprofile()
        sys.setprofile(self.profile)
        return self

    def __exit__(self, *exc: Any) -> None:
        sys.setprofile(self.previous_profile)
        self.stack.close()


def fixture(zone_id: str, width: int = 132, height: int = 50) -> tuple[Any, Any, Any]:
    content = load_content(ROOT/'src/karst41/content')
    game = HeadlessServer(content, character_state={})
    client = game.connect({'user_id': 1, 'handle': 'Measure\u754c', 'node_name': 'fixture'}, width=width, height=height)
    create(game, client, archetype=0, name='Measure', card='none')
    zone = game.core.world.zones[zone_id]
    actor = game.core.characters.sim.avatars[client.session.user_id].actor
    target = (16, 5) if zone_id == 'sodium-row' else zone.template.meta.spawn
    place(game, client, zone_id, game.core.world.free_tile(zone_id, target, actor))
    for instance in game.core.world.zones.values():
        instance.activate('s43-count-only', game.clock.now_tick())
    return game, client, actor


def execute(zone_id: str, mode: str, ticks: int, observed: bool) -> dict[str, Any]:
    game, client, actor = fixture(zone_id)
    session = client.session

    def drain() -> bytes:
        frames = b''.join(encode(frame) for frame in game.frames_for(client))
        session.acknowledge(session.view_revision)
        return frames

    drain()
    for _ in range(10):
        game.step()
        drain()
    frames_digest, bodies_digest = sha256(), sha256()
    observer = Observer(game)
    moves, inputs = 0, 0
    trace = []
    with observer if observed else ExitStack():
        for index in range(ticks):
            observer.tick = game.clock.now_tick()+1
            before = actor.position
            if mode == 'walk' and index % 2 == 0:
                client.send(Frame('key', {'k': 'right' if index % 4 == 0 else 'left', 't': 0}))
                inputs += 1
            game.step()
            moves += before != actor.position
            frames_digest.update(drain())
            body = game.core.characters.sim.views[session.id].previous['body']
            bodies_digest.update(encode(Frame('view', {'rev': session.view_revision, 'kind': 'zone', 'body': body})))
            trace.append({'tick': game.clock.now_tick(), 'position': list(actor.position), 'hp': actor.health})
    assert not session.closed, 'Counting fixture must remain connected'
    return dict(zone=zone_id, mode=mode, ticks=ticks, inputs=inputs, successful_moves=moves,
                frame_sha256=frames_digest.hexdigest(), body_sha256=bodies_digest.hexdigest(),
                actor_trace_sha256=sha256(json.dumps(trace).encode()).hexdigest(),
                counts={zone: dict(sorted(observer.rows[zone].items())) for zone in sorted(game.core.world.zones)},
                tick_counts={str(t): {z: dict(c) for z, c in sorted(zones.items())}
                             for t, zones in sorted(observer.events.items())})


def measure(ticks: int, zones: list[str]) -> dict[str, Any]:
    cases = []
    for zone in zones:
        for mode in ('idle', 'walk'):
            reference = execute(zone, mode, ticks, False)
            observed = execute(zone, mode, ticks, True)
            for key in ('frame_sha256', 'body_sha256', 'actor_trace_sha256', 'inputs', 'successful_moves'):
                assert observed[key] == reference[key], (zone, mode, key, reference[key], observed[key])
            cases.append(observed)
            print(json.dumps({'zone': zone, 'mode': mode, 'byte_identical_observer_control': True,
                              'moves': observed['successful_moves'], 'viewer_counts': observed['counts'][zone]}), flush=True)
    return dict(head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                runtime_tree=subprocess.check_output(['git', 'rev-parse', 'HEAD:src/karst41'], cwd=ROOT, text=True).strip(),
                measurement='count only; manual clock, no wall timers, native S11, DB or acceptance credit',
                fixture='One caller; all ten hubs active; ten warmup ticks; 50 measured ticks by default; deterministic seeded NPCs',
                observer_control='All encoded frame/body bytes and actor traces match independently executed unobserved controls',
                cases=cases)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ticks', type=int, default=50)
    parser.add_argument('--zone', action='append')
    args = parser.parse_args()
    zones = args.zone or sorted(load_content(ROOT/'src/karst41/content').zones)
    report = measure(args.ticks, zones)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress((json.dumps(report, indent=2)+'\n').encode(), mtime=0))
