"""Game 7.5: actual owned geometry, worker benefits and durable resale caps."""

from dataclasses import asdict, replace
from contextlib import closing
from math import ceil
import sqlite3

import pytest

from blacksite.content.schema import Allocation, Effect, ObjectSpec, StageTarget, TileChange, ZoneLayout
from blacksite.server.clinics import Operation
from blacksite.server.storage.db import Storage
from blacksite.server.vendors import VendorBudget
from blacksite.server.world.zone import ObjectState
from tests.contracts.test_adapter import live, shipped
from tests.contracts.test_service_adapter import service, start


def change(owner, sid, **values):
    node = replace(owner.content.services[sid], **values)
    owner.content.services[sid] = node
    owner.state.services.templates[sid] = node


def test_game_7_5_budget_cap_changes_keep_spending_even_above_the_smaller_cap() -> None:
    budget = VendorBudget(0)
    budget.refill(100, 4000)
    budget.spend(3800)
    budget.refill(200, 2000)
    assert budget.remaining == 0 and budget.spent == 3800
    restored = VendorBudget(**asdict(budget))
    restored.refill(300, 4000)
    assert restored.remaining == 200
    restored.refill(3600, 2000)
    assert restored.remaining == 2000 and restored.spent == 0


def test_architecture_15_2_budget_spending_survives_sqlite_restart_and_failed_cap_write(live, tmp_path) -> None:
    game, owner, callers, players = live
    budget = VendorBudget(0)
    budget.refill(100, 4000)
    budget.spend(3800)
    effect = {'player': None, 'items': [], 'delete_items': [], 'caches': {}, 'serial': 0,
              'budgets': {'fixture:surplus': asdict(budget)}}
    with closing(Storage(tmp_path/'budget.db', game.clock)) as store:
        store.commerce_write(effect)
        budget.refill(200, 2000)
        effect['budgets']['fixture:surplus'] = asdict(budget)
        store.db.execute("""CREATE TRIGGER fail_caps BEFORE INSERT ON meta
            WHEN NEW.key = 'vendor_budget_state'
            BEGIN SELECT RAISE(ABORT, 'fixture caps failure'); END""")
        with pytest.raises(sqlite3.IntegrityError, match='caps failure'):
            store.commerce_write(effect)
        assert store.character_state()['commerce']['budgets']['fixture:surplus']['remaining'] == 200
        store.db.execute('DROP TRIGGER fail_caps')
        store.commerce_write(effect)
    with closing(Storage(tmp_path/'budget.db', game.clock)) as store:
        restored = VendorBudget(**store.character_state()['commerce']['budgets']['fixture:surplus'])
        restored.refill(300, 4000)
        assert restored.remaining == 200 and restored.spent == 3800


def test_game_7_5_service_route_warns_and_expiry_preserves_an_independent_layer(live) -> None:
    game, owner, callers, players = live
    sid, target = service(live)
    zone = owner.world.zones[target.zone]
    layout = ZoneLayout('fixture-service-route', (TileChange((22, 4), 'wall'),),
                        ((22, 4),), (zone.template.meta.exits[0].id,))
    independent = ZoneLayout('fixture-event-route', (TileChange((23, 4), 'wall'),))
    zone.template = replace(zone.template, meta=replace(zone.template.meta,
                            layouts=(*zone.template.meta.layouts, layout, independent)))
    zone.schedule_layout('event:fixture', independent.id, game.clock.now_tick(), 50000)
    change(owner, sid, fault_effects=(Effect('route_hold', zone=zone.id, warning_seconds=5,
                                           params={'layout': layout.id}),), safe_return='Use the public hall.')
    owner.effects.compose(game.clock.now_tick())
    assert zone.passable((22, 4))
    game.clock.advance(50)
    owner.effects.compose(game.clock.now_tick())
    assert not zone.passable((22, 4)) and not zone.passable((23, 4))
    game.clock.advance(12000)
    owner.state.services.advance(owner.now())
    owner.effects.compose(game.clock.now_tick())
    assert zone.passable((22, 4)) and not zone.passable((23, 4))
    assert 'event:fixture' in zone.layers


