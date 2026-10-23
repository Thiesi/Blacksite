"""Game 9: accepted terms, verified facts and durable reward proposals."""

from dataclasses import replace
import json
from typing import Any

import pytest

from blacksite.content.schema import (
    ContractApproach, ContractTemplate, Permit, PublicationOption, Reward, Stage, StageTarget,
)
from blacksite.server.contracts.engine import Engine, Fact, Participant, objective_count


def template(tid: str = 'clear', **changes: Any) -> ContractTemplate:
    target = StageTarget('npc', zone='fixture', npc='fixture-drone')
    stage = Stage('resolve', 'clear', target, 'interact', 'defeated', tid+':resolve',
                  resolution='lethal', quantity=4)
    return replace(ContractTemplate(tid, 'wardens', stages=(stage,),
        reward=Reward((200, 200), {'wardens': 5}, xp=200), min_grade=1), **changes)


def party() -> tuple[Participant, ...]:
    return (Participant('a', 'bbs-a', 5, 'operator'), Participant('b', 'bbs-b', 7))


def test_game_9_3_parallel_crew_story_copies_cannot_pay_a_character_twice() -> None:
    job = template('parallel-story', story=True)
    engine = Engine('origin', {job.id: job})
    first = engine.accept(engine.story_offer(job.id, 'a'), party(), 0)
    second = engine.accept(engine.story_offer(job.id, 'b'), tuple(reversed(party())), 0)
    finish(engine, first.id, ('a','b'))
    finish(engine, second.id, ('a','b'))
    assert len(engine.claim(first.id, 'a', 30)) == 2
    assert engine.claim(second.id, 'b', 31) == ()
    assert second.state == 'turned_in'
    assert engine.quote(second, party()[0]).chits == 0
    assert engine.quote(first, party()[0]).chits == 220


def test_game_9_3_parallel_publications_keep_one_personal_payout_and_historical_quote_after_restart() -> None:
    options = (PublicationOption('private', 'Private', 'handler', Reward((400,400), xp=200)),
               PublicationOption('public', 'Publish', 'public', Reward((200,200), xp=200)))
    job = template('parallel-publication', story=True, branch_group='parallel-choice', publication_options=options)
    engine = Engine('origin', {job.id: job})
    one = engine.accept(engine.story_offer(job.id, 'a'), party(), 0)
    two = engine.accept(engine.story_offer(job.id, 'b'), tuple(reversed(party())), 0)
    finish(engine, one.id, ('a','b'))
    finish(engine, two.id, ('a','b'))
    assert [p.payment.chits for p in engine.claim(one.id, 'a', 30, 'private')] == [440]
    restored = Engine('origin', {job.id: job}, json.loads(json.dumps(engine.record())))
    assert restored.claim(two.id, 'a', 31, 'private') == ()
    assert restored.quote(restored.instances[two.id], party()[0], 'private').chits == 0
    assert restored.quote(restored.instances[one.id], party()[0]).chits == 440
    assert [p.player for p in restored.claim(two.id, 'b', 32, 'public')] == ['b']
    assert restored.claim(one.id, 'b', 33, 'public') == ()
    assert restored.branches[restored.branch_key('a','parallel-choice')] == 'private'
    assert restored.branches[restored.branch_key('b','parallel-choice')] == 'public'


def test_game_9_1_original_workers_resume_without_resetting_another_workers_progress_or_terms() -> None:
    job = template('resume')
    engine = Engine('origin', {job.id: job})
    instance = engine.accept(engine.board('wardens', 0)[0], party(), 0)
    roster, reward = instance.roster, instance.reward
    for person in party():
        engine.withdraw(instance.id, person.player)
    assert instance.failure == 'abandoned'
    engine.retry(instance.id, 'a', 10)
    progress = instance.stages[0]
    engine.observe(Fact('a', 'clear', 'defeated', progress.targets[0], 'new-unit', 'new-receipt',
        instance=instance.id, stage=progress.stage.id, attempt=progress.attempt, resolution='lethal'), 11)
    recorded = progress.record()
    engine.retry(instance.id, 'b', 12)
    assert not instance.withdrawn and progress.record() == recorded
    assert instance.roster == roster and instance.reward == reward and len(progress.targets) == 6
    with pytest.raises(ValueError, match='not yours'):
        engine.retry(instance.id, 'late', 13)


