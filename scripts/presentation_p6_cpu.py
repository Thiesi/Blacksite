"""A8: pair merged-main and current rendering on B2's pinned content.

CPU uses the unchanged P1/B2 12-second activities and meter. Deterministic
frame streams are compared separately, including ANSI bytes. NPC sweeps
are in-memory measurement fixtures; they never change shipped content.
"""

import argparse
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import sys
from tempfile import TemporaryDirectory
from typing import Any, Iterator
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT), str(ROOT/'scripts')]

from blacksite.content.loader import ContentTree, load_content
from blacksite.door.cells import CellBuffer
from blacksite.door.model import Display
from blacksite.door.present import places, zone
from presentation_p6_validation import git, module, snapshot
from tests.presentation import budget

BASE = '6f1eac4c150946864e8d99e90e5943ed7bdf23e2'
INPUT = 'f69541473704f1164cd5b5e8dbd315c2fa811504'
STARTS = {'core-plaza': (41, 26), 'vatside-clinics': (36, 17), 'sodium-row': (46, 14)}
SOURCES = ('src/blacksite/door/present/zone.py', 'src/blacksite/door/cells.py',
           'src/blacksite/door/present/places.py')


@contextmanager
def renderer(before: bool) -> Iterator[None]:
    """Substitute only trusted merged rendering code; A7 origin stays."""
    with ExitStack() as stack:
        if before:
            old_zone = module('_a8_before_zone', git('show', f'{BASE}:{SOURCES[0]}'))
            old_cells = module('_a8_before_cells', git('show', f'{BASE}:{SOURCES[1]}'))
            old_places = module('_a8_before_places', git('show', f'{BASE}:{SOURCES[2]}'))
            stack.enter_context(patch.object(zone, 'terrain', old_zone.terrain))
            stack.enter_context(patch.object(CellBuffer, 'diff', old_cells.CellBuffer.diff))
            stack.enter_context(patch.object(places, 'Places', old_places.Places))
        yield


def frame_stream(content: ContentTree, zid: str, size: tuple[int, int], tier: str,
                 known: bool) -> dict[str, Any]:
    digest, original = sha256(), Display.render

    def render(self: Display, *args: Any) -> Any:
        data, ack = original(self, *args)
        if data:
            digest.update(len(data).to_bytes(8, 'big'))
            digest.update(data)
        return data, ack

    with patch.object(Display, 'render', render):
        result = budget.frames(content, *size, tier, presentation=True,
                               fully_known=known, zone=zid, start=STARTS[zid])
    result['ansi_stream_sha256'] = digest.hexdigest()
    return result


def population(content: ContentTree, count: int) -> ContentTree:
    """Hold both fixed Sable posts and the warden; vary regulars only."""
    result = deepcopy(content)
    template = result.zones['sodium-row']
    assert sum(s.count for s in template.meta.spawners) == 8
    spawners = tuple(replace(s, count=s.count+count-8) if s.id == 'sodium-regular' else s
                     for s in template.meta.spawners)
    assert sum(s.count for s in spawners) == count
    result.zones[template.id] = replace(template, meta=replace(template.meta, spawners=spawners))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zone', choices=tuple(STARTS), required=True)
    parser.add_argument('--npc-count', type=int, choices=(8, 11, 16))
    parser.add_argument('--tier', choices=('16', '256', 'truecolor'))
    parser.add_argument('--size', choices=('80x24', '132x50'))
    parser.add_argument('--seconds', type=float, default=12.)
    parser.add_argument('--input-ref', default=INPUT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (args.output.exists() or not 0 < args.seconds <= 600
            or not re.fullmatch('[0-9a-f]{40}', args.input_ref)
            or args.npc_count is not None and args.zone != 'sodium-row'):
        parser.error('choose a new output, positive seconds <=600, full input id, Sodium-only sweep')
    dirty = bool(git('status', '--porcelain').strip())
    result: dict[str, Any] = dict(schema=1, head=git('rev-parse', 'HEAD').decode().strip(),
        baseline=BASE, input_ref=args.input_ref, dirty=dirty, platform=platform.platform(),
        python=sys.version, seconds=args.seconds,
        cpu_budget_reference=platform.system() == 'Linux' and args.seconds == 12. and not dirty,
        method='unchanged P1/B2 activity/Meter/MIX; 10 Hz ticks, 5 Hz walking; setup/server/codecs excluded',
        minutes=budget.MIX, source_sha256={p: sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES},
        npc_count=args.npc_count,
        sweep_fixture='2 fixed Sable + 1 warden unchanged; sodium-regular count 5/8/13; measurement only',
        cases=[])
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def retain() -> None:
        args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')

    with TemporaryDirectory(prefix='blacksite-a8-') as temporary:
        data = Path(temporary)/'content'
        result['input_files_sha256'] = snapshot(data, args.input_ref)
        content = load_content(data)
        assert not content.load_problems
        if args.npc_count is not None:
            content = population(content, args.npc_count)
        sizes = [tuple(map(int, args.size.split('x')))] if args.size else (
            [(132, 50)] if args.npc_count else [(80, 24), (132, 50)])
        try:
            for size in sizes:
                for tier in [args.tier] if args.tier else ('16', '256', 'truecolor'):
                    for known in (False, True) if size[0] == 132 else (False,):
                        row: dict[str, Any] = dict(zone=args.zone, size=size, tier=tier,
                            fully_known=known, start=STARTS[args.zone], arms={})
                        result['cases'].append(row)
                        for label in ('before', 'after'):
                            arm: dict[str, Any] = dict(activities={})
                            row['arms'][label] = arm
                            with renderer(label == 'before'):
                                for what in budget.MIX:
                                    arm['activities'][what] = budget.activity(content, *size, tier,
                                        what, args.seconds, presentation=True, fully_known=known,
                                        zone=args.zone, start=STARTS[args.zone])
                                    retain()
                                arm['cpu_s_per_hour'] = budget.hourly(arm['activities'])
                                arm['frames'] = frame_stream(content, args.zone, size, tier, known)
                            retain()
                        before, after = (row['arms'][label] for label in ('before', 'after'))
                        fields = ('initial_view', 'final_view', 'ticks', 'key_steps', 'successful_moves')
                        row['matched_workloads'] = all(before['activities'][what][f] == after['activities'][what][f]
                            for what in budget.MIX for f in fields)
                        row['ansi_bytes_identical'] = before['frames']['ansi_stream_sha256'] == after['frames']['ansi_stream_sha256']
                        row['cpu_change_s_per_hour'] = after['cpu_s_per_hour']-before['cpu_s_per_hour']
                        row['after_108_pass'] = after['cpu_s_per_hour'] <= 108
                        row['frame_budgets_pass'] = all(arm['frames']['delta_16kib_pass'] and
                            arm['frames']['render_p95_100ms_pass'] for arm in (before, after))
                        retain()
                        print(json.dumps({k: row[k] for k in ('zone', 'size', 'tier', 'fully_known',
                            'matched_workloads', 'ansi_bytes_identical', 'after_108_pass', 'cpu_change_s_per_hour')}
                            | {'cpu': [before['cpu_s_per_hour'], after['cpu_s_per_hour']]}), flush=True)
                        assert row['matched_workloads'] and row['ansi_bytes_identical'] and row['frame_budgets_pass']
        except Exception as exc:
            result['incomplete_error'] = dict(type=type(exc).__name__, message=str(exc))
            retain()
            raise
    result['complete'] = True
    result['all_108_pass'] = all(row['after_108_pass'] for row in result['cases'])
    retain()
    # CPU stays recorded; completion and every individual miss stay auditable.


if __name__ == '__main__':
    main()
