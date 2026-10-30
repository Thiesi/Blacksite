"""P5 on/off comparison using the P1 v1-provisional door workload."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]

from blacksite.content.loader import load_content
from tests.presentation.budget import MIX, activity, frames, hourly
from tests.presentation.mechanics import fingerprint


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=12.0)
    args = parser.parse_args()
    if not 0 < args.seconds <= 600:
        parser.error('seconds must be positive and at most 600')
    content = load_content(ROOT / 'src/blacksite/content')
    reference = platform.system() == 'Linux' and args.seconds == 12.0
    cases = []
    for width, height in ((80, 24), (132, 50)):
        for tier in ('16', '256', 'truecolor'):
            for known in (False, True) if width == 132 else (False,):
                arms = {}
                for enabled in (False, True):
                    activities = {what: activity(content, width, height, tier, what, args.seconds,
                                                 presentation=enabled, fully_known=known) for what in MIX}
                    arms['on' if enabled else 'off'] = {
                        'frames': frames(content, width, height, tier, presentation=enabled, fully_known=known),
                        'activities': activities, 'cpu_s_per_hour': hourly(activities)}
                for arm in arms.values():
                    assert arm['frames']['delta_16kib_pass'] and arm['frames']['render_p95_100ms_pass'], arms
                for what in MIX:
                    assert arms['on']['activities'][what]['initial_view'] == arms['off']['activities'][what]['initial_view']
                    assert arms['on']['activities'][what]['final_view'] == arms['off']['activities'][what]['final_view']
                    assert arms['on']['activities'][what]['successful_moves'] == arms['off']['activities'][what]['successful_moves']
                off, on = arms['off']['cpu_s_per_hour'], arms['on']['cpu_s_per_hour']
                row = {'size': [width, height], 'tier': tier, 'fully_known': known, 'arms': arms,
                       'cpu_delta_s_per_hour': on - off, 'new_worse': on > off,
                       'cpu_120s_per_hour_pass': on <= 120 if reference else None}
                cases.append(row)
                print(json.dumps({key: row[key] for key in ('size', 'tier', 'fully_known', 'cpu_delta_s_per_hour', 'new_worse')}), flush=True)
    report = {'schema': 1, 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True)),
              'created_utc': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(),
              'python': sys.version, 'processor': platform.processor(),
              'cpu_budget_reference': reference, 'seconds': args.seconds, 'mix': 'v1-provisional',
              'workload': 'p1-closed-walk-v3', 'minutes': MIX, 'mechanics_sha256': fingerprint(content)['sha256'],
              'tick_hz': 10, 'walking_key_hz': 5, 'arm_order': ['off', 'on'],
              'targets': {'render_p95_ms': 100, 'delta_bytes': 16384, 'cpu_s_per_hour': 120},
              'cpu_boundary': 'process_time_ns around Display.receive/key/update/render; server, codecs and terminal replay excluded',
              'npc_policy': 'shipped spawners, zone-id seeds, 30 warm-up ticks; no actor isolation',
              'knowledge_fixture': 'both arms seeded with all zone terrain only for fully_known cases',
              'policy': 'Frame budgets asserted; CPU verdict recorded; regressions require review and justification.',
              'cases': cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