def test_game_9_1_resume_cannot_add_a_fourth_active_generated_job() -> None:
    job = template('resume-cap')
    engine = Engine('origin', {job.id: job})
    offers = engine.board('wardens', 0)
    original = engine.accept(offers[0], party(), 0)
    engine.withdraw(original.id, 'b')
    for offer in offers[1:4]:
        engine.accept(offer, party()[1:], 1)
    with pytest.raises(ValueError, match='three active'):
        engine.retry(original.id, 'b', 2)
    assert 'b' in original.withdrawn


def test_game_9_3_opposite_branch_veteran_can_help_a_new_worker_without_another_payout_or_choice() -> None:
    clinic = template('clinic-help', story=True, branch_group='walked-help', branch='clinic')
    shield = template('shield-help', story=True, branch_group='walked-help', branch='shield')
    engine = Engine('origin', {j.id:j for j in (clinic,shield)})
    first = engine.accept(engine.story_offer(clinic.id, 'a'), party()[:1], 0)
    finish(engine, first.id)
    engine.claim(first.id, 'a', 30)
    with pytest.raises(ValueError, match='other branch'):
        engine.accept(engine.story_offer(shield.id, 'a'), party()[:1], 31)
    assisted = engine.accept(engine.story_offer(shield.id, 'b'), tuple(reversed(party())), 32)
    assert not next(p for p in assisted.roster if p.player == 'a').rewardable
    finish(engine, assisted.id, ('a','b'))
    assert [p.player for p in engine.claim(assisted.id, 'b', 60)] == ['b']
    assert engine.branches[engine.branch_key('a','walked-help')] == 'clinic'
    assert engine.branches[engine.branch_key('b','walked-help')] == 'shield'


def finish(engine: Engine, iid: str, actors: tuple[str, ...] = ('a',)) -> None:
    instance = engine.instances[iid]
    while instance.state == 'active':
        progress = instance.stages[instance.index]
        for index, target in enumerate(progress.targets):
            unit = f'{progress.stage.id}:{progress.attempt}:{index}'
            engine.observe(Fact(actors[index % len(actors)], progress.stage.verb,
                progress.stage.completion, target, unit, 'fact:'+unit,
                instance=iid, stage=progress.stage.id, attempt=progress.attempt,
                resolution=progress.stage.resolution), instance.accepted_at + 20)


@pytest.mark.parametrize('base,size,expected', [(4, 1, 4), (4, 2, 6), (4, 5, 12),
                                                (1, 2, 2), (1, 5, 3)])
def test_game_9_1_objective_roster_scaling(base: int, size: int, expected: int) -> None:
    assert objective_count(base, size) == expected
    assert objective_count(base, size, False) == base


def test_game_9_1_board_has_five_stable_offers_and_real_30_minute_refresh() -> None:
    jobs = {tid: template(tid, min_grade=grade) for tid, grade in [('low', 1), ('mid', 5), ('high', 10)]}
    engine = Engine('origin', jobs)
    first = engine.board('wardens', 0)
    assert len(first) == 5 and jobs[first[0].template].min_grade == 1
    assert engine.board('wardens', 1799.99) == first
    restored = Engine('origin', jobs, json.loads(json.dumps(engine.record())))
    assert restored.board('wardens', 1799) == first
    assert restored.board('wardens', 1800) != first


def test_game_9_1_frozen_roster_rejects_late_actor_and_pays_exact_terms_once() -> None:
    job = template()
    engine = Engine('origin', {job.id: job})
    offer = engine.board('wardens', 0)[0]
    instance = engine.accept(offer, party(), 0)
    assert len(instance.stages[0].targets) == 6
    assert instance.expires_at == 3600
    target = instance.stages[0].targets[0]
    assert not engine.observe(Fact('late', 'clear', 'defeated', target, 'late', 'late',
                                  instance=instance.id, resolution='lethal'), 1)
    finish(engine, instance.id, ('a', 'b'))
    payouts = engine.claim(instance.id, 'a', 30)
    assert [(p.player, p.payment.chits, p.payment.xp, p.payment.standing) for p in payouts] == [
        ('a', 275, 250, {'wardens': 6}), ('b', 250, 250, {'wardens': 6})]
    assert engine.claim(instance.id, 'a', 31) == ()
    with pytest.raises(ValueError, match='not yours'):
        engine.claim(instance.id, 'late', 31)
    restored = Engine('origin', {job.id: job}, json.loads(json.dumps(engine.record())))
    assert restored.claim(instance.id, 'a', 31) == ()


