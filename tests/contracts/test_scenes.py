"""Game 9.3: actual scoped bodies, source-owned defeats and escort receipts."""

from dataclasses import replace
from typing import Any

from blacksite.content.schema import StageTarget
from blacksite.server.contracts.engine import Engine
from blacksite.server.world.actors import Actor, mission_pair
from blacksite.server.world.movement import move
from blacksite.server.world.sight import private_visible
from tests.character_helpers import create, place
from tests.contracts.test_engine import template
from tests.npcs.test_engine import city, body


def test_game_9_3_mission_bodies_spawn_at_named_anchor_instead_of_zone_entry(city: tuple[Any, ...]) -> None:
    game, caller = city
    owner = game.core.contracts
    zone = owner.world.zones['vatside-clinics']
    anchor = next(obj for obj in zone.objects.values() if obj.spec.kind == 'vendor')
    base = template('anchored-scene', story=True)
    target = StageTarget('npc', zone=zone.id, object=anchor.spec.id, npc='npc-maintenance-drone')
    job = replace(base, stages=(replace(base.stages[0], target=target, quantity=1),))
    owner.content.contracts[job.id] = job
    owner.state.engine.templates[job.id] = job
    draft = owner.state.fork()
    instance = draft.engine.accept(draft.engine.story_offer(job.id, caller.session.player_id),
                                  (owner.participant(caller.session.player_id),), owner.now())
    owner.write(draft)
    game.commit_commerce()
    owner.scenes.reconcile()
    actor = next(a for a in owner.world.actors.values() if a.behaviour.get('mission') == instance.id)
    assert actor.behaviour['home'] == anchor.spec.tile
    assert actor.behaviour['home'] != zone.template.meta.spawn


def test_game_9_3_repeated_escort_action_assigns_all_four_willing_group_members(city: tuple[Any, ...]) -> None:
    game, caller = city
    owner, iid, actors = mission(city, verb='escort', quantity=4)
    # Isolate assigning the group; walking/arrival is covered separately.
    source = body(game, caller)
    zone = owner.world.zones[source.zone]
    for actor in actors:
        owner.world.leave(actor)
    nearby = [(source.x+dx, source.y+dy) for dx in (-1,0,1) for dy in (-1,0,1)
              if (dx,dy) != (0,0) and zone.passable((source.x+dx,source.y+dy))
              and not any(a.position == (source.x+dx,source.y+dy) for a in zone.actors.values())]
    assert len(nearby) >= len(actors)
    for actor, tile in zip(actors, nearby):
        owner.world.enter(actor, source.zone, tile)
    for _ in range(4):
        assert owner.actions.interact_npc(caller.session, iid)
        game.commit_commerce()
    assert all(actor.behaviour.get('escort') == caller.session.player_id for actor in actors)
    assert not owner.commerce.pending


def test_game_9_3_willing_group_waits_for_consent_then_follows_worker(city) -> None:
    game, caller = city
    owner, _, actors = mission(city, verb='escort', quantity=4, npc='npc-walked-template')
    positions = {actor.id: actor.position for actor in actors}
    zone = owner.world.zones[actors[0].zone]
    start = game.clock.now_tick()
    for tick in range(start, start+600):
        for actor in actors:
            game.core.npcs.act(actor, zone, tick, set())
    assert {actor.id: actor.position for actor in actors} == positions
    follower = actors[0]
    source = body(game, caller)
    assert game.core.npcs.escort(source, follower)
    game.core.npcs.act(follower, zone, start+600, set())
    assert follower.position != positions[follower.id]
    assert {a.id: a.position for a in actors[1:]} == {a.id: positions[a.id] for a in actors[1:]}


