"""Measure capture overhead using a native profile's write-call shape.

This synthetic benchmark executes no game operation or SQLite write. It
measures observer capture cost, not native acceptance or a gate adjustment.
"""

import argparse
from collections import deque
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from blacksite.server.write_profile import WriteProfile


def shape(root: Path) -> tuple[str, str, list[str], list[list[int]]]:
    richest: tuple[str, str, list[dict[str, Any]]] | None = None
    for path in sorted(root.glob('npc-profile-*.json')):
        raw = path.read_bytes()
        for call in json.loads(raw).get('write_calls', []):
            operations = call['operations']
            if richest is None or len(operations) > len(richest[2]):
                richest = path.name, hashlib.sha256(raw).hexdigest(), operations
    if richest is None or not richest[2]:
        raise ValueError('No captured write call in the profile root')
    name, digest, operations = richest
    labels = [row['operation'] for row in operations]
    children: list[list[int]] = [[] for _ in labels]
    if labels[0] != 'character_writes' or operations[0]['parent'] is not None:
        raise ValueError('Expected one character-write root')
    for index, row in enumerate(operations[1:], 1):
        parent = row['parent']
        if not isinstance(parent, int) or not 0 <= parent < index:
            raise ValueError('Invalid parent index in profile')
        children[parent].append(index)
    return name, digest, labels, children


def batch(labels: list[str], children: list[list[int]], calls: int,
          capture: bool) -> dict[str, float]:
    loop = SimpleNamespace(timings=deque(maxlen=calls), last_tick=0)
    core = SimpleNamespace(loop=loop)
    server = SimpleNamespace(core=core, storage=SimpleNamespace(db=object()),
                             status=lambda: {'tick': {}})
    probe = WriteProfile(server)

    def visit(index: int) -> None:
        for child in children[index]:
            probe.measure(labels[child], visit, child)

    server._character_writes = lambda: visit(0)
    core.status_provider = server.status
    with probe if capture else nullcontext():
        wall, cpu = time.perf_counter_ns(), time.thread_time_ns()
        for tick in range(calls):
            loop.last_tick = tick
            server._character_writes()
        cpu_us = (time.thread_time_ns()-cpu)/calls/1000
        wall_us = (time.perf_counter_ns()-wall)/calls/1000
    # Export is deliberately outside the measured capture batch, as it is
    # outside S11's gate. Also check the benchmark captured its whole shape.
    records = probe.calls
    assert len(records) == (calls if capture else 0)
    assert all(len(row['operations']) == len(labels) for row in records)
    return {'wall_us_per_call': wall_us, 'thread_cpu_us_per_call': cpu_us}


def benchmark(root: Path, calls: int, rounds: int) -> dict[str, Any]:
    name, digest, labels, children = shape(root)
    results: list[dict[str, Any]] = []
    for round_index in range(rounds):
        modes = (False, True) if round_index % 2 == 0 else (True, False)
        result = {str(mode): batch(labels, children, calls, mode) for mode in modes}
        results.append({'order': list(modes), 'baseline': result['False'],
                        'capture': result['True']})
    return {
        'purpose': 'Synthetic capture overhead; not game timing or acceptance',
        'profile': name, 'profile_sha256': digest,
        'operations_per_call': len(labels), 'calls_per_batch': calls,
        'rounds': results, 'python': sys.version, 'platform': platform.platform(),
        'median_increment_us_per_call': {
            metric: statistics.median(row['capture'][metric]-row['baseline'][metric]
                                      for row in results)
            for metric in ('wall_us_per_call', 'thread_cpu_us_per_call')},
        'limits': ('Replays labels and nesting without payload, SQLite, logging, '
                   'or all instance-wrapper work. Includes capture allocation/GC. '
                   'Does not bound whole-probe overhead or prove an unchanged '
                   'gate outcome. No time is subtracted from any gate.')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--calls', type=int, default=500)
    parser.add_argument('--rounds', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.calls <= 5000 or not 1 <= args.rounds <= 9:
        parser.error('Use 1..5000 calls and 1..9 rounds')
    args.output.write_text(json.dumps(benchmark(args.profile_root, args.calls, args.rounds),
                                     indent=2)+'\n', encoding='utf-8')
