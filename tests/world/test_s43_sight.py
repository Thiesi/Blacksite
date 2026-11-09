"""S43: keep game 5.2 rays and existing visibility invalidation exact."""

from itertools import product
from typing import cast

import pytest

from karst41.content.loader import ContentTree
from karst41.content.schema import ObjectSpec, Tile
from karst41.server.views.zone_view import Perception, build
from karst41.server.world.actors import Actor
from karst41.server.world.registry import World
from karst41.server.world.sight import line_of_sight, sees_actor, sight_radius, visible_tiles
from karst41.server.world.zone import ObjectState, ZoneInstance


def reference_line(a: Tile, b: Tile) -> list[Tile]:
    """Frozen pre-S43 implementation, independent of production helpers."""
    if a > b:
        return list(reversed(reference_line(b, a)))
    x, y = a
    dx, dy = abs(b[0] - x), -abs(b[1] - y)
    sx, sy = (1 if x < b[0] else -1), (1 if y < b[1] else -1)
    error = dx + dy
    result = []
    while True:
        result.append((x, y))
        if (x, y) == b:
            return result
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x += sx
        if doubled <= dx:
            error += dx
            y += sy


class Field:
    def __init__(self, blocked: set[Tile]) -> None:
        self.blocked = blocked
        self.queries: list[Tile] = []

    def opaque(self, tile: Tile) -> bool:
        self.queries.append(tile)
        return tile in self.blocked


def test_game_5_2_all_octants_ties_and_ignored_endpoints_match_reference() -> None:
    # Every ordered endpoint pair, including equal/adjacent points, negative
    # coordinates and all tie slopes. Probe every possible single blocker
    # in the bounding box, not just cells that the new traversal visits.
    points = list(product(range(-2, 3), repeat=2))
    for a, b in product(points, repeat=2):
        interior = reference_line(a, b)[1:-1]
        field = Field({a, b})
        assert line_of_sight(cast(ZoneInstance, field), a, b)
        assert set(field.queries) == set(interior)
        assert len(field.queries) == len(interior)
        for tile in product(range(min(a[0], b[0]), max(a[0], b[0])+1),
                            range(min(a[1], b[1]), max(a[1], b[1])+1)):
            field = Field({tile, a, b})
            assert line_of_sight(cast(ZoneInstance, field), a, b) == (tile not in interior), (a, b, tile)
            assert a not in field.queries and b not in field.queries
    # Larger, long and shallow/steep rays retain the same tie cells.
    for a, b in (((-31, 17), (47, -22)), ((3, 3), (5, 91)), ((91, 5), (3, 3))):
        interior = reference_line(a, b)[1:-1]
        for tile in interior:
            assert not line_of_sight(cast(ZoneInstance, Field({tile})), a, b)


def reference_visible(actor: Actor, zone: ZoneInstance, radius: int) -> set[Tile]:
    return {(x, y) for y in range(max(0, actor.y-radius), min(zone.template.height, actor.y+radius+1))
            for x in range(max(0, actor.x-radius), min(zone.template.width, actor.x+radius+1))
            if (x-actor.x)**2+(y-actor.y)**2 <= radius**2
            and not any(zone.opaque(tile) for tile in reference_line(actor.position, (x, y))[1:-1])}


def render(actor: Actor, zone: ZoneInstance, content: ContentTree, p: Perception,
           width: int, *, scouted: set[Tile] | None = None) -> dict:
    body = build(actor, zone, p, content, width, 24 if width == 80 else 50,
                 '12:00', False, 0, scouted=scouted)
    assert actor.visible == reference_visible(actor, zone, sight_radius(actor, zone, False))
    return body


