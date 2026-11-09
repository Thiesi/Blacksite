"""Demo only: start the Sodium Row demo server from this checkout.

    python scripts/demo_sodium/serve.py --install-dir <dir> [--signs]

The shared venv installs `karst41` from the main checkout, so a plain
`python -m karst41.server` would run main without the demo. This script
points the server at this checkout's source and refuses to start otherwise.

A world keeps its own copy of the content and only refreshes it when the
package version changes, so this script removes that copy and the server
writes this checkout's on start. Characters and the world database stay.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / 'src'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Start the Sodium Row demo server (demo only).')
    parser.add_argument('--install-dir', required=True, type=Path)
    parser.add_argument('--signs', action='store_true', help='far signs at night (pass --signs to play.py too)')
    args = parser.parse_args(argv)

    env = {**os.environ, 'PYTHONPATH': str(SOURCE), 'KARST41_DEMO': 'sodium-row-evening'}
    env.pop('KARST41_DEMO_SIGNS', None)
    env.pop('KARST41_DEMO_SEATED', None)
    if args.signs:
        env['KARST41_DEMO_SIGNS'] = 'charted'

    found = subprocess.run([sys.executable, '-c', 'import karst41; print(karst41.__file__)'],
                           env=env, capture_output=True, text=True, check=False).stdout.strip()
    if not found or Path(found).resolve().parents[1] != SOURCE:
        print(f'Refusing to start: karst41 comes from {found or "nowhere"}, not {SOURCE}.')
        return 2
    print(f'Demo server from {SOURCE}. Signs {"charted" if args.signs else "dark"}, '
          'posted cast with errands.')
    args.install_dir = args.install_dir.resolve()
    args.install_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(SOURCE))
    from karst41.server.storage.lease import Lease
    lease = Lease(args.install_dir / 'world.db.sessions')
    try:
        lease.acquire()
    except Exception:
        print('Refusing to start: another server holds this install directory.')
        return 2
    try:
        sys.path.insert(0, str(SOURCE.parent))
        from scripts.demo_sodium.content import install_overlay
        install_overlay(args.install_dir)
        target = (args.install_dir / 'content').resolve()
        if target.parent != args.install_dir:
            raise ValueError('Demo content must stay inside its install directory.')
        shutil.rmtree(target, ignore_errors=True)
    finally:
        lease.release()
    return subprocess.call([sys.executable, '-m', 'karst41.server', '--install-dir', str(args.install_dir), '--tcp'], env=env)


if __name__ == '__main__':
    sys.exit(main())
