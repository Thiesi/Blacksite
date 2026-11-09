"""Game 5.5 / entities 1.8: active reach and the declared covered crowd."""

from copy import deepcopy
from dataclasses import replace

import pytest

from blacksite.content.schema import Behaviour, Region, Spawner
from blacksite.content.validate import validate
from blacksite.server.npcs.templates import REACH_ACTIVE_TICKS, PROVOCATION_SECONDS, make_actor
from tests.npcs.test_engine import city, body
from tests.npcs.test_truce import row, npc, guard


@pytest.mark.parametrize('template', ['npc-sodium-regular', 'npc-plainclothes-warden'])
@pytest.mark.parametrize('stance,active,hold', [
    ('normal', True, True), ('normal', False, False),
    ('down', True, False), ('dead', True, False),
    ('sleeper', True, False), ('jacked', True, False),
])
def test_game_5_5_only_active_talk_capable_callers_hold_wander(city, template, stance, active, hold):
    game, caller = city
    source = body(game, caller)
    source.stance = stance
    actor = make_actor(game.core.characters.content.npcs[template], 'wanderer', {'home': (21, 3)})
    zone = game.core.world.zones[source.zone]
    game.core.world.enter(actor, zone.id, (21, 3))
    tick = caller.session.last_action_tick + REACH_ACTIVE_TICKS + (0 if active else 1)
    assert game.core.npcs.reach_holders(actor, zone, tick) == ([source.position] if hold else [])
    assert REACH_ACTIVE_TICKS == 300


def test_game_5_5_wander_filters_actual_steps_without_extra_rng(city):
    game, caller = city
    zone = game.core.world.zones[body(game, caller).zone]
    actor = make_actor(game.core.characters.content.npcs['npc-sodium-regular'], 'wanderer', {'home': (21, 3)})
    game.core.world.enter(actor, zone.id, (21, 3))
    rng = deepcopy(zone.rng)
    rng.choice((-1, 0, 1)); rng.choice((-1, 0, 1)); rng.randint(2, 10)
    game.core.npcs.act(actor, zone, game.clock.now_tick(), set())
    assert max(abs(actor.x-20), abs(actor.y-3)) <= 1
    assert zone.rng.getstate() == rng.getstate()


@pytest.mark.parametrize('template', ['npc-sodium-regular', 'npc-plainclothes-warden'])
@pytest.mark.parametrize('offset', [(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x, y) != (0, 0)])
def test_game_5_5_wander_keeps_every_neighbour_in_reach_over_many_ticks(city, template, offset):
    game, caller = city
    zone = game.core.world.zones[body(game, caller).zone]
    tile = 20+offset[0], 3+offset[1]
    actor = make_actor(game.core.characters.content.npcs[template], 'wanderer', {'home': tile})
    game.core.world.enter(actor, zone.id, tile)
    for tick in range(game.clock.now_tick(), game.clock.now_tick()+100):
        game.core.npcs.act(actor, zone, tick, set())
        assert max(abs(actor.x-20), abs(actor.y-3)) <= 1


def test_game_5_5_hold_does_not_block_a9_return_home(city):
    game, caller = city
    zone = game.core.world.zones[body(game, caller).zone]
    actor = make_actor(game.core.characters.content.npcs['npc-sodium-regular'], 'wanderer',
                       {'home': (25, 3), 'region': Region(25, 3, 2, 2)})
    game.core.world.enter(actor, zone.id, (21, 3))
    game.core.npcs.act(actor, zone, game.clock.now_tick(), set())
    assert actor.position == (22, 3)


def crowd(game):
    zone = game.core.world.zones['sodium-row']
    zone.template = replace(zone.template, meta=replace(zone.template.meta, spawners=(
        Spawner('crowd', 'npc-sodium-regular', 1, 60, tile=(28, 3)),
        Spawner('cover', 'npc-plainclothes-warden', 1, 60, tile=(29, 3), poses_as='crowd'),
        Spawner('other-crowd', 'npc-sodium-regular', 1, 60, tile=(28, 5)),
    )))
    actors = [npc(game, key, aid, tile) for key, aid, tile in (
        ('npc-sodium-regular', 'regular', (28, 3)),
        ('npc-plainclothes-warden', 'undercover', (29, 3)),
        ('npc-sodium-regular', 'other', (28, 5))) ]
    for actor, group in zip(actors, ('crowd', 'cover', 'other-crowd')):
        actor.behaviour['spawner'] = group
        game.core.npcs.spawners.slots[f'{zone.id}:{group}:0'] = {'actor': actor.id, 'until': 0}
    return zone, actors