@pytest.mark.parametrize('width', (80, 132))
def test_game_5_2_door_close_and_open_refresh_sight_and_grid(
    world: World, content_tree: ContentTree, width: int,
) -> None:
    zone = world.zones['vatside-wake-hall']
    actor = Actor('s43:viewer', 'Viewer')
    world.enter(actor, zone.id, (6, 5))
    door = ObjectState(ObjectSpec('s43-door', (7, 5), 'door'), open=True)
    zone.objects[door.spec.id] = door
    zone.doors[door.spec.tile] = door
    p = Perception()
    render(actor, zone, content_tree, p, width)
    original, revision = actor.visible, p.grid_revision
    assert (8, 5) in original
    assert zone.set_door(door.spec.id, False)
    render(actor, zone, content_tree, p, width)
    assert actor.visible is not original and (8, 5) not in actor.visible
    assert p.grid_revision == revision+1
    assert zone.set_door(door.spec.id, True)
    render(actor, zone, content_tree, p, width)
    assert (8, 5) in actor.visible and p.grid_revision == revision+2


@pytest.mark.parametrize('width', (80, 132))
def test_game_5_2_light_radius_and_dark_sight_refresh_sight_and_grid(
    world: World, content_tree: ContentTree, width: int,
) -> None:
    zone = world.zones['vatside-wake-hall']
    actor = Actor('s43:viewer', 'Viewer')
    world.enter(actor, zone.id, (6, 5))
    light = ObjectState(ObjectSpec('s43-light', actor.position, 'light'), state={'enabled': True})
    zone.objects[light.spec.id] = light
    p = Perception()
    render(actor, zone, content_tree, p, width)
    assert (14, 5) in actor.visible
    original, revision = actor.visible, p.grid_revision
    light.state['enabled'] = False
    # Even without an explicit geometry clear, the effective radius must
    # invalidate the cached result. The real control/expiry path is also
    # covered in the interlock effects tests.
    render(actor, zone, content_tree, p, width)
    assert sight_radius(actor, zone, False) == 5
    assert actor.visible is not original and (14, 5) not in actor.visible
    assert p.grid_revision == revision+1
    actor.effects.append({'dark_sight': 8})
    render(actor, zone, content_tree, p, width)
    assert (14, 5) in actor.visible and p.grid_revision == revision+2


@pytest.mark.parametrize('width', (80, 132))
def test_game_5_2_actor_motion_stealth_and_travel_keep_visibility_current(
    world: World, content_tree: ContentTree, width: int,
) -> None:
    zone = world.zones['vatside-wake-hall']
    actor = Actor('s43:viewer', 'Viewer')
    world.enter(actor, zone.id, (6, 5))
    target = Actor('s43:target', 'Target', x=14, y=5)
    p = Perception()
    render(actor, zone, content_tree, p, width)
    original, revision = actor.visible, p.grid_revision
    assert sees_actor(actor, target, original, 10)
    target.stance = 'stealth'
    assert not sees_actor(actor, target, original, 10)
    target.stance, target.x = 'normal', 17
    assert not sees_actor(actor, target, original, 10)
    # A different actor's movement does not erase a valid geometry cache;
    # actor disclosure still uses the target's current position/stance.
    assert visible_tiles(actor, zone, 10) is original
    actor.x += 1
    render(actor, zone, content_tree, p, width)
    assert actor.visible is not original and p.grid_revision == revision+1
    assert sees_actor(actor, target, actor.visible, 10)
    world.enter(actor, zone.id, (6, 5))
    assert actor.sight_key is None
    render(actor, zone, content_tree, p, width)
    assert not sees_actor(actor, target, actor.visible, 10)


def test_game_5_2_resize_and_scouting_preserve_the_existing_grid_invalidation(
    world: World, content_tree: ContentTree,
) -> None:
    zone = world.zones['vatside-wake-hall']
    actor = Actor('s43:viewer', 'Viewer')
    world.enter(actor, zone.id, (6, 5))
    p = Perception()
    small = render(actor, zone, content_tree, p, 80)
    cached, revision = actor.visible, p.grid_revision
    large = render(actor, zone, content_tree, p, 132)
    assert large['viewport'] != small['viewport'] and p.grid_revision == revision+1
    assert actor.visible is cached
    assert (22, 5) not in actor.visible and (22, 5) not in p.remembered[zone.id]
    render(actor, zone, content_tree, p, 132, scouted={(22, 5)})
    assert (22, 5) in p.remembered[zone.id] and p.grid_revision == revision+2
    assert actor.visible is cached
