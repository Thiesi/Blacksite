"""S25 native purchases and surgery on the shipped city, without overlays.

Grade five, +30 Halvard standing and 12,000 hand chits are disclosed
eligibility/funding setup. Admission, travel, purchases and surgery use
real caller keys. This is not evidence of earning or acquisition pace.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import traceback
from typing import Any

from accept_s10_netbbs import Connection, wait
from accept_s16_netbbs import clinic, commit_key, key, select
from accept_s20_netbbs import admission, grade
from accept_s25_city import CityProbe


class ServiceProbe(CityProbe):
    async def counter(self, caller: Connection, object_id: str, kind: str = 'vendor') -> Any:
        zone = self.service.world.zones[caller.avatar.zone]
        await self.walk(caller, zone.objects[object_id].spec.tile)
        await commit_key(self, caller, b'e', lambda: caller.session.id in self.commerce.menus)
        panel = self.commerce.menus[caller.session.id]
        assert (panel.kind, panel.target) == (kind, object_id), (panel.kind, panel.target, object_id)
        return panel

    async def close_menu(self, caller: Connection, leave_key: bytes = b'\x1b') -> None:
        await commit_key(self, caller, leave_key, lambda: caller.session.id not in self.commerce.menus)
        name = self.service.world.zones[caller.avatar.zone].template.meta.name
        await wait(lambda: name in caller.caller.screen.screen_text().splitlines()[0])

    async def row(self, caller: Connection, panel: Any, row: str) -> None:
        await select(caller, lambda: self.commerce.body(caller.session, panel)['rows'], panel, row)

    async def buy(self, caller: Connection, panel: Any, template: str) -> str:
        p = self.game.players[caller.session.player_id]
        old = {i: self.commerce.items[i].stack for i in p.inventory
               if self.commerce.items[i].template == template}
        before = p.chits_hand
        await self.row(caller, panel, template)
        def bought() -> bool:
            return any(self.commerce.items[i].template == template
                       and self.commerce.items[i].stack > old.get(i, 0) for i in p.inventory)
        await commit_key(self, caller, b'\r', bought)
        assert p.chits_hand < before
        return next(i for i in p.inventory if self.commerce.items[i].template == template
                    and self.commerce.items[i].stack > old.get(i, 0))


async def prepare(probe: ServiceProbe, size: tuple[int, int], label: str) -> Connection:
    caller = await probe.open(*size, label, 0, True, card='halvard')
    grade(probe, caller)
    p = probe.game.players[caller.session.player_id]
    p.chits_hand = 12000
    p.standing['halvard'] = 30
    probe.game.queue('save', p.bbs_user_id, p, immediate=True)
    probe.service._character_writes()
    probe.report('FIXTURE S25 services: grade five, Halvard +30, 12000 hand chits; no item, placement, combat or game-clock fixtures.')
    await probe.walk(caller, (21, 14))
    await key(caller, b'b')
    await wait(lambda: p.progress.get('wake_combat') == 'skipped')
    await admission(probe, caller, 'halvard')
    return caller


async def rifle(probe: ServiceProbe, caller: Connection, size: tuple[int, int]) -> dict[str, Any]:
    for zid in ('vatside-clinics', 'core-plaza', 'core-tram-hub', 'tramyard-market'):
        await probe.travel(caller, zid)
    p = probe.game.players[caller.session.player_id]
    vendor = probe.game.content.vendors['kestrel-depot']
    panel = await probe.counter(caller, vendor.object_id)
    before = p.chits_hand
    gun = await probe.buy(caller, panel, 'wpn_halvard_hv7')
    gun_cost = before-p.chits_hand
    ammo = await probe.buy(caller, panel, 'ammo_5x')
    assert probe.commerce.items[ammo].stack > 0
    probe.save(caller, 's25-real-depot-purchase')
    # Sell an actual starter item against the real counter's resale budget.
    baton = next(i for i in p.inventory if probe.commerce.items[i].template == 'wpn_kestrel_baton')
    await commit_key(probe, caller, b't', lambda: panel.sell)
    await probe.row(caller, panel, baton)
    hand = p.chits_hand
    await commit_key(probe, caller, b'\r', lambda: baton not in p.inventory)
    assert p.chits_hand > hand
    await probe.close_menu(caller)
    await commit_key(probe, caller, b'i', lambda: caller.session.id in probe.commerce.menus)
    panel = probe.commerce.menus[caller.session.id]
    await probe.row(caller, panel, gun)
    await commit_key(probe, caller, b'q', lambda: p.equipment.get('weapon_main') == gun)
    await probe.close_menu(caller)
    probe.save(caller, 's25-real-rifle-equipped')
    bank = next(o.spec.id for o in probe.service.world.zones[caller.avatar.zone].objects.values()
                if o.spec.kind == 'bank')
    panel = await probe.counter(caller, bank, 'bank')
    await probe.row(caller, panel, 'deposit')
    await commit_key(probe, caller, b'\r', lambda: caller.session.id in probe.commerce.prompts)
    before = p.chits_hand, p.chits_bank
    await caller.caller.write(b'100\r')
    await wait(lambda: p.chits_bank == before[1]+100)
    assert p.chits_hand == before[0]-100
    await probe.row(caller, panel, 'withdraw')
    await commit_key(probe, caller, b'\r', lambda: caller.session.id in probe.commerce.prompts)
    await key(caller, b'\x1b')
    await wait(lambda: caller.session.id not in probe.commerce.prompts)
    assert (p.chits_hand, p.chits_bank) == (before[0]-100, before[1]+100)
    probe.save(caller, 's25-market-bank-cancel')
    await probe.close_menu(caller, b'b')
    assert (p.chits_hand, p.chits_bank) == (before[0]-100, before[1]+100)
    # A separate actual caller walks from the Wake; no peer placement or
    # inventory fixture can stand in for a street drop and pickup.
    peer = await probe.open(*size, 'S25peer', 1, True)
    peer_player = probe.game.players[peer.session.player_id]
    await probe.walk(peer, (21, 14))
    await key(peer, b'b')
    await wait(lambda: peer_player.progress.get('wake_combat') == 'skipped')
    for zid in ('vatside-clinics', 'core-plaza', 'core-tram-hub', 'tramyard-market'):
        await probe.travel(peer, zid)
    zone = probe.service.world.zones[caller.avatar.zone]
    drop = probe.service.world.free_tile(zone.id, (64, 15), caller.avatar.actor)
    await probe.walk(caller, drop)
    beside = probe.service.world.free_tile(zone.id, drop, peer.avatar.actor)
    assert max(abs(a-b) for a, b in zip(drop, beside)) == 1
    await probe.walk(peer, beside)
    patch = next(i for i in p.inventory if probe.commerce.items[i].template == 'con_sablier_patch')
    await commit_key(probe, caller, b'i', lambda: caller.session.id in probe.commerce.menus)
    panel = probe.commerce.menus[caller.session.id]
    await probe.row(caller, panel, patch)
    await commit_key(probe, caller, b'd', lambda: patch not in p.inventory)
    cache = next(cid for cid, state in probe.commerce.caches.items() if patch in state['items'])
    await probe.close_menu(caller)
    away = probe.service.world.free_tile(zone.id, drop, caller.avatar.actor)
    await probe.walk(caller, away)
    panel = await probe.counter(peer, cache, 'cache')
    await probe.row(peer, panel, patch)
    await commit_key(probe, peer, b'\r', lambda: patch in peer_player.inventory)
    assert patch not in p.inventory and probe.commerce.items[patch].owner == peer_player.id
    probe.save(peer, 's25-market-peer-picked-up-drop')
    await probe.close_menu(peer)
    await probe.leave(peer, 's25-market-peer-left')
    return {'rifle_price_paid': gun_cost, 'rifle_equipped': True, 'ammunition': 'ammo_5x',
            'actual_starter_item_sold': True, 'market_bank_deposit': 100, 'withdrawal_cancelled': True,
            'two_caller_market_drop_pickup': True, 'pending': ['actual earning pace']}


async def surgery(probe: ServiceProbe, caller: Connection, size: tuple[int, int]) -> dict[str, Any]:
    for zid in ('vatside-clinics', 'core-plaza', 'spire-atrium', 'spire-mezzanine'):
        await probe.travel(caller, zid)
    p = probe.game.players[caller.session.player_id]
    vendor = probe.game.content.vendors['halvard-security']
    panel = await probe.counter(caller, vendor.object_id)
    before = p.chits_hand
    arm = await probe.buy(caller, panel, 'imp_halvard_reflex_arm')
    cost = before-p.chits_hand
    probe.save(caller, 's25-member-reflex-arm-purchase')
    await probe.close_menu(caller)
    await probe.travel(caller, 'spire-shaft-head')
    await probe.inspect(caller, 'member')
    for zid in ('spire-mezzanine', 'spire-atrium', 'core-plaza', 'vatside-clinics'):
        await probe.travel(caller, zid)
    vendor = probe.game.content.vendors['sablier-clinic']
    await probe.walk(caller, probe.service.world.zones[caller.avatar.zone].objects[vendor.object_id].spec.tile)
    await clinic(probe, caller, 'install:'+arm+':arms1')
    clinics = probe.service.core.progression.clinics
    screen = clinics.menus[caller.session.id]
    quote = screen.quoted
    assert quote and quote.failure == .02
    probe.save(caller, 's25-owned-purchased-arm-sablier-quote')
    await commit_key(probe, caller, b'y', lambda: not screen.confirm)
    installed = p.implants.get('arms1') == arm
    # A natural failed operation is retained as a failed acceptance run.
    assert installed, 'Natural 2% surgery failure: retain the run and retry with a fresh real purchase.'
    assert probe.service.core.progression.modifiers(p).multiplier('weapon_cooldown_multiplier') == .9
    await key(caller, b'\x1b')
    await wait(lambda: caller.session.id not in clinics.menus)
    probe.save(caller, 's25-purchased-arm-installed')
    for zid in ('core-tram-hub', 'sink-rim', 'sink-terraces', 'sink-floor'):
        await probe.travel(caller, zid)
    vendor = probe.game.content.vendors['black-clinic']
    zone = probe.service.world.zones[caller.avatar.zone]
    await probe.walk(caller, zone.objects[vendor.object_id].spec.tile)
    await clinic(probe, caller, 'buy:imp_ostrom_lowlight:eyes')
    screen = clinics.menus[caller.session.id]
    quote = screen.quoted
    template = probe.game.content.items['imp_ostrom_lowlight']
    assert quote and quote.failure == .15 and quote.item_price == (template.base_price*6+9)//10
    probe.save(caller, 's25-real-black-clinic-quote')
    before = p.chits_hand, dict(p.implants)
    await key(caller, b'\x1b')
    await wait(lambda: caller.session.id not in clinics.menus)
    assert (p.chits_hand, p.implants) == before
    return {'reflex_arm_real_purchase': cost, 'sablier_installed': True,
            'weapon_cooldown_multiplier': .9, 'member_shaft_head_walk': True,
            'black_item_multiplier': .6, 'black_failure_disclosed': .15,
            'black_confirmation_cancelled': True, 'pending': ['actual acquisition pace']}


async def accept(root: Path, python: Path, show: bool, size: tuple[int, int], case: str) -> None:
    probe = ServiceProbe(root, python, show)
    try:
        await probe.start()
        caller = await prepare(probe, size, 'S25'+case)
        result = await {'rifle': rifle, 'surgery': surgery}[case](probe, caller, size)
        await probe.leave(caller, 's25-'+case+'-left')
        assert not probe.errors and probe.service.failure is None
        (root/'s25-services.json').write_text(json.dumps({
            'passed': True, 'full_slice_acceptance': False, 'case': case, 'size': list(size),
            'transport': 'NetBBS Telnet -> registered native stdio', 'result': result,
            'fixtures': ['grade five', 'Halvard +30 admission standing', '12000 hand chits'],
            'journeys': probe.journeys, 'walks': probe.walks}, indent=2)+'\n', encoding='utf-8')
        probe.report(f'S25 PASS {case} {size}: actual city services; disclosed eligibility/funds; earning pace remains pending')
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
    parser.add_argument('--case', choices=('rifle', 'surgery'), required=True)
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, args.show,
                       tuple(map(int, args.size.split('x'))), args.case))
