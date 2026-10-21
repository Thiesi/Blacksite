"""Headless multi-session route through the ten-zone hub (S08)."""

from blacksite.server.protocol import Frame
from tests.character_helpers import act, create, place
from tests.world.test_exits import character_game, exit_at


def test_wake_hall_to_tin_halo_path(content_tree):
    game,caller = character_game(content_tree)
    observer = game.connect({"user_id":2,"handle":"Other界","node_name":"test"})
    create(game,observer)
    place(game,observer,"core-plaza",(87,4))
    for target in ("vatside-clinics","core-plaza","sodium-row","sodium-tin-halo","sodium-row","core-plaza","core-tram-hub","vatside-clinics","core-tram-hub"):
        exit_at(game,caller,target)
        act(game,caller,Frame("intent",{"name":"interact","args":{}}))
        avatar = game.core.characters.sim.avatars[caller.session.user_id]
        if avatar.travel:
            due = avatar.travel.arrival
            while game.clock.now_utc().timestamp() < due:
                game.step()
        assert avatar.zone == avatar.actor.zone == caller.session.subscribed == target
        if target == "core-plaza":
            views = game.core.characters.sim.views[observer.session.id]
            assert any(a["id"]==avatar.actor.id for a in views.previous["body"]["actors"]) or avatar.actor.y > 25
    act(game,caller,Frame("key",{"k":"m","t":0}))
    frame = next(f for f in reversed(game.frames_for(caller)) if f.type=="view")
    assert frame.data["kind"] == "menu"
    assert frame.data["body"]["title"] == "CITY MAP - The Core"
    assert "core-precinct" not in {r["id"] for r in frame.data["body"]["rows"]}
    act(game,caller,Frame("intent",{"name":"menu_select","args":{}}))
    assert next(f for f in reversed(game.frames_for(caller)) if f.type=="view").data["kind"] == "text"
    act(game,caller,Frame("key",{"k":"escape","t":0}))
    assert next(f for f in reversed(game.frames_for(caller)) if f.type=="view").data["kind"] == "zone"


def test_map_closes_after_60_seconds_on_contested_street(content_tree):
    game,caller=character_game(content_tree)
    place(game,caller,"vatside-clinics",(30,18))
    act(game,caller,Frame("key",{"k":"m","t":0}))
    game.step(599)
    assert caller.session.id not in game.core.characters.sim.maps
    assert any(f.type=="toast" and "not protected" in f.data["text"] for f in game.frames_for(caller))
