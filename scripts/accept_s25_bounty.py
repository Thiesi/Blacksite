"""S25: complete the S23 bounty handoff in the actual Sink Rim.

Reuses its disclosed grade/full-pool/banked-funds setup. Equipment,
market settlement, tram routes, combat and bounty payout use real keys.
No content, item, placement, reward or clock fixture.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import traceback
from typing import Any

from accept_s23_netbbs import run_case
from accept_s25_services import ServiceProbe


async def accept(root: Path, python: Path, show: bool, size: tuple[int, int]) -> None:
    assert not (root/'world').exists(), 'Use a fresh private acceptance world'
    probe = ServiceProbe(root, python, show)
    received: list[dict[str, Any]] = []
    try:
        await probe.start()
        probe.sent_keys = []
        receive = probe.service.core.receive
        def traced_receive(session: Any, frame: Any) -> None:
            if frame.type in ('key', 'intent', 'line'):
                received.append({'session': session.id, 'player': session.player_id,
                                 'type': frame.type, 'data': frame.data})
            receive(session, frame)
        probe.service.core.receive = traced_receive
        probe.report('FIXTURE S25 bounty: S23 grade/full pools and banked funds; no item, placement, reward or clock fixture.')
        result = await run_case(probe, *size, bounty_zone='sink-rim')
        assert result['passed'] and result['actual_combat_zone'] == 'sink-rim'
        assert not probe.errors and probe.service.failure is None
        (root/'s25-bounty.json').write_text(json.dumps({
            'passed': probe.server_start_seconds <= 3, 'functional_passed': True,
            'full_slice_acceptance': False, 'size': list(size), 'result': result,
            'fixtures': ['grade/full pools', 'banked funds'], 'placement_fixture': False,
            'item_fixture': False, 'clock_fixture': False, 'income_rate_claimed': False,
            'transport': 'NetBBS Telnet -> registered native stdio',
            'journeys': probe.journeys, 'walks': probe.walks}, indent=2)+'\n', encoding='utf-8')
        probe.report(f'S25 FUNCTIONAL PASS bounty {size}: actual Sink Rim travel, targeted death and 200-chit settlement')
        probe.assert_start_budget()
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        (root/'input-trace.json').write_text(json.dumps({
            'sent': getattr(probe, 'sent_keys', []), 'received': received}, indent=2)+'\n', encoding='utf-8')
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
