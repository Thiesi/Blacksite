"""Game 9.1 / S27: a neutral route without weakening story prerequisites."""

from dataclasses import replace

import pytest

from blacksite.content.loader import ContentTree
from blacksite.content.schema import ContractTemplate
from blacksite.server.contract_engine import Contracts
from blacksite.server.contracts.panels import Panel, takes_turnin
from blacksite.server.factions import relation
from blacksite.server.players import Player
from tests.character_helpers import place
from tests.harness import FakeClient, HeadlessServer
from tests.test_dialogue_runtime import content, setup


def referral(content: ContentTree) -> tuple[HeadlessServer, FakeClient, Player, Contracts, ContractTemplate]:
    game, caller, player = setup(content)
    owner = game.core.contracts
    # A disclosed hub-only story fixture isolates referral authority.
    # Future Season 1 maps/chains remain S25/S26 acceptance, not this test.
    base = owner.state.engine.templates['vesper-first-thing']
    job = replace(base, id='broker-proof', name='Recorded referral', giver='wardens',
                  story=True, min_grade=5, branch_group=None, branch=None,
                  reward=replace(base.reward, standing={'wardens': 5}),
                  unlock_conditions=('standing_at_least wardens 10', 'has_item story_vesper_card',
                                     'completed_contract vesper-first-thing', 'event_active curfew'))
    owner.content.contracts[job.id] = job
    owner.state.engine.templates[job.id] = job
    player.update_progression(1500)
    player.faction = 'sable'
    assert relation(owner.content.factions, player.faction, job.giver) == 'H'
    owner.state.engine.completed[player.id] = {'vesper-first-thing'}
    owner.event_active = lambda eid: eid == 'curfew'
    return game, caller, player, owner, job


def test_game_7_5_broker_waives_only_the_givers_minimum_standing(content: ContentTree) -> None:
    game, caller, player, owner, job = referral(content)
    assert owner.requirements(player.id, job) == ('standing_at_least wardens 10',)
    assert owner.requirements(player.id, job, broker=True) == ()
    harder = replace(job, unlock_conditions=(*job.unlock_conditions,
        'standing_at_least halvard 10', 'member_of wardens', 'has_item key_undercity'))
    assert owner.requirements(player.id, harder, broker=True) == (
        'standing_at_least halvard 10', 'member_of wardens', 'has_item key_undercity')
    player.grade = 4
    owner.event_active = lambda eid: False
    owner.state.engine.completed[player.id].clear()
    missing = owner.requirements(player.id, job, broker=True)
    assert 'grade_at_least 5' in missing
    assert 'event_active curfew' in missing
    assert 'completed_contract vesper-first-thing' in missing


@pytest.mark.parametrize(('faction', 'standing'), [
    (None, 0), (None, -10), ('halvard', 0), ('kestrel', 0), ('wardens', 0),
])
def test_game_9_1_nonhostile_callers_cannot_bypass_giver_standing(
    content: ContentTree, faction: str | None, standing: int,
) -> None:
    game, caller, player, owner, job = referral(content)
    offer = owner.offer(job.id, player.id, 'vesper')
    player.faction = faction
    player.standing['wardens'] = standing
    assert relation(owner.content.factions, player.faction, job.giver) != 'H'
    assert owner.requirements(player.id, job, broker=True) == ('standing_at_least wardens 10',)
    panel = Panel(game.clock.now_tick(), 'vesper', 'vesper')
    assert not any(row['id'] == job.id for row in owner.panels.rows(caller.session, panel))
    # A stale selection or a direct proposal cannot bypass the filtered board.
    with pytest.raises(ValueError, match='requires'):
        owner.propose(player.id, offer, (player.id,), broker='vesper')
    assert not owner.proposals and not owner.state.engine.instances
    # Non-hostile callers can still take the normal route once qualified.
    player.standing['wardens'] = 10
    assert owner.requirements(player.id, job, broker=True) == ()
    assert any(row['id'] == job.id for row in owner.panels.rows(caller.session, panel))


@pytest.mark.parametrize('change', ['membership', 'relation'])
def test_game_9_1_referral_rechecks_live_hostility_before_start(
    content: ContentTree, change: str,
) -> None:
    game, caller, player, owner, job = referral(content)
    proposal = owner.propose(player.id, owner.offer(job.id, player.id, 'vesper'),
                             (player.id,), broker='vesper')
    owner.consent(proposal.id, player.id)
    if change == 'membership':
        player.faction = None
    else:
        faction = owner.content.factions['sable']
        owner.content.factions['sable'] = replace(faction, relations={**faction.relations, 'wardens': 'N'})
    with pytest.raises(ValueError, match='requires'):
        owner.start(proposal.id, player.id)
    game.commit_commerce()
    assert not owner.state.engine.instances


