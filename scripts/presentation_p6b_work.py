"""Count generic terrain work with only origin policy changed (B2).

Deterministic write counts, not local CPU or wall-time reference numbers.
The original P5 pose and the central B2 lanes are deliberately separate.
"""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT), str(ROOT/'scripts')]

from blacksite.content.loader import ContentTree, load_content
from blacksite.door.cells import CellBuffer
from blacksite.door.present import zone
from presentation_p6b import ORIGIN_BASE, ZONES, route
from presentation_p6_validation import module
from tests.presentation import budget


def measure(content: ContentTree, zid: str, tier: str, start: tuple[int, int],
            origin: Callable[..., tuple[int, int]]) -> dict[str, Any]:
    writes = 0
    active = False
    counts: list[int] = []
    callers: list[budget.Caller] = []
    original_put, original_terrain = CellBuffer.put, zone.terrain
    original_caller = budget.Caller

    def put(buffer: CellBuffer, *args: Any, **kwargs: Any) -> Any:
        nonlocal writes
        if active:
            writes += 1
        return original_put(buffer, *args, **kwargs)

    def terrain(*args: Any, **kwargs: Any) -> None:
        nonlocal active
        before = writes
        active = True
        try:
            original_terrain(*args, **kwargs)
        finally:
            active = False
            counts.append(writes-before)

    class Caller(original_caller):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            nonlocal writes
            super().__init__(*args, **kwargs)
            callers.append(self)
            counts.clear()
            writes = 0  # Exclude entry/handshake; frames() retains Ctrl-L.

    with patch.object(CellBuffer, 'put', put), patch.object(zone, 'terrain', terrain), \
            patch.object(zone, 'origin', origin), patch.object(budget, 'Caller', Caller):
        sample = budget.frames(content, 132, 50, tier, presentation=True,
                               fully_known=True, zone=zid, start=start)
    return {'terrain_put_calls': sum(counts), 'terrain_draws': len(counts),
            'writes_per_draw': budget.stats(counts), 'successful_moves': sample['successful_moves'],
            'end_position': callers[0].avatar.actor.position,
            'viewport': callers[0].avatar.perception.viewport}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route', choices=('b2', 'p5', 'both'), default='both')
    parser.add_argument('--tier', choices=('16', '256', 'truecolor'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('preserve evidence; choose a new output path')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', 'src/blacksite',
                       'tests/presentation/budget.py'], cwd=ROOT).returncode:
        parser.error('tracked runtime and P1 harness must match HEAD')
    content = deepcopy(load_content(ROOT/'src/blacksite/content'))
    content.looks.clear()
    content.themes = None
    old = module('_b2_generic_old_origin', subprocess.check_output(
        ['git', 'show', f'{ORIGIN_BASE}:src/blacksite/door/present/zone.py'], cwd=ROOT)).origin
    current = zone.origin
    cases = []
    for zid in ZONES:
        poses = [('b2_lane', route(content, zid))] if args.route != 'p5' else []
        if zid == 'sodium-row' and args.route != 'b2':
            poses.append(('p5_default', (12, 11)))  # P1 Caller, consumed by P5.
        for pose, start in poses:
            for tier in ((args.tier,) if args.tier else ('16', '256', 'truecolor')):
                arms = {label: measure(content, zid, tier, start, origin) for label, origin in
                        (('old_origin', old), ('a7_origin', current))}
                keys = ('successful_moves', 'end_position', 'viewport', 'terrain_draws')
                if not all(arms['old_origin'][key] == arms['a7_origin'][key] for key in keys):
                    raise AssertionError(f'{zid}/{pose}/{tier}: work fixtures must match')
                cases.append({'zone': zid, 'pose': pose, 'start': start, 'size': [132, 50],
                              'tier': tier, 'fully_known': True, 'arms': arms})
    report = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_tree': subprocess.check_output(['git', 'rev-parse', 'HEAD:src/blacksite'], cwd=ROOT, text=True).strip(),
        'probe_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'local_cpu_or_timing_reference': False,
        'method': 'P1 frames: 80 ticks/40 keys, live seeded NPCs, fully known; generic content as B2; '
                  'only origin replaced; count CellBuffer.put only inside zone.terrain; '
                  'entry excluded, Ctrl-L retained; distinguish central B2 and original P5 poses',
        'scope': 'Generic whole-field versus clipped-field work only; not an attribution '
                 'of the entire historical P5 hourly CPU mixture', 'cases': cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
