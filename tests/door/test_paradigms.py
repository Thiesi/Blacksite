"""Paradigm prototypes: street view and scenes over the same simulation."""

from dataclasses import asdict, replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.door.model import Display
from blacksite.door.present import scene
from blacksite.server.protocol import Frame
from blacksite.server.views import looks
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer
from tests.server.test_looks import move, sim

ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def content():
    return load_content(ROOT / "src/blacksite/content")


@pytest.fixture
def trial(monkeypatch):
    monkeypatch.setattr(looks, "TRIAL", True)


def connected(info, content, zone, tile, width=80, height=24, tier="256", mode="street"):
    game = HeadlessServer(content, zone)
    client = game.connect(width=width, height=height)
    game.step()
    move(game, client, zone, tile)
    display = Display(replace(info, width=width, height=height, color_depth=tier))
    display.receive(Frame("welcome", {"keymap": asdict(content.keymaps), "palette": asdict(content.palette)}), 0)
    display.present, display.view_mode = True, mode

    def pump(ticks=1):
        for _ in range(ticks):
            game.step()
            for frame in game.frames_for(client):
                for out in display.receive(frame, 1):
                    client.send(out)
    pump(2)
    return game, client, display, pump


def draw(display, width, height, now=50.0):
    display.force_full = display.dirty = True
    display.last_render = -1
    terminal = FakeTerminal(width, height)
    terminal.write(display.render(now)[0])
    return terminal.screen_text()


@pytest.mark.parametrize("mode", ["street", "scene"])
@pytest.mark.parametrize("width,height", [(80, 24), (132, 50)])
@pytest.mark.parametrize("tier", ["16", "256", "truecolor"])
def test_eye_level_views_replay_cleanly(info, content, trial, mode, width, height, tier) -> None:
    game, client, display, pump = connected(info, content, "core-plaza", (45, 26), width, height, tier, mode)
    client.send(display.shape_frame())
    pump(2)
    text = draw(display, width, height)
    assert "Meridian Plaza" in text and ("facing" in text if mode == "street" else "WAYS" in text)


def test_street_keys_turn_locally_and_step_absolutely(info, content) -> None:
    _, _, display, _ = connected(info, content, "core-plaza", (45, 26))
    display.heading = "up"
    assert display.key("left", 1) == [] and display.heading == "left"
    sent = display.key("up", 2)
    assert [f.data["k"] for f in sent] == ["left"]  # forward, while facing west
    assert [f.data["k"] for f in display.key("down", 3)] == ["right"]  # a step back
    assert display.key("shift-up", 4)[0].data["k"] == "shift-left"


def test_threat_hands_eye_level_views_to_the_tactical_map(info, content) -> None:
    _, _, display, _ = connected(info, content, "core-plaza", (45, 26))
    display.body["nearby"] = [{"id": "x", "name": "Hostile", "relation": "!", "role": "npc_hostile"}]
    assert "TACTICAL" in draw(display, 80, 24)
    assert display.key("up", 5)[0].data["k"] == "up"  # arrows are absolute again


def test_scene_chooses_a_way_and_the_server_walks_there(info, content, trial) -> None:
    game, client, display, pump = connected(info, content, "core-plaza", (45, 26), mode="scene")
    options = scene.ways(display.body)
    assert options and all(o["kind"] in ("place", "exit", "thing") for o in options)
    goal = next(o for o in options if o["name"] == "The fountain")
    display.scene_cursor = options.index(goal)
    sent = display.key("enter", 6)
    assert sent[0].data == {"name": "walk_to", "args": {"at": goal["at"]}}
    client.send(sent[0])
    actor = sim(game).avatars[client.session.user_id].actor
    start = actor.position
    pump(1)
    assert max(abs(actor.x - start[0]), abs(actor.y - start[1])) <= 1  # ordinary steps, not a jump
    pump(200)
    assert actor.position == tuple(goal["at"])
    assert session_walks(game) == {}


def session_walks(game):
    return sim(game).walks


