"""S25: actual Terraces letting, privacy, bed return and bank impound.

Uses the services probe's disclosed eligibility/funds. No room, placement,
item or content overlay. Only housing UTC advances 22 days after bed
logout; live transport, movement and the visitor's 30 seconds are real.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path
import traceback

from accept_s10_netbbs import Connection, wait
from accept_s16_netbbs import commit_key, key
from accept_s18_netbbs import bed, choose, reconnect
from accept_s25_services import ServiceProbe, prepare
from blacksite.server.clock import ManualClock


async def deposit(probe: ServiceProbe, caller: Connection, amount: int) -> None:
    zone = probe.service.world.zones[caller.avatar.zone]
    bank = next(o.spec.id for o in zone.objects.values() if o.spec.kind == 'bank')
    panel = await probe.counter(caller, bank, 'bank')
    await probe.row(caller, panel, 'deposit')
    await commit_key(probe, caller, b'\r', lambda: caller.session.id in probe.commerce.prompts)
    p = probe.game.players[caller.session.player_id]
    before = p.chits_bank
    await wait(lambda: 'Chits:' in caller.caller.screen.screen_text())
    await caller.caller.write(str(amount).encode()+b'\r')
    await wait(lambda: p.chits_bank == before+amount)
    await probe.close_menu(caller)


async def house(probe: ServiceProbe, size: tuple[int, int]) -> dict:
    caller = await prepare(probe, size, 'S25home')
    housing = probe.service.core.apartments
    p = probe.game.players[caller.session.player_id]
    units = housing.geometry.units
    assert len(units) == 24
    assert Counter(u.definition.id for u in units.values()) == {
        'apt_terrace_cell': 8, 'apt_terrace_flat': 8, 'apt_terrace_corner': 8}
    unit = next(u for u in units.values() if u.definition.id == 'apt_terrace_cell')
    for zid in ('vatside-clinics', 'core-tram-hub'):
        await probe.travel(caller, zid)
    assert p.chits_bank == 0
    await deposit(probe, caller, 300)
    await probe.travel(caller, 'tramyard-market')
    vendor = probe.game.content.vendors['kestrel-depot']
    panel = await probe.counter(caller, vendor.object_id)
    rifle = await probe.buy(caller, panel, 'wpn_halvard_hv7')
    await probe.close_menu(caller)
    await probe.travel(caller, 'core-tram-hub')
    await probe.travel(caller, 'terraces-blocks')
    zone = probe.service.world.zones[unit.zone]
    letting = next(o.spec.id for o in zone.objects.values() if o.spec.params.get('letting'))
    await probe.walk(caller, zone.objects[letting].spec.tile)
    await commit_key(probe, caller, b'e', lambda: caller.session.id in housing.menus)
    await choose(probe, caller, unit.id)
    probe.save(caller, 's25-real-24-unit-letting')
    await commit_key(probe, caller, b'\r', lambda: p.apartment_id is not None)
    assert p.chits_bank == 0 and housing.lease(p)['unit'] == unit.id
    await key(caller, b'\x1b')
    await wait(lambda: caller.session.id not in housing.menus)
    await probe.walk(caller, unit.anchor.doorstep)
    await commit_key(probe, caller, b'e', lambda: unit.region.contains(caller.avatar.actor.position))
    quality, secured = probe.commerce.items[rifle].quality, probe.commerce.items[rifle].secured
    await probe.walk(caller, unit.tile((0, 2)))
    await commit_key(probe, caller, b'e', lambda: caller.session.id in housing.menus)
    await choose(probe, caller, rifle)
    await commit_key(probe, caller, b'\r', lambda: rifle in housing.lease(p)['storage'])
    probe.save(caller, 's25-real-apartment-storage')
    await key(caller, b'\x1b')
    await wait(lambda: caller.session.id not in housing.menus)
    await probe.walk(caller, unit.tile(unit.anchor.vestibule))
    await commit_key(probe, caller, b'e', lambda: not unit.region.contains(caller.avatar.actor.position))
    # The peer walks to the actual public doorstep and first proves refusal.
    peer = await probe.open(*size, 'S25guest', 1, True)
    guest = probe.game.players[peer.session.player_id]
    await probe.walk(peer, (21, 14))
    await key(peer, b'b')
    await wait(lambda: guest.progress.get('wake_combat') == 'skipped')
    for zid in ('vatside-clinics', 'vatside-vat-row', 'terraces-blocks'):
        await probe.travel(peer, zid)
    # Leave the resident's doorstep free for the visitor's physical approach.
    away = probe.service.world.free_tile(unit.zone, unit.anchor.doorstep, caller.avatar.actor)
    await probe.walk(caller, away)
    await probe.walk(peer, unit.anchor.doorstep)
    await key(peer, b'e')
    await wait(lambda: 'Locked. Tier 1.' in peer.caller.screen.screen_text())
    assert not unit.region.contains(peer.avatar.actor.position)
    probe.save(peer, 's25-real-door-locked-guest')
    waiting_tile = probe.service.world.free_tile(unit.zone,
        (unit.anchor.doorstep[0]+3, unit.anchor.doorstep[1]), peer.avatar.actor)
    await probe.walk(peer, waiting_tile)
    # Transfer the actual issued key through a street cache, with real keys.
    issued = next(i for i in p.inventory if probe.commerce.items[i].key_for == p.apartment_id)
    await commit_key(probe, caller, b'i', lambda: caller.session.id in probe.commerce.menus)
    panel = probe.commerce.menus[caller.session.id]
    await probe.row(caller, panel, issued)
    await commit_key(probe, caller, b'd', lambda: issued not in p.inventory)
    cache = next(cid for cid, state in probe.commerce.caches.items() if issued in state['items'])
    await probe.close_menu(caller)
    # Move back inside; the visitor sees only the separate delivery vestibule.
    await probe.walk(caller, unit.anchor.doorstep)
    await commit_key(probe, caller, b'e', lambda: unit.region.contains(caller.avatar.actor.position))
    panel = await probe.counter(peer, cache, 'cache')
    await probe.row(peer, panel, issued)
    await commit_key(probe, peer, b'\r', lambda: issued in guest.inventory)
    await probe.close_menu(peer)
    await probe.walk(peer, unit.anchor.doorstep)
    await commit_key(probe, peer, b'e', lambda: peer.avatar.actor.position == unit.tile(unit.anchor.vestibule))
    vestibule = peer.avatar.actor.position
    await key(peer, b'\x1b[A')
    await asyncio.sleep(.3)
    assert peer.avatar.actor.position == vestibule
    probe.save(peer, 's25-real-visitor-private-boundary')
    await wait(lambda: not unit.region.contains(peer.avatar.actor.position), 35)
    probe.save(peer, 's25-real-visitor-thirty-second-expiry')
    await probe.leave(peer, 's25-real-guest-left')
    # Rent draws from both bank and hand. Use the actual safe, which rent
    # does not draw from, to make the later lapse genuine.
    saved_chits = p.chits_hand
    await probe.walk(caller, unit.tile((1, 2)))
    await commit_key(probe, caller, b'e', lambda: caller.session.id in housing.menus)
    await choose(probe, caller, 'safe_deposit')
    await commit_key(probe, caller, b'\r', lambda: caller.session.id in housing.prompts)
    await wait(lambda: 'Chits:' in caller.caller.screen.screen_text())
    await caller.caller.write(str(saved_chits).encode()+b'\r')
    await wait(lambda: p.chits_hand == 0 and housing.lease(p)['safe_chits'] == saved_chits)
    assert p.chits_bank == 0
    probe.save(caller, 's25-real-safe-chits-before-lapse')
    await key(caller, b'\x1b')
    await wait(lambda: caller.session.id not in housing.menus)
    await bed(probe, caller, unit, 's25-real-bed')
    caller = await reconnect(probe, caller, *size, expected_zone=zone.template.meta.name)
    assert unit.region.contains(caller.avatar.actor.position) and housing.lease(p)['unit'] == unit.id
    probe.save(caller, 's25-real-home-reconnect')
    await bed(probe, caller, unit, 's25-real-bed-before-lapse')
    # Explicit deadline fixture, restricted to housing after logout.
    clock = ManualClock(epoch=housing.clock.now_utc()+timedelta(days=22))
    housing.clock = housing.geometry.clock = clock
    probe.report('FIXTURE S25 housing: housing UTC +22 days after bed logout; game/NetBBS clocks unchanged.')
    caller = await reconnect(probe, caller, *size, expected_zone=zone.template.meta.name)
    await wait(lambda: p.apartment_id is None)
    assert not unit.region.contains(caller.avatar.actor.position)
    assert housing.state['impounds'][p.id]['items'][rifle]['fee'] == 34
    assert housing.state['impounds'][p.id]['chits'] == saved_chits
    probe.save(caller, 's25-real-eviction')
    await probe.travel(caller, 'core-tram-hub')
    bank = next(o.spec.id for o in probe.service.world.zones[caller.avatar.zone].objects.values()
                if o.spec.kind == 'bank')
    panel = await probe.counter(caller, bank, 'bank')
    await probe.row(caller, panel, 'impound')
    await commit_key(probe, caller, b'\r', lambda: caller.session.id in housing.menus)
    await choose(probe, caller, 'chits')
    await commit_key(probe, caller, b'\r', lambda: p.chits_bank == saved_chits)
    await choose(probe, caller, rifle)
    probe.save(caller, 's25-real-bank-impound-fee')
    await commit_key(probe, caller, b'\r', lambda: rifle in p.inventory)
    assert p.chits_bank == saved_chits-34 and probe.commerce.items[rifle].quality == quality
    assert probe.commerce.items[rifle].secured == secured and probe.commerce.items[rifle].owner == p.id
    await key(caller, b'\x1b')
    await wait(lambda: caller.session.id not in housing.menus)
    await probe.close_menu(caller)
    await probe.leave(caller, 's25-real-housing-left')
    return {'units': 24, 'classes': [8, 8, 8], 'signing': 300, 'keyed_vestibule_seconds': 30,
            'resident_storage_private': True, 'bed_reconnect': True, 'eviction': True,
            'safe_and_impound_chits': saved_chits, 'bank_reclaim_fee': 34,
            'stored_template': 'wpn_halvard_hv7', 'actual_rifle_purchase': True,
            'item_quality_and_security_preserved': True}


async def accept(root: Path, python: Path, show: bool, size: tuple[int, int]) -> None:
    probe = ServiceProbe(root, python, show)
    try:
        await probe.start()
        result = await house(probe, size)
        assert not probe.errors and probe.service.failure is None
        (root/'s25-housing.json').write_text(json.dumps({
            'passed': probe.server_start_seconds <= 3, 'functional_passed': True,
            'full_slice_acceptance': False, 'size': list(size), 'result': result,
            'transport': 'NetBBS Telnet -> registered native stdio',
            'fixtures': ['grade five', 'Halvard +30 admission standing', '12000 hand chits',
                         'housing UTC +22 days after bed logout'],
            'journeys': probe.journeys, 'walks': probe.walks}, indent=2)+'\n', encoding='utf-8')
        probe.report(f'S25 FUNCTIONAL PASS housing {size}: actual 24-unit map, storage, visitor, bed, eviction and bank reclaim')
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
