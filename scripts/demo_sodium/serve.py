"""Demo only: start the Sodium Row demo server from this checkout.

    python scripts/demo_sodium/serve.py --install-dir <dir> [--bouncer] [--signs] [--seated]

The shared venv installs `blacksite` from the main checkout, so a plain
`python -m blacksite.server` would run main without the demo. This script
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
    parser.add_argument('--bouncer', action='store_true', help='the Halo turns away a truce-breaker (Q7)')
    parser.add_argument('--signs', action='store_true', help='far signs at night (pass --signs to play.py too)')
    parser.add_argument('--seated', action='store_true', help='bar and Halo drinkers sit still (round 2 comparison)')
    args = parser.parse_args(argv)

    env = {**os.environ, 'PYTHONPATH': str(SOURCE), 'BLACKSITE_DEMO': 'sodium-row-evening'}
    env.pop('BLACKSITE_DEMO_BOUNCER', None)
    env.pop('BLACKSITE_DEMO_SIGNS', None)
    env.pop('BLACKSITE_DEMO_SEATED', None)
    if args.bouncer:
        env['BLACKSITE_DEMO_BOUNCER'] = '1'
    if args.signs:
        env['BLACKSITE_DEMO_SIGNS'] = 'charted'
    if args.seated:
        env['BLACKSITE_DEMO_SEATED'] = '1'

    found = subprocess.run([sys.executable, '-c', 'import blacksite; print(blacksite.__file__)'],
                           env=env, capture_output=True, text=True, check=False).stdout.strip()
    if not found or Path(found).resolve().parents[1] != SOURCE:
        print(f'Refusing to start: blacksite comes from {found or "nowhere"}, not {SOURCE}.')
        return 2
    print(f'Demo server from {SOURCE}. Bouncer {"on" if args.bouncer else "off"}, signs {"charted" if args.signs else "dark"}, '
          f'drinkers {"seated" if args.seated else "moving"}.')
    args.install_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(SOURCE))
    from blacksite.server.storage.lease import Lease
    lease = Lease(args.install_dir / 'world.db.sessions')
    try:
        lease.acquire()
    except Exception:
        print('Refusing to start: another server holds this install directory.')
        return 2
    try:
        shutil.rmtree(args.install_dir / 'content', ignore_errors=True)
    finally:
        lease.release()
    return subprocess.call([sys.executable, '-m', 'blacksite.server', '--install-dir', str(args.install_dir), '--tcp'], env=env)


if __name__ == '__main__':
    sys.exit(main())