def test_game_7_5_reserve_cache_is_shared_scoped_and_receipt_backed(live) -> None:
    game, owner, callers, players = live
    sid, target = service(live)
    actor = game.core.combat.actor(players[0])
    obj = ObjectSpec('fixture-reserve-cache', actor.position, 'cache')
    owner.world.zones[actor.zone].objects[obj.id] = ObjectState(obj)
    change(owner, sid, allocations=(Allocation('common', 'Public'),
        Allocation('reserve', 'Workers', (Effect('cache', zone=actor.zone, audience='workers',
                                                params={'object': obj.id}),))))
    proposal = owner.propose_service(players[0].id, sid, 'reserve', (players[0].id,))
    owner.consent(proposal.id, players[0].id)
    owner.start(proposal.id, players[0].id)
    game.commit_commerce()
    instance = next(iter(owner.state.engine.instances.values()))
    owner.actions.perform(callers[0].session, instance.id, target)
    game.commit_commerce()
    before = sum(item.template == 'slv_power' for item in owner.commerce.items.values())
    assert not owner.effects.cache(callers[1].session)
    assert owner.effects.cache(callers[0].session)
    game.commit_commerce(error=True)
    assert owner.state.services.nodes[sid].cache_taken == 0
    assert owner.effects.cache(callers[0].session)
    game.commit_commerce()
    assert sum(item.template == 'slv_power' for item in owner.commerce.items.values())-before == 2
    with pytest.raises(ValueError, match='empty'):
        owner.effects.cache(callers[0].session)


def test_game_7_5_clinic_discount_changes_service_only_and_reserve_excludes_other_workers(live) -> None:
    game, owner, callers, players = live
    sid, target = service(live)
    vendor = next(vendor for vendor in owner.content.vendors.values() if vendor.clinic == 'sablier')
    item = next(template for entry in vendor.stock if (template := owner.content.items.get(entry.item))
        and template.implant and not template.implant.portable and template.implant.slot not in ('rig', 'arms')
        and not template.implant.requires and template.class_ != 'resonance')
    op = Operation('fixture-install', 'install', item.id, item.implant.slot)
    baseline = owner.progression.clinics.quote(players[0], vendor, op)
    effects = (Effect('price_modifier', zone=target.zone, audience='workers',
                      params={'service': 'surgery', 'multiplier': .8}),)
    change(owner, sid, allocations=(Allocation('common', 'Public'), Allocation('reserve', 'Workers', effects)))
    proposal = owner.propose_service(players[0].id, sid, 'reserve', (players[0].id,))
    owner.consent(proposal.id, players[0].id)
    owner.start(proposal.id, players[0].id)
    game.commit_commerce()
    instance = next(iter(owner.state.engine.instances.values()))
    owner.actions.perform(callers[0].session, instance.id, target)
    game.commit_commerce()
    bill = owner.progression.clinics.quote(players[0], vendor, op)
    assert bill.service_price == ceil(baseline.service_price*.8)
    assert (bill.item_price, bill.removal_price, bill.failure) == (baseline.item_price, baseline.removal_price, baseline.failure)
    assert owner.progression.clinics.quote(players[1], vendor, op).service_price == baseline.service_price


def test_game_7_5_reserve_credential_binds_one_gate_and_expires_without_ice_immunity(live) -> None:
    game, owner, callers, players = live
    sid, target = service(live)
    binding = StageTarget('core_control', core='lat-civic-ledger', control='hall-doors')
    change(owner, sid, allocations=(Allocation('common', 'Public'), Allocation('reserve', 'Workers',
        (Effect('reveal', audience='workers', binding=binding, params={'what': 'credential'}),))))
    proposal = owner.propose_service(players[0].id, sid, 'reserve', (players[0].id,))
    owner.consent(proposal.id, players[0].id)
    owner.start(proposal.id, players[0].id)
    game.commit_commerce()
    instance = next(iter(owner.state.engine.instances.values()))
    owner.actions.perform(callers[0].session, instance.id, target)
    game.commit_commerce()
    assert owner.control_permit(players[0].id, binding.core, binding.control)
    assert not owner.control_permit(players[1].id, binding.core, binding.control)
    assert not owner.control_permit(players[0].id, binding.core, 'other-gate')
    game.clock.advance(12000)
    assert not owner.control_permit(players[0].id, binding.core, binding.control)
