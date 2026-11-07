"""Sparse canonical observers; no write wrappers or connection proxy."""

from collections import deque
import time
from typing import Any


class MinimalProfile:
    def __init__(self, server: Any) -> None:
        self.storage = server.storage
        self.loop = server.core.loop
        self.commits: deque[tuple[int, int, int, bool]] = deque(
            maxlen=self.loop.timings.maxlen)
        self.inputs_done_ns = self.publishers_start_ns = 0

    def commit(self, start: int, end: int, success: bool) -> None:
        self.commits.append((self.loop.last_tick, start, end, success))

    def phase(self, name: str, tick: int) -> None:
        stamp = time.perf_counter_ns()
        if name == 'inputs_done':
            self.inputs_done_ns = stamp
        else:
            self.publishers_start_ns = stamp

    def intervals(self, start: int, end: int) -> dict[str, float]:
        return {
            'inputs_wall_ms': (self.inputs_done_ns-start)/1_000_000,
            'subsystems_wall_ms': (self.publishers_start_ns-self.inputs_done_ns)/1_000_000,
            'publishers_wall_ms': (end-self.publishers_start_ns)/1_000_000,
        }

    def __enter__(self) -> 'MinimalProfile':
        self.previous_commit = self.storage.commerce_commit_observer
        self.previous_phase = self.loop.phase_observer
        if self.previous_commit is not None or self.previous_phase is not None:
            raise RuntimeError('A canonical observer is already installed')
        self.storage.commerce_commit_observer = self.commit
        self.loop.phase_observer = self.phase
        return self

    def __exit__(self, *args: Any) -> None:
        self.storage.commerce_commit_observer = self.previous_commit
        self.loop.phase_observer = self.previous_phase

    def export(self) -> list[dict[str, Any]]:
        return [{'tick': tick, 'start_ns': start, 'end_ns': end,
                 'wall_ms': (end-start)/1_000_000, 'success': success,
                 'operation': 'commerce_write.sqlite_context_exit'}
                for tick, start, end, success in self.commits]
