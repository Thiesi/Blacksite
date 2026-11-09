"""Post-canonical standalone WAL/FULL disk baseline; not acceptance."""

import argparse
import json
import hashlib
from pathlib import Path
import platform
import sqlite3
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from karst41.server.clock import ManualClock
from karst41.server.storage.db import Storage


def wal_state(path: Path) -> dict[str, int]:
    """Read only the standalone WAL header, outside measured commit time.

    SQLite fileformat2: offset12 is checkpoint generation; offsets16/20
    are salts. A restart follows a completed checkpoint. A file-size
    plateau alone is only a reuse hint, not an exact checkpoint hook.
    """
    wal = Path(str(path)+'-wal')
    with wal.open('rb') as source:
        header = source.read(24)
    return {'bytes': wal.stat().st_size,
            'generation': int.from_bytes(header[12:16], 'big'),
            'salt1': int.from_bytes(header[16:20], 'big'),
            'salt2': int.from_bytes(header[20:24], 'big')}


def baseline(directory: Path, count: int = 4096,
             shape: dict[str, Any] | None = None) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory/'s40-disk-baseline.db'
    if any(Path(str(path)+suffix).exists() for suffix in ('', '-wal', '-shm')):
        raise FileExistsError('Refuse to replace an existing disk baseline database')
    if count < 1:
        raise ValueError('At least one commit is required')
    effect = json.loads(json.dumps(shape['effect'])) if shape else {
        'player': None, 'items': [], 'delete_items': [], 'budgets': {},
        'caches': {}, 'serial': 0}
    clock = ManualClock()
    store = Storage(path, clock)
    rows: list[dict[str, Any]] = []
    captured: list[tuple[int, int, bool]] = []
    store.commerce_commit_observer = lambda *span: captured.append(span)
    try:
        journal = store.db.execute('PRAGMA journal_mode').fetchone()[0]
        synchronous = store.db.execute('PRAGMA synchronous').fetchone()[0]
        threshold = store.db.execute('PRAGMA wal_autocheckpoint').fetchone()[0]
        page_size = store.db.execute('PRAGMA page_size').fetchone()[0]
        before = wal_state(path)
        initial = dict(before)
        for number in range(count):
            clock.advance()
            if effect['player']:
                # Only the standalone database sees this diagnostic counter.
                effect['player']['progress']['s40_baseline_serial'] = number
            effect['serial'] = number
            store.commerce_write(effect)
            start, end, success = captured.pop()
            assert success
            after = wal_state(path)
            restarted = any(after[key] != before[key]
                            for key in ('generation', 'salt1', 'salt2'))
            if restarted and rows:
                # The reset happens on this transaction's first write;
                # checkpoint completion is attributed to the preceding
                # commit in this single-connection, no-reader experiment.
                rows[-1]['checkpoint_inferred_from_next_restart'] = True
            rows.append({'commit': number+1, 'wall_ms': (end-start)/1_000_000,
                         'wal': after, 'wal_did_not_grow': after['bytes'] <= before['bytes'],
                         'header_restarted_this_transaction': restarted,
                         'checkpoint_inferred_from_next_restart': False})
            before = after
        values = [row['wall_ms'] for row in rows]
        ordered = sorted(values)
        def percentile(percent: int) -> float:
            return ordered[(len(ordered)*percent+99)//100-1]
        inferred = [row for row in rows if row['checkpoint_inferred_from_next_restart']]
        return {'diagnostic_only': True, 'phase': 'after_saved_canonical_result',
                'journal_mode': journal, 'synchronous': synchronous,
                'wal_autocheckpoint_pages': threshold, 'page_size': page_size,
                'database_directory': str(directory.resolve()),
                'filesystem_device': directory.stat().st_dev,
                'commits': count, 'representative_effect_json_bytes': len(
                    json.dumps(effect, ensure_ascii=False).encode('utf-8')),
                'shape_basis': shape.get('basis') if shape else 'Unit-test empty receipt',
                'not_captured_stalled_payload': True,
                'initial_wal': initial, 'max_wal_bytes': max(row['wal']['bytes'] for row in rows),
                'checkpoint_inferred_count': len(inferred),
                'checkpoint_preceding_commits': inferred,
                'commits_over_5_ms': [row for row in rows if row['wall_ms'] > 5],
                'commit_wall_ms': values, 'observations': rows,
                'p50_ms': percentile(50), 'p95_ms': percentile(95),
                'p99_ms': percentile(99), 'max_ms': max(values),
                'python': sys.version, 'sqlite': sqlite3.sqlite_version,
                'platform': platform.platform(),
                'limits': 'Actual Storage.commerce_write in a standalone database, using '
                          'a post-result representative player-only skill receipt; not '
                          'the captured stalled payload. WAL headers/stat are read after '
                          'commit timing. Next-transaction WAL restart infers a completed '
                          'checkpoint in the previous commit, not an SQLite checkpoint hook. '
                          'A size plateau alone does not prove a checkpoint. No explicit '
                          'checkpoint or synchronous/threshold change is made. The final '
                          'commit may checkpoint without a following restart observation.'}
    finally:
        store.commerce_commit_observer = None
        try:
            store.close()
        finally:
            for suffix in ('', '-wal', '-shm'):
                Path(str(path)+suffix).unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.profile_root
    if not list(root.glob('npc-profile-*-2.json')):
        parser.error('A saved final canonical profile is required before the disk baseline')
    shape_raw = (root/'disk-baseline-shape.json').read_bytes()
    result = baseline(root/'world', shape=json.loads(shape_raw))
    result['shape_sha256'] = hashlib.sha256(shape_raw).hexdigest()
    (root/'disk-baseline.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    if result['checkpoint_inferred_count'] < 3:
        raise SystemExit('Baseline did not observe three checkpoint/restart cycles; result saved')
