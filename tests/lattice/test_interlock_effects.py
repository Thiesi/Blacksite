"""Game 6.4/7.5: typed effects preserve safety, expiry and in-flight travel."""

from copy import deepcopy
from dataclasses import replace

import pytest

from blacksite.content.schema import TileChange, ZoneLayout
from blacksite.server.clock import TICK_HZ
from blacksite.server.interlock_effects import lighting_radius
from blacksite.server.world.actors import Actor
from blacksite.server.world.exits import schedule
from tests.character_helpers import place
from tests.lattice.test_engine import actor, intent, runners
from tests.lattice.test_encounters import enter
from tests.lattice.test_interlock import control_room, flip


def retarget(game, presence, kind, **changes):
    interlock = game.core.lattice.interlock
    control = control_room(game, presence)
    control = replace(control, **changes)
    interlock.controls[presence.core, control.id] = control
    graph = game.core.lattice.encounters.core(presence).graph
    room = graph.rooms[presence.room]
    graph.rooms[room.id] = replace(room, controls=tuple(control if c.id == control.id else c for c in room.controls))
    zone = game.core.world.zones[control.target.zone]
    obj = zone.objects[control.target.object]
    obj.spec = replace(obj.spec, kind=kind, params={k: v for k, v in obj.spec.params.items() if k != "open"})
    obj.open = None
    obj.state = {"enabled": True, "controlled": False}
    return interlock, zone, obj, control


