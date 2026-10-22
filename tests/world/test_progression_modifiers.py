"""Game 8.5/8.6: actual movement budgets and resource modifiers."""

import pytest

from blacksite.server.world.actors import Actor
from blacksite.server.world.movement import move, regenerate
from blacksite.server.world.sight import sight_radius, visible_tiles, sees_actor


def test_game_8_5_sprint_legs_keep_80ms_average_and_no_idle_burst(world):
    zone = world.zones["vatside-wake-hall"]
    counts = []
    for name, modifiers in (("plain", {}), ("legs", {"sprint_ms": 80, "stamina_cost_multiplier": .8})):
        actor = Actor(name, name, stamina=1000, stamina_max=1000, modifiers=modifiers)
        world.enter(actor, zone.id, (6,5))
        count = 0
        for tick in range(50):
            for _ in range(4):
                if move(actor, zone, "right" if count % 2 == 0 else "left", tick, sprint=True):
                    count += 1
        counts.append(count)
        assert actor.stamina == pytest.approx(1000-count*(1.6 if modifiers else 2))
        assert move(actor, zone, "right" if count % 2 == 0 else "left", 100, sprint=True)
        assert not move(actor, zone, "right", 100, sprint=True)
        world.leave(actor)
    assert counts == [50, 62]  # 5s of ticks, with bounded tick quantization.


def test_game_8_5_fractional_sprint_cost_and_regeneration_are_real(world):
    actor = Actor("legs", "Legs", stamina=1.7,
                  modifiers={"stamina_cost_multiplier": .8, "stamina_regen_multiplier": 1.5})
    world.enter(actor, "vatside-wake-hall", (6,5))
    assert move(actor, world.zones[actor.zone], "right", 1, sprint=True)
    assert actor.stamina == pytest.approx(.1)
    assert not regenerate(actor, 1, 1)
    assert regenerate(actor, 1, 2) and actor.stamina == pytest.approx(1.6)


def test_game_8_6_lullaby_slows_walk_and_sprint_without_changing_cost(world):
    actor = Actor("lullaby", "Lullaby", modifiers={"move_ms": 400})
    world.enter(actor, "vatside-wake-hall", (6,5))
    assert move(actor, world.zones[actor.zone], "right", 1, sprint=True)
    assert actor.cooldowns["move"] == 5 and actor.stamina == 68
    assert not move(actor, world.zones[actor.zone], "right", 4)
    assert move(actor, world.zones[actor.zone], "right", 5)


def test_game_8_5_lowlight_adds_dark_tiles_and_ghost_step_reduces_detection(world):
    actor = Actor("eyes", "Eyes", modifiers={"dark_sight_bonus": 3})
    world.enter(actor, "core-plaza", (36,13))
    zone = world.zones[actor.zone]
    # A real committed-style light state supplies S15's dark floor.
    light = next(o for o in zone.objects.values() if o.spec.kind == "light")
    actor.x, actor.y = light.spec.tile
    light.state["enabled"] = False
    assert sight_radius(actor, zone, False) == 8
    actor.effects.append({"dark_sight": 8})
    assert sight_radius(actor, zone, False) == 8
    world.leave(actor)
    zone = world.zones["vatside-wake-hall"]
    observer, target = Actor("observer","Observer"), Actor("ghost","Ghost",stance="stealth")
    world.enter(observer,zone.id,(6,5));world.enter(target,zone.id,(11,5))
    visible = visible_tiles(observer,zone,10)
    assert sees_actor(observer,target,visible,10)
    target.modifiers = {"stealth_sight_reduction": .6}
    assert not sees_actor(observer,target,visible,10)