@pytest.mark.parametrize('victim', [0, 1])
def test_game_5_5_declared_crowd_flees_and_calms_together_without_reveal(row, victim):
    game, caller, _ = row
    zone, (regular, covered, other) = crowd(game)
    source = body(game, caller)
    keeper = guard(game)
    arm = game.core.characters.content.items['wpn_kestrel_sidearm'].weapon
    game.core.combat.shot(source, (regular, covered)[victim], arm)
    assert keeper.target == source.id
    source.target = covered.id
    view = game.core.combat.target_view(source)
    assert view['name'] == 'Sodium regular' and view['class'] == 'civilian'
    assert not source.marked
    assert game.core.characters.players[source.id].warden_heat_until is None
    for actor in (regular, covered):
        assert actor.target == source.id and actor.behaviour['state'] == 'flee'
        assert not actor.revealed_to
        game.core.npcs.evaluate(actor, zone, game.clock.now_tick())
        assert actor.behaviour['state'] == 'flee' and not actor.revealed_to
    assert not game.core.npcs.hostile(other, source) and other.target is None
    game.clock.advance(PROVOCATION_SECONDS * 10)
    for actor in (regular, covered):
        game.core.npcs.act(actor, zone, game.clock.now_tick(), set())
        assert actor.target is None and actor.behaviour['state'] == 'base'


@pytest.mark.parametrize('victim', [0, 1])
def test_game_5_5_guards_answer_for_posed_faction_not_secret_faction(row, victim):
    game, caller, _ = row
    zone, actors = crowd(game)
    content = game.core.characters.content
    # A nontruce fixture separates faction recruitment from keeper response.
    zone.template = replace(zone.template, meta=replace(zone.template.meta, truce=None))
    regular = content.npcs['npc-sodium-regular']
    content.npcs[regular.id] = replace(regular, faction='sable')
    actors[0].faction = 'sable'
    local = guard(game)
    true_warden = npc(game, 'npc-warden-response', 'real-warden', (31, 3))
    source = body(game, caller)
    arm = content.items['wpn_kestrel_sidearm'].weapon
    game.core.combat.shot(source, actors[victim], arm)
    assert local.target == source.id
    assert true_warden.target is None
    assert source.id not in actors[1].revealed_to


def test_game_5_5_unarmed_cover_never_joins_secret_faction_guard_response(row):
    game, caller, _ = row
    zone, actors = crowd(game)
    content = game.core.characters.content
    covered = content.npcs['npc-plainclothes-warden']
    content.npcs[covered.id] = replace(covered, behaviours=(Behaviour('warden'),))
    target = npc(game, 'npc-warden-response', 'real-warden', (31, 3))
    source = body(game, caller)
    game.core.npcs.provoked(source, target)
    assert actors[1].target is None and not actors[1].revealed_to


def test_game_5_5_crowd_lost_sight_close_is_shared_across_evaluation_phases(row):
    game, caller, _ = row
    zone, (regular, covered, _) = crowd(game)
    source = body(game, caller)
    game.core.npcs.provoked(source, regular)
    tick = game.clock.now_tick()
    regular.behaviour.update(last_seen=tick-199, phase=(tick+1) % 5)
    covered.behaviour.update(last_seen=tick-197, phase=(tick+2) % 5)
    game.core.world.enter(source, zone.id, (90, 3))
    for elapsed in (1, 2, 3):
        game.step()
        for actor in (regular, covered):
            assert actor.behaviour['state'] == ('flee' if elapsed < 3 else 'base')
            assert (actor.target is None) == (elapsed == 3)


def test_entities_1_8_poses_as_validator_rejects_missing_wrong_zone_and_mismatch(repo_root):
    from blacksite.content.loader import load_content
    content = load_content(repo_root/'src/blacksite/content')
    assert not validate(content)
    zone = content.zones['sodium-row']
    foreign = next(sp.id for other in content.zones.values() if other.id != zone.id
                   for sp in other.meta.spawners if sp.id not in {sp.id for sp in zone.meta.spawners})
    for counterpart in (None, 'missing-crowd', foreign, 'plainclothes-warden'):
        content.zones[zone.id] = replace(zone, meta=replace(zone.meta, spawners=tuple(
            replace(sp, poses_as=counterpart) if sp.id == 'plainclothes-warden' else sp
            for sp in zone.meta.spawners)))
        assert any('poses_as' in problem.message for problem in validate(content))
    content.zones[zone.id] = zone
    regular = content.npcs['npc-sodium-regular']
    for change in ({'name': 'Other regular'}, {'behaviours': (Behaviour('guard'),)}):
        content.npcs[regular.id] = replace(regular, **change)
        assert any('poses_as' in problem.message for problem in validate(content))
    content.npcs[regular.id] = regular
    content.npcs['other-cover'] = replace(content.npcs['npc-plainclothes-warden'], id='other-cover')
    content.zones[zone.id] = replace(zone, meta=replace(zone.meta, spawners=(
        *(replace(sp, poses_as='other-cover') if sp.id == 'plainclothes-warden' else sp
          for sp in zone.meta.spawners),
        Spawner('other-cover', 'other-cover', 1, 60, tile=(10, 3), poses_as='sodium-regular'))))
    assert any('uncovered counterpart' in problem.message for problem in validate(content))
