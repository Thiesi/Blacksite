"""S23: installed native trading and a real contested-zone bounty kill.

Fixtures: grades/full pools and banked funds only. Routes, inventory,
market forms, collection, targeting, firing and death use keys.
No item, placement, reward, capture-clock or future-map fixture.
"""

import argparse
import asyncio
import json
from pathlib import Path
import traceback
from typing import Any

from accept_s10_netbbs import Connection, wait
from accept_s16_netbbs import commit_key, key, select
from accept_s19_netbbs import ContractProbe
from blacksite.admin.client import request
from blacksite.server.rules.character import grade_threshold


async def close_market(probe: ContractProbe, caller: Connection) -> None:
    await commit_key(probe, caller, b'\x1b', lambda: caller.session.id not in probe.service.core.market.views.menus)


async def choose(probe: ContractProbe, caller: Connection, value: bytes,
                 row: str | None = None, completed: Any = None) -> None:
    owner = probe.service.core.market
    panel = owner.views.menus[caller.session.id]
    if row is not None:
        await select(caller, lambda: owner.views.rows(caller.session, panel), panel, row)
    def state() -> tuple[Any, ...]:
        return (panel.kind, panel.mine, dict(panel.form), panel.confirmation,
                owner.views.prompts.get(caller.session.id))
    before = state()
    # Reissue only an unchanged choice when a timed view overtakes its ack.
    await commit_key(probe, caller, value, completed or (lambda: state() != before))


async def services(probe: ContractProbe, caller: Connection, terminal: str) -> None:
    await probe.near(caller, terminal)
    await commit_key(probe, caller, b'\x1b[20~', lambda: caller.session.id in probe.service.core.market.views.menus)
    assert probe.service.core.market.views.menus[caller.session.id].kind == 'terminal'


async def market(probe: ContractProbe, caller: Connection, terminal: str) -> None:
    await services(probe, caller, terminal)
    await choose(probe, caller, b'm')
    await wait(lambda: probe.service.core.market.views.menus[caller.session.id].kind == 'market')


async def amount(probe: ContractProbe, caller: Connection, field: str,
                 label: str, value: str) -> None:
    owner = probe.service.core.market
    await wait(lambda: owner.views.prompts.get(caller.session.id, ('', ''))[1] == field)
    await wait(lambda: label.lower() in caller.caller.screen.screen_text().lower())
    await key(caller, value.encode()+b'\r')


async def confirm(probe: ContractProbe, caller: Connection, completed: Any) -> None:
    await wait(lambda: probe.service.core.market.views.menus[caller.session.id].confirmation is not None)
    await commit_key(probe, caller, b'y', completed)
    await wait(lambda: not probe.commerce.pending)


async def list_item(probe: ContractProbe, caller: Connection, iid: str,
                    price: str = '50', buyout: str = '100') -> str:
    owner = probe.service.core.market
    before = set(owner.market.listings)
    await choose(probe, caller, b'l')
    await wait(lambda: owner.views.menus[caller.session.id].kind == 'items')
    await choose(probe, caller, b'\r', iid)
    await amount(probe, caller, 'price', 'Asking chits', price)
    await amount(probe, caller, 'buyout', 'Buyout chits', buyout)
    await wait(lambda: owner.views.menus[caller.session.id].kind == 'expiry')
    await choose(probe, caller, b'\r', '86400')
    await wait(lambda: 'Net at ask:' in caller.caller.screen.screen_text())
    if (price, buyout) == ('50', '100'):
        assert 'Net at ask: 47.' in caller.caller.screen.screen_text()
        assert 'Buyout net: 95.' in caller.caller.screen.screen_text()
    await confirm(probe, caller, lambda: bool(set(owner.market.listings)-before))
    return (set(owner.market.listings)-before).pop()


