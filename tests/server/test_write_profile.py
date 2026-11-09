"""S40: observational write probes and exact, race-free gate evidence."""

import json
import hashlib
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from karst41.server.clock import ManualClock
from karst41.server.storage.db import Storage
from scripts.write_profile import Sample, WriteProfile, difference
from tests.harness import HeadlessServer


class Metrics:
    def __init__(self) -> None:
        self.wall = self.thread = self.process = 0
        self.counters = (0, 0, 0, 0, 0, 0)

    def read(self) -> Sample:
        return Sample(self.wall, self.wall, self.thread, self.process, self.counters)


def service(store: Storage, writes: Callable[[], None]) -> SimpleNamespace:
    core = HeadlessServer().core
    def status() -> dict[str, Any]:
        tick = core.loop.timing()
        return {'tick': tick, 'tick_p99_ms': tick['p99_ms']}
    result = SimpleNamespace(core=core, storage=store, logs=None,
                             status=status, _character_writes=writes)
    # Mirror Server.start's pre-bound admin callback.
    core.status_provider = result.status
    return result


def test_s40_probe_preserves_snapshot_cadence_and_restores_bindings(scratch_dir: Path) -> None:
    clock = ManualClock()
    store = Storage(scratch_dir/'world.db', clock)
    proposal = {'nested': [1]}
    server = service(store, lambda: store.mark_dirty('meta', 'balance', proposal))
    original_writes, original_status = server._character_writes, server.status
    original_provider, original_db = server.core.status_provider, store.db
    try:
        with WriteProfile(server) as probe:
            server._character_writes()
            proposal['nested'].append(2)
            assert store.meta('balance') == 0  # No new immediate commit.
            clock.advance(299)
            store.flush_due()
            assert store.meta('balance') == 0
            clock.advance()
            store.flush_due()
            assert store.meta('balance') == {'nested': [1]}
            labels = [row['operation'] for row in probe.calls[0]['operations']]
            assert labels == ['character_writes', 'storage.mark_dirty:meta:balance', 'storage._json']
        assert server._character_writes is original_writes
        assert server.status is original_status
        assert server.core.status_provider is original_provider
        assert store.db is original_db
        assert not {'mark_dirty', '_json', '_flush'} & vars(store).keys()
    finally:
        store.close()


def test_s40_probe_records_cpu_and_switches_on_named_operation(scratch_dir: Path) -> None:
    store = Storage(scratch_dir/'world.db', ManualClock())
    metrics = Metrics()
    original_json = store._json
    def slow_json(value: Any) -> str:
        metrics.wall += 30_000_000
        metrics.thread += 1_000_000
        metrics.process += 4_000_000
        metrics.counters = (1, 2, 3, 0, 0, 0)
        return original_json(value)
    store._json = slow_json
    server = service(store, lambda: store.mark_dirty('meta', 'balance', 8))
    try:
        with WriteProfile(server, reader=metrics.read) as probe:
            server._character_writes()
            row = next(r for r in probe.calls[0]['operations'] if r['operation'] == 'storage._json')
            assert (row['wall_ms'], row['thread_cpu_ms'], row['process_cpu_ms']) == (30, 1, 4)
            assert row['thread_counters'] == {'voluntary_switches': 1, 'involuntary_switches': 2,
                                             'minor_faults': 3, 'major_faults': 0,
                                             'input_blocks': 0, 'output_blocks': 0}
            assert row['parent'] == 1
        assert store._json is slow_json
    finally:
        store.close()


def test_s40_probe_preserves_rollback_exception_and_restores_after_failure(scratch_dir: Path) -> None:
    store = Storage(scratch_dir/'world.db', ManualClock())
    original_db = store.db
    def failed_write() -> None:
        with store.db:
            store.db.execute("INSERT INTO meta VALUES('probe-rejected', '1')")
            raise ValueError('rejected')
    server = service(store, failed_write)
    original_provider = server.core.status_provider
    try:
        with pytest.raises(ValueError, match='rejected'):
            with WriteProfile(server) as probe:
                server._character_writes()
        assert store.meta('probe-rejected') is None
        assert store.db is original_db and server.core.status_provider is original_provider
        assert [r['operation'] for r in probe.calls[0]['operations']] == [
            'character_writes', 'sqlite.execute', 'sqlite.rollback']
    finally:
        store.close()