def test_game_6_4_only_opted_in_owner_effect_persists(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    interlock, zone, obj, control = retarget(game, presence, "light", action="toggle", owner_policy=True)
    faction = next(iter(game.core.loop.content.factions))
    game.core.characters.players[presence.player_id].faction = faction
    interlock.set_owner(presence.core, faction)
    game.commit_commerce()
    flip(game, a)
    game.commit_commerce()
    assert obj.state["enabled"] is False
    game.clock.advance(1801*TICK_HZ)
    interlock.compose()
    assert obj.state["enabled"] is False
    interlock.set_owner(presence.core, None)
    game.commit_commerce()
    assert obj.state["enabled"] is True


def test_game_6_4_lighting_changes_actual_sight_locally(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    interlock, zone, obj, control = retarget(game, presence, "light", action="toggle")
    obj.spec = replace(obj.spec, tile=(31, 5))
    flip(game, a)
    game.commit_commerce()
    assert lighting_radius(actor(game, a), zone, 12) == 5
    distant = Actor("distant", "Distant", "Distant", x=60, y=5)
    assert lighting_radius(distant, zone, 12) == 12
    game.clock.advance(control.reset_seconds*TICK_HZ)
    interlock.compose()
    assert lighting_radius(actor(game, a), zone, 12) == 12


def test_game_6_4_tram_hold_is_one_platform_30s_and_120s_immunity(runners):
    game, a, b, c = runners
    # Public district travel is outside this focused controller test.
    presence = enter(game, a, "lat-civic-ledger")
    presence.instance = presence.core = None
    presence.sector = "lat-core"
    presence.cell = next(c.id for c in game.core.lattice.sectors.records["lat-core"].cells if c.core_id == "lat-tram-signal")
    intent(game, a, "lat.enter", core="lat-tram-signal")
    control = control_room(game, presence, "tram-hold")
    interlock = game.core.lattice.interlock
    zone = game.core.world.zones[control.target.zone]
    obj = zone.objects[control.target.object]
    platform = interlock.platforms(zone, obj)[0]
    travel = schedule(platform, interlock.now())
    original_departure = travel.departure
    intent(game, a, "lat.flip", control="tram-hold")
    game.step(3*TICK_HZ)
    game.commit_commerce()
    interlock.sim.departures.apply((zone.id, platform.id), travel)
    assert travel.departure == original_departure+30
    assert travel.arrival == original_departure+40
    assert len(interlock.sim.departures.deadlines) == 1
    with pytest.raises(ValueError, match="immunity"):
        interlock.start_flip(presence, "tram-hold")
    travel.departed = True
    before = travel.departure, travel.arrival
    interlock.sim.departures.apply((zone.id, platform.id), travel)
    assert (travel.departure, travel.arrival) == before
    until, immune = interlock.sim.departures.deadlines[zone.id, platform.id]
    assert immune-until == 120


def test_game_6_4_turret_power_and_remote_initiator_permission(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    interlock, zone, obj, control = retarget(game, presence, "turret", action="disable")
    zone.template = replace(zone.template, meta=replace(zone.template.meta, safety="open", pockets=()))
    obj.spec = replace(obj.spec, params={"spawners": ["fixture-turret"]})
    turret = Actor("fixture:turret", "Turret", "Turret", kind="npc", behaviour={"spawner": "fixture-turret", "template": "npc-kestrel-staff", "phase": -1})
    game.core.world.enter(turret, zone.id, (29, 5))
    flip(game, a)
    game.commit_commerce()
    assert turret.behaviour["powered"] is False
    assert not game.core.combat.legal(turret, actor(game, b))
    # Re-enabling is still attributed to the physical initiating body.
    changed = replace(control, action="enable")
    graph = interlock.lat.encounters.core(presence).graph
    graph.rooms[presence.room] = replace(graph.rooms[presence.room], controls=(changed,))
    interlock.controls[presence.core, changed.id] = changed
    flip(game, a)
    game.commit_commerce()
    assert turret.behaviour["powered"]
    assert game.core.combat.legal(turret, actor(game, b))
    place(game, a, "vatside-wake-hall", (6, 5))
    assert not game.core.combat.legal(turret, actor(game, b))


def test_game_6_4_control_hazard_warns_and_expires_without_erasing_event(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    interlock, zone, obj, control = retarget(game, presence, "gantry", action="call",
        warning_seconds=5, safety_policy="hazard", reset_seconds=30)
    zone.template = replace(zone.template, meta=replace(zone.template.meta, safety="open", pockets=(),
        layouts=(ZoneLayout("fixture-gantry", (TileChange((31, 6), "hazard"),)),
                 ZoneLayout("fixture-event", (TileChange((32, 7), "cover-1"),)))))
    obj.spec = replace(obj.spec, params={"layout": "fixture-gantry"})
    flip(game, a)
    game.commit_commerce()
    zone.schedule_layout("event:fixture", "fixture-event", game.clock.now_tick(), 60*TICK_HZ)
    before = actor(game, b).health
    game.step(4*TICK_HZ)
    assert actor(game, b).health == before and zone.tile_id((31, 6)) != "hazard"
    game.step(2*TICK_HZ)
    assert actor(game, b).health < before and zone.tile_id((31, 6)) == "hazard"
    game.clock.advance(30*TICK_HZ)
    interlock.compose()
    assert zone.tile_id((31, 6)) != "hazard"
    assert zone.tile_id((32, 7)) == "cover-1" and "event:fixture" in zone.layers


def test_game_6_4_deferred_hazard_hit_settles_before_next_transfer(runners):
    game, a, b, c = runners
    interlock = game.core.lattice.interlock
    zone = game.core.world.zones["core-plaza"]
    zone.template = replace(zone.template, meta=replace(zone.template.meta, safety="open", pockets=()))
    source, target = actor(game, a), actor(game, b)
    before = target.health
    assert interlock.commerce.settle(None, {}, interlock.commerce.items,
        interlock.commerce.caches, interlock.commerce.serial, lambda success: None)
    interlock.physical.pending_damage[target.id, source.id, zone.id] = 5
    # Moving off the hazardous tile cannot erase an already-earned hit.
    game.core.world.enter(target, zone.id, (31, 7))
    observed = []
    interlock.commerce.enqueue_system(lambda: observed.append(target.health))
    game.commit_commerce()
    assert target.health == before-5 and observed == [before-5]
    # A protected body at impact is still protected from this player source.
    assert interlock.commerce.settle(None, {}, interlock.commerce.items,
        interlock.commerce.caches, interlock.commerce.serial, lambda success: None)
    interlock.physical.pending_damage[target.id, source.id, zone.id] = 5
    zone.template = replace(zone.template, meta=replace(zone.template.meta, safety="safe"))
    game.commit_commerce()
    assert target.health == before-5


def test_game_6_4_newer_route_effect_wins_without_erasing_older_timer(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    interlock, zone, obj, closed = retarget(game, presence, "lift", action="close",
        safety_policy="route", reset_seconds=600,
        alternate_route=game.core.world.zones["core-plaza"].template.meta.exits[1].id)
    exit_id = zone.template.meta.exits[0].id
    obj.spec = replace(obj.spec, params={"exits": [exit_id]})
    opened = replace(closed, id="fixture-open", action="open", reset_seconds=300)
    graph = interlock.lat.encounters.core(presence).graph
    graph.rooms[presence.room] = replace(graph.rooms[presence.room], controls=(closed, opened))
    interlock.controls[presence.core, opened.id] = opened
    flip(game, a)
    game.commit_commerce()
    assert (zone.id, exit_id) in interlock.sim.locked_exits
    flip(game, a, opened.id)
    game.commit_commerce()
    assert (zone.id, exit_id) not in interlock.sim.locked_exits

    game.clock.advance(301*TICK_HZ)
    interlock.compose()
    assert (zone.id, exit_id) in interlock.sim.locked_exits
    game.clock.advance(300*TICK_HZ)
    interlock.compose()
    assert (zone.id, exit_id) not in interlock.sim.locked_exits


def test_game_6_4_camera_mission_state_cannot_blind_combat_or_enable_safe_harm(runners):
    from blacksite.server.npcs.templates import make_actor
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    interlock, zone, obj, control = retarget(game, presence, "camera", action="disable")
    template = interlock.content.npcs["npc-warden-response"]
    warden = make_actor(template, "fixture:warden", {"home": (29, 5), "phase": -1})
    game.core.world.enter(warden, zone.id, (29, 5))
    target = actor(game, b)
    assert game.core.combat.visible(warden, target)
    assert not game.core.combat.legal(warden, target)
    flip(game, a)
    game.commit_commerce()
    assert not obj.state["enabled"]
    assert game.core.combat.visible(warden, target)
    assert not game.core.combat.legal(warden, target)


def test_game_6_4_patrol_beacon_moves_linked_crew_and_expires_after_15min(runners):
    from blacksite.server.npcs.templates import make_actor
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    interlock, zone, obj, control = retarget(game, presence, "patrol_beacon", action="call", reset_seconds=900)
    obj.spec = replace(obj.spec, params={"spawners": ["fixture-patrol"], "destination": [28, 5]})
    template = interlock.content.npcs["npc-kestrel-staff"]
    patrol = make_actor(template, "fixture:patrol", {"home": (29, 5), "spawner": "fixture-patrol", "phase": -1})
    game.core.world.enter(patrol, zone.id, (29, 5))
    flip(game, a)
    game.commit_commerce()
    game.step(2*TICK_HZ)
    assert patrol.position == (28, 5)
    game.clock.advance(900*TICK_HZ)
    interlock.compose()
    assert "interlock_diversion" not in patrol.behaviour
