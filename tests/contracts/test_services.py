"""Game 7.5: bounded public repairs survive reconnect and maintenance."""

from dataclasses import replace
import json

import pytest

from blacksite.content.schema import Allocation, Effect, ServiceNodeTemplate, Reward
from blacksite.server.contracts.engine import Engine
from blacksite.server.contracts.services import (
    ALLOCATION_SECONDS, FAULT_INTERVAL, FAULT_SECONDS, RESERVATION_SECONDS, Services,
)
from tests.contracts.test_engine import finish, party, template


def setup(sid: str = 'sump') -> tuple[Services, Engine]:
    job = template('repair-'+sid, service=True, crew_scaling=False,
                   reward=Reward((200, 200), {'wardens': 5}, xp=100))
    node = ServiceNodeTemplate(sid, sid, 'fixture', 'fixture-core', ('hardware',), (
        Allocation('common', 'Public service', (Effect('reveal', zone='fixture'),)),
        Allocation('reserve', 'Workers', (
            Effect('hazard', zone='fixture'),  # Public geometry remains visible to outsiders.
            Effect('cache', zone='fixture', audience='workers'),
        ))), contract=job.id, fault_effects=(Effect('price_modifier', zone='fixture'),))
    return Services('origin', {sid: node}), Engine('origin', {job.id: job})


def reserve(services: Services, engine: Engine, sid: str, choice: str = 'reserve', now: float = 3601):
    node = services.nodes[sid]
    services.reserve(sid, choice, tuple(p.player for p in party()), now, node.revision)
    offer = engine.offer(engine.templates[services.templates[sid].contract], node.order, node.reserved_until)
    return engine.accept(offer, party(), now)


@pytest.mark.parametrize('sid', ['sump', 'cold-chain', 'depot', 'zero'])
@pytest.mark.parametrize('choice', ['common', 'reserve'])
def test_game_7_5_each_service_fixed_rewards_allocation_and_original_cooldown(sid: str, choice: str) -> None:
    services, engine = setup(sid)
    assert services.advance(3599, 3599) == ()
    assert services.nodes[sid].state == 'normal'
    services.advance(3600, 1)
    instance = reserve(services, engine, sid, choice)
    assert len(instance.stages[0].targets) == 4  # No crew scaling.
    assert instance.expires_at == 4201
    assert engine.active_count('a') == 0
    finish(engine, instance.id, ('a', 'b'))
    assert services.complete(sid, instance, 3630)
    payouts = engine.claim(instance.id, 'a', 3630)
    assert [(p.payment.chits, p.payment.xp, p.payment.standing) for p in payouts] == [
        (220, 100, {'wardens': 5}), (200, 100, {'wardens': 5})]
    assert not services.complete(sid, instance, 3631)
    assert engine.claim(instance.id, 'a', 3631) == ()
    assert services.nodes[sid].allocation_expires == 4830
    with pytest.raises(ValueError, match='changed'):
        services.reserve(sid, 'common', ('b',), 3632, services.nodes[sid].revision)
    services.advance(4830, 1230)
    assert services.nodes[sid].state == 'normal'
    assert services.nodes[sid].next_fault_uptime == 7200
    services.advance(7200, 2370)
    second = reserve(services, engine, sid, choice, 7201)
    finish(engine, second.id, ('a', 'b'))
    services.complete(sid, second, 7230)
    assert len(engine.claim(second.id, 'a', 7230)) == 2  # Repeatable, not story helper.


def test_game_7_5_disconnect_restart_preserves_steps_and_original_deadline() -> None:
    services, engine = setup()
    services.advance(3600, 3600)
    instance = reserve(services, engine, 'sump')
    finish(engine, instance.id, ('a', 'b'))
    saved = json.loads(json.dumps({'services': services.record(), 'contracts': engine.record()}))
    restored = Services('origin', services.templates, saved['services'])
    contracts = Engine('origin', engine.templates, saved['contracts'])
    assert restored.advance(4199) == ()
    assert restored.uptime == 3600  # Offline time creates no backlog.
    assert contracts.instances[instance.id].state == 'complete'
    assert restored.nodes['sump'].reserved_until == 4201
    assert restored.advance(4201) == (instance.offer,)
    with pytest.raises(ValueError, match='reservation ended'):
        restored.complete('sump', contracts.instances[instance.id], 4201)
    assert restored.nodes['sump'].state == 'fault'
    restored.advance(4800)
    assert restored.nodes['sump'].state == 'normal'  # NPC repair, no player payout.
    assert not contracts.claims
    restored.advance(10**8)
    assert restored.nodes['sump'].state == 'normal'
    assert restored.nodes['sump'].next_fault_uptime == 7200


