"""Game 5.6: commissioned Spire and Shaft routes use real authorities."""

from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest

from blacksite.content.loader import ContentTree
from blacksite.content.schema import Exit, Requirement
from blacksite.content.schema import ObjectSpec
from blacksite.content.validate import validate
from blacksite.server.protocol import Frame
from blacksite.server.world.exits import permitted
from blacksite.server.world.zone import ObjectState
from tests.character_helpers import act, create, place, state
from tests.harness import HeadlessServer


@pytest.mark.parametrize('access,allowed', [
    ({'standing': {'halvard': 9}, 'items': []}, False),
    ({'standing': {'halvard': 10}, 'items': []}, True),
    ({'standing': {'halvard': -100}, 'items': ['key_visitor_pass']}, True),
    ({'standing': {'wardens': 100}, 'items': []}, False),
])
def test_game_5_6_atrium_accepts_standing_or_carried_pass(access: dict[str, Any], allowed: bool) -> None:
    gate = Exit('visitor-lift', (1, 1), 'spire-mezzanine', (1, 1), 'lift',
                Requirement('faction', 'halvard', 10),
                alternatives=(Requirement('pass', 'key_visitor_pass'),))
    original = deepcopy(access)
    assert permitted(gate, access) is allowed
    assert access == original  # A permission check never spends a pass.


def gated_game(content_tree: ContentTree, requirement: Requirement | None,
               alternatives: tuple[Requirement, ...] = ()) -> tuple[Any, Any, Exit]:
    game = HeadlessServer(content_tree, character_state={})
    caller = game.connect()
    create(game, caller)
    zone = game.core.world.zones['vatside-wake-hall']
    gate = replace(zone.template.meta.exits[0], kind='lift', requirement=requirement,
                   alternatives=alternatives, locked_text='The cage stays sealed until the finale.')
    zone.template = replace(zone.template, meta=replace(zone.template.meta, exits=(gate,)))
    place(game, caller, zone.id, gate.tile)
    return game, caller, gate


def test_game_5_6_friendly_nonmember_is_refused_but_actual_member_boards(content_tree: ContentTree) -> None:
    game, caller, gate = gated_game(content_tree, Requirement('member', 'halvard'))
    manager = game.core.characters
    player = manager.players[caller.session.player_id]
    player.standing['halvard'] = 100
    act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    avatar = manager.sim.avatars[caller.session.user_id]
    assert avatar.travel is None and avatar.zone == 'vatside-wake-hall'
    assert any(frame.type == 'log' and 'cage stays sealed' in frame.data['lines'][0]['text']
               for frame in game.frames_for(caller))
    player.faction = 'halvard'
    player.standing['halvard'] = 0
    act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    assert avatar.travel and avatar.travel.departed
    game.step(10)
    assert avatar.zone == gate.target_zone


def test_game_5_6_disabled_route_does_not_claim_a_member_lacks_credentials(content_tree: ContentTree) -> None:
    game, caller, gate = gated_game(content_tree, Requirement('member', 'halvard'))
    manager = game.core.characters
    manager.players[caller.session.player_id].faction = 'halvard'
    manager.sim.locked_exits.add(('vatside-wake-hall', gate.id))
    act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    avatar = manager.sim.avatars[caller.session.user_id]
    assert avatar.travel is None
    messages = [line['text'] for frame in game.frames_for(caller) if frame.type == 'log'
                for line in frame.data['lines']]
    assert any('controls' in message for message in messages)
    assert not any('cage stays sealed' in message for message in messages)


def test_game_5_6_story_uses_source_provider_and_expiry_cannot_drop_inflight_body(content_tree: ContentTree) -> None:
    game, caller, gate = gated_game(content_tree, Requirement('story', 'shaft-cage'))
    manager = game.core.characters
    player = manager.players[caller.session.player_id]
    player.progress['story_permissions'] = ['shaft-cage']
    act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    avatar = manager.sim.avatars[caller.session.user_id]
    assert avatar.travel is None  # Arbitrary progress is not authority.
    manager.route_permissions = lambda source: frozenset({'shaft-cage'}) if source.id == player.id else frozenset()
    act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    assert avatar.travel and avatar.actor.zone is None
    manager.route_permissions = lambda source: frozenset()
    game.step(10)
    assert avatar.zone == gate.target_zone and avatar.actor.zone == gate.target_zone


