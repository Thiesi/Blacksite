"""S43 setup-path check: digests with view revisions normalised.

A change in how the counting fixture is set up (for example, one fewer
menu view published before the scene starts) shifts every view revision
number, and so every frame and body hash, without changing what the
scene shows. This prints, for each S43 case, the frame and body digests
with `base`/`rev` normalised, and the actor trace digest unchanged.

Run it on two trees (the change and its base) and compare:

    python scripts/compare_s43_normalised.py > after.json
    (in the base tree) python scripts/compare_s43_normalised.py > before.json
    python scripts/compare_s43_normalised.py --compare before.json after.json

A setup-path re-pin is allowed only when every case matches here
(technical lead, S48c1a; see tests/world/test_s43_output.py).
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REVISION = re.compile(rb'"(base|rev)":\s*\d+')


def case_digests(case: dict[str, Any]) -> dict[str, str]:
    from karst41.server.protocol import Frame, encode
    from scripts.measure_s43_invalidations import fixture

    game, client, actor = fixture(case['zone'])
    session = client.session

    def drain() -> list[bytes]:
        frames = [encode(frame) for frame in game.frames_for(client)]
        session.acknowledge(session.view_revision)
        return frames

    drain()
    for _ in range(10):
        game.step()
        drain()
    frames, bodies, trace = sha256(), sha256(), []
    for index in range(case['ticks']):
        if case['mode'] == 'walk' and index % 2 == 0:
            client.send(Frame('key', {'k': 'right' if index % 4 == 0 else 'left', 't': 0}))
        game.step()
        for frame in drain():
            # Drop the length prefix (it moves with the revision's digit
            # count) and compare the JSON payload only.
            frames.update(REVISION.sub(rb'"\1":N', frame[frame.index(b'{'):]))
        body = game.core.characters.sim.views[session.id].previous['body']
        bodies.update(REVISION.sub(rb'"\1":N', encode(Frame('view', {'rev': 0, 'kind': 'zone', 'body': body}))))
        trace.append({'tick': game.clock.now_tick(), 'position': list(actor.position), 'hp': actor.health})
    return {'frames': frames.hexdigest(), 'bodies': bodies.hexdigest(),
            'actor_trace_sha256': sha256(json.dumps(trace).encode()).hexdigest()}


def digests() -> dict[str, dict[str, str]]:
    raw = (ROOT/'docs/ops/captures/s43/invalidations-before.json.gz').read_bytes()
    cases = json.loads(gzip.decompress(raw))['cases']
    return {f"{case['zone']}-{case['mode']}": case_digests(case) for case in cases}


def compare(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    lines = []
    for case in sorted(before.keys() | after.keys()):
        a, b = before.get(case), after.get(case)
        if a is None or b is None:
            lines.append(f'{case}: missing on one side')
            continue
        moved = [key for key in ('frames', 'bodies', 'actor_trace_sha256') if a[key] != b[key]]
        lines.append(f"{case}: {'match' if not moved else 'MOVED ' + ', '.join(moved)}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--compare', nargs=2, type=Path, metavar=('BEFORE', 'AFTER'))
    args = parser.parse_args()
    if args.compare:
        before, after = (json.loads(path.read_text(encoding='utf-8')) for path in args.compare)
        lines = compare(before, after)
        print('\n'.join(lines))
        return 0 if all(line.endswith(': match') for line in lines) else 1
    print(json.dumps(digests(), indent=1, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
