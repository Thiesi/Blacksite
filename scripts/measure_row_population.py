"""Issue 184: hosted P1 activity measurements; no shipped population change.

The unchanged budget.activity schedules the four published activities. A
group adapter steps one shared server and meters each ordinary Caller.
All population/placement changes below are declared in-memory fixtures.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import cProfile
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import platform
import pstats
import subprocess
import sys
import time
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]

from blacksite.content.loader import ContentTree, load_content
from blacksite.content.schema import Behaviour, Region
from blacksite.server.npcs.templates import make_actor
from blacksite.server.world.sight import line_of_sight
from tests.character_helpers import create
from tests.presentation import budget
from tests.scratch_guard import scratch_problem, temp_problem

ZONE = 'sodium-row'
STARTS = ((46, 14), (46, 15), (46, 16), (46, 17))
MOVING_REGION = Region(45, 8, 11, 5)
EXTRA_TEMPLATE = 'measurement-row-extra'
STATIONARY = (0, 20, 40, 80)
MOVING = (4, 8, 12)
TIERS = ('16', '256', 'truecolor')


def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def fixture_content(content: ContentTree, moving: int) -> ContentTree:
    """Same two posts/warden; ordinary wanderers in a declared visible region."""
    tree = deepcopy(content)
    zone = tree.zones[ZONE]
    tree.zones[ZONE] = replace(zone, meta=replace(zone.meta, spawners=tuple(
        replace(sp, count=moving, region=MOVING_REGION) if sp.id == 'sodium-regular'
        else sp for sp in zone.meta.spawners)))
    tree.npcs[EXTRA_TEMPLATE] = replace(tree.npcs['npc-sodium-regular'],
        id=EXTRA_TEMPLATE, name='Measurement extra',
        behaviours=(Behaviour('talker', {'anchor': True}),))
    return tree


def stationary_tiles(group: Group) -> list[tuple[int, int]]:
    """One nested layout across all counts/callers, visible along every route."""
    zone = group.game.core.world.zones[ZONE]
    routes = {(x + step, y) for x, y in STARTS for step in range(9)}
    reserved = group.game.core.npcs.spawners.reserved(zone)
    fixed = [sp.region for sp in zone.template.meta.spawners
             if sp.id != 'sodium-regular' and sp.region]
    # All routes share the shipped radius 13. No knowledge/sight rule is changed.
    assert zone.template.meta.sight_radius == 13
    candidates = []
    for y in range(zone.template.height):
        for x in range(zone.template.width):
            tile = (x, y)
            if (tile in routes or tile in reserved or MOVING_REGION.contains(tile)
                    or any(region.contains(tile) for region in fixed)
                    or not zone.can_enter(None, tile)
                    or zone.tiles[zone.tile_id(tile)].hazard):
                continue
            if all((x-a)**2 + (y-b)**2 <= 13**2 and line_of_sight(zone, (a, b), tile)
                   for a, b in routes):
                candidates.append(tile)
    # Interleave the visible bar-3 frontage with street tiles, then spread
    # deterministically. Smaller fixtures are prefixes of the same layout.
    key = lambda tile: sha256(f'row184:{tile}'.encode()).digest()
    bars = sorted((p for p in candidates if p[1] <= 8), key=key)
    street = sorted((p for p in candidates if p[1] > 8), key=key)
    ordered = []
    for index in range(max(len(bars), len(street))):
        if index < len(bars):
            ordered.append(bars[index])
        if index < len(street):
            ordered.append(street[index])
    assert len(ordered) >= 80, f'not enough legal visible fixture tiles: {len(ordered)}'
    return ordered


class Group:
    """budget.activity's caller interface, with one shared authoritative tick."""

    def __init__(self, content: ContentTree, stationary: int, moving: int,
                 callers: int, tier: str, known: bool = False) -> None:
        if stationary not in STATIONARY or moving not in MOVING or callers not in (1, 4):
            raise ValueError('choose a declared population/caller grid cell')
        self.callers: list[budget.Caller] = []
        self.frames: list[list[dict[str, Any]]] = [[] for _ in range(callers)]
        self.server = budget.Meter()
        self.tick_cpu_ms: list[float] = []
        self.moving_changes: Counter[str] = Counter()
        self.stationary = stationary
        self.moving = moving
        self.known = known
        tree = fixture_content(content, moving)
        original = budget.character_game

        def shared_game(source: ContentTree, width: int, height: int, **kwargs: Any) -> Any:
            if not self.callers:
                return original(source, width, height, **kwargs)
            game = self.callers[0].game
            uid = len(self.callers) + 1
            client = game.connect({'user_id': uid, 'handle': f'Observer{uid}\u754c',
                                   'node_name': 'row184'}, width=width, height=height)
            create(game, client, archetype=0, name=f'Observer{uid}\u754c', card='none')
            return game, client

        with patch.object(budget, 'character_game', shared_game):
            for start in STARTS[:callers]:
                self.callers.append(budget.Caller(tree, 132, 50, tier, ZONE,
                    presentation=True, fully_known=known, start=start))
        self.game = self.callers[0].game
        zone = self.game.core.world.zones[ZONE]
        tiles = stationary_tiles(self)
        template = self.game.core.loop.content.npcs[EXTRA_TEMPLATE]
        for index, tile in enumerate(tiles[:stationary]):
            actor = make_actor(template, f'row184:extra:{index:03}', {
                'home': tile, 'phase': index % 5, 'spawner': 'row184-stationary'})
            self.game.core.world.enter(actor, ZONE, tile)
        self.fixed_positions = {a.id: a.position for a in zone.actors.values()
                                if a.behaviour.get('template') == EXTRA_TEMPLATE}
        self.game.step(2)
        self.game.commit_commerce()
        for caller in self.callers:
            caller.drain(0)
            caller.display.prompt = caller.display.key_prompt = None
            caller.draw(0)
            caller.meter = budget.Meter()
            caller.moves = 0
        self.initial = self.receipt()
        self.check()

    @property
    def display(self) -> Any:
        return self.callers[0].display

    @property
    def meter(self) -> budget.Meter:
        total = budget.Meter()
        for caller in self.callers:
            total.cpu_ns += caller.meter.cpu_ns
            total.wall_ns += caller.meter.wall_ns
            total.calls.update(caller.meter.calls)
        return total

    @property
    def moves(self) -> int:
        return min(c.moves for c in self.callers)

    def key(self, key: str, now: float) -> None:
        for caller in self.callers:
            caller.key(key, now)

    def check(self) -> None:
        zone = self.game.core.world.zones[ZONE]
        actors = list(zone.actors.values())
        assert sum(a.kind == 'player' for a in actors) == len(self.callers)
        assert sum(a.behaviour.get('spawner') == 'sodium-regular' for a in actors) == self.moving
        assert sum(a.behaviour.get('spawner') == 'sable-enforcer' for a in actors) == 2
        assert sum(a.behaviour.get('spawner') == 'plainclothes-warden' for a in actors) == 1
        assert sum(a.behaviour.get('template') == EXTRA_TEMPLATE for a in actors) == self.stationary
        for aid, tile in self.fixed_positions.items():
            assert zone.actors[aid].position == tile, f'stationary extra moved: {aid}'
        required = set(self.fixed_positions) | {
            a.id for a in actors if a.behaviour.get('spawner') == 'sodium-regular'}
        for caller in self.callers:
            shown = {a['id'] for a in caller.display.body.get('actors', [])}
            assert required <= shown, f'fixture actors missing from caller view: {required-shown}'

    def tick(self, now: float) -> None:
        zone = self.game.core.world.zones[ZONE]
        positions = {a.id: a.position for a in zone.actors.values()}
        before = self.server.cpu_ns
        self.server.call('step', self.game.step)
        self.tick_cpu_ms.append((self.server.cpu_ns-before)/1e6)
        self.game.commit_commerce()  # Memory receipt handling stays outside P1 and tick meters.
        for actor in zone.actors.values():
            if actor.behaviour.get('spawner') == 'sodium-regular' and positions.get(actor.id) != actor.position:
                self.moving_changes[actor.id] += 1
        for caller in self.callers:
            caller.moves += positions[caller.avatar.actor.id] != caller.avatar.actor.position
            caller.drain(now)
        self.check()

    def draw(self, now: float) -> dict[str, Any] | None:
        frames = []
        for index, caller in enumerate(self.callers):
            frame = caller.draw(now)
            if frame:
                self.frames[index].append(frame)
                frames.append(frame)
        if not frames:
            return None
        return {'bytes': sum(f['bytes'] for f in frames)}

    def receipt(self) -> dict[str, Any]:
        return {'callers': [{'id': c.avatar.actor.id, 'position': c.avatar.actor.position,
            'view': budget.view_counts(c.display.body),
            'visible_actor_ids': [a['id'] for a in c.display.body.get('actors', [])]}
            for c in self.callers], 'extra_positions': self.fixed_positions,
            'moving_changes': dict(self.moving_changes), 'zone_tick': self.game.clock.now_tick()}


