"""Sparse S40 observations preserve transactions and deterministic ordering."""

from pathlib import Path
import sqlite3
from types import SimpleNamespace
from typing import Any

import pytest

from blacksite.server.clock import ManualClock
from blacksite.server.protocol import Frame
from blacksite.server.storage.db import Storage
from scripts.benchmark_s40_disk import baseline
from scripts.minimal_s40_profile import MinimalProfile
from tests.harness import HeadlessServer


def effect() -> dict[str, Any]:
    return {'player': None, 'items': [], 'delete_items': [],
            'budgets': {}, 'caches': {}, 'serial': 7}


def test_s40_commit_clock_brackets_only_existing_commit_and_freezes_tick(
        scratch_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = Storage(scratch_dir/'world.db', ManualClock())
    core = HeadlessServer().core
    core.loop.last_tick = 7263
    events: list[str] = []
    stamps = iter((100, 30_000_100))
    def clock() -> int:
        events.append('clock')
        return next(stamps)
    monkeypatch.setattr('blacksite.server.storage.db.perf_counter_ns', clock)
    store.db.set_trace_callback(lambda sql: events.append('commit') if sql == 'COMMIT' else None)
    original = store.db
    try:
        with MinimalProfile(SimpleNamespace(storage=store, core=core)) as probe:
            store.commerce_write(effect())
            core.loop.last_tick = 8000
            assert store.db is original and not store.db.in_transaction
            assert store.meta('item_serial') == 7
            assert probe.export() == [{'tick': 7263, 'start_ns': 100,
                'end_ns': 30_000_100, 'wall_ms': 30, 'success': True,
                'operation': 'commerce_write.sqlite_context_exit'}]
        assert events == ['clock', 'commit', 'clock']
        assert store.commerce_commit_observer is None and core.loop.phase_observer is None
    finally:
        store.close()


def test_s40_disabled_and_precommit_failure_read_no_clock(
        scratch_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = Storage(scratch_dir/'world.db', ManualClock())
    def forbidden() -> int:
        raise AssertionError('Disabled/precommit timer read a clock')
    monkeypatch.setattr('blacksite.server.storage.db.perf_counter_ns', forbidden)
    try:
        store.commerce_write(effect())
        store.commerce_commit_observer = lambda *args: pytest.fail('No commit was attempted')
        rejected = {**effect(), 'budgets': {'bad': {'remaining': 2}}}
        with pytest.raises(KeyError, match='hour'):
            store.commerce_write(rejected)
        assert not store.db.in_transaction and store.meta('item_serial') == 7
    finally:
        store.commerce_commit_observer = None
        store.close()


def test_s40_failed_commit_is_observed_without_losing_rollback_or_dirty_state(
        scratch_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class RejectedCommit(sqlite3.Connection):
        reject = False
        def __exit__(self, *args: Any) -> Any:
            if self.reject and args[0] is None:
                self.rollback()
                raise sqlite3.OperationalError('commit rejected')
            return super().__exit__(*args)
    connect = sqlite3.connect
    monkeypatch.setattr(sqlite3, 'connect', lambda *a, **kw: connect(*a, **kw, factory=RejectedCommit))
    store = Storage(scratch_dir/'world.db', ManualClock())
    stamps = iter((10, 20))
    monkeypatch.setattr('blacksite.server.storage.db.perf_counter_ns', lambda: next(stamps))
    observed = []
    store.commerce_commit_observer = lambda *args: observed.append(args)
    store.mark_dirty('meta', 'item_serial', 4)
    store.db.reject = True
    try:
        with pytest.raises(sqlite3.OperationalError, match='commit rejected'):
            store.commerce_write(effect())
        assert observed == [(10, 20, False)]
        assert store.meta('item_serial') is None
        assert store.dirty['meta', 'item_serial'] == 4
        assert not store.db.in_transaction
    finally:
        store.db.reject = False
        store.commerce_commit_observer = None
        store.close()


def test_s40_boundaries_split_input_subsystems_publishers_and_restore(
        scratch_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = HeadlessServer()
    client = server.connect()
    store = Storage(scratch_dir/'world.db', server.clock)
    events = []
    stamps = iter((20, 50))
    def clock() -> int:
        return next(stamps)
    monkeypatch.setattr('scripts.minimal_s40_profile.time.perf_counter_ns', clock)
    server.core.bus.subscribe('input', lambda event: events.append('input'))
    class Subsystem:
        def tick(self, ctx: Any) -> None:
            events.append('subsystem')
    server.core.loop.subsystems = [Subsystem()]
    server.core.loop.publishers = [lambda ctx: events.append('publisher')]
    client.send(Frame('key', {'k': 'up', 't': 0}))
    try:
        with pytest.raises(ValueError, match='leave'):
            with MinimalProfile(SimpleNamespace(storage=store, core=server.core)) as probe:
                server.step()
                assert probe.intervals(10, 80) == {
                    'inputs_wall_ms': .00001, 'subsystems_wall_ms': .00003,
                    'publishers_wall_ms': .00003}
                assert events == ['input', 'subsystem', 'publisher']
                raise ValueError('leave')
        assert server.core.loop.phase_observer is None and store.commerce_commit_observer is None
    finally:
        store.close()


def test_s40_disk_baseline_reports_every_commit_and_deletes_only_its_database(
        scratch_dir: Path) -> None:
    marker = scratch_dir/'keep.txt'
    marker.write_text('keep')
    result = baseline(scratch_dir, count=5)
    assert result['journal_mode'] == 'wal' and result['synchronous'] == 2
    values = result['commit_wall_ms']
    assert len(values) == 5
    assert result['max_ms'] == result['p99_ms'] == max(values)
    assert result['diagnostic_only'] is True
    assert list(scratch_dir.iterdir()) == [marker]
    path = scratch_dir/'s40-disk-baseline.db'
    path.write_bytes(b'preserve')
    with pytest.raises(FileExistsError):
        baseline(scratch_dir, count=1)
    assert path.read_bytes() == b'preserve'