async def prepare_weapon(probe: ContractProbe, caller: Connection) -> str:
    player = probe.game.players[caller.session.player_id]
    slot, iid = next((slot, iid) for slot, iid in player.equipment.items()
                     if probe.game.content.items[probe.commerce.items[iid].template].weapon)
    await commit_key(probe, caller, b'i', lambda: caller.session.id in probe.commerce.menus)
    await commit_key(probe, caller, b'e', lambda: probe.commerce.menus[caller.session.id].kind == 'equipment')
    screen = probe.commerce.menus[caller.session.id]
    await select(caller, lambda: probe.commerce.body(caller.session, screen)['rows'], screen, slot)
    await commit_key(probe, caller, b'\r', lambda: iid not in player.equipment.values() and not probe.commerce.pending)
    await commit_key(probe, caller, b'\x1b', lambda: caller.session.id not in probe.commerce.menus)
    if probe.commerce.items[iid].secured:
        await commit_key(probe, caller, b'i', lambda: caller.session.id in probe.commerce.menus)
        screen = probe.commerce.menus[caller.session.id]
        await select(caller, lambda: probe.commerce.body(caller.session, screen)['rows'], screen, iid)
        await commit_key(probe, caller, b's', lambda: not probe.commerce.items[iid].secured and not probe.commerce.pending)
        await commit_key(probe, caller, b'\x1b', lambda: caller.session.id not in probe.commerce.menus)
    assert probe.service.core.market.listable(player, probe.commerce.items[iid])
    return iid


def fixture(probe: ContractProbe, caller: Connection, grade: int, bank: int) -> None:
    player = probe.game.players[caller.session.player_id]
    player.update_progression(grade_threshold(grade))
    player.update_personhood(probe.game.identities[player.bbs_user_id], probe.service.clock.now_utc())
    player.chits_bank = bank
    probe.service.core.progression.sync_actor(player)
    actor = caller.avatar.actor
    player.health = actor.health = actor.health_max
    player.stamina = actor.stamina = actor.stamina_max
    player.shock = actor.shock = 0
    probe.game.snapshot(player, caller.avatar)
    probe.game.queue('save', player.bbs_user_id, player, immediate=True)
    probe.service._character_writes()


