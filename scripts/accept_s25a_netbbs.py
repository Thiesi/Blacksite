"""S25a native stdio proof on explicit fixture props in the shipped hub.

No S25 maps are loaded. Input uses a real registered NetBBS native door;
the private content.local overlay supplies the adjacency reproducer and
one water tile. This is automated functional proof, not human play.
"""

import argparse
import asyncio
import json
from pathlib import Path
import time
from typing import Any, Callable
from unittest.mock import patch

from accept_s10_netbbs import NativeProbe, wait
from accept_s11_netbbs import profile
from blacksite.content.loader import load_content
from blacksite.content.schema import ObjectSpec
from blacksite.content.validate import validate
from blacksite.server.world.zone import ObjectState
from blacksite.server import app as server_app

REPO = Path(__file__).resolve().parents[1]


def fixture(root: Path) -> None:
    source = REPO/'src/blacksite/content'
    local = root/'world/content.local'
    zones = local/'zones'
    zones.mkdir(parents=True, exist_ok=True)
    zone = json.loads((source/'zones/vatside-wake-hall.json').read_text(encoding='utf-8'))
    # Keep this fallback-input reproducer clear of wandering service NPCs,
    # whose intentionally higher-priority E handler would change the case.
    # The other nine shipped zones retain their full ordinary population.
    zone['spawners'] = []
    zone['objects'].append({'id': 's25a-fixture-terminal', 'tile': [8, 4],
        'kind': 'terminal', 'params': {'name': 'FIXTURE telemetry', 'training_core': 'lat-wake-hall'}})
    (zones/'vatside-wake-hall.json').write_text(json.dumps(zone, indent=2)+'\n', encoding='utf-8')
    rows = (source/'zones/vatside-wake-hall.map').read_text(encoding='utf-8').splitlines()
    rows[5] = rows[5][:7]+'~'+rows[5][8:]
    (zones/'vatside-wake-hall.map').write_text('\n'.join(rows)+'\n', encoding='utf-8')
    problems = validate(load_content(source, local))
    assert not problems, problems


async def accept(root: Path, door_python: Path, show: bool,
                 sizes: tuple[tuple[int, int], ...]) -> None:
    fixture(root)
    probe = NativeProbe(root, door_python, show)
    phases: list[dict[str, object]] = []

    def timed(label: str, function: Callable[..., Any]) -> Callable[..., Any]:
        def measured(*args: Any, **kwargs: Any) -> Any:
            wall, cpu = time.perf_counter(), time.thread_time()
            try:
                return function(*args, **kwargs)
            finally:
                phases.append({'phase': label, 'wall_ms': (time.perf_counter()-wall)*1000,
                    'cpu_ms': (time.thread_time()-cpu)*1000})
        return measured

    with patch.object(server_app.shutil, 'copyfile', timed('copy', server_app.shutil.copyfile)), \
         patch.object(server_app, 'load_content', timed('load', server_app.load_content)), \
         patch.object(server_app, 'validate', timed('validate', server_app.validate)):
        await probe.start()
    (root/'startup-profile.json').write_text(json.dumps({
        'startup_seconds': probe.server_start_seconds, 'phases': phases}, indent=2)+'\n', encoding='utf-8')
    results: list[dict[str, object]] = []
    try:
        for width, height in sizes:
            caller = await probe.open(width, height, 'S25a', 0, True)
            actor = caller.avatar.actor
            began = time.monotonic()
            await probe.walk(caller, (8, 5))
            water_walk = time.monotonic()-began
            assert water_walk >= .25, water_walk
            zone = probe.service.world.zones[actor.zone]
            # Explicit runtime fixtures isolate each underfoot kind on the
            # same reachable tile. They grant no money, gear or authority.
            for kind in ('light', 'camera', 'salvage_field'):
                marker = ObjectSpec('s25a-fixture-prop', actor.position, kind,
                    params={'ring': 1} if kind == 'salvage_field' else {})
                zone.objects[marker.id] = ObjectState(marker)
                await caller.caller.write(b'e')
                await wait(lambda: actor.id in probe.service.core.lattice.presences)
                await wait(lambda: 'LATTICE' in caller.caller.screen.screen_text().upper())
                probe.save(caller, f's25a-{kind}-jack-{width}x{height}')
                await caller.caller.write(b'j')
                await wait(lambda: actor.id not in probe.service.core.lattice.presences)
                await wait(lambda: 'Wake Hall' in caller.caller.screen.screen_text().splitlines()[0])
                del zone.objects[marker.id]
            zone.objects['s25a-fixture-prop'] = ObjectState(ObjectSpec('s25a-fixture-prop',
                actor.position, 'descent_console', params={'season_door': True,
                    'name': 'The season door is sealed.'}))
            await caller.caller.write(b'e')
            await wait(lambda: 'season door is sealed' in caller.caller.screen.screen_text().lower())
            await wait(lambda: 'Wake Hall' in caller.caller.screen.screen_text().splitlines()[0])
            assert actor.id not in probe.service.core.lattice.presences
            probe.save(caller, f's25a-console-interact-{width}x{height}')
            await caller.caller.write(b'j')
            await wait(lambda: actor.id in probe.service.core.lattice.presences)
            await caller.caller.write(b'j')
            await wait(lambda: actor.id not in probe.service.core.lattice.presences)
            await wait(lambda: 'Wake Hall' in caller.caller.screen.screen_text().splitlines()[0])
            del zone.objects['s25a-fixture-prop']
            try:
                p99 = await profile(probe, width, height)
            except AssertionError:
                # Retain a failed budget sample while finishing functional
                # evidence at every requested size. The final exit fails.
                samples = sorted(root.glob(f'npc-profile-{width}x{height}-*.json'))
                status = json.loads(samples[-1].read_text(encoding='utf-8'))['status']
                assert status['active_zones'] == len(probe.service.world.zones), status
                p99 = status['tick_p99_ms']
            results.append({'size': [width, height], 'water_walk_seconds': water_walk,
                'passive_props_jack': True, 'console_interact_and_J': True, 'npc_p99_ms': p99})
            await probe.leave(caller, f's25a-complete-{width}x{height}')
        assert not probe.errors, probe.errors
        budgets_ok = probe.server_start_seconds <= 3 and all(row['npc_p99_ms'] < 10 for row in results)
        (root/'result.json').write_text(json.dumps({'passed': budgets_ok, 'functional_passed': True,
            'transport': 'NetBBS Telnet native stdio', 'human_playtest': False,
            'fixtures': 'private hub overlay, one water tile and underfoot props',
            'startup_seconds': probe.server_start_seconds, 'runs': results}, indent=2)+'\n', encoding='utf-8')
        assert budgets_ok, (probe.server_start_seconds, results)
    finally:
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--size', choices=('80x24', '132x50'))
    args = parser.parse_args()
    sizes = (tuple(map(int, args.size.split('x'))),) if args.size else ((80, 24), (132, 50))
    asyncio.run(accept(args.root.resolve(), args.door_python, args.show, sizes))