def test_game_9_3_withdrawn_worker_cannot_keep_leading_the_groups_escort(city) -> None:
    game, caller = city
    second = game.connect({'user_id': 2, 'handle': 'Second', 'node_name': 'test'})
    create(game, second, name='Second', card='none')
    place(game, second, 'vatside-clinics', (21, 4))
    owner, iid, actors = mission(city, verb='escort', npc='npc-walked-template',
        roster=(caller.session.player_id, second.session.player_id))
    target = actors[0]
    place(game, caller, target.zone, (target.x-1, target.y))
    assert owner.actions.interact_npc(caller.session, iid)
    game.commit_commerce()
    draft = owner.state.fork()
    owner.withdraw(draft, iid, caller.session.player_id)
    owner.write(draft)
    game.commit_commerce()
    owner.scenes.reconcile()
    before = target.position
    place(game, caller, target.zone, (20, 3))
    game.core.npcs.act(target, owner.world.zones[target.zone], game.clock.now_tick()+100, set())
    assert target.position == before
    assert game.core.npcs.escort(body(game, second), target)


def mission(city, *, verb='clear', resolution='lethal', quantity=1, roster=None, npc=None):
    game, caller = city
    owner = game.core.contracts
    job = template('scene', story=True)
    target = StageTarget('npc', zone='vatside-clinics', tile=(24, 3),
                         npc=npc or ('npc-sablier-orderly' if verb == 'escort' else 'npc-maintenance-drone'))
    stage = replace(job.stages[0], verb=verb, target=target, quantity=quantity,
                    resolution=resolution if verb == 'clear' else None,
                    completion='arrived' if verb == 'escort' else 'subdued' if resolution == 'subdue' else 'defeated',
                    destination=StageTarget('zone_tile', zone='vatside-clinics', tile=(20, 3)) if verb == 'escort' else None)
    job = replace(job, stages=(stage,))
    owner.content.contracts[job.id] = job
    owner.state.engine.templates[job.id] = job
    draft = owner.state.fork()
    instance = draft.engine.accept(draft.engine.story_offer(job.id, caller.session.player_id),
        tuple(owner.participant(pid) for pid in (roster or (caller.session.player_id,))), owner.now())
    owner.write(draft)
    game.commit_commerce()
    owner.scenes.reconcile()
    actors = [a for a in owner.world.actors.values() if a.behaviour.get('mission') == instance.id]
    return owner, instance.id, actors


def test_game_9_3_frozen_roster_permissions_survive_leaving_crew_and_reject_late_join(city) -> None:
    game, caller = city
    second = game.connect({'user_id': 2, 'handle': 'Second', 'node_name': 'test'})
    third = game.connect({'user_id': 3, 'handle': 'Third', 'node_name': 'test'})
    create(game, second, name='Second', card='none')
    create(game, third, name='Third', card='none')
    place(game, second, 'vatside-clinics', (21, 3))
    place(game, third, 'vatside-clinics', (22, 3))
    owner, iid, actors = mission(city, roster=(caller.session.player_id, second.session.player_id))
    target = actors[0]
    assert game.core.combat.legal(body(game, second), target)
    assert game.core.npcs.escort(body(game, third), target) is False
    assert not game.core.combat.legal(body(game, third), target)
    assert not game.core.combat.legal(target, body(game, third))
    assert private_visible(body(game, second), target)
    assert not private_visible(body(game, third), target)
    # Even joining the current social crew grants no accepted mission access.
    crews = game.core.crews
    crews.perform(caller.session, 'invite', third.session.player_id)
    invitation = next(iter(crews.registry.invites.values()))
    crews.perform(third.session, 'accept', invitation.id)
    assert not game.core.combat.legal(body(game, third), target)
    outsider = body(game, third)
    game.core.world.enter(outsider, target.zone, (target.x-1, target.y))
    assert move(outsider, game.core.world.zones[target.zone], 'right', game.clock.now_tick()+100)
    assert outsider.position == target.position  # Invisible bodies cannot block the street.
    assert not mission_pair(Actor('street-npc', 'Street', kind='npc'), target)


