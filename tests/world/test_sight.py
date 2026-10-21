"""Game design 5.2 sight and reciprocal wall occlusion."""

from blacksite.server.world.actors import Actor
from blacksite.server.world.registry import World
from blacksite.server.world.sight import line, line_of_sight, sees_actor, visible_tiles


def test_radius_10_in_wake_hall_and_cache(world: World) -> None:
    actor = Actor("test:actor:1", "Observer", x=6, y=5)
    zone = world.zones["vatside-wake-hall"]
    assert zone.template.meta.sight_radius == 10
    visible = visible_tiles(actor, zone, 10)
    assert (16, 5) in visible and (17, 5) not in visible
    assert visible_tiles(actor, zone, 10) is visible
    actor.x += 1
    assert visible_tiles(actor, zone, 10) is not visible


def test_opaque_wall_blocks_los_and_symmetric(world: World) -> None:
    zone = world.zones["vatside-wake-hall"]
    assert not line_of_sight(zone, (19, 5), (22, 5))
    for x in range(4, 18):
        for y in range(3, 16):
            a, b = (x, y), (27, 14)
            assert line(a, b) == list(reversed(line(b, a)))
            assert line_of_sight(zone, a, b) == line_of_sight(zone, b, a)


def test_stealth_halves_range_to_be_seen(world: World) -> None:
    zone = world.zones["vatside-wake-hall"]
    observer = Actor("test:actor:1", "A", x=6, y=5)
    target = Actor("test:actor:2", "B", x=14, y=5)
    visible = visible_tiles(observer, zone, 10)
    assert sees_actor(observer, target, visible, 10)
    target.stance = "stealth"
    assert not sees_actor(observer, target, visible, 10)
    target.x = 11
    assert sees_actor(observer, target, visible, 10)
