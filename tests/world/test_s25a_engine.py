"""S25a regressions use shipped hubs and fixtures, never S25's maps."""

from copy import deepcopy
from dataclasses import replace
from random import Random

import pytest

from blacksite.content.loader import ContentTree
from blacksite.content.schema import ObjectSpec, Tile
from blacksite.server.protocol import Frame
from blacksite.server.world.actors import Actor
from blacksite.server.world.registry import World
from blacksite.server.world.sight import sight_radius
from blacksite.server.world.zone import ObjectState
from tests.character_helpers import act, create, place
from tests.harness import HeadlessServer


@pytest.mark.parametrize("kind", ["light", "camera", "salvage_field"])
def test_game_5_6_passive_prop_underfoot_does_not_block_adjacent_jack_in(
        content_tree: ContentTree, kind: str) -> None:
    game = HeadlessServer(deepcopy(content_tree), character_state={})
    caller = game.connect()
    create(game, caller, archetype=0)
    zone = game.core.world.zones['vatside-wake-hall']
    terminal = next(obj for obj in zone.objects.values() if obj.spec.kind == 'terminal')
    tile = next((terminal.spec.tile[0]+dx, terminal.spec.tile[1]+dy)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if zone.passable((terminal.spec.tile[0]+dx, terminal.spec.tile[1]+dy))
        and not any(obj.spec.tile == (terminal.spec.tile[0]+dx, terminal.spec.tile[1]+dy)
                    for obj in zone.objects.values()))
    place(game, caller, zone.id, tile)
    zone.objects['fixture-marker'] = ObjectState(ObjectSpec('fixture-marker', tile, kind,
        params={'ring': 1} if kind == 'salvage_field' else {}))
    game.core.salvage.tick()
    game.commit_commerce()
    act(game, caller, Frame('key', {'k': 'e', 't': 0}))
    assert caller.session.player_id in game.core.lattice.presences


def test_game_5_6_console_underfoot_preserves_interact_and_explicit_j(
        content_tree: ContentTree) -> None:
    game = HeadlessServer(deepcopy(content_tree), character_state={})
    caller = game.connect()
    create(game, caller, archetype=0)
    zone = game.core.world.zones['vatside-wake-hall']
    terminal = next(obj for obj in zone.objects.values() if obj.spec.kind == 'terminal')
    tile = (terminal.spec.tile[0]+1, terminal.spec.tile[1])
    place(game, caller, zone.id, tile)
    zone.objects['fixture-console'] = ObjectState(ObjectSpec('fixture-console', tile, 'descent_console',
        params={'season_door': True, 'name': 'The season door is sealed.'}))
    act(game, caller, Frame('key', {'k': 'e', 't': 0}))
    assert caller.session.player_id not in game.core.lattice.presences
    assert any(frame.type == 'log' and any('season door is sealed' in line['text'].lower()
        for line in frame.data['lines']) for frame in game.frames_for(caller))
    act(game, caller, Frame('key', {'k': 'j', 't': 0}))
    assert caller.session.player_id in game.core.lattice.presences


@pytest.mark.parametrize('zone_id,base', [
    ('under-service', 5), ('under-drowned', 4), ('under-caverns', 3),
    ('under-outworks', 6), ('under-shaft-foot', 10),
])
def test_game_5_2_undercity_per_zone_sight_and_existing_light_effects(
        world: World, zone_id: str, base: int) -> None:
    # The new geography belongs to S25b. Exercise its gazetteer lighting
    # values on a hub fixture through the production sight calculation.
    zone = world.zones['vatside-wake-hall']
    zone.template = replace(zone.template, meta=replace(zone.template.meta,
        id=zone_id, sight_radius=base, sight_radius_night=None))
    actor = Actor('observer', 'Wide界', x=6, y=5)
    assert sight_radius(actor, zone, False) == base
    actor.effects = [{'dark_sight': 5}]  # Existing carried-light floor path.
    assert sight_radius(actor, zone, False) == max(base, 5)
    actor.effects = [{'kind': 'flare', 'dark_sight': 8}]
    assert sight_radius(actor, zone, False) == max(base, 8)
    actor.effects = []
    actor.modifiers = {'dark_sight_bonus': 3}
    assert sight_radius(actor, zone, False) == base+(3 if base <= 5 else 0)
    actor.modifiers = {}
    light = ObjectState(ObjectSpec('fixture-lamp', actor.position, 'light'), state={'enabled': False})
    zone.objects[light.spec.id] = light
    assert sight_radius(actor, zone, False) == min(base, 5)
    light.state['enabled'] = True
    assert sight_radius(actor, zone, False) == base


def test_game_5_2_expired_passage_recovers_from_public_spawn(world: World) -> None:
    zone = world.zones['vatside-wake-hall']
    saved = (7, 5)
    zone.geometry[saved] = 'wall'
    tile = world.free_tile(zone.id, saved, Actor('returning', 'Returning'))
    assert tile != saved and zone.passable(tile)
    pending = [zone.template.meta.spawn]
    seen = set(pending)
    while pending:
        x, y = pending.pop()
        for neighbour in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
            if neighbour not in seen and zone.passable(neighbour) and not zone.tiles[zone.tile_id(neighbour)].hazard:
                seen.add(neighbour)
                pending.append(neighbour)
    assert tile in seen
    available = seen-{a.position for a in zone.actors.values()}
    assert abs(tile[0]-saved[0])+abs(tile[1]-saved[1]) == min(
        abs(p[0]-saved[0])+abs(p[1]-saved[1]) for p in available)


def test_game_8_4_hazard_fields_only_spawn_harvestable_nodes(content_tree: ContentTree) -> None:
    game = HeadlessServer(deepcopy(content_tree), character_state={})
    salvage = game.core.salvage
    zone = game.core.world.zones['vatside-wake-hall']
    # Make almost all otherwise available floor hazardous: any unfiltered
    # seed would put a node where damage interrupts every harvest.
    safe = (6, 5)
    for y in range(zone.template.height):
        for x in range(zone.template.width):
            if zone.passable((x, y)):
                zone.geometry[x, y] = 'hazard'
    zone.geometry[safe] = 'floor'
    for seed in range(8):
        draft = {'zones': {zone.id: {'ring': 1, 'nodes': {}}}, 'serial': 0}
        assert salvage.spawn(zone.id, draft, Random(seed))
        assert next(iter(draft['zones'][zone.id]['nodes'].values()))['tile'] == list(safe)


def test_architecture_6_1_idle_salvage_keeps_rng_and_receipts(content_tree: ContentTree) -> None:
    game = HeadlessServer(deepcopy(content_tree), character_state={})
    salvage = game.core.salvage
    zone = game.core.world.zones['vatside-wake-hall']
    marker = ObjectSpec('fixture-field', (6, 5), 'salvage_field', params={'ring': 1})
    zone.objects[marker.id] = ObjectState(marker)
    salvage.tick()
    assert game.commit_commerce()
    before = deepcopy(salvage.state)
    salvage.tick()
    assert salvage.state == before and not game.core.commerce.outbox
    salvage.elapsed += salvage.rules.respawn_seconds
    salvage.tick()
    assert game.commit_commerce()
    assert salvage.state['zones'][zone.id]['respawn_at'] > before['zones'][zone.id]['respawn_at']