def test_any_key_takes_back_control(info, content, trial) -> None:
    game, client, display, pump = connected(info, content, "core-plaza", (45, 26), mode="scene")
    client.send(Frame("intent", {"name": "walk_to", "args": {"at": [45, 36]}}))
    pump(3)
    assert session_walks(game)
    client.send(Frame("key", {"k": "i", "t": 0}))
    pump(1)
    assert not session_walks(game)


def test_walks_never_route_through_unknown_ground(info, content, trial) -> None:
    game, client, _, pump = connected(info, content, "vatside-clinics", (40, 3), mode="scene")
    actor = sim(game).avatars[client.session.user_id].actor
    client.send(Frame("intent", {"name": "walk_to", "args": {"at": [13, 10]}}))  # inside an unseen clinic
    pump(40)
    assert actor.position == (40, 3) and not session_walks(game)


def test_walk_and_deep_camera_are_trial_only(info, content) -> None:
    game, client, display, pump = connected(info, content, "core-plaza", (45, 26))
    client.send(Frame("intent", {"name": "walk_to", "args": {"at": [45, 30]}}))
    client.send(display.shape_frame())
    pump(10)
    assert not session_walks(game)
    assert display.body["viewport"]["h"] == 17


def test_deep_camera_looks_as_far_as_it_is_wide(info, content, trial) -> None:
    _, client, display, pump = connected(info, content, "core-plaza", (45, 26))
    client.send(display.shape_frame())
    pump(2)
    assert display.body["viewport"]["h"] == 40  # the whole plaza, north to south


# --- Prototype C: the auto view ---------------------------------------------


def auto(info, content, zone, tile):
    game, client, display, pump = connected(info, content, zone, tile, mode="auto")
    display.card_zone = None  # arrive again, now in auto
    client.send(display.shape_frame())
    pump(2)
    return game, client, display, pump


def test_auto_looks_on_arrival_then_settles_into_a_scene_on_safe_ground(info, content, trial) -> None:
    _, _, display, _ = auto(info, content, "core-plaza", (45, 26))
    assert display.context.choose(display.body, 1) == ("scene", "LOOK", True)
    looking = draw(display, 80, 24, now=1.5)
    assert "LOOK" in looking and "facing" in looking
    assert display.key("down", 2) == []  # the look closes; the scene's cursor moves
    assert display.context.choose(display.body, 2) == ("scene", "SCENE", False)
    assert "WAYS" in draw(display, 80, 24, now=2.5) and "SCENE" in draw(display, 80, 24, now=2.5)


def test_auto_uses_the_map_on_contested_ground(info, content, trial) -> None:
    _, _, display, _ = auto(info, content, "sodium-row", (34, 12))
    display.context.look_until = 0
    assert display.context.choose(display.body, 2)[:2] == ("map", "MAP")
    assert display.key("up", 2)[0].data["k"] == "up"  # tile by tile, absolute


def test_auto_holds_the_tactical_map_after_a_threat(info, content, trial) -> None:
    _, _, display, _ = auto(info, content, "core-plaza", (45, 26))
    calm = dict(display.body)
    threat = dict(calm, nearby=[{"id": "x", "name": "Hostile", "relation": "!", "role": "npc_hostile"}])
    assert display.context.choose(threat, 10)[:2] == ("map", "TACTICAL")
    assert display.context.choose(calm, 13)[:2] == ("map", "TACTICAL")  # no flicker out of a fight
    assert display.context.choose(calm, 16)[:2] == ("scene", "SCENE")


def test_auto_looks_where_a_walk_arrives(info, content, trial) -> None:
    game, client, display, pump = auto(info, content, "core-plaza", (45, 26))
    display.context.look_until = 0
    client.send(Frame("intent", {"name": "walk_to", "args": {"at": [45, 30]}}))
    pump(3)
    assert display.context.walk_goal == [45, 30]
    pump(80)
    assert display.context.look_until > 0 and display.context.walk_goal is None
