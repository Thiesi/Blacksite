"""City travel: game design §5.6 and the gazetteer tram timetable."""

from dataclasses import replace

import pytest

from blacksite.content.schema import Exit, Requirement
from blacksite.server.protocol import Frame
from blacksite.server.world.actors import Actor
from blacksite.server.world.exits import schedule, TRAM_INTERVAL_SECONDS, TRAM_RIDE_SECONDS, LIFT_SECONDS, CABLE_SECONDS
from tests.character_helpers import act, create, place, state
from tests.harness import HeadlessServer


def character_game(content_tree):
    game = HeadlessServer(content_tree, character_state={})
    caller = game.connect()
    create(game, caller)
    return game, caller


def exit_at(game, caller, target):
    manager = game.core.characters
    avatar = manager.sim.avatars[caller.session.user_id]
    ex = next(e for e in game.core.world.zones[avatar.zone].template.meta.exits if e.target_zone == target)
    place(game, caller, avatar.zone, ex.tile)
    return ex


def test_street_exit_instant(content_tree):
    game, caller = character_game(content_tree)
    place(game, caller, "vatside-clinics", (76,2))
    old = game.core.world.zones["vatside-clinics"]
    act(game, caller, Frame("intent", {"name":"move", "args":{"dir":"right"}}))
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    assert avatar.zone == caller.session.subscribed == "core-plaza"
    assert caller.session.id not in old.listeners
    assert avatar.actor.id not in old.actors
    assert avatar.actor.id in game.core.world.zones["core-plaza"].actors
    assert "core-plaza" in avatar.seen_zones
    frames = game.frames_for(caller)
    assert any(f.type == "view" and f.data["kind"] == "zone" and f.data["body"]["me"]["zone"] == "core-plaza" for f in frames)


def test_door_locked_by_pass_logs_and_stays(content_tree):
    game, caller = character_game(content_tree)
    zone = game.core.world.zones["vatside-wake-hall"]
    ex = replace(zone.template.meta.exits[0], requirement=Requirement("pass", "itm-vesper-card"))
    zone.template = replace(zone.template, meta=replace(zone.template.meta, exits=(ex,)))
    place(game, caller, zone.id, ex.tile)
    sim = game.core.characters.sim
    sim.access_provider = lambda session: {"items":[]}
    act(game, caller, Frame("intent", {"name":"interact", "args":{}}))
    assert sim.avatars[caller.session.user_id].zone == zone.id
    assert any(f.type == "log" and "requirement" in f.data["lines"][0]["text"] for f in game.frames_for(caller))
    sim.access_provider = lambda session: {"items":["itm-vesper-card"]}
    act(game, caller, Frame("intent", {"name":"interact", "args":{}}))
    assert sim.avatars[caller.session.user_id].zone == "vatside-clinics"


@pytest.mark.parametrize("kind,seconds", [("lift",1),("ladder",1),("cable",3)])
def test_lift_1s(content_tree, kind, seconds):
    game, caller = character_game(content_tree)
    zone = game.core.world.zones["vatside-wake-hall"]
    ex = replace(zone.template.meta.exits[0], kind=kind)
    zone.template = replace(zone.template, meta=replace(zone.template.meta, exits=(ex,)))
    place(game, caller, zone.id, ex.tile)
    act(game, caller, Frame("intent", {"name":"interact", "args":{}}))
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    assert avatar.actor.zone is None
    assert avatar.actor.id not in game.core.world.actors
    game.step(seconds*10-2)
    assert avatar.zone == zone.id
    game.step()
    assert avatar.zone == "vatside-clinics"
    assert avatar.actor.zone == avatar.zone


def test_tram_departs_every_90s_ride_10s(content_tree):
    assert (TRAM_INTERVAL_SECONDS,TRAM_RIDE_SECONDS,LIFT_SECONDS,CABLE_SECONDS) == (90,10,1,3)
    ex = Exit("tram", (2,2), "core-tram-hub", (2,3), "tram")
    assert (schedule(ex,89).departure,schedule(ex,89).arrival) == (90,100)
    assert schedule(ex,90).departure == 180
    game, caller = character_game(content_tree)
    place(game, caller,"core-tram-hub", (24,14))
    act(game,caller,Frame("key",{"k":"e","t":0}))
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    ride = avatar.travel
    assert avatar.actor.zone == "core-tram-hub"
    while game.clock.now_utc().timestamp() < ride.departure:
        game.step()
    assert avatar.actor.zone is None
    assert avatar.zone == "core-tram-hub"
    act(game,caller,Frame("key",{"k":"escape","t":0}))
    assert avatar.travel is ride
    while game.clock.now_utc().timestamp() < ride.arrival:
        game.step()
    assert avatar.actor.zone == "vatside-clinics"
    assert avatar.travel is None


