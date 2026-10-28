"""S25 hazardous geography with a funded, equipped caller who fights back.

Grade five and 12000 hand chits are explicit setup. Gear, medicine,
movement, combat and interactions use real keys. No membership, item,
placement, reward or clock fixture. This is not new-player affordability.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import traceback

from accept_s10_netbbs import wait
from accept_s16_netbbs import key
from accept_s20_netbbs import grade
from accept_s25_city import CASES
from accept_s25_work_orders import WorkOrderProbe, equipment


async def accept(root: Path, python: Path, show: bool, size: tuple[int, int], case: str) -> None:
    assert not (root/'world').exists(), 'Use a fresh private acceptance world'
    probe = WorkOrderProbe(root, python, show)
    visited: list[str] = []
    try:
        await probe.start()
        origin = 'vatside-wake-hall'
        for destination in CASES[case]:
            assert any(ex.target_zone == destination for ex in
                       probe.service.world.zones[origin].template.meta.exits), (origin, destination)
            origin = destination
        caller = await probe.open(*size, 'S25'+case, 0, True, card='halvard')
        player = probe.game.players[caller.session.player_id]
        assert player.standing.get('halvard') == 10 and player.chits_hand == 200 and player.faction is None
        grade(probe, caller)
        player.chits_hand = 12000
        probe.game.queue('save', player.bbs_user_id, player, immediate=True)
        probe.service._character_writes()
        probe.report('FIXTURE S25 hazardous survey: grade five and12000 hand chits; actual gear/medicine purchases; no membership/item/placement/reward/clock fixture.')
        await probe.walk(caller, (21, 14))
        await key(caller, b'b')
        await wait(lambda: player.progress.get('wake_combat') == 'skipped')
        await equipment(probe, caller)
        probe.combat_prepared = True
        await probe.route(caller, 'vatside-wake-hall')
        for destination in CASES[case]:
            await probe.travel(caller, destination)
            if destination not in visited:
                await probe.inspect(caller, case)
                visited.append(destination)
        assert player.faction is None  # Membership refusal remains meaningful.
        await probe.leave(caller, 's25-'+case+'-'+str(size[0])+'-left')
        assert not probe.errors and probe.service.failure is None
        (root/'s25-survey.json').write_text(json.dumps({
            'passed': probe.server_start_seconds <= 3, 'functional_passed': True,
            'scope': 'prepared actual-city walking, combat, terminal cards and map rendering',
            'full_slice_acceptance': False, 'case': case, 'size': list(size), 'visited': visited,
            'journeys': probe.journeys, 'walks': probe.walks,
            'transport': 'NetBBS Telnet -> registered native stdio',
            'fixtures': ['grade five', '12000 hand chits'], 'membership_fixture': False,
            'item_fixture': False, 'placement_fixture': False, 'clock_fixture': False,
            'income_rate_claimed': False, 'starter_affordability_claimed': False},
            indent=2)+'\n', encoding='utf-8')
        probe.assert_start_budget()
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        (root/'s25-partial.json').write_text(json.dumps({
            'passed': False, 'case': case, 'size': list(size), 'visited': visited,
            'journeys': probe.journeys, 'walks': probe.walks,
            'fixtures': ['grade five', '12000 hand chits']}, indent=2)+'\n', encoding='utf-8')
        raise
    finally:
        if hasattr(probe, 'node'):
            await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--size', choices=('80x24', '132x50'), required=True)
    parser.add_argument('--case', choices=('southern', 'deep'), required=True)
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, args.show,
                       tuple(map(int, args.size.split('x'))), args.case))
