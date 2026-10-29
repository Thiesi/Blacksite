"""P3 Wake Hall E/J predictions through a real NetBBS native stdio door.

Use ordinary creation, movement and menu keys, with normal NPCs, clock,
funds and content. No position, inventory or simulation fixtures are used.
Captures supply wording for presentation review; they grant no human gate.
"""

import argparse
import asyncio
import json
from pathlib import Path
import subprocess
from typing import Any

from accept_s10_netbbs import NativeProbe, wait
from blacksite.layout import compute
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
                caller = await probe.open(width, height, 'P3'+tier, archetype=0,
                    sixteen=tier == '16', truecolor=tier == 'truecolor')
                assert caller.session.caps['tier'] == tier
                sim = probe.game.sim
                screen = caller.caller.screen
                lat = probe.service.core.lattice
                layout = compute(width, height)

                def zone_body() -> dict[str, Any]:
                    return (sim.views[caller.session.id].previous or {}).get('body', {})

                async def predicted(target: str) -> dict[str, str]:
                    def ready() -> bool:
                        body = zone_body()
                        focus = body.get('focus')
                        return bool(focus and focus['id'] == target
                            and caller.session.ack_revision == caller.session.view_revision
                            and f"E {focus['verb']} {focus['label']}" in screen.screen_text().splitlines()[layout.hint.y])
                    await wait(ready)
                    return dict(zone_body()['focus'])

                def save(label: str) -> None:
                    probe.save(caller, label)
                    (root/(label+'.json')).write_text(json.dumps(snapshot(screen), ensure_ascii=False,
                        indent=2)+'\n', encoding='utf-8', newline='\n')

                # Cross the authored tutorial corridor and explicitly skip its
                # training fight. This is the existing Wake Hall route.
                await probe.walk(caller, (21, 14))
                await caller.caller.write(b'b')
                await wait(lambda: probe.game.players[caller.session.player_id].progress.get('wake_combat') == 'skipped')
                await probe.walk(caller, (34, 15))
                outfitter = await predicted('wake-outfitter')
                jack = dict(zone_body()['jack_focus'])
                assert jack['id'] == 'wake-terminal'
                save(f'outfitter-before-e-{width}x{height}-{tier}')
                await caller.caller.write(b'e')
                await wait(lambda: caller.session.id in probe.commerce.menus
                    and probe.commerce.menus[caller.session.id].target == outfitter['id']
                    and caller.session.ack_revision == caller.session.view_revision
                    and 'Sablier Wake Outfitter' in screen.screen_text())
                save(f'outfitter-after-e-{width}x{height}-{tier}')
                await caller.caller.write(b'\x1b')
                await predicted('wake-outfitter')
                # On this same tile E opens the counter, while J explicitly
                # selects its adjacent terminal. Both targets were disclosed.
                await caller.caller.write(b'j')
                await wait(lambda: caller.session.player_id in lat.presences and 'INTEGRITY' in screen.screen_text())
                await caller.caller.write(b'j')
                await wait(lambda: caller.avatar.actor.stance == 'normal')
                await predicted('wake-outfitter')
                # Outside counter range, fallback E now selects the terminal.
                await probe.walk(caller, (36, 15))
                terminal = await predicted('wake-terminal')
                save(f'terminal-before-e-{width}x{height}-{tier}')
                await caller.caller.write(b'e')
                await wait(lambda: caller.session.player_id in lat.presences and 'INTEGRITY' in screen.screen_text()
                    and caller.session.ack_revision == caller.session.view_revision)
                kind, body = sim.overlays[caller.session.id]
                assert kind == 'lattice' and 'focus' in body and 'jack_focus' in body
                assert body['jack_focus']['verb'] == 'jack out' and body['jack_focus']['label'] == ''
                save(f'terminal-after-e-{width}x{height}-{tier}')
                await caller.caller.write(b'j')
                await wait(lambda: caller.avatar.actor.stance == 'normal')
                await predicted('wake-terminal')
                await probe.leave(caller, f'finished-{width}x{height}-{tier}')
                cases.append({'size': [width, height], 'tier': tier,
                    'outfitter_e': outfitter, 'outfitter_j': jack,
                    'terminal_e': terminal, 'predicted_equals_opened': True,
                    'explicit_j_uses_terminal_beside_counter': True, 'clean_exit': True})
        assert not probe.errors, probe.errors
    finally:
        await probe.close()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == head
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    result = {'head': head, 'passed': True, 'cases': cases, 'human_approval': False,
        'transport': 'NetBBS Telnet -> registered native stdio',
        'fixtures': 'private node/world only; ordinary keys, normal NPCs, rules, funds and clock'}
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
