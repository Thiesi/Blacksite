"""B2 cold/warm render breakdown; separate from the unchanged hourly meter.

Headless diagnostic only. This does not produce native acceptance captures.
"""

import argparse
from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter_ns
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT), str(ROOT/'scripts')]

from blacksite.content.loader import ContentTree, load_content
from blacksite.door.cells import CellBuffer, cell_width
from blacksite.door.present import zone
from blacksite.door.present.places import Places
from presentation_p6b import ZONES, route
from tests.presentation.budget import Caller, KEYS, stats


def emitted_cells(current: CellBuffer, previous: CellBuffer | None) -> int:
    """Count emitted display columns, including wide glyphs, after timing.

    Match diff's glyph-head, equality, size and reserved-corner rules. ANSI
    cursor/style bytes emit no cells. Continuation cells are counted by
    their glyph's width, rather than counted again as empty glyphs.
    """
    if previous is not None and (previous.width, previous.height) != (current.width, current.height):
        previous = None
    return sum(cell_width(cell.glyph[0])
               for y, row in enumerate(current.cells)
               for x, cell in enumerate(row[:current.width-(y == current.height-1)])
               if cell.glyph and (previous is None or cell != previous.cells[y][x]))


class ProfileCaller(Caller):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.samples: list[dict[str, Any]] = []
        self.phase = 'entry'
        self.sample_key: str | None = None
        super().__init__(*args, **kwargs)

    def draw(self, now: float) -> dict[str, Any] | None:
        terrain_ns = terrain_cells = 0
        diff_ns = diff_bytes = 0
        buffers: list[tuple[CellBuffer, CellBuffer | None]] = []
        original_terrain, original_cell, original_diff = zone.terrain, Places.cell, CellBuffer.diff

        def terrain(*args: Any, **kwargs: Any) -> None:
            nonlocal terrain_ns
            started = perf_counter_ns()
            original_terrain(*args, **kwargs)
            terrain_ns += perf_counter_ns()-started

        def cell(saved: Places, *args: Any, **kwargs: Any) -> Any:
            nonlocal terrain_cells
            terrain_cells += 1
            return original_cell(saved, *args, **kwargs)

        def diff(current: CellBuffer, previous: CellBuffer | None) -> bytes:
            nonlocal diff_ns, diff_bytes
            started = perf_counter_ns()
            data = original_diff(current, previous)
            diff_ns += perf_counter_ns()-started
            diff_bytes += len(data)
            buffers.append((current, previous))
            return data

        saved = getattr(self.display.paint, 'place_cache', None)
        with patch.object(zone, 'terrain', terrain), patch.object(Places, 'cell', cell), \
                patch.object(CellBuffer, 'diff', diff):
            frame = super().draw(now)
        # This full-buffer count runs OUTSIDE render's timer. Do not use
        # this instrumented Caller's Meter for an hourly CPU verdict.
        emitted = sum(emitted_cells(current, previous) for current, previous in buffers)
        wall_ms = frame['render_wall_ms'] if frame else None
        self.samples.append({'phase': self.phase, 'key': self.sample_key,
            'position': list(self.avatar.actor.position),
            'viewport': dict(self.display.body.get('viewport', {})), 'frame': frame,
            'terrain_wall_ms': terrain_ns/1e6, 'terrain_cells': terrain_cells,
            'terrain_frame_percent': 100*terrain_ns/1e6/wall_ms if wall_ms else None,
            'diff_wall_ms': diff_ns/1e6, 'diff_bytes': diff_bytes, 'emitted_cells': emitted,
            'places_replaced': saved is not getattr(self.display.paint, 'place_cache', None)})
        return frame


def profile(content: ContentTree, zid: str, tier: str, known: bool, *,
            caller_factory: Callable[..., ProfileCaller] = ProfileCaller) -> dict[str, Any]:
    start = route(content, zid)
    caller = caller_factory(content, 132, 50, tier, zid, presentation=True,
                            fully_known=known, start=start)
    keys = KEYS['walking where there is no scene']
    now = 1.0
    phases = []
    for phase in ('cold', 'warm'):
        caller.phase = phase
        initial = {'position': list(caller.avatar.actor.position),
                   'viewport': dict(caller.display.body['viewport'])}
        before_moves = caller.moves
        for key in keys:
            # P1 frames() order/cadence: key, server tick, update/render,
            # then another tick without input. One closed eight-tile walk.
            caller.sample_key = key
            now += .101
            caller.key(key, now)
            caller.tick(now)
            caller.draw(now)
            caller.sample_key = None
            now += .101
            caller.tick(now)
            caller.draw(now)
        final = {'position': list(caller.avatar.actor.position),
                 'viewport': dict(caller.display.body['viewport'])}
        if caller.moves-before_moves != len(keys) or initial != final:
            raise AssertionError(f'{zid}/{tier}/{phase}: walk must move every key and return to same viewport')
        samples = [s for s in caller.samples if s['phase'] == phase]
        steps = [s for s in samples if s['key'] is not None]
        phases.append({'phase': phase, 'initial': initial, 'final': final,
            'successful_moves': caller.moves-before_moves,
            'steps': {field: stats([s[field] for s in steps if s[field] is not None])
                      for field in ('terrain_wall_ms', 'terrain_frame_percent', 'terrain_cells',
                                    'diff_wall_ms', 'diff_bytes', 'emitted_cells')},
            'places_replacements': sum(s['places_replaced'] for s in samples)})
    return {'zone': zid, 'start': start, 'size': [132, 50], 'tier': tier,
            'fully_known': known, 'phases': phases, 'samples': caller.samples}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zone', choices=ZONES, required=True)
    parser.add_argument('--tier', choices=('16', '256', 'truecolor'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('preserve evidence; choose a new output path')
    result: dict[str, Any] = {'schema': 1,
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_tree': subprocess.check_output(['git', 'rev-parse', 'HEAD:src/blacksite'], cwd=ROOT, text=True).strip(),
        'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip()),
        'created_utc': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(),
        'python': sys.version, 'method': 'P1 Caller/frames order; 10-Hz ticks, 5-Hz keys; '
            'cold right*8/left*8, then warm repeat, same caller/viewport; entry separate; '
            'ordinary and fully-known headless fixtures; shipped NPCs retained',
        'boundary': 'instrumented zone.terrain and CellBuffer.diff; column count outside render timer; '
            'terrain includes Places.cell counter overhead; no hourly CPU or budget acceptance',
        'warm_policy': 'retain caches and knowledge; do not force a cache hit or hide invalidations',
        'cases': [], 'complete': False}
    result['linux_timing_reference'] = platform.system() == 'Linux' and not result['dirty']
    content = load_content(ROOT/'src/blacksite/content')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for tier in ((args.tier,) if args.tier else ('16', '256', 'truecolor')):
            for known in (False, True):
                result['cases'].append(profile(content, args.zone, tier, known))
        result['complete'] = True
    except Exception as exc:
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
