"""Game 9.2/9.3: acquired evidence and scoped publication consequences."""

from dataclasses import replace
import json
from pathlib import Path

from blacksite.content.loader import ContentTree
from blacksite.content.schema import Bundle, EvidenceRecord, Permit, PublicationOption, Reward, StageTarget
from blacksite.server.contracts.engine import Fact
from blacksite.server.contracts.ledger import Ledger
from tests.contracts.test_engine import finish, party, template


def ledger() -> Ledger:
    target = StageTarget('core_control', core='warehouse', control='entry')
    options = (
        PublicationOption('private', 'Deliver privately', 'handler', Reward((400, 400), xp=200),
                          Permit('maintenance_credential', 'warehouse', 1200, target)),
        PublicationOption('public', 'Publish route', 'public', Reward((200, 200), xp=200),
                          Permit('route', 'warehouse', 1200, target)),
    )
    job = template(story=True, branch_group='ration', publication_options=options,
                   evidence_assets=('record',))
    evidence = EvidenceRecord('record', 'optional-prose', 'The consignment IDs match.',
        'A signed manifest', 'The loads go to reserve.', related_objective='clear', related_stage='resolve',
        question='Who changed the destination?', next_action='Bring the record to the handler.')
    content = ContentTree(Path('.'), None, contracts={job.id: job}, evidence={evidence.id: evidence})
    return Ledger('origin', content)


def test_game_9_2_verified_objective_acquires_separate_source_claim_without_reading_prose() -> None:
    state = ledger()
    job = state.engine.templates['clear']
    instance = state.engine.accept(state.engine.story_offer(job.id, 'a'), party(), 0)
    target = instance.stages[0].targets[0]
    fact = Fact('a', 'clear', 'defeated', target, 'npc1', 'defeat1', instance=instance.id,
                resolution='lethal', contributors=('b', 'late'))
    assert not state.observe(replace(fact, actor='late', contributors=()), 1)
    assert not state.journal
    assert state.observe(fact, 2) == (instance.id,)
    assert set(state.journal) == {'a', 'b'}
    row = state.journal['a']['record']
    assert row['observation'] == 'The consignment IDs match.'
    assert row['claim'] == 'The loads go to reserve.'
    assert row['question'] and row['next_action'] and row['location']['zone'] == 'fixture'
    assert row['observed_at'] == 2 and row['publication'] == ''
    assert not state.observe(fact, 3)
    assert state.journal['a']['record']['observed_at'] == 2


def test_game_9_2_public_permit_is_global_and_one_job_cannot_extend_it_per_worker() -> None:
    state = ledger()
    instance = state.engine.accept(state.engine.story_offer('clear', 'a'), party(), 0)
    finish(state.engine, instance.id, ('a', 'b'))
    state.claim(instance.id, 'a', 30, 'public')
    target = StageTarget('core_control', core='warehouse', control='entry')
    assert state.permits_target('late', 'route', target, 31)
    assert not state.permits_target('late', 'route', replace(target, control='other'), 31)
    restored = Ledger('origin', state.content, json.loads(json.dumps(state.record())))
    restored.claim(instance.id, 'b', 100, 'public')
    assert not restored.permits_target('late', 'route', target, 1230)
    assert restored.permits_target('late', 'route', target, 1229)
    restored.expire(1230)
    assert not restored.permits


def test_game_9_3_private_credential_and_publication_live_only_in_committed_draft() -> None:
    state = ledger()
    instance = state.engine.accept(state.engine.story_offer('clear', 'a'), party(), 0)
    target = instance.stages[0].targets[0]
    evidence = state.content.evidence['record']
    state.acquire('a', evidence, target, 1, instance.id)
    finish(state.engine, instance.id, ('a', 'b'))
    draft = state.fork()
    draft.claim(instance.id, 'a', 30, 'private')
    gate = StageTarget('core_control', core='warehouse', control='entry')
    assert draft.permits_target('a', 'maintenance_credential', gate, 31)
    assert not draft.permits_target('b', 'maintenance_credential', gate, 31)
    assert draft.journal['a']['record']['publication'] == 'private'
    assert state.journal['a']['record']['publication'] == '' and not state.permits


def test_game_9_5_inactive_authored_contract_cannot_publish_a_board() -> None:
    state = ledger()
    # Bundle membership is the actual production activation boundary.
    state.content.bundles['future'] = Bundle('future', 'authoring', {'contracts': ('clear',)})
    inactive = Ledger('origin', state.content)
    assert not inactive.engine.templates