def test_game_7_5_referral_appears_at_the_broker_and_commits_its_original_faction(content: ContentTree) -> None:
    game, caller, player, owner, job = referral(content)
    panel = Panel(game.clock.now_tick(), 'vesper', 'vesper')
    rows = owner.panels.rows(caller.session, panel)
    assert any(row['id'] == job.id for row in rows)
    offer = owner.offer(job.id, player.id, 'vesper')
    with pytest.raises(ValueError, match='requires'):
        owner.propose(player.id, offer, (player.id,))
    proposal = owner.propose(player.id, offer, (player.id,), broker='vesper')
    owner.consent(proposal.id, player.id)
    owner.start(proposal.id, player.id)
    assert not owner.state.engine.instances
    game.commit_commerce()
    instance = next(iter(owner.state.engine.instances.values()))
    assert instance.giver == 'wardens' and instance.runtime['broker'] == 'vesper'
    assert owner.state.fork().engine.instances[instance.id].runtime['broker'] == 'vesper'
    assert takes_turnin('vesper', instance) and takes_turnin('wardens', instance)
    assert not takes_turnin('sable', instance)


def test_game_7_5_moving_away_before_consent_start_cannot_use_a_cached_referral(content: ContentTree) -> None:
    game, caller, player, owner, job = referral(content)
    offer = owner.offer(job.id, player.id, 'vesper')
    proposal = owner.propose(player.id, offer, (player.id,), broker='vesper')
    owner.consent(proposal.id, player.id)
    place(game, caller, 'vatside-wake-hall', (6, 5))
    with pytest.raises(ValueError):
        owner.start(proposal.id, player.id)
    assert not owner.state.engine.instances


def test_game_7_5_referral_never_claims_a_public_service_order(content: ContentTree) -> None:
    game, caller, player, owner, job = referral(content)
    assert not takes_turnin('vesper', replace(
        # A completed service receipt still belongs to its local source.
        owner.state.engine.fork().accept(owner.state.engine.story_offer(job.id, player.id),
                                        (owner.participant(player.id),), owner.now()),
        service=True))
    service = replace(job, id='broker-service-proof', service=True)
    owner.content.contracts[service.id] = service
    owner.state.engine.templates[service.id] = service
    with pytest.raises(ValueError, match='neutral story referral'):
        owner.propose(player.id, owner.state.engine.offer(service, 'service-proof', owner.now()+600),
                      (player.id,), broker='vesper')


def test_game_7_5_broker_rechecks_nonstanding_prerequisites_at_start(content: ContentTree) -> None:
    game, caller, player, owner, job = referral(content)
    proposal = owner.propose(player.id, owner.offer(job.id, player.id, 'vesper'),
                             (player.id,), broker='vesper')
    owner.consent(proposal.id, player.id)
    owner.event_active = lambda eid: False
    with pytest.raises(ValueError, match='requires'):
        owner.start(proposal.id, player.id)
    assert not owner.state.engine.instances


def test_game_7_5_completed_story_returns_through_the_broker_and_pays_its_giver_once(content: ContentTree) -> None:
    game, caller, player, owner, job = referral(content)
    proposal = owner.propose(player.id, owner.offer(job.id, player.id, 'vesper'),
                             (player.id,), broker='vesper')
    owner.consent(proposal.id, player.id)
    owner.start(proposal.id, player.id)
    game.commit_commerce()
    instance = next(iter(owner.state.engine.instances.values()))
    # Completed-objective fixture isolates counter routing and payment;
    # actual source fulfilment belongs to the S19 objective/native tests.
    instance.state = 'complete'
    instance.contributions.add(player.id)
    expected = instance.reward.chits
    before = player.chits_hand
    panel = Panel(game.clock.now_tick(), 'vesper', 'vesper')
    owner.panels.act(caller.session, panel, 't', instance.id)
    assert panel.confirmation == ('turn-in', instance.id, '')
    owner.panels.act(caller.session, panel, 'y', instance.id)
    game.commit_commerce()
    assert owner.state.engine.instances[instance.id].state == 'turned_in'
    assert player.chits_hand == before+expected
    assert player.standing['wardens'] == 5 and player.standing.get('sable', 0) == 0
    owner.claim(instance.id, player.id)
    game.commit_commerce()
    assert player.chits_hand == before+expected
