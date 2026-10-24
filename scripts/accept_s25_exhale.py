"""S25 actual Exhale key, carried-key passage and closed-layout recovery.

Real operator force/cancel, keys and persisted restart. Disclosed grade
and funding setup; no item, placement, reward or clock fixture.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import traceback

from accept_s10_netbbs import wait
from accept_s16_netbbs import commit_key
from accept_s18_netbbs import reconnect
from accept_s25_services import ServiceProbe, prepare
from blacksite.admin.client import request
from blacksite.server.app import Server


async def accept(root: Path, python: Path, show: bool, size: tuple[int, int]) -> None:
    assert not (root/'world').exists(), 'Use a fresh private acceptance world'
    probe = ServiceProbe(root, python, show)
    try:
        await probe.start()
        caller = await prepare(probe, size, 'S25breath')
        pid = caller.session.player_id
        player = probe.game.players[pid]
        assert not any(probe.commerce.items[i].template == 'key_undercity' for i in player.inventory)
        for destination in ('vatside-clinics', 'vatside-vat-row', 'under-service'):
            await probe.travel(caller, destination)
        listed = await request(probe.service.install_dir, 'event.list')
        assert listed['ok'], listed
        cleared = []
        for forecast in listed['plans']:
            if forecast['state'] == 'planned':
                cancelled = await request(probe.service.install_dir, 'event.cancel', {'plan': forecast['id']})
                assert cancelled['ok'], cancelled
                cleared.append(forecast['id'])
        forced = await request(probe.service.install_dir, 'event.force', {'event': 'exhale'})
        assert forced['ok'], forced
        plan = forced['plan']
        event_id = plan['id']
        await wait(lambda: any(cache.get('event') == event_id for cache in probe.commerce.caches.values()), 15)
        cache_id, cache = next((i, cache) for i, cache in probe.commerce.caches.items()
                               if cache.get('event') == event_id)
        assert cache['zone'] == 'under-service'
        key_id, = cache['items']
        assert probe.commerce.items[key_id].template == 'key_undercity'
        panel = await probe.counter(caller, cache_id, 'cache')
        await probe.row(caller, panel, key_id)
        await commit_key(probe, caller, b'\r', lambda: key_id in player.inventory)
        await probe.close_menu(caller)
        probe.save(caller, 's25-exhale-actual-key-acquired')
        for destination in ('under-drowned', 'under-caverns', 'under-outworks', 'under-drowned'):
            await probe.travel(caller, destination)
        # This is the credential-gated direction; the reverse stays free.
        before = tuple(player.inventory)
        await probe.travel(caller, 'under-outworks')
        assert key_id in player.inventory and tuple(player.inventory) == before
        zone = probe.service.world.zones['under-outworks']
        layout = next(layout for layout in zone.template.meta.layouts if layout.id == 'exhale-shortcut')
        passage = next(change.tile for change in layout.changes
                       if not zone.tiles[zone.template.tile_at(change.tile)].passable)
        await wait(lambda: zone.passable(passage), 15)
        await probe.walk(caller, passage)
        assert caller.avatar.actor.position == passage and caller.avatar.actor.health > 0
        probe.save(caller, 's25-exhale-open-wall-before-logout')
        await probe.leave(caller, 's25-exhale-unsafe-logout')
        # Keep the real sleeper interval: expiry would recover the body to
        # shelter and no longer exercise an unsafe saved position. A live
        # geometry guard may defer closure around the sleeper; restarting
        # restores the cancelled source's base wall from persisted state.
        await wait(lambda: pid in probe.game.sleepers)
        saved = probe.game.players[pid].tile
        assert tuple(saved) == passage, (saved, passage)
        cancelled = await request(probe.service.install_dir, 'event.cancel', {'plan': event_id})
        assert cancelled['ok'], cancelled
        assert probe.service.core.events.scheduler.plans[event_id].state == 'cancelled'
        await probe.service.stop()
        probe.service = Server(root/'world', tcp=True)
        await probe.service.start()
        probe.game = probe.service.core.characters
        probe.commerce = probe.service.core.commerce
        probe.combat = probe.service.core.combat
        assert not probe.service.world.zones['under-outworks'].passable(passage)
        caller = await reconnect(probe, caller, *size, expected_zone='Blacksite Outworks')
        actor = caller.avatar.actor
        zone = probe.service.world.zones['under-outworks']
        recovered = actor.position
        assert recovered != passage and not zone.passable(passage)
        assert zone.can_enter(actor, recovered) and not zone.tiles[zone.tile_id(recovered)].hazard
        assert key_id in probe.game.players[pid].inventory
        assert probe.commerce.items[key_id].template == 'key_undercity'
        # A recovered body must still be able to take the public return.
        await probe.travel(caller, 'under-caverns')
        probe.save(caller, 's25-exhale-reconnected-and-public-return')
        await probe.leave(caller, 's25-exhale-finished')
        assert not probe.errors and probe.service.failure is None
        (root/'s25-exhale.json').write_text(json.dumps({
            'passed': probe.server_start_seconds <= 3, 'functional_passed': True,
            'full_slice_acceptance': False, 'size': list(size), 'plan': plan,
            'actual_key': key_id, 'carried_key_retained': True,
            'saved_opening': list(passage), 'recovered_position': list(recovered),
            'public_return': 'under-caverns', 'real_server_restart': True,
            'clock_fixture': False, 'placement_fixture': False, 'item_fixture': False,
            'fixtures': ['grade five', 'Halvard +30 admission standing', '12000 hand chits'],
            'operator_actions': ['force exhale', 'cancel exact committed plan'],
            'cancelled_unpaid_startup_forecasts': cleared,
            'income_rate_claimed': False,
            'transport': 'NetBBS Telnet -> registered native stdio',
            'journeys': probe.journeys, 'walks': probe.walks}, indent=2)+'\n', encoding='utf-8')
        probe.report(f'S25 FUNCTIONAL PASS Exhale {size}: actual key, carried-key passage, closed-wall restart recovery')
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
