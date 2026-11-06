"""Post-canonical standalone WAL/FULL disk baseline; not acceptance."""

import argparse
import json
from pathlib import Path
import platform
import sqlite3
import sys
import time
from typing import Any


def baseline(directory: Path, count: int = 256) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory/'s40-disk-baseline.db'
    if any(Path(str(path)+suffix).exists() for suffix in ('', '-wal', '-shm')):
        raise FileExistsError('Refuse to replace an existing disk baseline database')
    connection = sqlite3.connect(path)
    values: list[float] = []
    try:
        journal = connection.execute('PRAGMA journal_mode=WAL').fetchone()[0]
        connection.execute('PRAGMA synchronous=FULL')
        synchronous = connection.execute('PRAGMA synchronous').fetchone()[0]
        connection.execute('CREATE TABLE baseline(id INTEGER PRIMARY KEY, value BLOB)')
        connection.commit()
        payload = bytes(4096)
        for number in range(count):
            connection.execute('INSERT INTO baseline VALUES(?,?)', (number, payload))
            began = time.perf_counter_ns()
            connection.commit()
            values.append((time.perf_counter_ns()-began)/1_000_000)
        ordered = sorted(values)
        def percentile(percent: int) -> float:
            return ordered[(len(ordered)*percent+99)//100-1]
        return {'diagnostic_only': True, 'phase': 'after_saved_canonical_result',
                'journal_mode': journal, 'synchronous': synchronous,
                'database_directory': str(directory.resolve()),
                'filesystem_device': directory.stat().st_dev,
                'commits': count, 'payload_bytes': len(payload),
                'commit_wall_ms': values,
                'p50_ms': percentile(50), 'p95_ms': percentile(95),
                'p99_ms': percentile(99), 'max_ms': max(values),
                'python': sys.version, 'sqlite': sqlite3.sqlite_version,
                'platform': platform.platform(),
                'limits': 'Standalone new database on the game proof filesystem, no game '
                          'payload; clean commits do not refute intermittent game/disk stalls.'}
    finally:
        connection.close()
        for suffix in ('', '-wal', '-shm'):
            Path(str(path)+suffix).unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.profile_root
    if not list(root.glob('npc-profile-*-2.json')):
        parser.error('A saved final canonical profile is required before the disk baseline')
    result = baseline(root/'world')
    (root/'disk-baseline.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
