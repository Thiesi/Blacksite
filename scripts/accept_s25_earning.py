"""S25 first earning-to-upgrade route on the actual city, without fixtures.

This measures a one-time starter job and actual rifle/ammunition purchase.
It does not extrapolate that job into repeatable income or claim the
separate high-tier program, implant or human pacing acceptance gates.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import time
import traceback

from accept_s16_netbbs import commit_key
from accept_s19_netbbs import first_job
from accept_s25_services import ServiceProbe


async def accept(root: Path, python: Path, show: bool, size: tuple[int, int]) -> None:
    probe = ServiceProbe(root, python, show)
    try:
        await probe.start()
        began = time.monotonic()
        job = await first_job(probe, *size, False, leave=False)
        job_seconds = time.monotonic()-began
        caller = probe.connections[-1]
        player = probe.game.players[caller.session.player_id]
        assert player.faction is None and player.chits_bank == 0 and player.chits_hand == 400
        assert probe.game.content.items['wpn_halvard_hv7'].base_price > 200
        probe.save(caller, 's25-first-earned-400-chits')
        for zid in ('sodium-row', 'core-plaza', 'core-tram-hub', 'tramyard-market'):
            await probe.travel(caller, zid)
        vendor = probe.game.content.vendors['kestrel-depot']
        panel = await probe.counter(caller, vendor.object_id)
        gun = await probe.buy(caller, panel, 'wpn_halvard_hv7')
        ammo = await probe.buy(caller, panel, 'ammo_5x')
        assert probe.commerce.items[ammo].stack > 0 and 0 <= player.chits_hand < 400
        await probe.close_menu(caller)
        await commit_key(probe, caller, b'i', lambda: caller.session.id in probe.commerce.menus)
        panel = probe.commerce.menus[caller.session.id]
        await probe.row(caller, panel, gun)
        await commit_key(probe, caller, b'q', lambda: player.equipment.get('weapon_main') == gun)
        await probe.close_menu(caller)
        elapsed, remaining = time.monotonic()-began, player.chits_hand
        probe.save(caller, 's25-earned-rifle-and-ammunition-equipped')
        await probe.leave(caller, 's25-earned-upgrade-left')
        assert not probe.errors and probe.service.failure is None
        (root/'s25-earning.json').write_text(json.dumps({
            'passed': True, 'full_slice_acceptance': False, 'size': list(size), 'fixtures': [],
            'transport': 'NetBBS Telnet -> registered native stdio', 'job': job,
            'one_time_job_seconds': job_seconds, 'job_and_upgrade_seconds': elapsed,
            'earned_chits': 200, 'starter_chits': 200, 'remaining_chits': remaining,
            'rifle': 'wpn_halvard_hv7', 'ammo': 'ammo_5x', 'equipped': True,
            'repeatable_income_claimed': False, 'rate_extrapolation': False,
            'pending': ['repeatable full-city earnings', 'high-tier program and implant acquisition',
                        'human gameplay pacing'],
            'journeys': probe.journeys, 'walks': probe.walks}, indent=2)+'\n', encoding='utf-8')
        probe.report(f'S25 PASS earned upgrade {size}: actual first job {job_seconds:.1f}s, '
                     f'rifle/ammo equipped at {elapsed:.1f}s, {remaining} chits remain; no fixtures or income extrapolation')
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
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
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, args.show, tuple(map(int, args.size.split('x')))))
