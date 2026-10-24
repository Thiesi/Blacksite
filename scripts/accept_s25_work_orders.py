"""S25 public repairs on their shipped maps, with real network encounters.

Discloses grade/funding and the S19 one-hour service-uptime setup. No
content overlay, supplied item, placement, ICE, reward or UTC fixture.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import deque
import json
from pathlib import Path
import time
import traceback
from typing import Any

from accept_s10_netbbs import Connection, wait
from accept_s16_netbbs import commit_key, key, select
from accept_s19_netbbs import board_row, close_jobs
from accept_s19_services import drive_job, enter_core, leave_network, network_stage
from accept_s25_services import ServiceProbe, prepare


class WorkOrderProbe(ServiceProbe):
    async def target(self, caller: Connection, actor_id: str) -> None:
        actor = caller.avatar.actor
        zone = self.service.world.zones[actor.zone]
        enemy = zone.actors.get(actor_id)
        began = time.monotonic()
        while (enemy and enemy.health > 0 and enemy.stance not in ('down', 'dead')
               and enemy.zone == actor.zone and self.combat.visible(actor, enemy)
               and actor.target != actor_id):
            assert time.monotonic()-began < 10, ('visible target selection stalled', actor_id)
            await key(caller, b'\t')
            # A moving patrol may leave sight before the acknowledgement.
            # Re-evaluate the live candidates instead of waiting for an
            # impossible selection of the old snapshot.
            await asyncio.sleep(.1)

    async def before_walk_step(self, caller: Connection) -> None:
        if getattr(self, 'combat_prepared', False):
            await clear_for_repair(self, caller)

    async def near(self, caller: Connection, object_id: str) -> None:
        zid = caller.avatar.zone
        if object_id not in self.service.world.zones[zid].objects:
            zid = next(zid for zid, zone in self.service.world.zones.items() if object_id in zone.objects)
        if caller.avatar.zone != zid:
            await self.route(caller, zid)
        await super().near(caller, object_id)

    async def route(self, caller: Connection, destination: str) -> None:
        origin = caller.avatar.zone
        pending, paths = deque([origin]), {origin: []}
        while pending and destination not in paths:
            zid = pending.popleft()
            for passage in self.service.world.zones[zid].template.meta.exits:
                if (passage.hidden or passage.requirement or passage.kind == 'cable'
                        or passage.target_zone in paths):
                    continue
                paths[passage.target_zone] = [*paths[zid], passage.target_zone]
                pending.append(passage.target_zone)
        assert destination in paths, (origin, destination)
        for zid in paths[destination]:
            await self.travel(caller, zid)


async def heal(probe: WorkOrderProbe, caller: Connection) -> None:
    player = probe.game.players[caller.session.player_id]
    actor = caller.avatar.actor
    if actor.health >= actor.health_max/2:
        return
    patch = next((iid for iid in player.inventory
                  if probe.commerce.items[iid].template == 'con_sablier_patch'), None)
    if patch:
        block = probe.game.content.items['con_sablier_patch'].consumable
        if player.progress.get('item_cooldowns', {}).get(block.cooldown_class, 0) > probe.service.clock.now_utc().timestamp():
            return
        before = probe.commerce.items[patch].stack
        await commit_key(probe, caller, b'i', lambda: caller.session.id in probe.commerce.menus)
        await probe.row(caller, probe.commerce.menus[caller.session.id], patch)
        last_hit = actor.cooldowns.get('last_hit')
        await commit_key(probe, caller, b'u', lambda: patch not in probe.commerce.items
                         or probe.commerce.items[patch].stack < before
                         or caller.session.id in probe.commerce.using
                         or actor.cooldowns.get('last_hit') != last_hit or actor.health <= 0)
        # Receipt of a use channel ends retries. Repeated U would restart
        # its timer; incoming damage cancels it under the ordinary rules.
        if caller.session.id in probe.commerce.using:
            await wait(lambda: caller.session.id not in probe.commerce.using or actor.health <= 0,
                       float(block.use_seconds)+3)
        assert actor.health > 0, 'Repair worker defeated while using medicine'
        await probe.close_menu(caller)


async def clear_for_repair(probe: WorkOrderProbe, caller: Connection) -> None:
    """Clear actual visible attackers before a damage-interrupted channel."""
    began = time.monotonic()
    while True:
        actor = caller.avatar.actor
        assert actor.health > 0, 'Repair worker defeated'
        zone = probe.service.world.zones[caller.avatar.zone]
        enemies = [other for other in zone.actors.values()
                   if other.stance not in ('down', 'dead') and other.health > 0
                   and probe.service.core.npcs.hostile(other, actor)
                   and probe.combat.visible(actor, other) and probe.combat.legal(actor, other)]
        if not enemies:
            await heal(probe, caller)
            return
        assert time.monotonic()-began < 120, 'Repair approach remains under attack'
        enemy = min(enemies, key=lambda other: ((other.x-actor.x)**2+(other.y-actor.y)**2, other.id))
        await probe.target(caller, enemy.id)
        while enemy.health > 0 and probe.combat.visible(actor, enemy):
            assert actor.health > 0, 'Repair worker defeated'
            assert time.monotonic()-began < 120, 'Repair approach remains under attack'
            await heal(probe, caller)
            await key(caller, b'f')
            await asyncio.sleep(.1)  # Normal tick delivery, not an accelerated clock.


async def equipment(probe: WorkOrderProbe, caller: Connection) -> None:
    panel = await probe.counter(caller, 'wake-outfitter')
    for _ in range(8):
        await probe.buy(caller, panel, 'con_sablier_patch')
    await probe.close_menu(caller)
    await probe.route(caller, 'tramyard-market')
    player = probe.game.players[caller.session.player_id]
    panel = await probe.counter(caller, probe.game.content.vendors['kestrel-depot'].object_id)
    gun = await probe.buy(caller, panel, 'wpn_halvard_hv7')
    vest = await probe.buy(caller, panel, 'arm_kestrel_vest')
    await probe.buy(caller, panel, 'ammo_5x')
    await probe.buy(caller, panel, 'ammo_5x')
    await probe.close_menu(caller)
    for iid, slot in ((gun, 'weapon_main'), (vest, 'body')):
        await commit_key(probe, caller, b'i', lambda: caller.session.id in probe.commerce.menus)
        panel = probe.commerce.menus[caller.session.id]
        await probe.row(caller, panel, iid)
        await commit_key(probe, caller, b'q', lambda: player.equipment.get(slot) == iid)
        await probe.close_menu(caller)
    # Sell the actual starter weapons this rifle replaces, keeping the
    # worker from hauling a redundant load through the flooded approach.
    panel = await probe.counter(caller, probe.game.content.vendors['kestrel-depot'].object_id)
    await commit_key(probe, caller, b't', lambda: panel.sell)
    for template in ('wpn_kestrel_sidearm', 'wpn_kestrel_baton'):
        iid = next(iid for iid in player.inventory if probe.commerce.items[iid].template == template)
        await probe.row(caller, panel, iid)
        await commit_key(probe, caller, b'\r', lambda: iid not in player.inventory)
    await probe.close_menu(caller)


async def network_equipment(probe: WorkOrderProbe, caller: Connection) -> None:
    """Buy a public five-slot loadout suitable for an interrupting patrol."""
    programs = ((0, 'prg_lance'), (2, 'prg_locksmith'), (3, 'prg_bunker'))
    await probe.route(caller, 'sodium-tin-halo')
    await probe.near(caller, 'vesper')
    owner = probe.service.core.contracts
    await commit_key(probe, caller, b'e', lambda: caller.session.id in owner.panels.menus)
    await commit_key(probe, caller, b'v', lambda: caller.session.id in probe.commerce.menus)
    panel = probe.commerce.menus[caller.session.id]
    player = probe.game.players[caller.session.player_id]
    for program in ('prg_lance', 'prg_bunker'):
        await probe.row(caller, panel, program)
        before = player.chits_hand
        await commit_key(probe, caller, b'\r', lambda: program in player.progress.get('known_programs', ()))
        assert player.chits_hand < before
    await probe.close_menu(caller)
    vendor = probe.game.content.vendors['oldworks-bench']
    await probe.route(caller, vendor.zone)
    panel = await probe.counter(caller, vendor.object_id)
    await probe.buy(caller, panel, 'item_rig_portable_ow_slab')
    for program in ('prg_locksmith',):
        await probe.row(caller, panel, program)
        before = player.chits_hand
        await commit_key(probe, caller, b'\r', lambda: program in player.progress.get('known_programs', ()))
        assert player.chits_hand < before
    await probe.close_menu(caller)
    zone = probe.service.world.zones[caller.avatar.zone]
    terminal = next(obj.spec.id for obj in zone.objects.values()
                    if obj.spec.kind == 'terminal' and not zone.allows_hostile(obj.spec.tile))
    await probe.near(caller, terminal)
    await key(caller, b'j')
    lattice = probe.service.core.lattice
    await wait(lambda: player.id in lattice.presences)
    presence = lattice.presences[player.id]
    assert lattice.public(presence) and not presence.instance
    encounter = lattice.encounters
    assert len(presence.rig) == 5
    # Unload the two starters before binding the two-slot attack. The
    # purchased deck holds attack, shield and Key without a fixture.
    for slot, program in ((0, None), (1, None), *programs):
        await commit_key(probe, caller, b'r', lambda: caller.session.id in encounter.menus)
        screen = encounter.menus[caller.session.id]
        await select(caller, lambda: encounter.rows(presence, screen), screen, str(slot))
        await commit_key(probe, caller, b'\r', lambda: screen.kind == 'binding')
        await select(caller, lambda: encounter.rows(presence, screen), screen, program or '')
        await commit_key(probe, caller, b'\r', lambda: presence.rig[slot] == program)
        assert player.rig['slots'][slot] == program
        await commit_key(probe, caller, b'\x1b', lambda: caller.session.id not in encounter.menus)
    await commit_key(probe, caller, b'3', lambda: presence.key_tier >= 2)
    probe.save(caller, 's25-real-public-locksmith-purchased-loaded-and-activated')
    await leave_network(probe, caller)


async def accept(root: Path, python: Path, show: bool, size: tuple[int, int],
                 sid: str, allocation: str) -> None:
    assert not (root/'world').exists(), 'Use a fresh private acceptance world'
    probe = WorkOrderProbe(root, python, show)
    try:
        await probe.start()
        # A real Ghost starter has a native rig and Pick/Umbrella. Their
        # ordinary ICE encounters are part of this proof, not loaned gear.
        caller = await prepare(probe, size, 'S25repair', archetype=1, membership=False)
        await equipment(probe, caller)
        probe.combat_prepared = True
        await network_equipment(probe, caller)
        owner = probe.service.core.contracts
        player = probe.game.players[caller.session.player_id]
        service = probe.game.content.services[sid]
        await probe.route(caller, service.zone)
        zone = probe.service.world.zones[service.zone]
        giver = probe.game.content.contracts[service.contract].giver
        board = next(obj.spec for obj in zone.objects.values()
                     if obj.spec.essential and obj.spec.params.get('contract_handler') == giver)
        # The same explicit uptime setup as S19 exposes the fault without
        # advancing UTC, NPCs, capture clocks or the caller's journey.
        draft = owner.state.fork()
        draft.services.advance(owner.now(), 3600)
        owner.write(draft)
        await wait(lambda: not probe.commerce.pending)
        assert owner.state.services.nodes[sid].state == 'fault'
        probe.report('FIXTURE S25 repair: 3600 seconds of service uptime only; grade/funds already disclosed; no item/placement/ICE/UTC fixture.')
        await probe.near(caller, board.id)
        panel = await board_row(probe, caller, 'service:'+sid)
        await commit_key(probe, caller, b'1' if allocation == 'common' else b'2',
                         lambda: panel.confirmation is not None)
        await commit_key(probe, caller, b'y', lambda: owner.state.services.nodes[sid].state == 'repairing')
        node = owner.state.services.nodes[sid]
        iid = next(job.id for job in owner.state.engine.instances.values() if job.offer == node.order)
        deadline = node.reserved_until
        await close_jobs(probe, caller)
        before = player.chits_hand, player.xp
        # Jack from a real public pocket, keeping the body off the repair
        # site's contested floor while the core encounter runs.
        terminals = [obj.spec.id for candidate in probe.service.world.zones.values()
                     if candidate.template.meta.sector == zone.template.meta.sector
                     for obj in candidate.objects.values()
                     if obj.spec.kind == 'terminal' and obj.spec.essential
                     and not candidate.allows_hostile(obj.spec.tile)
                     and obj.spec.params.get('contract_handler') == giver]
        terminal = 'cold-chain-loan-terminal' if sid == 'cold-chain' else min(terminals)
        await drive_job(probe, caller, iid, {'terminal': terminal, 'before_objective': clear_for_repair,
                                          'key_slot': 2, 'respect_gates': True,
                                          'keep_final_network': sid == 'relay-zero' and allocation == 'reserve'})
        node = owner.state.services.nodes[sid]
        assert node.state == 'allocated' and node.allocation == allocation
        assert player.chits_hand-before[0] == 200 and player.xp-before[1] >= 100
        layouts: list[dict[str, Any]] = []
        benefits: list[dict[str, Any]] = []
        choice = next(choice for choice in service.allocations if choice.id == allocation)
        for effect in choice.effects:
            if effect.type == 'route_hold':
                layout = next(layout for layout in zone.template.meta.layouts
                              if layout.id == effect.params['layout'])
                await wait(lambda: all(zone.tile_id(change.tile) == change.tile_id
                                       for change in layout.changes), 15)
                layouts.append({'id': layout.id, 'tiles': [
                    {'tile': list(change.tile), 'type': zone.tile_id(change.tile),
                     'movement_cost': zone.tiles[zone.tile_id(change.tile)].movement_cost}
                    for change in layout.changes]})
            elif effect.type == 'cache':
                await probe.route(caller, effect.zone)
                await probe.near(caller, effect.params['object'])
                def units() -> int:
                    return sum(probe.commerce.items[i].stack for i in player.inventory
                               if probe.commerce.items[i].template == 'slv_power'
                               and not probe.commerce.items[i].mission)
                original = units()
                await commit_key(probe, caller, b'e', lambda: units() == original+2)
                benefits.append({'cache': effect.params['object'], 'collected_power_units': 2})
            elif effect.type == 'reveal' and effect.params.get('what') == 'credential':
                assert effect.binding is not None
                control = probe.service.core.lattice.interlock.controls[
                    effect.binding.core, effect.binding.control]
                gate = zone.objects[control.target.object]
                assert not gate.open
                assert owner.effects.permits(player.id, effect.binding.core, effect.binding.control)
                await network_stage(probe, caller, effect.binding, {
                    'terminal': terminal, 'key_slot': 2, 'respect_gates': True})
                await wait(lambda: gate.open is True)
                await leave_network(probe, caller)
                await probe.route(caller, zone.id)
                await probe.walk(caller, zone.objects['relay-zero-hardware'].spec.tile)
                await probe.walk(caller, gate.spec.tile)
                await probe.counter(caller, probe.game.content.vendors['oldworks-bench'].object_id)
                await probe.close_menu(caller)
                benefits.append({'control': control.id, 'opened_and_walked': gate.spec.id})
            elif effect.type == 'reveal' and effect.params.get('what') == 'patrol_route':
                assert effect.binding is not None
                await enter_core(probe, caller, effect.binding.core, {
                    'terminal': terminal, 'key_slot': 2, 'respect_gates': True})
                patrols = owner.effects.patrols(player.id)
                assert patrols
                probe.save(caller, 's25-relay-zero-common-published-patrols')
                benefits.append({'published_patrols': patrols})
                await leave_network(probe, caller)
            elif effect.type == 'price_modifier' and effect.params.get('service') == 'buyback_budget':
                vendor = probe.game.content.vendors[effect.params['vendor']]
                await probe.route(caller, vendor.zone)
                await probe.counter(caller, vendor.object_id)
                factor = owner.effects.budget(vendor, vendor.zone+':'+vendor.object_id)
                assert factor == 2
                probe.save(caller, 's25-depot-common-real-surplus-counter')
                benefits.append({'vendor': vendor.id, 'buyback_budget_multiplier': factor})
                await probe.close_menu(caller)
            elif effect.type == 'price_modifier' and effect.params.get('service') == 'surgery':
                vendor = probe.game.content.vendors[effect.params['vendor']]
                await probe.route(caller, vendor.zone)
                await probe.near(caller, vendor.object_id)
                factor = owner.effects.fee(player, vendor)
                assert factor == (.9 if allocation == 'common' else .8)
                benefits.append({'vendor': vendor.id, 'surgery_fee_multiplier': factor})
        probe.save(caller, f's25-{sid}-{allocation}-real-repair-paid')
        await probe.route(caller, 'vatside-clinics')
        await probe.leave(caller, f's25-{sid}-{allocation}-public-return')
        assert not probe.errors and probe.service.failure is None
        (root/'s25-work-order.json').write_text(json.dumps({
            'passed': probe.server_start_seconds <= 3, 'functional_passed': True,
            'full_slice_acceptance': False, 'size': list(size), 'service': sid,
            'allocation': allocation, 'board': board.id, 'network_terminal': terminal,
            'purchased_network_program': 'prg_locksmith',
            'purchased_attack_program': 'prg_lance',
            'purchased_shield_program': 'prg_bunker',
            'purchased_portable_rig': 'item_rig_portable_ow_slab',
            'job': iid, 'reservation_deadline': deadline, 'layouts': layouts, 'benefits': benefits,
            'reward_chits': player.chits_hand-before[0], 'reward_xp': player.xp-before[1],
            'service_uptime_fixture_seconds': 3600, 'game_utc_fixture': False,
            'item_fixture': False, 'placement_fixture': False, 'ice_fixture': False,
            'fixtures': ['grade five', '12000 hand chits', 'one hour service uptime'],
            'faction_membership': False,
            'income_rate_claimed': False,
            'transport': 'NetBBS Telnet -> registered native stdio',
            'journeys': probe.journeys, 'walks': probe.walks}, indent=2)+'\n', encoding='utf-8')
        probe.report(f'S25 FUNCTIONAL PASS {sid}/{allocation} {size}: local board, real repair/core, payment and public return')
        probe.assert_start_budget()
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        if hasattr(probe, 'game') and 'caller' in locals():
            actor = caller.avatar.actor
            player = probe.game.players[caller.session.player_id]
            presence = probe.service.core.lattice.presences.get(player.id)
            (root/'failure-state.json').write_text(json.dumps({
                'zone': caller.avatar.zone, 'tile': list(actor.position),
                'health': actor.health, 'maximum_health': actor.health_max,
                'stance': actor.stance, 'rig': player.rig,
                'lattice': {'sector': presence.sector, 'cell': presence.cell,
                            'core': presence.core, 'room': presence.room} if presence else None,
                'inventory': [(probe.commerce.items[iid].template, probe.commerce.items[iid].stack)
                              for iid in player.inventory],
                'jobs': [{'template': job.template, 'state': job.state, 'index': job.index}
                         for job in probe.service.core.contracts.state.engine.instances.values()]},
                indent=2)+'\n', encoding='utf-8')
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
    parser.add_argument('--service', choices=('cold-chain', 'sump', 'depot', 'relay-zero'), required=True)
    parser.add_argument('--allocation', choices=('common', 'reserve'), required=True)
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, args.show,
                       tuple(map(int, args.size.split('x'))), args.service, args.allocation))
