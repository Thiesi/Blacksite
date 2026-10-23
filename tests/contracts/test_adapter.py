"""Game 9/architecture 15: live adapters freeze consent and own payouts."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from blacksite.content.loader import ContentTree, load_content
from blacksite.server.contracts.engine import Fact
from blacksite.server.crews import GUARD_SECONDS
from blacksite.server.clock import TICK_HZ
from tests.character_helpers import create
from tests.contracts.test_engine import template
from tests.harness import HeadlessServer
from tests.character_helpers import place


@pytest.fixture(scope='module')
def shipped() -> ContentTree:
    return load_content(Path(__file__).parents[2]/'src/blacksite/content')


@pytest.fixture
def live(shipped: ContentTree) -> tuple[Any, ...]:
    content = deepcopy(shipped)
    job = template()
    content.contracts[job.id] = job
    game = HeadlessServer(content, character_state={})
    callers, players = [], []
    for index in range(3):
        caller = game.connect({'user_id': index+1, 'handle': 'Caller'+str(index), 'node_name': 'fixture'})
        create(game, caller, name='Caller'+str(index), archetype=1)
        callers.append(caller)
        players.append(game.core.characters.players[caller.session.player_id])
    crews = game.core.crews
    crews.perform(callers[0].session, 'invite', players[1].id)
    invitation = next(i for i in crews.registry.invites.values() if i.target == players[1].id)
    crews.perform(callers[1].session, 'accept', invitation.id)
    game.commit_characters()
    return game, game.core.contracts, callers, players


def accept(live: tuple[Any, ...]) -> str:
    game, contracts, callers, players = live
    offer = contracts.state.engine.board('wardens', contracts.now())[0]
    proposal = contracts.propose(players[0].id, offer, tuple(p.id for p in players[:2]))
    for player in players[:2]:
        contracts.consent(proposal.id, player.id)
    contracts.start(proposal.id, players[0].id)
    game.commit_commerce()
    return next(iter(contracts.state.engine.instances))


def complete(live: tuple[Any, ...], iid: str) -> None:
    game, contracts, callers, players = live
    instance = contracts.state.engine.instances[iid]
    assert game.core.commerce.settle(None, {}, game.core.commerce.items, {},
                                    game.core.commerce.serial, lambda success: None)
    effect = game.core.commerce.outbox[-1]
    for index, target in enumerate(instance.stages[0].targets):
        assert contracts.source_fact(effect, Fact(players[index % 2].id, 'clear', 'defeated', target,
            f'unit{index}', f'defeat{index}', instance=iid, resolution='lethal')) == (iid,)
    assert contracts.state.engine.instances[iid].state == 'active'
    game.commit_commerce()
    assert contracts.state.engine.instances[iid].state == 'complete'


def test_game_9_1_actual_guards_participate_but_late_crew_members_do_not(live) -> None:
    game, contracts, callers, players = live
    iid = accept(live)
    for index, caller in enumerate(callers):
        place(game, caller, 'core-plaza', (20+index, 4))
    crews = game.core.crews
    crews.perform(callers[0].session, 'invite', players[2].id)
    invitation = next(i for i in crews.registry.invites.values() if i.target == players[2].id)
    crews.perform(callers[2].session, 'accept', invitation.id)
    game.step((GUARD_SECONDS+1)*TICK_HZ)
    assert (players[0].id, players[1].id) in crews.guarded_at
    assert (players[0].id, players[2].id) in crews.guarded_at
    instance = contracts.state.engine.instances[iid]
    assert game.core.commerce.settle(None, {}, game.core.commerce.items, {},
                                    game.core.commerce.serial, lambda success: None)
    effect = game.core.commerce.outbox[-1]
    for index, target in enumerate(instance.stages[0].targets):
        contracts.source_fact(effect, Fact(players[0].id, 'clear', 'defeated', target,
            f'unit{index}', f'guarded-defeat{index}', instance=iid, resolution='lethal'))
    game.commit_commerce()
    assert contracts.state.engine.instances[iid].contributions == {p.id for p in players[:2]}


def test_game_9_1_proposal_requires_each_consent_and_failed_freeze_consumes_nothing(live) -> None:
    game, contracts, callers, players = live
    offer = contracts.state.engine.board('wardens', contracts.now())[0]
    proposal = contracts.propose(players[0].id, offer, tuple(p.id for p in players[:2]))
    assert not contracts.state.engine.instances
    contracts.consent(proposal.id, players[0].id)
    with pytest.raises(ValueError, match='Every listed participant'):
        contracts.start(proposal.id, players[0].id)
    with pytest.raises(ValueError, match='not yours'):
        contracts.consent(proposal.id, players[2].id)
    contracts.consent(proposal.id, players[1].id)
    contracts.start(proposal.id, players[0].id)
    assert not contracts.state.engine.instances
    game.commit_commerce(error=True)
    assert not contracts.state.engine.instances and proposal.id in contracts.proposals
    contracts.start(proposal.id, players[0].id)
    effects = game.commit_commerce()
    assert effects[0]['contracts_state']['engine']['instances']
    assert proposal.id not in contracts.proposals
    assert len(next(iter(contracts.state.engine.instances.values())).stages[0].targets) == 6


def test_game_9_1_real_secondary_payouts_survive_failure_and_exclude_late_crew_join(live) -> None:
    game, contracts, callers, players = live
    iid = accept(live)
    complete(live, iid)
    game.core.crews.perform(callers[0].session, 'invite', players[2].id)
    invitation = next(i for i in game.core.crews.registry.invites.values() if i.target == players[2].id)
    game.core.crews.perform(callers[2].session, 'accept', invitation.id)
    before = [(p.chits_hand, p.xp, deepcopy(p.standing)) for p in players]
    contracts.claim(iid, players[0].id)
    game.commit_commerce(error=True)
    assert [(p.chits_hand, p.xp, p.standing) for p in players] == before
    assert not contracts.state.engine.instances[iid].paid
    contracts.claim(iid, players[0].id)
    contracts.claim(iid, players[1].id)  # Queued duplicate sees the installed receipt.
    effects = game.commit_commerce()
    assert len(effects) == 1
    assert len(effects[0]['players']) == 2
    assert [(p.chits_hand-chits, p.xp-xp) for p, (chits, xp, _) in zip(players, before)] == [
        (250, 250), (250, 250), (0, 0)]
    assert contracts.state.engine.instances[iid].state == 'turned_in'
    assert all('contract:contract:clear' in players[i].progress['reward_receipts'] for i in (0, 1))


def test_game_9_1_live_disconnect_drops_proposal_but_keeps_accepted_objective(live) -> None:
    game, contracts, callers, players = live
    iid = accept(live)
    snapshot = contracts.state.engine.instances[iid].record()
    contracts.disconnect(callers[1].session)
    assert contracts.state.engine.instances[iid].record() == snapshot
    assert contracts.state.engine.instances[iid].roster[1].player == players[1].id
