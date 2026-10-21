"""Architecture 6.1/15.2 zone lifecycle, layered geometry and safety."""

from dataclasses import replace

import pytest

from blacksite.content.schema import TileChange, ZoneLayout
from blacksite.server.world.actors import Actor
from blacksite.server.world.movement import move
from blacksite.server.world.registry import World


def test_dormant_lazy_wake_and_seeded_rng(world: World) -> None:
    zone = world.zones["vatside-wake-hall"]
    assert zone.dormant
    assert zone.activate("session-a", 100) == 100
    assert not zone.dormant
    zone.deactivate("session-a", 130)
    assert zone.dormant and zone.wake(200) == 70
    other = World(world.content, {key: value.seed for key, value in world.zones.items()})
    assert [zone.rng.randrange(10000) for _ in range(20)] == [other.zones[zone.id].rng.randrange(10000) for _ in range(20)]


def test_actor_in_one_zone_only(world: World) -> None:
    actor = Actor("test:actor:1", "A")
    world.enter(actor, "vatside-wake-hall", (6, 5))
    world.enter(actor, "vatside-clinics", (3, 2))
    assert actor.id not in world.zones["vatside-wake-hall"].actors
    assert world.actors[actor.id] is actor
    with pytest.raises(ValueError):
        world.enter(Actor(actor.id, "duplicate"), "vatside-wake-hall", (6, 5))


def test_closed_member_door_blocks_movement_and_invalidates_sight(world: World) -> None:
    from blacksite.server.world.sight import visible_tiles

    zone = world.zones["vatside-clinics"]
    door = next(obj for obj in zone.objects.values() if obj.spec.kind == "door" and obj.spec.tile == (70, 12))
    actor = Actor("test:actor:1", "A")
    world.enter(actor, zone.id, (70, 13))
    assert zone.set_door(door.spec.id, False)
    before = visible_tiles(actor, zone, 12)
    assert (70, 10) not in before and not zone.passable(door.spec.tile)
    assert zone.set_door(door.spec.id, True)
    assert zone.passable(door.spec.tile) and (70, 10) in visible_tiles(actor, zone, 12)
    assert zone.set_door(door.spec.id, False)
    assert (70, 10) not in visible_tiles(actor, zone, 12)


def test_layer_expiry_preserves_other_sources_and_occupied_body(world: World) -> None:
    zone = world.zones["vatside-clinics"]
    actor = Actor("test:actor:1", "A")
    world.enter(actor, zone.id, (31, 18))
    zone.schedule_layout("service:cold", "reserve", 0, 4)
    zone.schedule_layout("event:closure", "reserve", 0, 2)
    zone.compose(0)
    assert zone.passable(actor.position)
    assert move(actor, zone, "right", 1)
    zone.compose(1)
    assert not zone.passable((31, 18))
    zone.compose(2)
    assert not zone.passable((31, 18)) and "service:cold" in zone.layers
    zone.compose(4)
    assert zone.passable((31, 18)) and not zone.layers


def test_safe_body_indirect_delayed_and_forced_movement(world: World) -> None:
    a, b = Actor("test:actor:1", "A"), Actor("test:actor:2", "B")
    world.enter(a, "vatside-clinics", (30, 18))
    world.enter(b, a.zone, (32, 18))
    assert world.permits_harm(a, b)
    # A previously accepted delayed/indirect effect must recheck the body.
    world.enter(b, a.zone, (10, 8))
    b.effects = [{"jacked": True}]
    assert not world.permits_harm(a, b)
    zone = world.zones[b.zone]
    assert zone.safety_at(b.position) == "pocket"
    assert not move(b, zone, "right", 1, forced=True)
    world.enter(a, "vatside-wake-hall", (6, 5))
    assert not world.permits_harm(a, b)


def test_hazard_warning_and_safe_geometry_guard(world: World) -> None:
    zone = world.zones["vatside-clinics"]
    unsafe = ZoneLayout("unsafe", (TileChange((10, 8), "hazard"),), ((10, 8),))
    zone.template = replace(zone.template, meta=replace(zone.template.meta, layouts=(unsafe,)))
    with pytest.raises(ValueError, match="five seconds"):
        zone.schedule_layout("event:bad", "unsafe", 0, 10, 49)
    zone.schedule_layout("event:bad", "unsafe", 0, 10, 50)
    zone.compose(50)
    assert zone.tile_id((10, 8)) != "hazard"


def test_stacked_closures_keep_escape_and_expiry_does_not_undo_other_layer(world: World) -> None:
    zone = world.zones["vatside-clinics"]
    grid = [list(row) for row in zone.template.grid]
    for y in range(1, 33):
        grid[y][30] = "floor" if y in (16, 20) else "wall"
    variants = (ZoneLayout("upper", (TileChange((30, 16), "locked-door"),)),
                ZoneLayout("lower", (TileChange((30, 20), "locked-door"),)))
    zone.template = replace(zone.template, grid=tuple(map(tuple, grid)), meta=replace(zone.template.meta, layouts=variants))
    zone.schedule_layout("a:service", "upper", 0, 2)
    zone.schedule_layout("b:event", "lower", 0, 4)
    zone.compose(0)
    assert not zone.passable((30, 16)) and zone.passable((30, 20))
    zone.compose(2)
    assert zone.passable((30, 16)) and not zone.passable((30, 20))