def test_game_5_6_alternative_credentials_restore_with_acknowledged_journey(content_tree: ContentTree) -> None:
    game, caller, gate = gated_game(content_tree, Requirement('story', 'shaft-cage'),
                                    (Requirement('member', 'halvard'),))
    game.core.characters.players[caller.session.player_id].faction = 'halvard'
    act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    assert avatar.travel and avatar.travel.departed
    arrival = avatar.travel.arrival
    game.core.sessions.disconnect(caller.session)
    restored = HeadlessServer(content_tree, character_state=state(game), clock=game.clock)
    again = restored.connect()
    restored.step()
    resumed = restored.core.characters.sim.avatars[again.session.user_id]
    assert resumed.travel and resumed.travel.arrival == arrival
    assert resumed.travel.exit.alternatives == gate.alternatives
    assert not restored.core.characters.route_permissions(restored.core.characters.players[again.session.player_id])
    restored.step(10)
    assert resumed.zone == gate.target_zone


@pytest.mark.parametrize('primary,alternatives,reason', [
    (None, (Requirement('member', 'halvard'),), 'alternatives need a primary'),
    (Requirement('member', 'ninth-faction'), (), 'ninth-faction'),
    (Requirement('story', '../arbitrary-path'), (), 'story permission must be a slug'),
])
def test_entities_1_1_rejects_unbound_or_malformed_route_credentials(content_tree: ContentTree,
        primary: Requirement | None, alternatives: tuple[Requirement, ...], reason: str) -> None:
    tree = deepcopy(content_tree)
    zone = tree.zones['vatside-wake-hall']
    gate = replace(zone.meta.exits[0], requirement=primary, alternatives=alternatives)
    tree.zones[zone.id] = replace(zone, meta=replace(zone.meta, exits=(gate,)))
    assert any(reason in str(problem) for problem in validate(tree))


def test_game_5_6_bulkhead_accepts_local_open_latch_without_an_item(content_tree: ContentTree) -> None:
    game, caller, gate = gated_game(content_tree, Requirement('key', 'key_undercity'),
        (Requirement('open', 'vatside-wake-hall', object='fixture-bulkhead'),))
    zone = game.core.world.zones['vatside-wake-hall']
    latch = ObjectState(ObjectSpec('fixture-bulkhead', (2, 2), 'door'), open=False)
    zone.objects[latch.spec.id] = latch
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    assert avatar.travel is None
    latch.open = True  # Committed interlock state is the alternative authority.
    act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    assert avatar.travel and avatar.travel.departed
    game.step(10)
    assert avatar.zone == gate.target_zone


def test_game_5_6_same_named_latch_in_another_zone_grants_nothing() -> None:
    gate = Exit('bulkhead', (1, 1), 'under-outworks', (1, 1), 'door',
                Requirement('open', 'under-drowned', object='bulkhead'))
    assert not permitted(gate, {'zone': 'under-service', 'open_objects': {'bulkhead'}})


def test_game_5_6_hidden_door_is_usable_after_physically_finding_its_tile(content_tree: ContentTree) -> None:
    game, caller, original = gated_game(content_tree, None)
    zone = game.core.world.zones['vatside-wake-hall']
    gate = replace(original, hidden=True, kind='door')
    zone.template = replace(zone.template, meta=replace(zone.template.meta, exits=(gate,)))
    place(game, caller, zone.id, (gate.tile[0]-1, gate.tile[1]))
    focus, _ = game.core.interaction_views(caller.session)
    assert focus is None or focus['id'] != gate.id
    act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    assert avatar.zone == zone.id
    # The first adjacent interaction may close the ordinary physical
    # door. Open it before walking onto the unmarked transition tile.
    if gate.tile in zone.doors and not zone.doors[gate.tile].open:
        act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    act(game, caller, Frame('intent', {'name': 'move', 'args': {'dir': 'right'}}))
    assert avatar.actor.position == gate.tile
    focus, _ = game.core.interaction_views(caller.session)
    assert focus and focus['id'] == gate.id
    act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    assert avatar.zone == gate.target_zone


def test_game_5_6_walking_over_a_hidden_street_does_not_change_zone(content_tree: ContentTree) -> None:
    game, caller, original = gated_game(content_tree, None)
    zone = game.core.world.zones['vatside-wake-hall']
    gate = replace(original, hidden=True, kind='street')
    zone.template = replace(zone.template, meta=replace(zone.template.meta, exits=(gate,)))
    place(game, caller, zone.id, gate.tile)
    sim = game.core.characters.sim
    avatar = sim.avatars[caller.session.user_id]
    sim.interact(caller.session, avatar, game.clock.now_tick(), street=True)
    assert avatar.zone == zone.id and avatar.travel is None
    act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    assert avatar.zone == gate.target_zone