def test_game_9_1_unrelated_or_idle_accepted_member_does_not_gain_credit() -> None:
    job = template()
    engine = Engine('origin', {job.id: job})
    instance = engine.accept(engine.board('wardens', 0)[0], party(), 0)
    finish(engine, instance.id)
    assert [p.player for p in engine.claim(instance.id, 'a', 30)] == ['a']


def test_architecture_15_2_discarded_source_draft_changes_no_branch_or_reward() -> None:
    job = template(story=True, branch_group='walked', branch='clinic')
    engine = Engine('origin', {job.id: job})
    before = engine.record()
    draft = engine.fork()
    instance = draft.accept(draft.story_offer(job.id, 'a'), party()[:1], 0)
    finish(draft, instance.id)
    assert draft.claim(instance.id, 'a', 30)
    assert engine.record() == before
    assert not engine.branches and not engine.claims


def test_game_9_3_fixed_branch_is_once_per_character_and_retry_keeps_it() -> None:
    clinic = template('clinic', story=True, branch_group='walked', branch='clinic')
    shield = template('shield', story=True, branch_group='walked', branch='shield')
    engine = Engine('origin', {j.id: j for j in (clinic, shield)})
    instance = engine.accept(engine.story_offer('clinic', 'a'), party()[:1], 0)
    with pytest.raises(ValueError, match='other branch'):
        engine.accept(engine.story_offer('shield', 'a'), party()[:1], 1)
    progress = instance.stages[0]
    engine.observe(Fact('enemy', 'clear', '', progress.targets[0], 'loss', 'loss',
                       instance=instance.id, failure='The escort is lost.'), 2)
    engine.retry(instance.id, 'a', 3)
    assert instance.stages[0].attempt == 1 and instance.state == 'active'
    assert engine.branches[engine.branch_key('a', 'walked')] == 'clinic'


def test_game_9_2_publication_choice_is_personal_with_exact_permits_and_vectors() -> None:
    options = (
        PublicationOption('private', 'Deliver privately', 'handler',
            Reward((400, 400), {'kestrel': 10}, 'explicit', 200),
            Permit('maintenance_credential', 'warehouse', 1200,
                   StageTarget('core_control', core='warehouse', control='entry'))),
        PublicationOption('public', 'Publish the record', 'public',
            Reward((200, 200), {'unmoored': 10, 'kestrel': -10}, 'explicit', 200),
            Permit('route', 'warehouse', 1200,
                   StageTarget('npc', zone='depot', npc='warehouse-patrol'))),
    )
    job = template(story=True, branch_group='ration', publication_options=options)
    roster = tuple(replace(p, archetype='ghost') for p in party())
    engine = Engine('origin', {job.id: job})
    instance = engine.accept(engine.story_offer(job.id, 'a'), roster, 0)
    finish(engine, instance.id, ('a', 'b'))
    one = engine.claim(instance.id, 'a', 30, 'private')
    assert len(one) == 1 and one[0].payment.chits == 400 and one[0].permit.kind == 'maintenance_credential'
    with pytest.raises(ValueError, match='committed choice'):
        engine.claim(instance.id, 'a', 31, 'public')
    restored = Engine('origin', {job.id: job}, json.loads(json.dumps(engine.record())))
    two = restored.claim(instance.id, 'b', 31, 'public')
    assert two[0].payment.standing == {'unmoored': 10, 'kestrel': -10}
    assert two[0].payment.xp == 200 and two[0].permit.kind == 'route'
    assert two[0].permit.binding.npc == 'warehouse-patrol'
    assert restored.instances[instance.id].state == 'turned_in'


def test_game_9_1_subdue_does_not_count_a_kill_and_stale_retry_facts_are_ignored() -> None:
    base = template(story=True)
    stage = replace(base.stages[0], resolution='subdue', completion='subdued', quantity=1)
    job = replace(base, stages=(stage,))
    engine = Engine('origin', {job.id: job})
    instance = engine.accept(engine.story_offer(job.id, 'a'), party()[:1], 0)
    target = stage.target
    killed = Fact('a', 'clear', 'defeated', target, 'old-npc', 'kill', instance=instance.id, resolution='lethal')
    engine.observe(killed, 1)
    assert instance.state == 'failed' and not instance.stages[0].complete
    engine.retry(instance.id, 'a', 2)
    assert not engine.observe(replace(killed, completion='subdued', resolution='subdue'), 3)
    engine.observe(replace(killed, completion='subdued', resolution='subdue', attempt=1,
                           subject='new-npc', receipt='restrain'), 3)
    assert instance.state == 'complete'


