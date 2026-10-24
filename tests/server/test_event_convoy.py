"""Game 12: shared Convoy source, rollback and nonexclusive public jobs.

This deliberately labelled fixture uses a clear corridor on a shipped
map, without ambient spawners. Source/receipt tests do not claim real
Scour geography or native player walking acceptance.
"""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from blacksite.content.loader import load_content
from blacksite.content.schema import (
    ContractTemplate, Effect, EventTemplate, Reward, Route, Stage, StageTarget, Waypoint,
    ObjectSpec,
)
from blacksite.server.clock import ManualClock, TICK_HZ
from blacksite.server.rules.events import ROLL_SECONDS, SCHEDULES
from blacksite.server.world.zone import ObjectState
from blacksite.server.items import make_item
from tests.character_helpers import create, place
from tests.harness import HeadlessServer


@pytest.fixture(scope='module')
def base_content() -> Any:
    return load_content(Path(__file__).parents[2]/'src/blacksite/content')


@pytest.fixture
def convoy_game(base_content: Any) -> tuple[Any, ...]:
    content = deepcopy(base_content)
    content.bundles.pop('s24-future-events', None)  # Clear-corridor fixture only.
    zid = 'vatside-clinics'
    zone = content.zones[zid]
    reserved = {e.tile for e in zone.meta.exits} | {obj.tile for obj in zone.meta.objects}
    if zone.meta.spawn:
        reserved.add(zone.meta.spawn)
    def clear(tile: tuple[int, int]) -> bool:
        key = zone.tile_at(tile)
        return bool(key in content.tiles and content.tiles[key].passable and not content.tiles[key].hazard
            and tile not in reserved and not any(pocket.contains(tile) for pocket in zone.meta.pockets))
    start = next((x, y) for y in range(2, zone.height-2) for x in range(2, zone.width-15)
                 if all(clear((x+dx, y+dy)) for dx in range(13) for dy in (-1, 0, 1)))
    points = tuple((start[0]+dx, start[1]) for dx in (0, 6, 12))
    content.zones[zid] = replace(zone, meta=replace(zone.meta, spawners=()))
    route = Route('fixture-convoy-road', tuple(Waypoint(zid, tile) for tile in points), 2)
    content.routes[route.id] = route
    target = StageTarget('npc', zone=zid, tile=start, npc='npc-courier')
    jobs = []
    for kind in ('escort', 'clear'):
        stage = Stage('source', kind, target, 'wait', 'arrived' if kind == 'escort' else 'defeated',
            f'fixture-{kind}', resolution='lethal' if kind == 'clear' else None)
        job = ContractTemplate(f'fixture-event-{kind}', 'vesper', type=kind, stages=(stage,),
            reward=Reward((200, 200), xp=100), crew_scaling=False, event_only=True,
            unlock_conditions=('event_active convoy',))
        content.contracts[job.id] = job
        jobs.append(job)
    content.events = {'convoy': EventTemplate('convoy', 'Convoy', (zid,), *SCHEDULES['convoy'],
        route=route.id, effects=(Effect('convoy_route', params={'npc': 'npc-courier'}),
            *(Effect('event_contract', params={'contract': job.id}) for job in jobs)))}
    clock = ManualClock()
    game = HeadlessServer(content, character_state={
        'events': {'last_roll': int(clock.now_utc().timestamp()//ROLL_SECONDS)}}, clock=clock)
    clients, players = [], []
    for index in range(3):
        client = game.connect({'user_id': index+1, 'handle': f'Convoy界{index}', 'node_name': 'test'})
        create(game, client, archetype=0, name=f'Convoy界{index}')
        clients.append(client)
        players.append(game.core.characters.players[client.session.player_id])
    for index in range(2):
        place(game, clients[index], zid, (start[0], start[1]+(-1 if index == 0 else 1)))
    game.commit_commerce()
    result: list[Any] = []
    game.core.events.admin('event.force', {'event': 'convoy'}, result.append)
    game.step()
    game.commit_commerce()
    assert result[0]['ok']
    game.clock.advance(6*TICK_HZ)
    game.step()
    game.commit_commerce()
    game.step()  # Spawn only after the activation receipt commits.
    game.commit_commerce()
    convoys = [actor for actor in game.core.world.actors.values() if actor.behaviour.get('convoy')]
    assert convoys, {'plans': game.core.events.scheduler.record(), 'now': game.core.events.now(),
        'extra': game.core.events.convoys.extra(game.core.world.zones[zid]),
        'slots': game.core.npcs.spawners.slots}
    actor = convoys[0]
    plan = game.core.events.scheduler.plans[actor.behaviour['convoy']]
    return game, clients, players, actor, plan.id, points


def accept(game: Any, player: Any, kind: str) -> str:
    owner = game.core.contracts
    offer = next(offer for offer in owner.offers('vesper')
                 if offer.event_plan and owner.content.contracts[offer.template].type == kind)
    proposal = owner.propose(player.id, offer, (player.id,))
    proposal.consent.add(player.id)
    owner.start(proposal.id, player.id)
    game.commit_commerce()
    return next(instance.id for instance in owner.state.engine.instances.values()
                if instance.offer == offer.id and instance.roster[0].player == player.id)


def test_game_12_beacon_consumption_and_route_change_share_one_receipt(convoy_game: tuple[Any, ...]) -> None:
    game, clients, players, actor, pid, points = convoy_game
    owner, player = game.core.events, players[0]
    iid = 'fixture:beacon'
    item = make_item(iid, owner.content.items['con_kestrel_beacon'], player.id, game.clock.now_utc().isoformat())
    owner.commerce.items[iid] = item
    player.inventory.append(iid)
    before = owner.scheduler.plans[pid].revision
    assert owner.convoys.use(clients[0].session, item)
    game.commit_commerce(error=True)
    assert iid in player.inventory and not owner.scheduler.plans[pid].allocations.get('detour')
    assert owner.convoys.use(clients[0].session, item)
    game.commit_commerce()
    assert iid not in player.inventory and iid not in owner.commerce.items
    plan = owner.scheduler.plans[pid]
    assert plan.revision > before and plan.allocations['detour']['zone'] == actor.zone
    assert 'Detour:' in owner.text(plan, detailed=True)
    with pytest.raises(ValueError, match='already has a signal'):
        owner.convoys.use(clients[0].session, item)


def follow(game: Any, clients: list[Any], actor: Any) -> None:
    for index, client in enumerate(clients[:2]):
        body = game.core.characters.sim.avatars[client.session.user_id].actor
        game.core.world.enter(body, actor.zone, (actor.x, actor.y+(-1 if index == 0 else 1)))


def test_game_12_same_public_offer_two_identities_and_one_convoy(convoy_game: tuple[Any, ...]) -> None:
    game, clients, players, actor, pid, points = convoy_game
    instances = [accept(game, player, 'escort') for player in players[:2]]
    owner = game.core.contracts
    assert owner.state.engine.instances[instances[0]].offer == owner.state.engine.instances[instances[1]].offer
    owner.scenes.reconcile()
    assert len([a for a in game.core.world.actors.values() if a.behaviour.get('convoy') == pid]) == 1
    assert not any(a.behaviour.get('mission') in instances for a in game.core.world.actors.values())
    assert not game.core.events.convoys.extra(game.core.world.zones[actor.zone])
    assert all(owner.state.engine.instances[i].expires_at == game.core.events.scheduler.plans[pid].ends_at
               for i in instances)


def test_game_12_actual_legs_pay_each_worker_once_and_no_afk_credit(convoy_game: tuple[Any, ...]) -> None:
    game, clients, players, actor, pid, points = convoy_game
    instances = [accept(game, player, 'escort') for player in players]
    for _ in range(160):
        follow(game, clients, actor)
        game.step()
        game.commit_commerce()
        game.commit_characters()
        if 'convoy-arrived' in game.core.events.scheduler.plans[pid].reward_receipts:
            break
    else:
        raise AssertionError('The convoy never follows its authored corridor.')
    owner = game.core.contracts
    assert [owner.state.engine.instances[i].state for i in instances] == ['complete', 'complete', 'active']
    before = [player.chits_hand for player in players]
    for iid, player in zip(instances[:2], players[:2]):
        owner.claim(iid, player.id)
        game.commit_commerce()
    assert [player.chits_hand-before[index] for index, player in enumerate(players)] == [200, 200, 0]
    owner.claim(instances[0], players[0].id)
    game.commit_commerce()
    assert players[0].chits_hand == before[0]+200
    assert not game.core.events.jobs.offers('vesper')


def test_arch_15_2_failed_waypoint_retries_without_private_copy(convoy_game: tuple[Any, ...]) -> None:
    game, clients, players, actor, pid, points = convoy_game
    before = deepcopy(game.core.events.scheduler.record())
    index = game.core.events.scheduler.plans[pid].allocations['waypoint']
    assert index == 1
    game.core.world.enter(actor, actor.zone, points[index])
    assert game.core.events.convoys.move(actor, game.core.world.zones[actor.zone], game.clock.now_tick(), set())
    game.commit_commerce(error=True)
    assert game.core.events.scheduler.record() == before
    game.core.events.convoys.move(actor, game.core.world.zones[actor.zone], game.clock.now_tick(), set())
    game.commit_commerce()
    assert game.core.events.scheduler.plans[pid].allocations['waypoint'] == 2
    game.core.npcs.spawners.process(game.core.world.zones[actor.zone], game.core.events.now())
    assert len([a for a in game.core.world.actors.values() if a.behaviour.get('convoy') == pid]) == 1


def test_game_12_cancel_between_proposal_and_acceptance_consumes_no_job_slot(convoy_game: tuple[Any, ...]) -> None:
    game, clients, players, actor, pid, points = convoy_game
    owner = game.core.contracts
    offer = next(offer for offer in owner.offers('vesper') if offer.event_plan)
    proposal = owner.propose(players[0].id, offer, (players[0].id,))
    proposal.consent.add(players[0].id)
    game.core.events.admin('event.cancel', {'plan': pid}, lambda result: None)
    game.step()
    game.commit_commerce()
    with pytest.raises(ValueError):
        owner.start(proposal.id, players[0].id)
    assert not owner.state.engine.instances


def test_game_12_convoy_death_closes_escort_and_credits_actual_raider(convoy_game: tuple[Any, ...]) -> None:
    game, clients, players, actor, pid, points = convoy_game
    escort = accept(game, players[1], 'escort')
    raid = accept(game, players[0], 'clear')
    source = game.core.world.actors[players[0].id]
    actor.health, actor.stance = 0, 'dead'
    game.core.npcs.died(source, actor)
    game.commit_commerce()
    plan = game.core.events.scheduler.plans[pid]
    assert plan.allocations['convoy_lost'] and 'convoy-lost' in plan.reward_receipts
    assert game.core.contracts.state.engine.instances[escort].state == 'failed'
    assert game.core.contracts.state.engine.instances[raid].state == 'complete'
    assert not game.core.events.jobs.offers('vesper')
    before = players[0].chits_hand
    game.core.contracts.claim(raid, players[0].id)
    game.commit_commerce()
    assert players[0].chits_hand == before+200


def test_game_12_restart_resumes_waypoint_with_one_shared_body(convoy_game: tuple[Any, ...]) -> None:
    game, clients, players, actor, pid, points = convoy_game
    iid = accept(game, players[0], 'escort')
    state = {'players': [player.record() for player in players],
        'identities': deepcopy(game.core.characters.identities),
        'serial': game.core.characters.serial,
        'items': [item.record() for item in game.core.commerce.items.values()],
        'contracts': game.core.contracts.record(), 'events': game.core.events.scheduler.record(),
        'npcs': deepcopy(game.core.npcs.spawners.record())}
    waypoint = state['events']['plans'][0]['allocations']['waypoint']
    restored = HeadlessServer(game.core.loop.content, character_state=state, clock=game.clock)
    for _ in range(5):
        restored.step()
        restored.commit_commerce()
    bodies = [body for body in restored.core.world.actors.values() if body.behaviour.get('convoy') == pid]
    assert len(bodies) == 1
    assert restored.core.events.scheduler.plans[pid].allocations['waypoint'] == waypoint
    assert restored.core.contracts.state.engine.instances[iid].runtime['event_plan'] == pid
    assert not any(body.behaviour.get('mission') == iid for body in restored.core.world.actors.values())


def test_arch_15_2_failed_convoy_death_pays_no_raid_and_can_retry(convoy_game: tuple[Any, ...]) -> None:
    game, clients, players, actor, pid, points = convoy_game
    iid = accept(game, players[0], 'clear')
    before = deepcopy(game.core.events.scheduler.record())
    actor.health, actor.stance = 0, 'dead'
    game.core.npcs.died(game.core.world.actors[players[0].id], actor)
    game.commit_commerce(error=True)
    assert game.core.events.scheduler.record() == before
    assert game.core.contracts.state.engine.instances[iid].state == 'active'
    assert actor.id in game.core.world.actors and actor.health == 1 and actor.stance == 'normal'


def test_game_12_cancel_does_not_remove_a_body_with_queued_death_source(convoy_game: tuple[Any, ...]) -> None:
    game, clients, players, actor, pid, points = convoy_game
    game.core.events.admin('event.cancel', {'plan': pid}, lambda result: None)
    actor.health, actor.stance = 0, 'dead'
    game.core.npcs.died(game.core.world.actors[players[0].id], actor)
    game.commit_commerce()
    assert actor.id not in game.core.world.actors
    assert actor.id not in game.core.npcs.pending_deaths
    assert game.core.events.scheduler.plans[pid].state == 'cancelled'


def test_game_12_muster_object_does_not_prevent_convoy_spawning(convoy_game: tuple[Any, ...]) -> None:
    game, clients, players, actor, pid, points = convoy_game
    zone = game.core.world.zones[actor.zone]
    spec = ObjectSpec('fixture-muster', actor.position, 'terminal')
    zone.template = replace(zone.template, meta=replace(zone.template.meta,
        objects=(*zone.template.meta.objects, spec)))
    zone.objects[spec.id] = ObjectState(spec)
    game.core.world.leave(actor)
    game.core.npcs.spawners.process(zone, game.core.events.now())
    bodies = [body for body in game.core.world.actors.values() if body.behaviour.get('convoy') == pid]
    assert len(bodies) == 1 and bodies[0].position != spec.tile
    assert max(abs(a-b) for a, b in zip(bodies[0].position, spec.tile)) <= 1