def activity(content: ContentTree, stationary: int, moving: int, callers: int,
             tier: str, what: str, known: bool = False) -> dict[str, Any]:
    group = Group(content, stationary, moving, callers, tier, known)
    # Reuse P1's actual scheduler/mix rather than copying its timing loop.
    with patch.object(budget, 'Caller', lambda *args, **kwargs: group):
        result = budget.activity(content, 132, 50, tier, what, 12., presentation=True,
                                 fully_known=known, zone=ZONE, start=STARTS[0])
    elapsed = result['elapsed_s']
    assert all(c.moves == result['key_steps'] for c in group.callers)
    result['per_caller'] = [{'cpu_s_per_minute': c.meter.cpu_ns/1e9/elapsed*60,
        'cpu_s': c.meter.cpu_ns/1e9, 'calls': dict(c.meter.calls), 'moves': c.moves,
        'output_frames': len(group.frames[index]),
        'output_bytes': sum(f['bytes'] for f in group.frames[index])}
        for index, c in enumerate(group.callers)]
    result['server_cpu_s_per_minute'] = group.server.cpu_ns/1e9/elapsed*60
    result['server_tick_cpu_ms'] = budget.stats(group.tick_cpu_ms)
    result['server_tick_cpu_ms_samples'] = group.tick_cpu_ms
    result['initial_fixture'] = group.initial
    result['final_fixture'] = group.receipt()
    result['moving_position_changes'] = sum(group.moving_changes.values())
    assert result['moving_position_changes'] > 0, 'wandering fixture must actually move'
    return result


