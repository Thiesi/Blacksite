"""Predeclared same-runner controls for M184 technical findings 1 and 2.

A8's workload/script is unchanged. Only its current-runtime/old-content
arm supplies an exact Git data snapshot instead of the historical overlay.
Each A8 arm runs in a separate interpreter, preventing mixed runtime imports.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
A8 = '4ab6470b10821f9fddbac718615af7d56c6048eb'
OLD_INPUT = 'dd489f9ec7676b2c37b553fa7587c4d0a4ed6d56'
PREFIX = 'src/blacksite/content/'


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def exact_snapshot(root: Path, destination: Path, ref: str) -> dict[str, str]:
    data = subprocess.check_output(['git', 'archive', '--format=tar', ref, PREFIX], cwd=root)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            if not member.isfile() or member.name.endswith('.py'):
                continue
            relative = Path(member.name).relative_to(PREFIX)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('unsafe Git content member')
            target = destination/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source:
                target.write_bytes(source.read())
    return {str(p.relative_to(destination)): sha256(p.read_bytes()).hexdigest()
            for p in sorted(destination.rglob('*')) if p.is_file()}


def a8_arm(root: Path, ref: str, output: Path, exact: bool) -> None:
    # This entry point imports no current Blacksite/tests module first.
    sys.path[:0] = [str(root/'src'), str(root), str(root/'scripts')]
    script = root/'scripts/presentation_p6_cpu.py'
    spec = importlib.util.spec_from_file_location('_row184_a8_control', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.snapshot
    audit: dict[str, Any] = {'head': git(root, 'rev-parse', 'HEAD'),
        'runtime_tree': git(root, 'rev-parse', 'HEAD:src'),
        'input_ref': ref, 'input_tree': git(root, 'rev-parse', ref+':src/blacksite/content'),
        'exact_snapshot_adapter': exact,
        'script_sha256': sha256(script.read_bytes()).hexdigest(),
        'budget_sha256': sha256((root/'tests/presentation/budget.py').read_bytes()).hexdigest()}

    def snapshot(destination: Path, input_ref: str) -> dict[str, str]:
        result = (exact_snapshot(root, destination, input_ref) if exact
                  else original(destination, input_ref))
        audit['actual_input_sha256'] = {
            str(p.relative_to(destination)): sha256(p.read_bytes()).hexdigest()
            for p in sorted(destination.rglob('*')) if p.is_file()}
        output.with_suffix('.input.json').write_text(json.dumps(audit, indent=2)+'\n', encoding='utf-8')
        return result

    module.snapshot = snapshot
    sys.argv = [str(script), '--zone', 'sodium-row', '--npc-count', '11',
        '--tier', '16', '--size', '132x50', '--input-ref', ref, '--output', str(output)]
    module.main()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a8-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--a8-arm', action='store_true')
    parser.add_argument('--input-ref')
    parser.add_argument('--exact-snapshot', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('refuse to overwrite the predeclared execution')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.a8_arm:
        a8_arm(args.a8_root, args.input_ref, args.output, args.exact_snapshot)
        return
    head = git(ROOT, 'rev-parse', 'HEAD')
    assert git(args.a8_root, 'rev-parse', 'HEAD') == A8
    result: dict[str, Any] = {'schema': 1, 'head': head,
        'runtime_tree': git(ROOT, 'rev-parse', 'HEAD:src'),
        'platform': platform.platform(), 'python': sys.version, 'host': platform.node(),
        'cpu_clock_resolution_s': time.get_clock_info('process_time').resolution,
        'cpu_budget_reference': platform.system() == 'Linux' and not git(ROOT, 'status', '--porcelain'),
        'predeclared_plan': 6729408184, 'arms': [], 'complete': False,
        'order': ['historical-a8', 'current-old-content', 'current-content',
                  'group-1-m8', 'group-4-m8', 'group-1-m4', 'group-4-m4']}
    failures = []
    result['failed_arms'] = failures

    def retain() -> None:
        args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')

    for label, source, ref, exact in (
        ('historical-a8', args.a8_root, OLD_INPUT, False),
        ('current-old-content', ROOT, OLD_INPUT, True),
        ('current-content', ROOT, head, False),
    ):
        output = args.output.parent/(label+'.json')
        command = [sys.executable, '-B', str(Path(__file__).resolve()), '--a8-arm',
            '--a8-root', str(source), '--input-ref', ref, '--output', str(output)]
        if exact:
            command.append('--exact-snapshot')
        started = time.monotonic()
        with output.with_suffix('.log').open('w', encoding='utf-8') as log:
            completed = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT)
        arm = {'label': label, 'report': output.name, 'exit_code': completed.returncode,
               'wall_seconds': time.monotonic()-started}
        result['arms'].append(arm)
        if completed.returncode:
            failures.append(label)
        retain()

    # Only now import current helpers in the parent. Old runtime imports
    # were isolated in child processes, not monkeypatched into this one.
    sys.path[:0] = [str(ROOT/'src'), str(ROOT), str(ROOT/'scripts')]
    from blacksite.content.loader import load_content
    from measure_row_population import activity
    from tests.presentation import budget
    content = load_content(ROOT/'src/blacksite/content')
    assert not content.load_problems
    for moving, callers in ((8, 1), (8, 4), (4, 1), (4, 4)):
        arm: dict[str, Any] = {'label': f'group-{callers}-m{moving}', 'stationary': 0,
            'moving': moving, 'callers': callers, 'tier': '16', 'fully_known': False,
            'activities': {}}
        result['arms'].append(arm)
        try:
            for what in budget.MIX:
                arm['activities'][what] = activity(content, 0, moving, callers, '16', what)
                retain()
            arm['door_total_cpu_s_per_hour'] = budget.hourly(arm['activities'])
            arm['door_per_caller_cpu_s_per_hour'] = [sum(
                arm['activities'][what]['per_caller'][i]['cpu_s_per_minute']*minutes
                for what, minutes in budget.MIX.items()) for i in range(callers)]
            arm['door_mean_cpu_s_per_hour'] = arm['door_total_cpu_s_per_hour']/callers
            arm['door_max_cpu_s_per_hour'] = max(arm['door_per_caller_cpu_s_per_hour'])
            arm['server_cpu_s_per_hour'] = sum(
                arm['activities'][what]['server_cpu_s_per_minute']*minutes
                for what, minutes in budget.MIX.items())
            arm['complete'] = True
        except Exception as exc:
            arm['error'] = {'type': type(exc).__name__, 'message': str(exc)}
            failures.append(arm['label'])
        retain()
    audit_paths = [args.output.parent/(label+'.input.json')
                   for label in ('historical-a8', 'current-old-content', 'current-content')]
    audits = [json.loads(path.read_text()) for path in audit_paths if path.exists()]
    result['missing_audits'] = [path.name for path in audit_paths if not path.exists()]
    result['old_inputs_identical'] = (len(audits) == 3 and
        audits[0]['actual_input_sha256'] == audits[1]['actual_input_sha256'])
    result['a8_scripts_identical'] = len(audits) == 3 and len({a['script_sha256'] for a in audits}) == 1
    result['p1_budgets_identical'] = len(audits) == 3 and len({a['budget_sha256'] for a in audits}) == 1
    if not all(result[key] for key in ('old_inputs_identical', 'a8_scripts_identical', 'p1_budgets_identical')):
        failures.append('input-or-method-audit')
    result['complete'] = not failures
    retain()
    if failures:
        raise SystemExit('control arms failed, retained without retry: '+', '.join(failures))


if __name__ == '__main__':
    main()
