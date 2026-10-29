"""Record P1 frame and provisional session CPU baselines (no runtime edits)."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]

from blacksite.content.loader import load_content
from tests.presentation.budget import MIX, activity, frames, hourly
from tests.presentation.mechanics import fingerprint


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=12.0, help='Real seconds per activity; reference is 12')
    args = parser.parse_args()
    if not 0 < args.seconds <= 600:
        parser.error('seconds must be positive and at most 600')
    content = load_content(ROOT/'src/blacksite/content')
    cpu_budget_reference = platform.system() == 'Linux' and args.seconds == 12.0
    rows = []
    for width, height in ((80, 24), (132, 50)):
        for tier in ('16', '256', 'truecolor'):
            activities = {what: activity(content, width, height, tier, what, args.seconds) for what in MIX}
            row = {'size': [width, height], 'tier': tier, 'glyph_tier': 'cp437',
                'frames': frames(content, width, height, tier), 'activities': activities,
                'cpu_s_per_hour': hourly(activities),
                'cpu_120s_per_hour_pass': hourly(activities) <= 120 if cpu_budget_reference else None}
            rows.append(row)
            print(json.dumps({k: row[k] for k in ('size', 'tier', 'cpu_s_per_hour')}), flush=True)
    report = {'schema': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
        'platform': platform.platform(), 'processor': platform.processor(), 'python': sys.version,
        'mechanics_sha256': fingerprint(content)['sha256'], 'mix': 'v1-provisional', 'minutes': MIX,
        'sample_seconds': args.seconds, 'reference_duration': args.seconds == 12.0,
        'cpu_budget_reference': cpu_budget_reference,
        'cpu_clock_policy': 'process_time_ns per method; Windows scheduler-tick quantization makes '
            'its CPU totals diagnostic only; use hosted Linux for the CPU budget reference',
        'npc_policy': 'shipped spawners retained; 30 warm-up ticks after placement; zone-ID seeds',
        'cpu_boundary': 'process CPU around Display.receive/key/update/render; server, harness, protocol codecs, '
            'socket/stdin pumps and terminal replay excluded; warm-up excluded; no background painter in shipped door',
        'comparison': 'V1 weights, starts, keys and real-time schedule; shipped content only, '
            'shipped NPCs, no trial overlay; both walking categories use shipped map; '
            'V1 measured wall duration of method calls, P1 records actual process CPU',
        'targets': {'render_p95_ms': 100, 'delta_bytes': 16384, 'cpu_s_per_hour': 120},
        'policy': 'baseline only: report existing budget misses; no optimization or acceptance waiver', 'cases': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