def profile(content: ContentTree, stationary: int, moving: int,
            callers: int, tier: str) -> dict[str, Any]:
    """Separate untimed diagnostic: 200 shared server ticks, not CPU acceptance."""
    group = Group(content, stationary, moving, callers, tier)
    profiler = cProfile.Profile(timer=time.process_time)
    for tick in range(200):
        profiler.runcall(group.game.step)
        group.game.commit_commerce()
        for caller in group.callers:
            caller.drain(1.0 + tick*.101)
            caller.draw(1.0 + tick*.101)
    group.check()
    rows = []
    stats = pstats.Stats(profiler)
    for (filename, line, function), (primitive, calls, own, cumulative, _) in stats.stats.items():
        if 'blacksite' in filename or filename.endswith('harness.py'):
            rows.append({'file': filename.replace(str(ROOT), '.'), 'line': line,
                'function': function, 'calls': calls, 'primitive_calls': primitive,
                'own_s': own, 'cumulative_s': cumulative})
    return {'stationary': stationary, 'moving': moving, 'callers': callers,
        'ticks': 200, 'acceptance_credit': False, 'scope': 'shared game.step only',
        'timer': 'process_time; separately profiled standing callers, not the P1 mix',
        'total_profile_cpu_s': stats.total_tt,
        'functions': sorted(rows, key=lambda r: -r['cumulative_s'])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--callers', type=int, choices=(1, 4), required=True)
    parser.add_argument('--tier', choices=TIERS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--known-corners', action='store_true')
    parser.add_argument('--profiles', action='store_true')
    args = parser.parse_args()
    problem = scratch_problem(ROOT) or temp_problem()
    if problem:
        parser.error(problem)
    if args.output.exists():
        parser.error('remove the previous fixed-path report before starting a new run')
    content = load_content(ROOT/'src/blacksite/content')
    assert not content.load_problems
    dirty = bool(git('status', '--porcelain'))
    result: dict[str, Any] = {'schema': 1, 'head': git('rev-parse', 'HEAD'),
        'runtime_tree': git('rev-parse', 'HEAD:src'), 'dirty': dirty,
        'content_tree': git('rev-parse', 'HEAD:src/blacksite/content'),
        'platform': platform.platform(), 'python': sys.version, 'seconds': 12.,
        'cpu_budget_reference': platform.system() == 'Linux' and not dirty,
        'minutes': budget.MIX, 'size': [132, 50], 'tier': args.tier,
        'callers': args.callers, 'cases': [], 'profiles': [],
        'method': 'unchanged budget.activity/Meter/MIX; shared 10Hz server; 5Hz walking',
        'server_scope': 'HeadlessServer.step including simulation and per-session views; excludes receipt commits/I/O',
        'fixture': 'anchored talker copies; visible street/bar-3 frontage; wander region45,8,11,5; four separate horizontal lanes; two Sable posts and warden unchanged',
        'source_sha256': {p: sha256((ROOT/p).read_bytes()).hexdigest() for p in (
            'tests/presentation/budget.py', 'scripts/measure_row_population.py')},
        'complete': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def retain() -> None:
        args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')

    try:
        for known in (False, True) if args.known_corners else (False,):
            for stationary in STATIONARY:
                for moving in MOVING:
                    if known and (stationary not in (0, 80) or moving not in (4, 12)):
                        continue
                    row: dict[str, Any] = {'stationary': stationary, 'moving': moving,
                        'fully_known': known, 'activities': {}}
                    result['cases'].append(row)
                    for what in budget.MIX:
                        row['activities'][what] = activity(content, stationary, moving,
                            args.callers, args.tier, what, known)
                        retain()
                    row['door_total_cpu_s_per_hour'] = budget.hourly(row['activities'])
                    row['door_per_caller_cpu_s_per_hour'] = [sum(
                        row['activities'][what]['per_caller'][index]['cpu_s_per_minute']*minutes
                        for what, minutes in budget.MIX.items()) for index in range(args.callers)]
                    row['door_mean_cpu_s_per_hour'] = row['door_total_cpu_s_per_hour']/args.callers
                    row['door_max_cpu_s_per_hour'] = max(row['door_per_caller_cpu_s_per_hour'])
                    row['within_108'] = row['door_max_cpu_s_per_hour'] <= 108
                    row['server_cpu_s_per_hour'] = sum(
                        row['activities'][what]['server_cpu_s_per_minute']*minutes
                        for what, minutes in budget.MIX.items())
                    retain()
                    print(json.dumps({k: row[k] for k in ('stationary', 'moving', 'fully_known',
                        'door_mean_cpu_s_per_hour', 'door_max_cpu_s_per_hour',
                        'within_108', 'server_cpu_s_per_hour')}), flush=True)
        if args.profiles:
            for stationary, moving in ((0, 4), (80, 4), (0, 12), (80, 12)):
                result['profiles'].append(profile(content, stationary, moving, args.callers, args.tier))
                retain()
        result['complete'] = True
    except Exception as exc:
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        retain()


if __name__ == '__main__':
    main()