def test_game_7_5_reservation_race_and_frozen_roster_withdrawal() -> None:
    services, engine = setup()
    services.advance(3600, 3600)
    old_revision = services.nodes['sump'].revision
    instance = reserve(services, engine, 'sump')
    with pytest.raises(ValueError, match='changed'):
        services.reserve('sump', 'common', ('late',), 3602, old_revision)
    assert not services.withdraw('sump', instance.offer, 'late')
    assert services.withdraw('sump', instance.offer, 'a')
    assert services.nodes['sump'].state == 'repairing'
    assert services.nodes['sump'].workers == {'b'}
    assert services.withdraw('sump', instance.offer, 'b')
    assert services.nodes['sump'].state == 'fault'
    later = reserve(services, engine, 'sump', 'common', 3603)
    assert later.offer != instance.offer
    assert later.roster == instance.roster


def test_game_7_5_shared_cache_cannot_multiply_after_restart_or_crew_change() -> None:
    services, engine = setup('depot')
    services.advance(3600, 3600)
    instance = reserve(services, engine, 'depot')
    finish(engine, instance.id, ('a', 'b'))
    services.complete('depot', instance, 3630)
    assert [e.type for e in services.effects('depot', 'late', 3631)] == ['hazard']
    assert [e.type for e in services.effects('depot', 'a', 3631)] == ['hazard', 'cache']
    assert services.take_cache('depot', instance.offer, 'late', 2, 3631) == 0
    assert services.take_cache('depot', instance.offer, 'a', 1, 3631) == 1
    restored = Services('origin', services.templates, json.loads(json.dumps(services.record())))
    assert restored.take_cache('depot', instance.offer, 'b', 8, 3632) == 1
    assert restored.take_cache('depot', instance.offer, 'a', 1, 3632) == 0
    assert restored.take_cache('depot', instance.offer, 'a', 1, 4830) == 0
    assert restored.effects('depot', 'a', 4830) == ()


def test_game_7_5_time_step_and_discarded_draft_never_accumulate_offline_faults() -> None:
    services, engine = setup()
    draft = services.fork()
    draft.advance(100000, 4 * FAULT_INTERVAL)
    assert draft.nodes['sump'].generation == 1
    assert draft.nodes['sump'].next_fault_uptime == 5 * FAULT_INTERVAL
    assert draft.nodes['sump'].fault_expires == 100000 + FAULT_SECONDS
    reserve(draft, engine, 'sump', now=100001)
    assert services.uptime == 0 and services.nodes['sump'].state == 'normal'
    assert draft.nodes['sump'].reserved_until == 100001 + RESERVATION_SECONDS
    assert ALLOCATION_SECONDS == FAULT_SECONDS == 1200


def test_game_7_5_service_contracts_do_not_appear_on_regular_boards_or_use_job_slots() -> None:
    services, engine = setup()
    assert engine.board('wardens', 0) == ()
    ordinary = template('ordinary')
    engine.templates = {**engine.templates, ordinary.id: ordinary}
    for offer in engine.board('wardens', 1800)[:3]:
        engine.accept(offer, party(), 1800)
    assert engine.active_count('a') == 3
    services.advance(3600, 3600)
    instance = reserve(services, engine, 'sump')
    assert instance.service and not instance.story and not instance.scaling
    assert engine.active_count('a') == 3


def test_game_7_5_unfinished_or_wrong_contract_cannot_allocate_service() -> None:
    services, engine = setup()
    services.advance(3600, 3600)
    instance = reserve(services, engine, 'sump')
    with pytest.raises(ValueError, match='Finish'):
        services.complete('sump', instance, 3602)
    finish(engine, instance.id)
    with pytest.raises(ValueError, match='Finish'):
        services.complete('sump', replace(instance, roster=instance.roster[:1]), 3630)