@pytest.mark.parametrize('count,expected', [(0, 0), (99, 99), (100, 99)])
@pytest.mark.parametrize('trace_writes', [False, True])
def test_s40_serialized_gate_reproduces_same_status_samples_after_later_ticks(
        scratch_dir: Path, count: int, expected: int, trace_writes: bool) -> None:
    store = Storage(scratch_dir/'world.db', ManualClock())
    server = service(store, lambda: None)
    try:
        with WriteProfile(server, trace_writes=trace_writes) as probe:
            for value in range(1, count + 1):
                server.core.loop.record_timing(value/1000)
            # The admin input is processed before the current tick's timing
            # is appended. Later work can even clear/replace the deque.
            response = json.loads(json.dumps(server.core.status_provider()))
            server.core.loop.record_timing(1)
            server.core.loop.timings.clear()
            server.core.status_provider()
            gate = json.loads(json.dumps(probe.gate(response)))
            samples = sorted(gate['samples_ms'])
            p99 = samples[(len(samples)*99+99)//100-1] if samples else 0
            assert gate['count'] == count
            assert gate['samples_ms'] == list(range(1, count+1))
            assert p99 == response['tick_p99_ms'] == gate['reported']['p99_ms'] == expected
        assert '_write_profile_gate' not in server.status()
    finally:
        store.close()


def test_s40_missing_thread_counters_and_slow_sampling_are_explicit() -> None:
    row = difference(Sample(0, 2_000_000, 0, 0, None),
                     Sample(12_000_000, 15_000_000, 1_000_000, 1_000_000, None))
    assert row['wall_ms'] == 10
    assert row['sampling_wall_ms'] == 5
    assert row['thread_counters'] is None


def test_s40_status_only_gate_installs_no_write_observer(scratch_dir: Path) -> None:
    store = Storage(scratch_dir/'world.db', ManualClock())
    server = service(store, lambda: store.mark_dirty('meta', 'balance', 8))
    original_writes, original_db = server._character_writes, store.db
    def forbidden_clock() -> Sample:
        raise AssertionError('Detailed observer ran in a canonical gate')
    try:
        with WriteProfile(server, reader=forbidden_clock, trace_writes=False) as probe:
            assert server._character_writes is original_writes and store.db is original_db
            assert not {'mark_dirty', '_json', '_flush'} & vars(store).keys()
            server._character_writes()
            response = server.core.status_provider()
            assert probe.gate(response)['count'] == 0 and not probe.calls
            assert probe.metadata()['trace_writes'] is False
        assert server._character_writes is original_writes and store.db is original_db
    finally:
        store.close()


def test_s40_formats_records_after_collection(scratch_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """S40's observer must not format a counter dictionary in each tick."""
    store = Storage(scratch_dir/'world.db', ManualClock())
    server = service(store, lambda: store.mark_dirty('meta', 'balance', 8))
    converted: list[str] = []
    def exported(start: Sample, end: Sample) -> dict[str, Any]:
        assert not probe.current, 'Formatting ran inside a measured write'
        converted.append('span')
        return difference(start, end)
    monkeypatch.setattr('scripts.write_profile.difference', exported)
    try:
        with WriteProfile(server) as probe:
            for _ in range(3):
                server._character_writes()
            assert not converted
        rows = probe.iter_calls()
        assert not converted
        first = next(rows)
        assert len(converted) == 3  # Later rows have not been expanded.
        records = json.loads(json.dumps([first, *rows]))
        assert len(records) == 3 and len(converted) == 9
        assert len(records[0]['operations']) == 3
        assert [span['operation'] for span in records[0]['operations']] == [
            'character_writes', 'storage.mark_dirty:meta:balance', 'storage._json']
    finally:
        store.close()


@pytest.mark.parametrize('calls', [0, 3])
def test_s40_stream_export_and_small_shape_manifest(scratch_dir: Path, calls: int) -> None:
    store = Storage(scratch_dir/'world.db', ManualClock())
    server = service(store, lambda: store.mark_dirty('meta', 'balance', 8))
    try:
        with WriteProfile(server) as probe:
            for tick in range(calls):
                server.core.loop.last_tick = tick
                server._character_writes()
        path = scratch_dir/'trace.json'
        manifest = probe.export_trace(path, {'diagnostic_only': True})
        saved = json.loads(path.read_text(encoding='utf-8'))
        assert saved['write_calls'] == probe.calls
        assert saved['diagnostic_only'] and saved['write_probe']['trace_writes']
        assert manifest['profile_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert manifest['trace_bytes'] == path.stat().st_size
        assert manifest['exported_calls'] == calls
        expected = [{'operation': op['operation'], 'parent': op['parent']}
                    for op in probe.calls[0]['operations']] if calls else []
        assert manifest['operations'] == expected
        assert manifest['richest_tick'] == (0 if calls else None)
    finally:
        store.close()
