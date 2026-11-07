"""Paired cost of the actual sparse observers, without disk or gameplay."""

import argparse
import json
from pathlib import Path
import platform
import statistics
import sys
import time
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from blacksite.server.bus import EventBus
from blacksite.server.clock import ManualClock
from blacksite.server.loop import TickLoop
from blacksite.server.sessions import Sessions
from blacksite.server.storage.db import Storage
from minimal_s40_profile import MinimalProfile


class NoDisk:
    """Synthetic transaction body; never wraps a real connection."""
    def __enter__(self) -> 'NoDisk':
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def execute(self, *args: Any) -> None:
        pass


def batch(kind: str, capture: bool, calls: int) -> float:
    clock = ManualClock()
    loop = TickLoop(clock, EventBus(), Sessions(clock, 'benchmark'))
    store = Storage.__new__(Storage)
    store.clock, store.db = clock, NoDisk()
    store.commerce_commit_observer = None
    store.dirty, store.dirty_since = {}, {}
    observer = MinimalProfile(SimpleNamespace(storage=store, core=SimpleNamespace(loop=loop)))
    effect = {'player': None, 'items': [], 'delete_items': [],
              'budgets': {}, 'caches': {}, 'serial': 0}
    if capture:
        store.commerce_commit_observer = observer.commit
        loop.phase_observer = observer.phase
    began = time.perf_counter_ns()
    if kind == 'commit':
        for _ in range(calls):
            store.commerce_write(effect)
    else:
        for _ in range(calls):
            clock.advance()
            start = time.perf_counter_ns()
            loop.step()
            end = time.perf_counter_ns()
            if capture:
                observer.intervals(start, end)
    return (time.perf_counter_ns()-began)/calls/1000


def benchmark(calls: int = 100_000, rounds: int = 7) -> dict[str, Any]:
    result: dict[str, Any] = {'python': sys.version, 'platform': platform.platform(),
        'calls_per_batch': calls, 'limits': 'Synthetic no-disk transaction and empty loop; '
        'wall-clock cost only, no thread CPU/rusage, no gate subtraction or timing assertion.'}
    for kind in ('commit', 'loop'):
        rows = []
        for number in range(rounds):
            order = (False, True) if number % 2 == 0 else (True, False)
            values = {mode: batch(kind, mode, calls) for mode in order}
            rows.append({'order': list(order), 'baseline_us': values[False],
                         'observed_us': values[True], 'increment_us': values[True]-values[False]})
        result[kind] = {'rounds': rows, 'median_increment_us': statistics.median(
            row['increment_us'] for row in rows)}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(benchmark(), indent=2)+'\n', encoding='utf-8')