def test_tram_lazy_wake_departure(content_tree):
    game,caller = character_game(content_tree)
    game.clock.advance(917)
    game.core.loop.step()
    place(game,caller,"core-tram-hub",(24,14))
    act(game,caller,Frame("key",{"k":"e","t":0}))
    ride = game.core.characters.sim.avatars[caller.session.user_id].travel
    assert ride.departure % 90 == 0
    assert ride.departure-game.clock.now_utc().timestamp() < 90


def test_s15_hold_bounded_then_immune_and_in_flight_unaffected():
    from blacksite.server.world.exits import DepartureHolds, MAX_HOLD_SECONDS, HOLD_IMMUNITY_SECONDS
    assert (MAX_HOLD_SECONDS,HOLD_IMMUNITY_SECONDS)==(30,120)
    holds=DepartureHolds()
    platform=("core-tram-hub","to-clinics")
    ride=schedule(Exit("to-clinics",(2,2),"vatside-clinics",(3,30),"tram"),89)
    assert holds.hold(platform,89,ride.departure)
    holds.apply(platform,ride)
    assert (ride.departure,ride.arrival)==(120,130)
    assert not holds.hold(platform,90,ride.departure)
    holds.apply(platform,ride)
    assert ride.departure==120
    ride.departed=True
    assert holds.hold(platform,240,270)
    holds.apply(platform,ride)
    assert ride.arrival==130


def test_exit_target_tile_passable(world):
    for zone in world.zones.values():
        for ex in zone.template.meta.exits:
            assert world.zones[ex.target_zone].passable(ex.target_tile)


def test_occupied_arrival_uses_neighbour(content_tree):
    game, caller = character_game(content_tree)
    ex = exit_at(game, caller, "vatside-clinics")
    blocker = Actor("blocker", "Other")
    game.core.world.enter(blocker,ex.target_zone,ex.target_tile)
    act(game,caller,Frame("key",{"k":"e","t":0}))
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    assert avatar.zone == ex.target_zone
    assert avatar.actor.position != blocker.position


def test_ride_survives_reconnect_and_restart(content_tree):
    game, caller = character_game(content_tree)
    place(game,caller,"core-tram-hub",(24,14))
    act(game,caller,Frame("key",{"k":"e","t":0}))
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    while not avatar.travel.departed:
        game.step()
    arrival = avatar.travel.arrival
    game.core.sessions.disconnect(caller.session)
    saved = state(game)
    restored = HeadlessServer(content_tree, character_state=saved, clock=game.clock)
    again = restored.connect()
    restored.step()
    av = restored.core.characters.sim.avatars[again.session.user_id]
    assert av.travel and av.actor.zone is None
    assert av.travel.arrival == arrival
    while restored.clock.now_utc().timestamp() < arrival:
        restored.step()
    assert av.zone == "vatside-clinics"
    restored.core.sessions.disconnect(again.session)
    assert av.actor.stance == "sleeper"  # Arrival platform is contested.


def test_memory_and_discovery_survive_round_trip(content_tree):
    game,caller = character_game(content_tree)
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    remembered = dict(avatar.perception.remembered[avatar.zone])
    exit_at(game,caller,"vatside-clinics")
    act(game,caller,Frame("key",{"k":"e","t":0}))
    exit_at(game,caller,"vatside-wake-hall")
    act(game,caller,Frame("key",{"k":"e","t":0}))
    assert set(remembered) <= avatar.perception.remembered["vatside-wake-hall"].keys()
    assert avatar.seen_zones == {"vatside-wake-hall","vatside-clinics"}


@pytest.mark.parametrize("restart",[False,True])
def test_offline_tram_arrival_obeys_destination_logout(content_tree,restart):
    game,caller=character_game(content_tree)
    place(game,caller,"core-tram-hub",(24,14))
    act(game,caller,Frame("key",{"k":"e","t":0}))
    avatar=game.core.characters.sim.avatars[caller.session.user_id]
    while not avatar.travel.departed: game.step()
    pid=avatar.actor.id
    game.core.sessions.disconnect(caller.session)
    if restart:
        game=HeadlessServer(content_tree,character_state=state(game),clock=game.clock)
    game.step(100)
    player=game.core.characters.players[pid]
    assert player.zone=="vatside-clinics"
    assert "travel" not in player.progress
    assert game.core.world.actors[pid].stance=="sleeper"
    game.step(600)
    assert pid not in game.core.world.actors
    assert player.zone=="vatside-wake-hall"
    again=game.connect()
    assert game.core.characters.sim.avatars[again.session.user_id].zone=="vatside-wake-hall"
