"""Game 7.5: live service consent, source composition and fixed payouts."""

from dataclasses import replace

from blacksite.content.schema import Allocation, Reward, ServiceNodeTemplate, Stage, StageTarget
from blacksite.server.contracts.engine import Fact
from blacksite.server.contracts.services import Services
from tests.contracts.test_adapter import live, shipped
from tests.contracts.test_engine import template


def service(live):
    game, owner, callers, players = live
    target = StageTarget('zone_tile', zone=players[0].zone, tile=game.core.combat.actor(players[0]).position)
    job = template('repair', service=True, crew_scaling=False,
                   stages=(Stage('inspect', 'survey', target, 'inspect', 'observed', 'fixture:repair'),),
                   reward=Reward((200, 200), {'wardens': 5}, xp=100))
    node = ServiceNodeTemplate('fixture-service', 'Fixture service', target.zone, 'fixture-core', (),
        (Allocation('common', 'Public'), Allocation('reserve', 'Workers')), contract=job.id)
    owner.content.contracts[job.id] = job
    owner.state.engine.templates[job.id] = job
    owner.content.services[node.id] = node
    owner.state.services = Services(owner.origin, {node.id: node})
    owner.state.services.advance(owner.now(), 3600)  # Explicit fixture fault, no live wall-time wait.
    return node.id, target


def start(live, sid, members):
    game, owner, callers, players = live
    proposal = owner.propose_service(members[0], sid, 'common', tuple(members))
    for pid in members:
        owner.consent(proposal.id, pid)
    owner.start(proposal.id, members[0])
    game.commit_commerce()
    return next(i for i in owner.state.engine.instances.values() if i.service)


def test_game_7_5_start_freezes_reservation_and_final_action_pays_without_extra_turn_in(live) -> None:
    game, owner, callers, players = live
    sid, target = service(live)
    proposal = owner.propose_service(players[0].id, sid, 'common', (players[0].id,))
    assert owner.state.services.nodes[sid].state == 'fault'
    owner.consent(proposal.id, players[0].id)
    owner.start(proposal.id, players[0].id)
    game.commit_commerce(error=True)
    assert owner.state.services.nodes[sid].state == 'fault'
    owner.start(proposal.id, players[0].id)
    game.commit_commerce()
    instance = next(iter(owner.state.engine.instances.values()))
    assert instance.expires_at == owner.state.services.nodes[sid].reserved_until
    before = players[0].chits_hand, players[0].xp
    owner.actions.perform(callers[0].session, instance.id, target)
    effect = owner.commerce.outbox[0]
    assert effect['contracts_state']['services']['nodes'][sid]['state'] == 'allocated'
    assert effect['contracts_state']['engine']['instances'][instance.id]['state'] == 'turned_in'
    game.commit_commerce(error=True)
    assert (players[0].chits_hand, players[0].xp) == before
    assert owner.state.services.nodes[sid].state == 'repairing'
    owner.actions.perform(callers[0].session, instance.id, target)
    game.commit_commerce()
    assert (players[0].chits_hand-before[0], players[0].xp-before[1]) == (200, 100)
    assert owner.state.services.nodes[sid].state == 'allocated'
    owner.claim(instance.id, players[0].id)
    assert not owner.commerce.pending


def test_game_7_5_two_claimants_cannot_crash_queue_or_reserve_same_fault(live) -> None:
    game, owner, callers, players = live
    sid, target = service(live)
    proposals = []
    for player in (players[0], players[2]):
        proposal = owner.propose_service(player.id, sid, 'common', (player.id,))
        owner.consent(proposal.id, player.id)
        proposals.append(proposal)
    owner.start(proposals[0].id, players[0].id)
    owner.start(proposals[1].id, players[2].id)
    game.commit_commerce()
    assert len(owner.state.engine.instances) == 1
    assert owner.state.services.nodes[sid].roster == (players[0].id,)
    assert not owner.commerce.pending


def test_game_7_5_source_xp_and_worker_reward_compose_in_one_actual_transfer(live) -> None:
    game, owner, callers, players = live
    sid, target = service(live)
    instance = start(live, sid, (players[0].id,))
    player = players[0]
    from blacksite.server.progression import Grant
    source_patch, identity, _ = owner.progression.reward_patch(player, Grant('run', 'source-unit', True,
        scope='fixture-core', core='fixture-core', tier=1))
    source_patch['chits_hand'] = player.chits_hand+80
    before = player.xp, player.chits_hand
    owner.commerce.settle(player, source_patch, owner.commerce.items, owner.commerce.caches,
                         owner.commerce.serial, lambda success: None, identity)
    effect = owner.commerce.outbox[-1]
    owner.source_fact(effect, Fact(player.id, 'survey', 'observed', target, 'actual-unit', 'actual-unit',
                                  instance=instance.id, stage='inspect'))
    game.commit_commerce()
    assert player.xp-before[0] == 140  # 40 run + fixed 100 work order, once each.
    assert player.chits_hand-before[1] == 280
    assert game.core.characters.identities[player.bbs_user_id]['run_xp_days']['fixture-core']
    assert owner.state.services.nodes[sid].state == 'allocated'


def test_game_7_5_partial_withdrawal_retains_reservation_for_remaining_worker(live) -> None:
    game, owner, callers, players = live
    sid, target = service(live)
    instance = start(live, sid, (players[0].id, players[1].id))
    draft = owner.state.fork()
    owner.withdraw(draft, instance.id, players[1].id)
    owner.write(draft)
    game.commit_commerce()
    assert owner.state.services.nodes[sid].workers == {players[0].id}
    owner.actions.perform(callers[0].session, instance.id, target)
    game.commit_commerce()
    assert owner.state.services.nodes[sid].state == 'allocated'
    assert owner.state.engine.instances[instance.id].paid == {players[0].id}