def test_game_9_3_npc_defeat_progress_and_loot_share_the_actual_source_write(city) -> None:
    game, caller = city
    owner, iid, actors = mission(city)
    target, source = actors[0], body(game, caller)
    target.health = 0
    game.core.npcs.died(source, target)
    effect = game.core.commerce.outbox[0]
    assert effect['contracts_state']['engine']['instances'][iid]['state'] == 'complete'
    assert owner.state.engine.instances[iid].state == 'active'
    game.commit_commerce(error=True)
    assert target.id in owner.world.actors and target.health == 1
    assert owner.state.engine.instances[iid].state == 'active'
    target.health = 0
    game.core.npcs.died(source, target)
    game.commit_commerce()
    assert owner.state.engine.instances[iid].state == 'complete'
    assert target.id not in owner.world.actors
    owner.scenes.reconcile()
    assert not any(a.behaviour.get('mission') == iid for a in owner.world.actors.values())


def test_architecture_15_2_deferred_impact_observes_prior_source_and_contract_commit(city) -> None:
    game, caller = city
    owner, iid, actors = mission(city, quantity=2)
    one, two = actors
    source = body(game, caller)
    commerce = owner.commerce
    flush = commerce.after_settle
    delivered = []
    def deferred_impact() -> None:
        flush()
        if not delivered:
            delivered.append(True)
            two.health = 0
            game.core.npcs.died(source, two)
    commerce.after_settle = deferred_impact
    one.health = 0
    game.core.npcs.died(source, one)
    effects = game.commit_commerce()
    assert len(effects) == 2
    assert owner.state.engine.instances[iid].state == 'complete'
    assert owner.state.engine.instances[iid].stages[0].subjects == {one.id, two.id}


def test_game_9_3_scene_checkpoint_reconstructs_same_units_without_replaying_completed_targets(city) -> None:
    game, caller = city
    owner, iid, actors = mission(city, quantity=2)
    survivor, defeated = actors
    survivor.health, survivor.shock = 13, 31
    defeated.health = 0
    game.core.npcs.died(body(game, caller), defeated)
    game.commit_commerce()
    saved = owner.record()
    before = survivor.id, survivor.position, survivor.health, survivor.shock
    owner.world.leave(survivor)
    owner.install(saved)
    owner.scenes.reconcile()
    rebuilt = [a for a in owner.world.actors.values() if a.behaviour.get('mission') == iid]
    assert [(a.id, a.position, a.health, a.shock) for a in rebuilt] == [before]
    assert owner.state.engine.instances[iid].stages[0].subjects == {defeated.id}


def test_game_9_3_subdue_uses_commit_receipt_and_cannot_be_replaced_by_lethal(city) -> None:
    game, caller = city
    owner, iid, actors = mission(city, resolution='subdue')
    target, source = actors[0], body(game, caller)
    owner.subdued(source, target)
    game.commit_commerce(error=True)
    assert target.id in owner.world.actors and owner.state.engine.instances[iid].state == 'active'
    owner.subdued(source, target)
    game.commit_commerce()
    assert target.stance == 'restrained' and target.id not in owner.world.actors
    assert owner.state.engine.instances[iid].state == 'complete'


def test_game_9_3_willing_escort_arrives_only_after_following_and_a_saved_source_receipt(city) -> None:
    game, caller = city
    owner, iid, actors = mission(city, verb='escort')
    target, source = actors[0], body(game, caller)
    assert target.behaviour['willing']
    assert game.core.npcs.escort(source, target)
    game.core.world.enter(target, source.zone, (21, 3))
    owner.scenes.escorts(game.clock.now_tick())
    assert owner.state.engine.instances[iid].state == 'active'
    game.commit_commerce(error=True)
    assert target.id in owner.world.actors
    owner.scenes.escorts(game.clock.now_tick())
    game.commit_commerce()
    assert owner.state.engine.instances[iid].state == 'complete'
    assert target.id not in owner.world.actors
