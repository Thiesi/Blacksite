"""S25: real Scour salvage, Landing crafting and Old Works filtering.

No content, item, funds, grade, placement or clock fixtures. The planner
knows node coordinates; its times do not measure human exploration.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import time
import traceback
from typing import Any

from accept_s10_netbbs import Connection, wait
from accept_s16_netbbs import commit_key, key, use
from accept_s25_services import ServiceProbe


async def clear_hostiles(probe: ServiceProbe, caller: Connection) -> None:
    actor = caller.avatar.actor
    async with asyncio.timeout(60):
        while True:
            zone = probe.service.world.zones[actor.zone]
            enemies = [other for other in zone.actors.values()
                       if other.stance not in ('down', 'dead')
                       and probe.service.core.npcs.hostile(other, actor)
                       and probe.combat.visible(actor, other)
                       and probe.combat.legal(actor, other)]
            if not enemies:
                return
            assert actor.health > 0, 'The actual salvage caller was defeated'
            enemy = min(enemies, key=lambda other: (
                (other.x-actor.x)**2+(other.y-actor.y)**2, other.id))
            await probe.target(caller, enemy.id)
            await caller.caller.write(b'f')
            await asyncio.sleep(.2)


async def run(probe: ServiceProbe, size: tuple[int, int]) -> dict[str, Any]:
    caller = await probe.open(*size, 'S25salvage', 0, True, card='none')
    player = probe.game.players[caller.session.player_id]
    assert player.chits_hand == 200 and player.chits_bank == 0 and player.grade == 1
    began = time.monotonic()
    await probe.walk(caller, (21, 14))
    await key(caller, b'b')
    await wait(lambda: player.progress.get('wake_combat') == 'skipped')
    for zid in ('vatside-clinics', 'core-tram-hub', 'tramyard-market',
                'tramyard-depots', 'tramyard-wall-gate', 'scour-ring-1'):
        await probe.travel(caller, zid)
    fab = probe.service.core.fabrication
    field = probe.service.core.salvage.state['zones']['scour-ring-1']
    harvest_began = time.monotonic()
    # Use natural committed nodes, including their actual amounts and RNG.
    async with asyncio.timeout(660):
        while fab.amounts(player).get('hull', 0) < 3:
            nodes = [(oid, node) for oid, node in field['nodes'].items()
                     if node['grade'] == 'hull']
            if not nodes:
                await asyncio.sleep(1)
                field = probe.service.core.salvage.state['zones']['scour-ring-1']
                continue
            oid, node = min(nodes, key=lambda pair: (
                abs(pair[1]['tile'][0]-caller.avatar.actor.x)
                + abs(pair[1]['tile'][1]-caller.avatar.actor.y), pair[0]))
            await probe.walk(caller, tuple(node['tile']))
            await clear_hostiles(probe, caller)
            before = fab.amounts(player).get('hull', 0)
            await commit_key(probe, caller, b'e', lambda: player.id in fab.channels)
            await wait(lambda: fab.amounts(player).get('hull', 0) >= 3
                       or player.id not in fab.channels, 20)
            assert fab.amounts(player).get('hull', 0) > before, 'Harvest was interrupted before a unit'
            field = probe.service.core.salvage.state['zones']['scour-ring-1']
        await key(caller, b'b')
        await wait(lambda: player.id not in fab.channels)
    harvested = fab.amounts(player)['hull']
    harvest_seconds = time.monotonic()-harvest_began
    probe.save(caller, 's25-real-ring-one-three-hull')
    await probe.travel(caller, 'scour-landing')
    vendor = probe.game.content.vendors['landing-trade']
    panel = await probe.counter(caller, vendor.object_id)
    before_chits = player.chits_hand
    schematic = await probe.buy(caller, panel, 'sch_ring_wrench')
    schematic_cost = before_chits-player.chits_hand
    await probe.close_menu(caller)
    await use(probe, caller, schematic)
    assert 'sch_ring_wrench' in player.progress['known_schematics']
    zone = probe.service.world.zones[caller.avatar.zone]
    shop = next(obj.spec for obj in zone.objects.values() if obj.spec.kind == 'workshop')
    await probe.walk(caller, shop.tile)
    await commit_key(probe, caller, b'e', lambda: caller.session.id in fab.menus)
    old = set(player.inventory)
    await commit_key(probe, caller, b'f', lambda: player.id in fab.channels)
    await wait(lambda: any(iid not in old and probe.commerce.items[iid].template == 'wpn_ferry_wrench'
                          for iid in player.inventory), 10)
    made = next(probe.commerce.items[iid] for iid in player.inventory
                if iid not in old and probe.commerce.items[iid].template == 'wpn_ferry_wrench')
    assert .85 <= made.quality <= 1.15 and fab.amounts(player)['hull'] == harvested-2
    await key(caller, b'i')
    await wait(lambda: caller.session.id in probe.commerce.menus)
    panel = probe.commerce.menus[caller.session.id]
    await probe.row(caller, panel, made.id)
    await wait(lambda: f'Damage {26*made.quality:g}' in caller.caller.screen.screen_text())
    probe.save(caller, 's25-real-landing-crafted-quality')
    await probe.close_menu(caller)
    panel = await probe.counter(caller, vendor.object_id)
    await commit_key(probe, caller, b't', lambda: panel.sell)
    hull = next(iid for iid in player.inventory if probe.commerce.items[iid].template == 'slv_hull')
    await probe.row(caller, panel, hull)
    before_chits = player.chits_hand
    await commit_key(probe, caller, b'\r', lambda: player.chits_hand == before_chits+18)
    await probe.close_menu(caller)
    probe.save(caller, 's25-real-landing-eighteen-chit-hull-sale')
    for zid in ('scour-ring-1', 'tramyard-wall-gate', 'tramyard-depots',
                'tramyard-market', 'core-tram-hub', 'oldworks-main', 'oldworks-yards'):
        await probe.travel(caller, zid)
    zone = probe.service.world.zones[caller.avatar.zone]
    shop = next(obj.spec for obj in zone.objects.values() if obj.spec.kind == 'workshop')
    await probe.walk(caller, shop.tile)
    await commit_key(probe, caller, b'e', lambda: caller.session.id in fab.menus)
    before_inputs = fab.amounts(player)
    await key(caller, b'f')
    await wait(lambda: 'rigs and programs only' in caller.caller.screen.screen_text())
    assert player.id not in fab.channels and fab.amounts(player) == before_inputs
    probe.save(caller, 's25-real-oldworks-fabrication-refusal')
    await key(caller, b'b')
    await wait(lambda: caller.session.id not in fab.menus)
    result = {'harvested_hull': harvested, 'harvest_and_approach_seconds': harvest_seconds,
              'schematic_paid': schematic_cost, 'crafted_quality': made.quality,
              'hull_sale': 18, 'oldworks_filter': True, 'elapsed_seconds': time.monotonic()-began,
              'remaining_chits': player.chits_hand, 'human_exploration_measured': False,
              'income_rate_extrapolated': False}
    await probe.leave(caller, 's25-real-fabrication-left')
    return result


async def accept(root: Path, python: Path, show: bool, size: tuple[int, int]) -> None:
    probe = ServiceProbe(root, python, show)
    try:
        await probe.start()
        result = await run(probe, size)
        assert not probe.errors and probe.service.failure is None
        (root/'s25-fabrication.json').write_text(json.dumps({
            'passed': probe.server_start_seconds <= 3, 'functional_passed': True,
            'full_slice_acceptance': False, 'size': list(size), 'fixtures': [],
            'transport': 'NetBBS Telnet -> registered native stdio', 'result': result,
            'journeys': probe.journeys, 'walks': probe.walks}, indent=2)+'\n', encoding='utf-8')
        probe.report(f'S25 FUNCTIONAL PASS fabrication {size}: actual Ring One harvest, Landing purchase/craft/sale and Old Works refusal')
        probe.assert_start_budget()
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
