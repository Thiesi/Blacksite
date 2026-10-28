"""S25: operator-forced Ring-fall on the actual populated Ring Three.

Uses disclosed service eligibility/funds, actual equipment purchases and
authenticated operator commands. No content, placement or clock fixture.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import traceback

from accept_s10_netbbs import wait
from accept_s16_netbbs import commit_key, key
from accept_s25_fabrication import OUTWARD
from accept_s25_services import ServiceProbe, prepare
from blacksite.admin.client import request


async def accept(root: Path, python: Path, show: bool, size: tuple[int, int]) -> None:
    assert not (root/'world').exists(), 'Use a fresh private acceptance world'
    probe = ServiceProbe(root, python, show)
    try:
        await probe.start()
        outward = (*OUTWARD, 'scour-ring-2', 'scour-ring-3')
        returning = ('scour-ring-2', 'scour-ring-1', 'scour-landing')
        origin = 'vatside-wake-hall'
        for destination in (*outward, *returning):
            assert any(ex.target_zone == destination for ex in
                       probe.service.world.zones[origin].template.meta.exits), (origin, destination)
            origin = destination
        caller = await prepare(probe, size, 'S25impact')
        player = probe.game.players[caller.session.player_id]
        for zid in outward:
            await probe.travel(caller, zid)
            if zid == 'tramyard-market':
                vendor = probe.game.content.vendors['kestrel-depot']
                panel = await probe.counter(caller, vendor.object_id)
                gun = await probe.buy(caller, panel, 'wpn_halvard_hv7')
                await probe.buy(caller, panel, 'ammo_5x')
                await probe.close_menu(caller)
                await commit_key(probe, caller, b'i', lambda: caller.session.id in probe.commerce.menus)
                panel = probe.commerce.menus[caller.session.id]
                await probe.row(caller, panel, gun)
                await commit_key(probe, caller, b'q', lambda: player.equipment.get('weapon_main') == gun)
                await probe.close_menu(caller)
        zid = 'scour-ring-3'
        # Stand on the actual convoy road, outside the authored impact sites.
        road = next(point.tile for route in probe.game.content.routes.values()
                    for point in route.waypoints if point.zone == zid)
        await probe.walk(caller, road)
        owner = probe.service.core.events
        # A fresh world's ordinary roll can already reserve this kind or
        # route. Use real operator cancellation of those unpaid forecasts;
        # forcing an event must not bypass the production reservation rules.
        listed = await request(probe.service.install_dir, 'event.list')
        assert listed['ok'], listed
        cleared = []
        for forecast in listed['plans']:
            if forecast['state'] == 'planned':
                cancelled = await request(probe.service.install_dir, 'event.cancel', {'plan': forecast['id']})
                assert cancelled['ok'], cancelled
                cleared.append(forecast['id'])
        result = await request(probe.service.install_dir, 'event.force', {'event': 'ring-fall', 'where': zid})
        assert result['ok'], result
        plan = result['plan']
        pid = plan['id']
        assert plan['where'] == [zid] and plan['forced']
        probe.save(caller, 's25-real-ring-three-impact-warning')
        await wait(lambda: any(current.id == pid for current in owner.active()), 15)
        def event_nodes() -> dict[str, int]:
            return {zone: sum(node.get('event') == pid for node in field['nodes'].values())
                    for zone, field in probe.service.core.salvage.state['zones'].items()}
        await wait(lambda: event_nodes().get(zid) == 10)
        counts = event_nodes()
        assert all(count == (10 if zone == zid else 0) for zone, count in counts.items()), counts
        await wait(lambda: any(actor.behaviour.get('event') == pid
                              for actor in probe.service.world.actors.values()))
        recovery = [actor for actor in probe.service.world.actors.values()
                    if actor.behaviour.get('event') == pid]
        assert recovery and all(actor.zone == zid and actor.faction == 'halvard' for actor in recovery)
        current = owner.scheduler.plans[pid]
        assert current.allocations['sites'] == plan['allocations']['sites']
        effects = owner.scheduler.effects(current)
        for index, site in current.allocations['sites'].items():
            effect = effects[int(index)]
            assert site['zone'] == zid and effect.region is not None
            assert effect.region.contains(tuple(site['tile']))
            assert all(effect.region.contains(tuple(tile)) for tile in site.get('tiles', ()))
            assert list(road) not in site.get('tiles', ())
        spawn_regions = [effect.region for effect in effects if effect.type == 'npc_spawn']
        assert all(any(region and region.contains(tuple(actor.behaviour['home']))
                       for region in spawn_regions) for actor in recovery)
        probe.save(caller, 's25-real-ring-three-extra-salvage')
        await key(caller, b'm')
        await wait(lambda: 'CITY MAP' in caller.caller.screen.screen_text())
        probe.save(caller, 's25-real-ring-three-event-overview')
        await key(caller, b'\x1b')
        await wait(lambda: caller.session.id not in probe.game.sim.maps)
        # The active encounter must retain the actual public return route.
        for destination in returning:
            await probe.travel(caller, destination)
        cancelled = await request(probe.service.install_dir, 'event.cancel', {'plan': pid})
        assert cancelled['ok'], cancelled
        assert owner.scheduler.plans[pid].state == 'cancelled'
        await probe.leave(caller, 's25-real-ringfall-left')
        assert not probe.errors and probe.service.failure is None
        (root/'s25-events.json').write_text(json.dumps({
            'passed': probe.server_start_seconds <= 3, 'functional_passed': True,
            'full_slice_acceptance': False, 'size': list(size), 'event_nodes': counts,
            'plan': plan, 'recovery': [{'id': actor.id, 'template': actor.behaviour['template'],
                                      'zone': actor.zone, 'faction': actor.faction,
                                      'home': actor.behaviour['home']} for actor in recovery],
            'public_return': list(returning), 'clock_fixture': False, 'placement_fixture': False,
            'fixtures': ['grade five', 'Halvard +30 admission standing', '12000 hand chits'],
            'operator_actions': ['force ring-fall --where scour-ring-3', 'cancel exact committed plan'],
            'cancelled_unpaid_startup_forecasts': cleared,
            'income_rate_claimed': False, 'transport': 'NetBBS Telnet -> registered native stdio',
            'journeys': probe.journeys, 'walks': probe.walks}, indent=2)+'\n', encoding='utf-8')
        probe.report(f'S25 FUNCTIONAL PASS Ring-fall {size}: actual Ring Three impact, recovery, ten scoped nodes and public return')
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
