"""Demo only: prepare a playtest character offline (demo/sodium-row-evening).

Create the character normally through the door first, then stop the
server and run this against the same install directory. It edits the
saved character through the storage layer and nothing else:

    python scripts/demo_sodium/seed.py --install-dir <dir> --name Ash \
        --grade 5 --faction kestrel --completed vesper-first-thing

Grade sets the matching XP and legal discharge. Faction sets standing
+40 with that faction and joins it, as the join rules require (+30).
Never run it while the server holds the install directory.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))  # this checkout, not the venv's install

from karst41.server.clock import RealClock  # noqa: E402
from karst41.server.players import Player
from karst41.server.rules.character import grade_threshold, health_max
from karst41.server.storage.db import Storage
from karst41.server.storage.lease import Lease

FACTIONS = ('halvard', 'sablier', 'kestrel', 'wardens', 'choir', 'sable', 'unmoored', 'ferrymen')
STANDING = 40


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Prepare a Sodium Row playtest character (demo only).')
    parser.add_argument('--install-dir', required=True, type=Path)
    parser.add_argument('--name', required=True, help='character name, as created through the door')
    parser.add_argument('--grade', type=int, default=5)
    parser.add_argument('--faction', choices=FACTIONS)
    parser.add_argument('--completed', action='append', default=[], help='contract id to record as completed')
    args = parser.parse_args(argv)

    database = args.install_dir / 'world.db'
    if not database.exists():
        print(f'No world at {database}. Create the character through the door first.')
        return 2
    lease = Lease(args.install_dir / 'world.db.sessions')
    try:
        lease.acquire()
    except Exception:
        print('Stop the server first: it holds this install directory.')
        return 2
    storage = Storage(database, RealClock())
    try:
        state = storage.character_state()
        matches = [p for p in state['players'] if p.get('name', '').lower() == args.name.lower()]
        if len(matches) != 1:
            print(f'Expected one character named {args.name!r}, found {len(matches)}.')
            return 2
        player = matches[0]
        now = datetime.now(timezone.utc).isoformat()
        # The game's own grade-up path: attributes, Vitals and grade points.
        body = Player.from_record(player)
        target = grade_threshold(max(body.grade, args.grade))
        if target > body.xp:
            body.update_progression(target)
        body.health = health_max(body.attributes['vitals'])
        player = {**player, **body.record()}
        player['legal_at'] = player.get('legal_at') or now
        if args.faction:
            player['standing'] = {**(player.get('standing') or {}), args.faction: STANDING}
            player['faction'] = args.faction
        storage.mark_dirty('players', player['id'], player)
        identity = state['identities'].get(player['bbs_user_id'])
        if identity is not None:
            identity['legal_at'] = identity.get('legal_at') or now
            storage.mark_dirty('identities', player['bbs_user_id'], identity)
        if args.completed:
            contracts = storage.meta('contracts_state') or {}
            engine = contracts.setdefault('engine', {})
            done = set(engine.setdefault('completed', {}).get(player['id'], []))
            engine['completed'][player['id']] = sorted(done | set(args.completed))
            storage.mark_dirty('meta', 'contracts_state', contracts)
        storage.flush_now()
    finally:
        storage.close()
        lease.release()
    faction = f", {args.faction} +{STANDING}" if args.faction else ''
    print(f"{player['name']}: grade {player['grade']}{faction}"
          + (f", completed {', '.join(args.completed)}" if args.completed else '') + '.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
