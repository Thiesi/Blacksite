"""P4: additive view facts and first-entry history through native stdio.

Ordinary creation, movement, training skip, jack-in and menu keys only.
The private node/world has normal NPCs, rules and clock throughout.
"""

import argparse
import asyncio
import json
from pathlib import Path
import subprocess
from typing import Any

from accept_s10_netbbs import NativeProbe, wait
from tests.presentation.snapshots import snapshot


async def accept(root: Path, door_python: Path, show: bool,
                 sizes: tuple[tuple[int, int], ...]) -> None:
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    root.mkdir(parents=True, exist_ok=False)
    probe = NativeProbe(root, door_python, show)
    await probe.start()
    cases: list[dict[str, Any]] = []
    try:
        for width, height in sizes:
            for tier in ('16', '256', 'truecolor'):
                caller = await probe.open(width, height, 'P4'+tier, sixteen=tier == '16', truecolor=tier == 'truecolor')
                assert caller.session.caps['tier'] == tier
                screen = caller.caller.screen
                await wait(lambda: caller.session.ack_revision == caller.session.view_revision)
                def save(label: str) -> None:
                    probe.save(caller, label)
                    (root/(label+'.json')).write_text(json.dumps(snapshot(screen), ensure_ascii=False,
                        indent=2)+'\n', encoding='utf-8', newline='\n')
                body = probe.game.sim.views[caller.session.id].previous['body']
                assert body['me']['district'] == 'Vatside' and not body['me']['pvp']
                assert all('class' in a and 'jacked' in a for a in body['actors'])
                place = [line for line in caller.session.log_ring if line['kind'] == 'place']
                assert len(place) == 1
                assert all('kind' in line for line in caller.session.log_ring)
                assert not any('restart' in line['text'].lower() for line in caller.session.log_ring)
                save(f'wake-{width}x{height}-{tier}')
                await caller.caller.write(b'\x10')
                await wait(lambda: 'SCROLLBACK' in screen.screen_text() and place[0]['text'][:24] in screen.screen_text())
                save(f'place-history-{width}x{height}-{tier}')
                await caller.caller.write(b'\x1b')
                await wait(lambda: 'Wake Hall' in screen.screen_text().splitlines()[0])
                await probe.walk(caller, (21, 14))
                await caller.caller.write(b'b')
                await wait(lambda: probe.game.players[caller.session.player_id].progress.get('wake_combat') == 'skipped')
                await probe.walk(caller, (34, 15))
                await caller.caller.write(b'j')
                lat = probe.service.core.lattice
                await wait(lambda: caller.session.player_id in lat.presences and 'INTEGRITY' in screen.screen_text())
                await wait(lambda: caller.session.ack_revision == caller.session.view_revision)
                presence = lat.presences[caller.session.player_id]
                body = lat.view(caller.session, presence)
                assert body['theme'] and all('label' in edge for edge in body['edges'])
                assert all('owner' in cell and 'tier' in cell for cell in body['cells'] if cell['core'])
                assert body['me']['district'] == 'Vatside' and not body['me']['pvp']
                save(f'lattice-{width}x{height}-{tier}')
                await caller.caller.write(b'j')
                await wait(lambda: caller.avatar.actor.stance == 'normal')
                await probe.leave(caller, f'finished-{width}x{height}-{tier}')
                cases.append({'size': [width, height], 'tier': tier, 'name': f'P4{tier}界{width}',
                    'place_line': place[0]['text'], 'world_history_has_kinds': True,
                    'crew_restart_outside_world_history': True, 'lattice_fields': True,
                    'clean_exit': True})
        assert not probe.errors, probe.errors
    finally:
        await probe.close()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == head
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    result = {'head': head, 'passed': True, 'cases': cases, 'human_approval': False,
        'transport': 'NetBBS Telnet -> registered native stdio', 'fixtures': 'private node/world only'}
    (root/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',
                                  encoding='utf-8', newline='\n')
    print(json.dumps({'passed': True, 'cases': len(cases)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--size', choices=['80x24', '132x50'])
    args = parser.parse_args()
    sizes = ((tuple(map(int, args.size.split('x'))),) if args.size else ((80, 24), (132, 50)))
    asyncio.run(accept(args.root.resolve(), args.door_python, args.show, sizes))
