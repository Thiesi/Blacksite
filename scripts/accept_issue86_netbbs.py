"""Capture registered Lattice edges through NetBBS native stdio.

Discovery and sector presence are explicit private acceptance fixtures.
The service builds real views and the installed door renders them over
Telnet. No composed screen is injected into the terminal.
"""

import argparse
import asyncio
import json
from pathlib import Path

from accept_s10_netbbs import NativeProbe, wait


async def accept(root: Path, door_python: Path, tier: str) -> None:
    probe = NativeProbe(root, door_python, False)
    await probe.start()
    results = []
    try:
        lattice = probe.service.core.lattice
        for width, height in ((80, 24), (132, 50)):
            caller = await probe.open(width, height, 'Edge86', 0, tier == '16', truecolor=tier == 'truecolor')
            await probe.walk(caller, (21, 14))
            await caller.caller.write(b'b')
            player = probe.game.players[caller.session.player_id]
            await wait(lambda: player.progress.get('wake_combat') == 'skipped')
            terminal = next(obj for obj in probe.service.world.zones[caller.avatar.zone].objects.values()
                if obj.spec.params.get('training_core') == 'lat-wake-hall')
            await probe.walk(caller, terminal.spec.tile)
            await caller.caller.write(b'j')
            await wait(lambda: player.id in lattice.presences)
            presence = lattice.presences[player.id]
            for sid, sector in sorted(lattice.sectors.records.items()):
                # Labelled fixture: disclose the whole existing sector. Its
                # topology, credentials, glyph table and renderer are shipped.
                lattice.saved(player).setdefault('found_cells', {})[sid] = [cell.id for cell in sector.cells]
                presence.sector, presence.cell = sid, lattice.sectors.entrance(sid)
                caller.session.needs_full_view = True
                heading = sector.district.upper()+' / LATTICE'
                await wait(lambda: heading in caller.caller.screen.screen_text().splitlines()[0]
                    and caller.session.ack_revision == caller.session.view_revision)
                body = lattice.view(caller.session, presence)
                cells = {c['id']: c for c in body['cells']}
                vertical = any(edge['kind'] == 'hidden' and cells[edge['a']]['x'] == cells[edge['b']]['x']
                    for edge in body['edges'])
                screen = caller.caller.screen.screen_text()
                assert '\u2506' not in screen
                if vertical:
                    graph = '\n'.join(''.join(row[:width-24]) for row in caller.caller.screen.grid[1:height-5])
                    assert ':' in graph, (sid, width, tier)
                probe.save(caller, f'issue86-{sid}-{width}x{height}-{tier}')
                results.append({'sector': sid, 'size': [width, height], 'tier': tier,
                    'hidden_vertical': vertical, 'cp437_hidden_vertical': ':'})
            await caller.caller.write(b'j')
            await wait(lambda: player.id not in lattice.presences)
            await probe.leave(caller, f'issue86-return-{width}x{height}-{tier}')
        assert not probe.errors, probe.errors
        (root/'result.json').write_text(json.dumps({'passed': True, 'human_approval': False,
            'transport': 'NetBBS Telnet native stdio',
            'fixtures': 'all authored sector discoveries and sector presence; no rule or map changes',
            'runs': results}, indent=2)+'\n', encoding='utf-8')
    finally:
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--tier', choices=('16', '256', 'truecolor'), default='256')
    args = parser.parse_args()
    asyncio.run(accept(args.root.resolve(), args.door_python, args.tier))
