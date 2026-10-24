"""S24 installed-wheel native stdio: forecasts, boundaries and restart.

Disclosed fixtures: event sites/S19 service bay, scheduler trigger/UTC
advance, grade/pools and Ferrymen Kin. Walking and menu/cast inputs are
real. This does not close S25 geography or S25/S26 human pacing gates.
"""

import argparse
import asyncio
from dataclasses import asdict
from datetime import timedelta
import json
from pathlib import Path
import traceback
from typing import Any

from accept_s10_netbbs import wait
from accept_s16_netbbs import commit_key, key
from accept_s19_netbbs import ContractProbe
from accept_s19_services import reconnect, enter_core, leave_network, reserve, drive_job
from accept_s23_netbbs import fixture, services
from events_fixture import build_fixture
from blacksite.admin.client import request
from blacksite.server.app import Server
from blacksite.server.clock import RealClock, TICK_HZ
from blacksite.server.rules.events import ROLL_SECONDS
from blacksite.server.storage.db import Storage


class FixtureClock(RealClock):
    def __init__(self) -> None:
        super().__init__()
        self.offset = 0.0

    def now_utc(self) -> Any:
        return super().now_utc()+timedelta(seconds=self.offset)


async def mutation(probe: Any, action: Any) -> None:
    await wait(lambda: not probe.commerce.pending and not probe.commerce.waiting)
    action()
    await wait(lambda: not probe.commerce.pending)


