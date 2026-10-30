"""Issue 67: live recruiter list and fractional ICE text at both sizes.

The ICE/program fractions are explicit private-training fixtures; casts,
selection and street travel use normal native-door inputs.
"""

import argparse
import asyncio
from dataclasses import replace
import json
from math import isclose
from pathlib import Path

from accept_s10_netbbs import NativeProbe, wait
from accept_s14_netbbs import choose, menu, program


async def accept(root: Path, door_python: Path, tier: str, show: bool = False) -> None:
    probe = NativeProbe(root, door_python, show)
    await probe.start()
    results: list[dict[str, object]] = []
    try:
        for width, height in ((80, 24), (132, 50)):
            caller = await probe.open(width, height, 'Issue67', 1, tier == '16',
                capture_cards=True, truecolor=tier == 'truecolor')
            assert caller.session.caps['tier'] == tier, caller.session.caps
            lattice = probe.service.core.lattice
            encounters = lattice.encounters
            player = probe.game.players[caller.session.player_id]
            await probe.walk(caller, (21, 14))
            await caller.caller.write(b'b')
            await wait(lambda: player.progress.get('wake_combat') == 'skipped')
            terminal = next(obj for obj in probe.service.world.zones[caller.avatar.zone].objects.values()
                            if obj.spec.params.get('training_core') == 'lat-wake-hall')
            await probe.walk(caller, terminal.spec.tile)
            await caller.caller.write(b'j')
            await wait(lambda: player.id in lattice.presences)
            presence = lattice.presences[player.id]
            await wait(lambda: 'INTEGRITY' in caller.caller.screen.screen_text())
            await caller.caller.write(b'e')
            await wait(lambda: caller.session.id in encounters.menus)
            await menu(probe, caller, 'enter:lat-wake-hall')
            await wait(lambda: presence.core == 'lat-wake-hall')
            defender = encounters.defenders(presence)[0]
            await wait(lambda: defender.template.name in caller.caller.screen.screen_text()
                and '/ CORE' in caller.caller.screen.screen_text().splitlines()[0]
                and caller.session.ack_revision == caller.session.view_revision)
            defender.integrity, defender.maximum = 30, 40
            mods = probe.game.progression.modifiers(player)
            multiplier = 1+mods.skill(player, 'programs')/200
            pick = encounters.content.programs['prg_pick']
            encounters.content.programs[pick.id] = replace(pick,
                effect=replace(pick.effect, amount=10.0075/multiplier))
            try:
                await choose(probe, caller, 'ice:'+defender.id)
                await wait(lambda: presence.target == defender.id and caller.session.id not in encounters.menus)
                await program(probe, caller, 1, lambda: isclose(defender.integrity, 19.9925))
                await wait(lambda: '19.99/40' in caller.caller.screen.screen_text()
                    and '10.01. Integrity 19.99.' in caller.caller.screen.screen_text())
                assert isclose(defender.integrity, 19.9925)
                probe.save(caller, f'issue67-fractional-ice-{width}x{height}')
                results.append({'size': [width, height], 'tier': tier, 'all_recruiters': True,
                    'ice_integrity': defender.integrity, 'display': '19.99/40', 'damage_text': '10.01'})
            finally:
                encounters.content.programs[pick.id] = pick
            await caller.caller.write(b'b')
            await wait(lambda: presence.instance is None)
            await caller.caller.write(b'j')
            await wait(lambda: player.id not in lattice.presences)
            await wait(lambda: 'Wake Hall' in caller.caller.screen.screen_text().splitlines()[0])
            await probe.leave(caller, f'issue67-return-{width}x{height}')
        assert not probe.errors, probe.errors
        (root/'result.json').write_text(json.dumps({'passed': True,
            'transport': 'NetBBS Telnet native stdio', 'human_playtest': False,
            'fixtures': 'private training ICE integrity and Pick effect amount',
            'runs': results}, indent=2)+'\n', encoding='utf-8')
    finally:
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--tier', choices=('16', '256', 'truecolor'), default='256')
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    asyncio.run(accept(args.root.resolve(), args.door_python, args.tier, args.show))