def test_game_9_1_finite_target_pool_requires_distinct_observations() -> None:
    targets = tuple(StageTarget('zone_tile', zone='fixture', tile=(i, 2)) for i in range(3))
    stage = Stage('survey', 'survey', targets[0], 'inspect', 'observed', 'survey:receipt',
                  target_pool=targets[1:])
    job = template(stages=(stage,))
    roster = tuple(Participant(str(i), f'bbs-{i}') for i in range(5))
    engine = Engine('origin', {job.id: job})
    instance = engine.accept(engine.board('wardens', 0)[0], roster, 0)
    assert len(set(instance.stages[0].targets)) == 3
    fact = Fact('0', 'survey', 'observed', instance.stages[0].targets[0], 'tile:0', 'visit:0')
    assert engine.observe(fact, 1)
    assert not engine.observe(replace(fact, receipt='visit:again'), 2)
    assert not instance.stages[0].complete
    finish(engine, instance.id, tuple(str(i) for i in range(5)))
    assert instance.state == 'complete'


def test_game_9_1_full_slots_include_completed_jobs_and_apply_again_on_retry() -> None:
    job = template()
    engine = Engine('origin', {job.id: job})
    offers = engine.board('wardens', 0)
    jobs = [engine.accept(offer, party()[:1], 0) for offer in offers[:3]]
    finish(engine, jobs[0].id)
    with pytest.raises(ValueError, match='three active'):
        engine.accept(offers[3], party()[:1], 1)
    engine.withdraw(jobs[1].id, 'a')
    fourth = engine.accept(offers[3], party()[:1], 1)
    with pytest.raises(ValueError, match='three active'):
        engine.retry(jobs[1].id, 'a', 2)
    assert engine.expire(3600)
    assert fourth.state == 'active'
    engine.expire(3601)
    assert all(i.state in ('failed', 'turned_in') for i in engine.instances.values())
    engine.expire(3602)
    assert not engine.instances


def test_game_9_1_withdrawal_does_not_cancel_another_frozen_participant() -> None:
    job = template()
    engine = Engine('origin', {job.id: job})
    instance = engine.accept(engine.board('wardens', 0)[0], party(), 0)
    engine.withdraw(instance.id, 'a')
    assert instance.state == 'active' and len(instance.stages[0].targets) == 6
    finish(engine, instance.id, ('b',))
    assert [p.player for p in engine.claim(instance.id, 'b', 30)] == ['b']


def test_game_9_1_alternative_sequence_keeps_the_reward_and_survives_restart() -> None:
    base = template(story=True)
    target = StageTarget('core_control', core='loan', control='latch')
    alternative = ContractApproach('network', 'Use the loan terminal', (
        Stage('network-latch', 'hack', target, 'flip', 'flipped', 'network:latch'),))
    job = replace(base, approaches=(alternative,))
    engine = Engine('origin', {job.id: job})
    offer = engine.story_offer(job.id, 'a')
    instance = engine.accept(offer, party()[:1], 0, 'network')
    restored = Engine('origin', {job.id: job}, json.loads(json.dumps(engine.record())))
    assert restored.instances[instance.id].stages[0].targets == (target,)
    finish(restored, instance.id)
    payout = restored.claim(instance.id, 'a', 30)[0]
    assert payout.payment.chits == 220 and payout.payment.xp == 200


def test_game_9_1_paid_story_participant_can_help_a_new_caller_without_another_reward() -> None:
    job = template(story=True)
    engine = Engine('origin', {job.id: job})
    offer = engine.story_offer(job.id, 'a')
    original = engine.accept(offer, party()[:1], 0)
    finish(engine, original.id)
    assert engine.claim(original.id, 'a', 30)
    replay = engine.accept(offer, (party()[0], Participant('new', 'bbs-new')), 40)
    assert not replay.roster[0].rewardable
    finish(engine, replay.id, ('a', 'new'))
    assert [p.player for p in engine.claim(replay.id, 'new', 70)] == ['new']
