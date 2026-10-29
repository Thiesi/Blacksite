"""Compare P1 and the unmodified V1 activity on one host and runtime.

Pass a separate checkout of V1 at 1060c9d as --v1-root. Each case runs in
its own process; neither the checkout nor its renderer is edited. The
original V1 activity still supplies its wall-time result. Instrumentation
adds process CPU, movement and render counts alongside that result.
"""

import argparse
import asyncio
from collections import Counter
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
V1_REVISION = '1060c9df2ac6b140db932b4e888989d192502b20'
ACTIVITY = 'walking where there is no scene'


def result(cpu_ns: int, wall_ns: int, calls: dict[str, int], moves: int,
           outputs: int, elapsed: float) -> dict[str, Any]:
    return {'elapsed_s': elapsed, 'process_cpu_s_per_minute': cpu_ns / 1e9 / elapsed * 60,
        'method_wall_s_per_minute': wall_ns / 1e9 / elapsed * 60,
        'successful_moves': moves, 'successful_moves_per_minute': moves / elapsed * 60,
        'calls': dict(calls), 'output_frames': outputs}


def p1(runtime: Path, seconds: float) -> dict[str, Any]:
    os.environ.pop('BLACKSITE_PRESENTATION_TRIAL', None)
    sys.path[:0] = [str(runtime/'src'), str(ROOT), str(runtime)]
    from blacksite.content.loader import load_content
    from tests.presentation import budget

    meters = []

    class DualMeter(budget.Meter):
        def __init__(self) -> None:
            super().__init__()
            self.observed_wall_ns = self.outputs = 0
            self.method_cpu_ns: Counter[str] = Counter()
            self.method_wall_ns: Counter[str] = Counter()
            meters.append(self)

        def call(self, name: str, function: Callable[..., Any], *args: Any) -> Any:
            started, cpu_before = time.perf_counter_ns(), self.cpu_ns
            try:
                value = super().call(name, function, *args)
                if name == 'render' and value[0]:
                    self.outputs += 1
                return value
            finally:
                wall = time.perf_counter_ns() - started
                self.observed_wall_ns += wall
                self.method_wall_ns[name] += wall
                self.method_cpu_ns[name] += self.cpu_ns - cpu_before

    budget.Meter = DualMeter
    measured = budget.activity(load_content(runtime/'src/blacksite/content'),
                              132, 50, 'truecolor', ACTIVITY, seconds)
    meter = meters[-1]  # The constructor resets the meter after warm-up.
    elapsed = measured['elapsed_s']
    return {**result(meter.cpu_ns, meter.observed_wall_ns, meter.calls,
        measured['successful_moves'], meter.outputs, measured['elapsed_s']),
        'method_cpu_s_per_minute': {k: v/1e9/elapsed*60 for k,v in meter.method_cpu_ns.items()},
        'method_wall_s_per_minute_by_method': {k: v/1e9/elapsed*60 for k,v in meter.method_wall_ns.items()},
        'key_steps': measured['key_steps'], 'activity_result': measured,
        'renderer': 'shipped', 'trial': False}


