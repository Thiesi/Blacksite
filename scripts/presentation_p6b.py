"""B2 shipped-zone budgets, with the unchanged P1 meter and P6 arms.

The headless pose/knowledge fixtures here are not native walk evidence.
Only a clean Linux run at 12 seconds per activity is a CPU reference.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT), str(ROOT/'scripts')]

from blacksite.content.loader import ContentTree, load_content
from blacksite.door.present import zone
from presentation_p6 import wire_walk
from presentation_p6_validation import module
from tests.presentation.budget import MIX, activity, frames, hourly

ZONES = ('core-plaza', 'vatside-clinics', 'sodium-row')
REFERENCE = ROOT/'tests/presentation/p6b-p5-reference.json'
ORIGIN_BASE = 'fd4020e7eaa413301145eca969333f2239a6cfcf'


def origin_control(content: ContentTree, zid: str, start: tuple[int, int],
                   size: tuple[int, int], tier: str, seconds: float,
                   current: dict[str, Any]) -> dict[str, Any]:
    """Isolate origin policy on identical shipped data, not historical P5.

    Only the old origin function is substituted. Both arms use the P1
    activity/meter unchanged, with the same NPCs, knowledge and seeds.
    This isolates the combined clipping/caching policy; it does not
    separately attribute those two effects or explain every P5 change.
    """
    source = subprocess.check_output(
        ['git', 'show', f'{ORIGIN_BASE}:src/blacksite/door/present/zone.py'], cwd=ROOT)
    old = module('_b2_origin_control', source).origin
    with patch.object(zone, 'origin', old):
        activities = {what: activity(content, *size, tier, what, seconds,
                                    presentation=True, fully_known=True,
                                    zone=zid, start=start) for what in MIX}
    keys = ('initial_view', 'final_view', 'successful_moves', 'ticks', 'key_steps')
    matched = all(activities[what][key] == current['activities'][what][key]
                  for what in MIX for key in keys)
    before, after = hourly(activities), current['cpu_s_per_hour']
    return {'baseline_origin_ref': ORIGIN_BASE, 'only_origin_replaced': True,
            'matched_workloads': matched, 'baseline_activities': activities,
            'old_moving_clipped_cpu_s_per_hour': before,
            'a7_still_whole_cpu_s_per_hour': after,
            'a7_minus_old_s_per_hour': after-before,
            'causal_boundary': 'origin policy only; combined clipping and cache geometry effects; '
                               'historical P5 has different content and is not this control'}


def route(content: ContentTree, zid: str) -> tuple[int, int]:
    """Pick and disclose nine public floor cells; never remove live traffic."""
    zone = content.zones[zid]
    reserved = {obj.tile for obj in zone.meta.objects} | {ex.tile for ex in zone.meta.exits}
    public = {tile for region in zone.meta.public for tile in region.tiles()}
    candidates = []
    for y in range(zone.height):
        for x in range(zone.width-8):
            tiles = [(x+dx, y) for dx in range(9)]
            if all(zone.tile_at(tile) == 'floor' and tile not in reserved and tile in public for tile in tiles):
                candidates.append((x, y))
    if not candidates:
        raise ValueError(f'{zid}: no public nine-cell floor route')
    # The Plaza centre's fountain frontage was blocked by live traffic in
    # the diagnostic. Use its southern public lane, keeping all NPCs live.
    target_y = 26 if zid == 'core-plaza' else zone.height//2
    return min(candidates, key=lambda p: (abs(p[0]+4-zone.width//2)+abs(p[1]-target_y), p))


def measure(content: ContentTree, bare: ContentTree, zid: str, start: tuple[int, int],
            size: tuple[int, int], tier: str, known: bool, seconds: float,
            reference: dict[str, Any]) -> dict[str, Any]:
    arms = {}
    for label, tree in (('generic', bare), ('looks', content)):
        activities = {what: activity(tree, *size, tier, what, seconds, presentation=True,
                                    fully_known=known, zone=zid, start=start) for what in MIX}
        sample = frames(tree, *size, tier, presentation=True, fully_known=known, zone=zid, start=start)
        arms[label] = {'activities': activities, 'cpu_s_per_hour': hourly(activities), 'frames': sample}
    for what in MIX:
        for field in ('initial_view', 'final_view', 'successful_moves'):
            assert arms['generic']['activities'][what][field] == arms['looks']['activities'][what][field]
    p5 = next(row['cpu_s_per_hour'] for row in reference['cases']
              if row['size'] == list(size) and row['tier'] == tier and row['fully_known'] == known)
    cpu = arms['looks']['cpu_s_per_hour']
    verdict = {'cpu_s_per_hour': cpu, 'cpu_120s_per_hour_pass': cpu <= 120,
               'p5_final_cpu_s_per_hour': p5, 'difference_from_p5_s_per_hour': cpu-p5,
               'difference_from_p5_percent': (cpu/p5-1)*100,
               'p5_regression_requires_explanation': cpu > p5,
               'cpu_at_or_above_108s_per_hour_finding': cpu >= .9*120,
               'paired_looks_cost_s_per_hour': cpu-arms['generic']['cpu_s_per_hour']}
    result = {'zone': zid, 'start': start, 'size': size, 'tier': tier, 'fully_known': known,
              'arms': arms, 'verdict': verdict, 'frame_budgets_pass': all(
                  arm['frames']['delta_16kib_pass'] and arm['frames']['render_p95_100ms_pass']
                  for arm in arms.values()),
              'wire': wire_walk(content, *size, tier, known, zone=zid, start=start)}
    if size == (132, 50) and known:
        result['origin_policy_control'] = origin_control(
            content, zid, start, size, tier, seconds, arms['looks'])
    print(json.dumps({k: result[k] for k in ('zone', 'start', 'size', 'tier', 'fully_known', 'verdict')}), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zone', choices=ZONES, required=True)
    parser.add_argument('--size', choices=('80x24', '132x50'))
    parser.add_argument('--tier', choices=('16', '256', 'truecolor'))
    parser.add_argument('--known', action='store_true', help='Diagnostic subset: fully known only')
    parser.add_argument('--seconds', type=float, default=12.)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 0 < args.seconds <= 600 or args.output.exists():
        parser.error('choose positive seconds <=600 and a new output path')
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip())
    content = load_content(ROOT/'src/blacksite/content')
    assert content.zones[args.zone].meta.charted and args.zone in content.looks
    bare = deepcopy(content)
    bare.looks.clear()
    bare.themes = None
    reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
    start = route(content, args.zone)
    sizes = (tuple(map(int, args.size.split('x'))),) if args.size else ((80, 24), (132, 50))
    cases = []
    result = {'schema': 1, 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'dirty': dirty, 'created_utc': datetime.now(timezone.utc).isoformat(),
              'platform': platform.platform(), 'python': sys.version,
              'cpu_budget_reference': platform.system() == 'Linux' and args.seconds == 12. and not dirty,
              'seconds': args.seconds, 'mix': 'v1-provisional', 'minutes': MIX,
              'cpu_boundary': 'unchanged P1 Meter: Display receive/key/update/render; server/codecs excluded',
              'tick_hz': 10, 'walking_key_hz': 5,
              'fixture': 'shipped geometry/objects/exits/spawners, zone-id seeds, 30 warm-up ticks; '
                         'disclosed headless start, all-terrain knowledge only for fully_known, both arms identical',
              'comparison': 'P6 generic/looks arms on each shipped zone; P5 final is a historical cross-run '
                            'reference with different zones/content, not an isolated cause measurement',
              'policy': 'Frame budgets asserted; CPU recorded with verdict, regressions require explanation/review',
              'p5_reference': {k: v for k, v in reference.items() if k != 'cases'}, 'cases': cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def retain() -> None:
        args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')

    for size in sizes:
        for tier in ((args.tier,) if args.tier else ('16', '256', 'truecolor')):
            for known in ((True,) if args.known else ((False, True) if size[0] == 132 else (False,))):
                try:
                    cases.append(measure(content, bare, args.zone, start, size, tier, known, args.seconds, reference))
                except Exception as exc:
                    result['incomplete_error'] = {'type': type(exc).__name__, 'message': str(exc),
                                                   'size': size, 'tier': tier, 'fully_known': known}
                    retain()
                    raise
                retain()  # Preserve each completed measurement, including misses.
    result['complete'] = True
    result['frame_budgets_pass'] = all(case['frame_budgets_pass'] for case in cases)
    retain()
    if not result['frame_budgets_pass']:
        raise SystemExit('Frame budget exceeded; full failed measurements retained in '+str(args.output))


if __name__ == '__main__':
    main()
