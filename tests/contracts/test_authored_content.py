"""Game 9.1/9.4/9.5: shipped pools and dormant story sequences.

Pure fact replay verifies authored stage accounting and settlement. It is
not full-city navigation, NPC combat, native acceptance or human pacing.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.server.contracts.engine import Engine, Fact, Participant
from blacksite.server.contracts.ledger import Ledger
from tests.contracts.test_engine import finish


@pytest.fixture(scope='module')
def authored():
    content = load_content(Path(__file__).parents[2]/'src/blacksite/content')
    assert not validate(content)
    return content


def test_game_9_5_complete_authored_bundle_stays_dormant_and_has_all_faction_pools(authored):
    stories = [j for j in authored.contracts.values() if j.season == 1]
    assert len(stories) == 33
    assert Counter(j.giver for j in stories) == dict(halvard=4,sablier=4,kestrel=4,wardens=4,
                                                   choir=4,sable=4,unmoored=5,ferrymen=4)
    state = Ledger('authored', authored)
    assert not {j.id for j in stories} & state.engine.templates.keys()
    assert set(state.services.nodes) == {'cold-chain', 'sump', 'depot', 'relay-zero'}
    counts = Counter(j.giver for j in state.engine.templates.values() if not j.story and not j.service and not j.event_only)
    assert counts == dict(vesper=6,**{f:3 for f in authored.factions})
    assert {j.type for j in state.engine.templates.values() if j.giver == 'vesper' and not j.story} == {
        'fetch','hack','escort','clear','plant','survey'}
    for job in stories:
        assert any(authored.evidence[e].related_stage == job.stages[-1].id for e in job.evidence_assets)


@pytest.mark.parametrize('size',(1,2,5))
def test_game_9_1_every_generated_template_resolves_and_settles_each_supported_roster(authored,size):
    for job in authored.contracts.values():
        if job.story or job.service or job.event_only:
            continue
        engine = Engine('authored',{job.id:job})
        party = tuple(Participant(str(i),'bbs-'+str(i),10) for i in range(size))
        offered = engine.board(job.giver,0)[0]
        instance = engine.accept(offered,party,0)
        # Adapter tests verify guard proximity/time. Here each verified
        # fact includes the cooperating roster, including support workers
        # when a survey has fewer distinct points than crew members.
        while instance.state == 'active':
            progress = instance.stages[instance.index]
            for index,target in enumerate(progress.targets):
                unit = f'{progress.stage.id}:{index}'
                engine.observe(Fact(party[index % size].player,progress.stage.verb,progress.stage.completion,
                    target,unit,unit,instance=instance.id,stage=progress.stage.id,
                    resolution=progress.stage.resolution,contributors=tuple(p.player for p in party)),20)
        payouts = engine.claim(instance.id,'0',30)
        assert len(payouts) == size
        assert all(p.payment.chits == int(200*(1+.25*(size-1))) for p in payouts)


def test_game_12_event_jobs_cannot_appear_in_an_ordinary_board_roll(authored):
    jobs = {job.id: job for job in authored.contracts.values() if job.event_only}
    assert len(jobs) == 2
    engine = Engine('event-board', jobs)
    for giver in ('vesper', 'kestrel', 'sable'):
        assert engine.board(giver, 0) == ()


def test_game_9_4_all_33_authored_story_sequences_replay_to_one_fixed_reward(authored):
    for job in authored.contracts.values():
        if job.season != 1:
            continue
        engine = Engine('story',{job.id:job})
        instance = engine.accept(engine.story_offer(job.id,'a'),(Participant('a','bbs-a',10),),0)
        finish(engine,instance.id)
        option = next(iter(instance.options),None)
        payouts = engine.claim(instance.id,'a',30,option)
        assert len(payouts) == 1 and payouts[0].payment.xp == 200
        assert engine.claim(instance.id,'a',31,option) == ()
        restored = Engine('story',engine.templates,deepcopy(engine.record()))
        assert restored.claim(instance.id,'a',32,option) == ()


def test_game_9_1_vesper_brokers_distinct_nonmember_jobs_and_keeps_own_slot(authored):
    engine = Ledger('variety',authored).engine
    for epoch in range(10):
        offers = engine.board('vesper',epoch*1800)
        assert len(offers) == len({o.template for o in offers}) == 5
        assert engine.templates[offers[0].template].giver == 'vesper'
    assert any(engine.templates[o.template].giver != 'vesper' for o in offers)


def test_game_9_4_either_walked_outcome_preserves_both_main_story_continuations(authored):
    assert 'receipt walked-templates-s1' in authored.contracts['sab-s1-2-provenance'].unlock_conditions
    assert 'completed_contract sab-s1-1-retrieval' not in authored.contracts['sab-s1-2-provenance'].unlock_conditions
    assert 'receipt walked-templates-s1' in authored.contracts['unm-s1-3-fresher'].unlock_conditions
    assert 'completed_contract unm-s1-2-vat-nine' not in authored.contracts['unm-s1-3-fresher'].unlock_conditions
