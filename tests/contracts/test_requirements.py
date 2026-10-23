"""Game 9.3: story prerequisites are authority, not board decoration."""

import pytest
from typing import Any

from blacksite.server.contracts.engine import Offer

from tests.contracts.test_adapter import live, shipped
from tests.contracts.test_engine import template


def job(live: tuple[Any, ...], **fields: Any) -> Offer:
    game, owner, callers, players = live
    spec = template('locked-story', story=True, **fields)
    owner.content.contracts[spec.id] = spec
    owner.state.engine.templates[spec.id] = spec
    return owner.state.engine.story_offer(spec.id, players[0].id)


def test_game_9_3_direct_proposal_cannot_bypass_standing_or_prior_receipt(live: tuple[Any, ...]) -> None:
    game, owner, callers, players = live
    offer = job(live, unlock_conditions=('standing_at_least wardens 10', 'completed_contract previous-story'))
    with pytest.raises(ValueError, match='standing'):
        owner.propose(players[0].id, offer, (players[0].id,))
    players[0].standing['wardens'] = 10
    with pytest.raises(ValueError, match='complete previous-story'):
        owner.propose(players[0].id, offer, (players[0].id,))
    assert not owner.proposals and not owner.state.engine.instances
    owner.state.engine.completed[players[0].id] = {'previous-story'}
    assert owner.propose(players[0].id, offer, (players[0].id,))


def test_game_9_3_start_rechecks_changed_facts_without_committing_branches(live: tuple[Any, ...]) -> None:
    game, owner, callers, players = live
    offer = job(live, unlock_conditions=('standing_at_least wardens 10',), branch_group='fixture-choice', branch='one')
    players[0].standing['wardens'] = 10
    proposal = owner.propose(players[0].id, offer, (players[0].id,))
    owner.consent(proposal.id, players[0].id)
    players[0].standing['wardens'] = 0
    with pytest.raises(ValueError, match='standing'):
        owner.start(proposal.id, players[0].id)
    assert not owner.state.engine.instances and not owner.state.engine.branches and not owner.commerce.pending
    players[0].standing['wardens'] = 10
    owner.start(proposal.id, players[0].id)
    game.commit_commerce()
    assert owner.state.engine.instances


def test_game_9_3_paid_story_helper_can_assist_without_repeating_standing_grind(live: tuple[Any, ...]) -> None:
    game, owner, callers, players = live
    offer = job(live, unlock_conditions=('standing_at_least wardens 10',))
    players[0].standing['wardens'] = 10
    owner.state.engine.completed[players[1].id] = {offer.template}
    proposal = owner.propose(players[0].id, offer, tuple(p.id for p in players[:2]))
    for player in players[:2]:
        owner.consent(proposal.id, player.id)
    owner.start(proposal.id, players[0].id)
    game.commit_commerce()
    instance = next(iter(owner.state.engine.instances.values()))
    assert instance.roster[0].rewardable and not instance.roster[1].rewardable
