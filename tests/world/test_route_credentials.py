"""Game 5.6: commissioned Spire and Shaft routes use real authorities."""

from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest

from blacksite.content.loader import ContentTree
from blacksite.content.schema import Exit, Requirement
from blacksite.content.validate import validate
from blacksite.server.protocol import Frame
from blacksite.server.world.exits import permitted
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


def gated_game(content_tree: ContentTree, requirement: Requirement,
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
