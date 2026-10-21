"""Game design 3.1, 5.1 and 5.2 movement contracts."""

from blacksite.server.world.actors import Actor
from blacksite.server.world.movement import SPRINT_COST, SPRINT_TICKS, STAMINA_REGEN, WALK_TICKS, move, regenerate
from blacksite.server.world.registry import World


def test_walk_200ms_per_tile(world: World) -> None:
    actor = Actor("test:actor:1", "Walker")
    world.enter(actor, "vatside-wake-hall", (6, 5))
    zone = world.zones[actor.zone]
    assert WALK_TICKS == 2
    assert move(actor, zone, "right", 1)
    assert not move(actor, zone, "right", 2)
    assert move(actor, zone, "right", 3)
    assert actor.position == (8, 5)


def test_sprint_100ms_and_stamina_drain(world: World) -> None:
    actor = Actor("test:actor:1", "Runner")
    world.enter(actor, "vatside-wake-hall", (6, 5))
    zone = world.zones[actor.zone]
    assert (SPRINT_TICKS, SPRINT_COST, STAMINA_REGEN) == (1, 2, 1)
    for tick in (1, 2, 3):
        assert move(actor, zone, "right", tick, sprint=True)
        regenerate(actor, 1, tick)
    assert actor.stamina == 64 and actor.position == (9, 5)
    assert regenerate(actor, 1, 4) and actor.stamina == 65


def test_diagonal_same_cost_and_no_corner_cut(world: World) -> None:
    actor = Actor("test:actor:1", "Walker")
    world.enter(actor, "vatside-wake-hall", (6, 5))
    zone = world.zones[actor.zone]
    assert move(actor, zone, "down_right", 1)
    assert actor.position == (7, 6) and actor.cooldowns["move"] == 3
    world.enter(actor, zone.id, (19, 13))
    assert not move(actor, zone, "down_right", 3)


def test_wall_and_actor_block_and_zero_stamina_walks(world: World) -> None:
    a, b = Actor("test:actor:1", "A"), Actor("test:actor:2", "B")
    world.enter(a, "vatside-wake-hall", (6, 5))
    world.enter(b, a.zone, (7, 5))
    zone = world.zones[a.zone]
    assert not move(a, zone, "right", 1)
    assert a.position == (6, 5)
    world.leave(b)
    a.stamina = 0
    assert move(a, zone, "right", 1, sprint=True)
    assert a.cooldowns["move"] == 3 and a.stamina == 0
    world.enter(a, zone.id, (19, 5))
    assert not move(a, zone, "right", 3)


def test_design_3_1_preview_pools() -> None:
    actor = Actor("test:actor:1", "Preview")
    assert actor.health == actor.health_max == 50 + 2 * 40
    assert actor.stamina == actor.stamina_max == 30 + 20 + 40 // 2