async def run_case(probe: ContractProbe, width: int, height: int) -> dict[str, Any]:
    callers = []
    for label, grade, bank in (('S23Seller', 5, 1000), ('S23Buyer', 5, 100),
                                ('S23Hunter', 5, 1000), ('S23Wake', 2, 0)):
        caller = await probe.open(width, height, label, 0, True)
        send, sid = caller.caller.write, caller.session.id
        async def traced_write(data: bytes, send: Any = send, sid: str = sid) -> None:
            probe.sent_keys.append({'session': sid, 'hex': data.hex()})
            await send(data)
        caller.caller.write = traced_write
        fixture(probe, caller, grade, bank)
        callers.append(caller)
        # Leave the gurney free for the next actual caller.
        await probe.walk(caller, probe.service.world.free_tile(caller.avatar.zone, (10+2*len(callers), 10)))
    seller, buyer, hunter, wake = callers
    probe.report(f'S23 {width}x{height}: four actual callers ready')
    pa, pb, pc, pd = [probe.game.players[c.session.player_id] for c in callers]
    owner = probe.service.core.market
    iid = await prepare_weapon(probe, seller)
    original = probe.commerce.items[iid].record()
    await probe.route(seller, 'core-plaza')
    terminal = 'plaza-public-1'
    await market(probe, seller, terminal)
    probe.report(f'S23 {width}x{height}: seller reaches actual public services')
    lid = await list_item(probe, seller, iid)
    await choose(probe, seller, b'm')
    await wait(lambda: owner.views.menus[seller.session.id].mine)
    await wait(lambda: 'MY LISTINGS' in seller.caller.screen.screen_text())
    probe.save(seller, f's23-listed-{width}')
    assert probe.commerce.items[iid].owner == 'market'

    await probe.route(buyer, 'sodium-tin-halo')
    terminal_b = next(o.spec.id for o in probe.service.world.zones[buyer.avatar.zone].objects.values() if o.spec.kind == 'terminal')
    await market(probe, buyer, terminal_b)
    await wait(lambda: pa.bbs_handle in buyer.caller.screen.screen_text())
    await choose(probe, buyer, b'd', lid)
    await amount(probe, buyer, 'bid', 'Bid chits', '60')
    await confirm(probe, buyer, lambda: owner.market.highest(lid) is not None)
    assert pb.chits_bank == 40
    probe.save(buyer, f's23-bid-{width}')
    await choose(probe, seller, b'k', lid)
    await confirm(probe, seller, lambda: 'active bid' in seller.caller.screen.screen_text().lower())
    assert owner.market.listings[lid].status == 'open' and pb.chits_bank == 40
    await choose(probe, buyer, b'u', lid)
    await confirm(probe, buyer, lambda: owner.market.listings[lid].status == 'sold')
    assert (pa.chits_bank, pb.chits_bank) == (1095, 0)
    totals = owner.core.relays.record()['factions']['kestrel']
    assert totals['treasury'] == 5 and totals['influence'] == 0
    status = await request(probe.service.install_dir, 'status')
    assert status['treasury']['kestrel'] == 5
    assert probe.commerce.items[iid].owner == 'impound:'+pb.id
    assert owner.lat.interlock.state['impounds'][pb.id]['items'][iid] == {'fee': 0, 'source': 'market'}
    probe.save(buyer, f's23-buyout-{width}')
    await close_market(probe, seller)
    await close_market(probe, buyer)

    await probe.route(buyer, 'vatside-clinics')
    bank = next(o.spec.id for o in probe.service.world.zones[buyer.avatar.zone].objects.values() if o.spec.kind == 'bank')
    # Adjacent hardware has its own E card. Stand on the public till so
    # the actual nearest-object interaction selects banking unambiguously.
    await probe.walk(buyer, probe.service.world.zones[buyer.avatar.zone].objects[bank].spec.tile)
    await commit_key(probe, buyer, b'e', lambda: buyer.session.id in probe.commerce.menus)
    assert probe.commerce.menus[buyer.session.id].kind == 'bank'
    await commit_key(probe, buyer, b'c', lambda: buyer.session.id in owner.views.menus)
    await choose(probe, buyer, b'\r', iid)
    await confirm(probe, buyer, lambda: iid in pb.inventory)
    assert pb.chits_bank == 0 and probe.commerce.items[iid].owner == pb.id
    collected = probe.commerce.items[iid].record()
    assert {k: v for k, v in collected.items() if k != 'owner'} == {k: v for k, v in original.items() if k != 'owner'}
    probe.save(buyer, f's23-collected-{width}')
    await close_market(probe, buyer)
    probe.report(f'S23 PASS {width}x{height}: real routes, listing, escrow 60, net buyout 40, 95/5 settlement and exact free bank collection')

    await services(probe, seller, terminal)
    await choose(probe, seller, b'o')
    await wait(lambda: owner.views.menus[seller.session.id].kind == 'bounties')
    await choose(probe, seller, b'p')
    await wait(lambda: owner.views.menus[seller.session.id].kind == 'targets')
    await choose(probe, seller, b'\r', pb.id)
    await amount(probe, seller, 'bounty', 'Bounty chits', '200')
    await confirm(probe, seller, lambda: bool(owner.bounties.rows))
    bounty = next(iter(owner.bounties.rows.values()))
    assert pa.chits_bank == 895 and bounty.target == pb.id and bounty.chits == 200
    probe.save(seller, f's23-bounty-{width}')
    await close_market(probe, seller)

    await probe.route(hunter, 'vatside-clinics')
    await probe.walk(buyer, (32, 18))
    await probe.walk(hunter, (33, 18))
    zone = probe.service.world.zones[buyer.avatar.zone]
    assert zone.template.meta.safety == 'contested' and zone.allows_hostile(buyer.avatar.actor.position)
    await probe.target(hunter, pb.id)
    async with asyncio.timeout(100):
        while owner.bounties.rows[bounty.id].status == 'active':
            # F attacks using the normal carried-ammo rules. R opens rigs.
            await key(hunter, b'f')
            await asyncio.sleep(.2)
    await wait(lambda: not probe.commerce.pending)
    bounty = owner.bounties.rows[bounty.id]
    assert bounty.status == 'claimed' and bounty.claimed_by == pc.id
    assert pc.chits_bank == 1200 and pb.chits_bank == 0
    cache = next(c for c in probe.commerce.caches.values() if iid in c['items'])
    assert cache['victim'] == pb.id and cache['killer'] == pc.id
    probe.save(hunter, f's23-claimed-{width}')
    probe.report(f'S23 PASS {width}x{height}: actual targeted fire/death pays 200; victim cache rights retained')

    await services(probe, seller, terminal)
    await choose(probe, seller, b'o')
    await wait(lambda: owner.views.menus[seller.session.id].kind == 'bounties')
    assert not owner.views.rows(seller.session, owner.views.menus[seller.session.id])
    await choose(probe, seller, b'p')
    await wait(lambda: owner.views.menus[seller.session.id].kind == 'targets')
    await choose(probe, seller, b'\r', pd.id,
                 lambda: 'Nobody pays for a Wake.' in seller.caller.screen.screen_text())
    await wait(lambda: 'Nobody pays for a Wake.' in seller.caller.screen.screen_text())
    assert pa.chits_bank == 895 and len(owner.bounties.rows) == 1
    probe.save(seller, f's23-wake-refused-{width}')
    await close_market(probe, seller)
    result = {'passed': True, 'size': [width, height], 'listing': lid, 'item': iid,
        'seller': pa.id, 'buyer': pb.id, 'hunter': pc.id, 'bounty': bounty.id,
        'escrow': 60, 'extra_buyout': 40, 'seller_sale': 95, 'treasury': 5,
        'buyer_bank': 0, 'seller_bank': 895, 'hunter_bank': 1200,
        'exact_instance': True, 'free_collection': True, 'active_bid_cancel_refused': True,
        'wake_bounty_refused': True, 'victim_cache_rights': True,
        'actual_combat_zone': 'vatside-clinics', 'future_sink_geography': 'S25 pending'}
    for index, caller in enumerate(callers):
        await probe.leave(caller, f's23-left-{index}-{width}')
    return result