async def jump(probe: Any, seconds: float) -> None:
    def staged() -> None:
        owner = probe.service.core.events
        probe.service.clock.offset += seconds
        draft = owner.scheduler.fork()
        draft.last_roll = int(owner.now()//ROLL_SECONDS)
        transitions = draft.advance(owner.now(), owner.eligible)
        assert owner.write(draft, transitions)
    await mutation(probe, staged)


async def forecast(probe: Any, caller: Any, pid: str) -> dict[str, Any]:
    owner = probe.service.core.events
    terminal = next(obj.spec.id for obj in probe.service.world.zones[caller.avatar.zone].objects.values()
        if obj.spec.kind == 'terminal')
    await services(probe, caller, terminal)
    await commit_key(probe, caller, b'v', lambda: caller.session.id in owner.views.menus)
    panel = owner.views.menus[caller.session.id]
    plans = owner.views.plans(caller.session, panel)
    assert plans[panel.cursor].id == pid
    await commit_key(probe, caller, b'r', lambda: panel.selected == pid and not probe.commerce.pending)
    player = probe.game.players[caller.session.player_id]
    saved = dict(player.progress['event_forecasts'][pid])
    await wait(lambda: 'FORECASTS' in caller.caller.screen.screen_text())
    probe.save(caller, 's24-forecast-'+str(caller.session.caps['width']))
    for _ in range(2):
        before = panel.selected, caller.session.id in owner.views.menus
        await commit_key(probe, caller, b'\x1b', lambda: (panel.selected, caller.session.id in owner.views.menus) != before)
    return saved


async def restart(probe: Any, callers: list[Any], size: tuple[int, int]) -> list[Any]:
    for index, caller in enumerate(callers):
        await probe.leave(caller, 's24-before-restart-'+str(index))
    clock = probe.service.clock
    await probe.service.stop()
    probe.service = Server(probe.root/'world', tcp=True, clock=clock)
    await probe.service.start()
    probe.game, probe.commerce, probe.combat = (probe.service.core.characters,
        probe.service.core.commerce, probe.service.core.combat)
    return [await reconnect(probe, caller, *size) for caller in callers]


async def run(probe: Any, descriptor: dict[str, Any], size: tuple[int, int]) -> dict[str, Any]:
    width, height = size
    cantor = await probe.open(width, height, 'S24Cantor', 2, True)
    worker = await probe.open(width, height, 'S24Worker', 1, True)
    for caller in (cantor, worker):
        fixture(probe, caller, 5, 0)
    player = probe.game.players[cantor.session.player_id]
    assert player.archetype == 'cantor'
    assert probe.game.players[worker.session.player_id].archetype == 'ghost'
    player.faction, player.standing['ferrymen'] = 'ferrymen', 90
    probe.game.queue('save', player.bbs_user_id, player, immediate=True)
    probe.service._character_writes()
    owner = probe.service.core.events
    def publish() -> None:
        draft = owner.scheduler.fork()
        plan = draft.reserve(owner.content.events['ring-fall'], owner.now(), 241, owner.eligible)
        owner.effects.allocate(draft, plan)
        owner.jobs.allocate(draft, plan)
        assert owner.write(draft, [])
    await mutation(probe, publish)
    plan = next(plan for plan in owner.scheduler.reserved() if plan.template == 'ring-fall')
    pid, signature = plan.id, (plan.seed, plan.where, plan.starts_at, plan.allocations)
    assert plan.starts_at-plan.announced_at >= 3600
    saved = await forecast(probe, cantor, pid)
    assert owner.place(plan.where[0]) in saved['text']
    cantor, worker = await restart(probe, [cantor, worker], size)
    owner = probe.service.core.events
    resumed = owner.scheduler.plans[pid]
    assert (resumed.seed, resumed.where, resumed.starts_at, resumed.allocations) == signature
    assert probe.game.players[cantor.session.player_id].progress['event_forecasts'][pid] == saved
    await forecast(probe, cantor, pid)
    await jump(probe, max(0, resumed.starts_at-owner.now()+.1))
    await wait(lambda: any(plan.id == pid for plan in owner.active()), 12)
    nodes = probe.service.core.salvage.state['zones'][plan.where[0]]['nodes']
    assert sum(node.get('event') == pid for node in nodes.values()) == 10
    assert owner.scheduler.plans[pid].where == signature[1]
    probe.save(cantor, 's24-ring-source-'+str(width))
    probe.report(f'S24 PASS {width}x{height}: committed forecast survives restart; exact fixture ring adds ten nodes once')
    assert (await request(probe.service.install_dir, 'event.cancel', {'plan': pid}))['ok']

    await probe.route(cantor, 'core-plaza')
    result = await request(probe.service.install_dir, 'event.force', {'event': 'curfew'})
    assert result['ok'], result
    curfew = result['plan']['id']
    await wait(lambda: owner.curfew('core-plaza'), 12)
    assert not probe.service.world.zones[cantor.avatar.zone].allows_hostile(cantor.avatar.actor.position)
    # Reach the boundary along Vatside's public path. The general shortest
    # route to Sodium Row crosses the very Core restriction being tested.
    boundary = 'vatside-clinics'
    await probe.route(worker, boundary)
    zone = probe.service.world.zones[worker.avatar.zone]
    inbound = next(exit for exit in zone.template.meta.exits if exit.target_zone.startswith('core-'))
    await probe.walk(worker, inbound.tile)
    await key(worker, b'e')
    await wait(lambda: 'inbound Core' in worker.caller.screen.screen_text())
    assert worker.avatar.zone == zone.id
    probe.save(worker, 's24-curfew-inbound-'+str(width))
    await probe.travel(cantor, next(exit.target_zone for exit in probe.service.world.zones[cantor.avatar.zone].template.meta.exits
        if not exit.target_zone.startswith('core-') and exit.target_zone in probe.service.world.zones))
    assert not cantor.avatar.zone.startswith('core-')
    assert (await request(probe.service.install_dir, 'event.cancel', {'plan': curfew}))['ok']
    probe.report(f'S24 PASS {width}x{height}: actual outward Core journey completes and actual inbound attempt is refused; safety remains')

    await probe.route(cantor, descriptor['zone'])
    presence = await enter_core(probe, cantor, descriptor['core'], descriptor)
    encounters = probe.service.core.lattice.encounters
    ice = next(ice for ice in encounters.core(presence).ice.values() if ice.template.id == 'ice_ticker')
    damage, casting = ice.maximum-ice.integrity, ice.phase_origin
    start = probe.service.clock.now_tick()
    result = await request(probe.service.install_dir, 'event.force', {'event': 'choir-surge'})
    assert result['ok'], result
    surge = result['plan']['id']
    assert ice.template.id == 'ice_ticker'
    await wait(lambda: 'Surge in 5s' in cantor.caller.screen.screen_text())
    probe.save(cantor, 's24-surge-warning-'+str(width))
    await wait(lambda: ice.template.id == 'ice_ticker_surge', 12)
    assert probe.service.clock.now_tick()-start >= 5*TICK_HZ
    assert ice.maximum-ice.integrity == damage and ice.phase_origin == casting
    assert not ice.template.black
    probe.save(cantor, 's24-surge-active-'+str(width))
    probe.report(f'S24 PASS {width}x{height}: native local warning remains visible for the compatible five-second swap')
    await leave_network(probe, cantor)
    await wait(lambda: probe.commerce.ready(cantor.session)
        and cantor.session.id not in probe.game.sim.external_views)
    hymn = owner.content.hymns['hymn_steady']
    # Steady is learned at creation; quick keys remain deliberate choices.
    await commit_key(probe, cantor, b'v', lambda: cantor.session.id in probe.combat.menus)
    assert list(owner.content.hymns)[probe.combat.menus[cantor.session.id]] == hymn.id
    await commit_key(probe, cantor, b'1', lambda: probe.game.players[cantor.session.player_id].progress.get(
        'quick_abilities', {}).get('1') == hymn.id)
    await commit_key(probe, cantor, b'\x1b', lambda: cantor.session.id not in probe.combat.menus)
    cast_records = []
    effect = probe.combat.ability_effect
    def observed(player: Any, hymn: Any) -> dict[str, Any]:
        result = effect(player, hymn)
        cast_records.append((player.id, hymn.id, probe.service.clock.now_tick(), result))
        return result
    probe.combat.ability_effect = observed
    body = cantor.avatar.actor
    body.shock = 60
    body.cooldowns['last_hit'] = probe.service.clock.now_tick()
    await key(cantor, b'1')
    await wait(lambda: bool(cast_records))
    record = next(record for record in cast_records if record[0] == cantor.session.player_id and record[1] == hymn.id)
    assert record[3]['shock'] == hymn.effect['shock']*1.3
    assert body.shock <= 60+hymn.effect['shock']*1.3
    assert body.cooldowns['ability:'+hymn.id]-record[2] in (
        round(hymn.cooldown_seconds*TICK_HZ), round(hymn.cooldown_seconds*TICK_HZ)+1)
    probe.report(f'S24 PASS {width}x{height}: actual jack-in, five-second compatible swap and actual Cantor cast retain cooldown and +30% relief')

    await probe.route(worker, descriptor['zone'])
    contracts = probe.service.core.contracts
    def fault() -> None:
        draft = contracts.state.fork()
        draft.services.advance(contracts.now(), 3600)
        contracts.write(draft)
        assert probe.commerce.pending
    await mutation(probe, fault)
    iid = await reserve(probe, worker, 'sump', 'common')
    await drive_job(probe, worker, iid, descriptor)
    assert contracts.state.services.nodes['sump'].state == 'allocated'
    relays = probe.service.core.relays
    def ownership() -> None:
        draft = relays.ledger.fork()
        draft.set_owner('cold-chain', 'ferrymen', None, relays.now(), relays.rates())
        assert relays.write(draft, interlock=relays.ownership_patch('cold-chain', 'ferrymen'))
    await mutation(probe, ownership)
    exhale = await request(probe.service.install_dir, 'event.force', {'event':'exhale'})
    assert exhale['ok'], exhale
    eid = exhale['plan']['id']
    await wait(lambda: any(plan.id == eid for plan in owner.active()), 12)
    keys = {iid for iid, item in probe.commerce.items.items() if item.template == 'key_undercity'}
    assert len(keys) == 1
    allocation = asdict(contracts.state.services.nodes['sump'])
    cantor, worker = await restart(probe, [cantor, worker], size)
    owner = probe.service.core.events
    assert {iid for iid, item in probe.commerce.items.items() if item.template == 'key_undercity'} == keys
    assert owner.scheduler.plans[eid].ends_at == exhale['plan']['ends_at']
    assert (await request(probe.service.install_dir, 'event.cancel', {'plan':eid}))['ok']
    contracts = probe.service.core.contracts
    assert asdict(contracts.state.services.nodes['sump']) == allocation
    assert probe.service.core.relays.owner('cold-chain') == 'ferrymen'
    bay = probe.service.world.zones[descriptor['zone']]
    assert bay.passable(tuple(descriptor['shortcut'])) and bay.passable((25,12))
    assert not any(name.startswith('event:') for name in bay.layers)
    probe.save(worker, 's24-composed-cancel-'+str(width))
    probe.report(f'S24 PASS {width}x{height}: real service allocation and relay ownership survive event restart/cancel; one key receipt')
    for index, caller in enumerate((cantor,worker)):
        await probe.leave(caller, 's24-left-'+str(index))
    return dict(passed=True,size=list(size),forecast=pid,forecast_restart=True,forecast_source_ring=signature[1],
        ring_nodes=10,curfew_inbound_refused=True,curfew_outbound_completed=True,curfew_safety=True,
        surge_warning_seconds=5,surge_compatible=True,cantor_actual_cast=True,cantor_actual_shock_relief=True,
        cantor_cooldown_unchanged=True,
        sump_actual_allocation=True,relay_owner_retained=True,exhale_restart_keys=1,
        event_cancel_preserves_other_sources=True,placement_fixture=False,
        future_geography='S25 pending',human_pacing='S25/S26 pending')


async def accept(root: Path, python: Path, show: bool, size: tuple[int, int]) -> None:
    shipped = Path(__file__).parents[1]/'src/blacksite/content'
    descriptor = build_fixture(shipped, root/'world/content.local')
    clock = FixtureClock()
    # Suppress only the initial random roll; explicit source publication and
    # later UTC jumps below exercise normal scheduler/receipt paths.
    store = Storage(root/'world/world.db', clock)
    try:
        store.mark_dirty('meta','events_state',{'last_roll':int(clock.now_utc().timestamp()//ROLL_SECONDS)})
        store.flush_now()
    finally:
        store.close()
    probe = ContractProbe(root, python, show)
    probe.service = Server(root/'world', tcp=True, clock=clock)
    await probe.start()
    probe.sent_keys = []
    try:
        probe.report('S24 fixtures: event sites/S19 bay, explicit roll and UTC advance, grade/pools and +90 Ferrymen Kin. No placement, progress, reward, defeat or combat-clock fixture.')
        result = await run(probe, descriptor, size)
        assert not probe.errors and probe.service.failure is None
        (root/'s24-results.json').write_text(json.dumps({'passed':True,'run':result,
            'transport':'NetBBS Telnet -> registered native stdio',
            'fixtures':descriptor['event_fixtures']+['S19 service bay','roll trigger/UTC advance','grade/pools','Ferrymen +90'],
            'placement_fixture':False,'human_pacing':'S25/S26 pending'},indent=2)+'\n',encoding='utf-8')
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
    finally:
        (root/'input-trace.json').write_text(json.dumps(probe.sent_keys,indent=2)+'\n',encoding='utf-8')
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--door-python',type=Path,required=True)
    parser.add_argument('--show',action='store_true')
    parser.add_argument('--size',choices=('80x24','132x50'),required=True)
    args = parser.parse_args()
    asyncio.run(accept(args.root,args.door_python,args.show,tuple(map(int,args.size.split('x')))))