def v1(runtime: Path, seconds: float, shipped: bool) -> dict[str, Any]:
    directory = runtime/'scripts/presentation_mockups'
    sys.path[:0] = [str(runtime/'src'), str(runtime), str(directory)]
    spec = importlib.util.spec_from_file_location('comparison_v1', directory/'v1_budget.py')
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SAMPLE = seconds
    probes = []

    class DualClock(module.DoorClock):
        def __init__(self, caller: Any, painter: Any) -> None:
            self.cpu_ns = self.wall_ns = self.moves = self.outputs = 0
            self.calls: Counter[str] = Counter()
            self.method_cpu_ns: Counter[str] = Counter()
            self.method_wall_ns: Counter[str] = Counter()
            if shipped:
                caller.display.present = False  # Control only; no source edit.
            step = caller.game.step

            def counted_step(*args: Any, **kwargs: Any) -> Any:
                before = caller.avatar.actor.zone, caller.avatar.actor.position
                value = step(*args, **kwargs)
                self.moves += before != (caller.avatar.actor.zone, caller.avatar.actor.position)
                return value

            caller.game.step = counted_step
            super().__init__(caller, painter)
            probes.append(self)

        def timed(self, call: Callable[..., Any]) -> Callable[..., Any]:
            name = call.__name__

            def measured(*args: Any, **kwargs: Any) -> Any:
                wall, cpu = time.perf_counter_ns(), time.process_time_ns()
                try:
                    value = call(*args, **kwargs)
                    if name == 'render' and value[0]:
                        self.outputs += 1
                    return value
                finally:
                    wall_ns = time.perf_counter_ns() - wall
                    cpu_ns = time.process_time_ns() - cpu
                    self.cpu_ns += cpu_ns
                    self.wall_ns += wall_ns
                    self.method_cpu_ns[name] += cpu_ns
                    self.method_wall_ns[name] += wall_ns
                    self.spent += wall_ns / 1e9  # Preserve V1's own wall-time meter.
                    self.calls[name] += 1
            return measured

    module.DoorClock = DualClock
    original = asyncio.run(module.activity(132, 50, 'modern', 'truecolor', ACTIVITY))
    probe = probes[-1]
    elapsed = probe.spent / original * 60
    return {**result(probe.cpu_ns, probe.wall_ns, probe.calls, probe.moves,
        probe.outputs, elapsed), 'key_steps': probe.calls['key'],
        'method_cpu_s_per_minute': {k: v/1e9/elapsed*60 for k,v in probe.method_cpu_ns.items()},
        'method_wall_s_per_minute_by_method': {k: v/1e9/elapsed*60 for k,v in probe.method_wall_ns.items()},
        'original_v1_wall_s_per_minute': original,
        'renderer': 'shipped' if shipped else 'V1 proposal map', 'trial': True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v1-root', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--seconds', type=float, default=12.0)
    parser.add_argument('--case', choices=('p1-v1-runtime', 'v1', 'v1-shipped', 'p1-current'),
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    runtime = args.v1_root.resolve()
    source = runtime/'scripts/presentation_mockups/v1_budget.py'
    if not source.is_file() or not 0 < args.seconds <= 600:
        parser.error('requires a V1 checkout and 0 < seconds <= 600')
    if args.case:
        measured = p1(ROOT if args.case == 'p1-current' else runtime, args.seconds) if args.case.startswith('p1-') else v1(runtime, args.seconds, args.case == 'v1-shipped')
        print(json.dumps({'case': args.case, **measured}), flush=True)
        return
    if args.output is None:
        parser.error('--output is required')
    rows = []
    for case in ('p1-v1-runtime', 'v1', 'v1-shipped', 'p1-current'):
        command = [sys.executable, str(Path(__file__).resolve()), '--v1-root', str(runtime),
                   '--seconds', str(args.seconds), '--case', case]
        run = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                             timeout=max(120, args.seconds + 90))
        if run.returncode:
            raise RuntimeError(f'{case} failed: {run.stderr}\n{run.stdout}')
        row = json.loads(run.stdout.splitlines()[-1])
        rows.append(row)
        print(json.dumps(row), flush=True)
    report = {'schema': 1, 'platform': platform.platform(), 'python': sys.version,
        'p1_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'v1_revision': V1_REVISION, 'v1_script_sha256': sha256(source.read_bytes()).hexdigest(),
        'activity': ACTIVITY, 'size': [132, 50], 'tier': 'truecolor', 'sample_seconds': args.seconds,
        'policy': 'first three cases use the identical pinned V1 runtime; P1-current isolates revision differences; V1 source is unedited; wall and process CPU are separate; Windows CPU remains diagnostic',
        'cases': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