async def accept(root: Path, python: Path, show: bool, size: tuple[int, int]) -> None:
    probe = ContractProbe(root, python, show)
    await probe.start()
    probe.sent_keys = []
    received: list[dict[str, Any]] = []
    receive = probe.service.core.receive
    def traced_receive(session: Any, frame: Any) -> None:
        if frame.type in ('key', 'intent', 'line'):
            received.append({'session': session.id, 'player': session.player_id,
                             'type': frame.type, 'data': frame.data})
        receive(session, frame)
    probe.service.core.receive = traced_receive
    try:
        probe.report('S23 fixtures: grade 5/full pools/banked funds for three callers; grade 2 for one. No item, placement, reward or future-map fixture.')
        result = await run_case(probe, *size)
        assert not probe.errors and probe.service.failure is None
        (root/'s23-results.json').write_text(json.dumps({'passed': True, 'run': result,
            'transport': 'NetBBS Telnet -> registered native stdio',
            'fixtures': ['grade/full pools', 'banked funds'], 'placement_fixture': False,
            'item_fixture': False, 'human_pacing': 'S25/S26 pending'}, indent=2)+'\n', encoding='utf-8')
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        (root/'input-trace.json').write_text(json.dumps({'sent': probe.sent_keys,
            'received': received}, indent=2)+'\n', encoding='utf-8')
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--size', choices=('80x24', '132x50'), required=True)
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, args.show, tuple(map(int,args.size.split('x')))))
