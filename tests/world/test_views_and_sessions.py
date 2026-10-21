"""Architecture 5.3/5.4, UI 2 and two-caller deterministic integration."""

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path

from blacksite.content.loader import ContentTree
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from blacksite.server.protocol import Frame, encode
from blacksite.server.views.zone_view import camera
from tests.harness import FakeClient, HeadlessServer


def display(game: HeadlessServer, client: FakeClient, width: int = 80, height: int = 24) -> Display:
    model = Display(DoorInfo(Path('.'), Path('.'), client.session.door_info, width, height, "256", 3600))
    for frame in game.frames_for(client):
        model.receive(frame, 0)
    return model


def receive(game: HeadlessServer, client: FakeClient, model: Display, ack: bool = True) -> list[Frame]:
    frames = game.frames_for(client)
    for frame in frames:
        model.receive(frame, game.clock.now_tick() / 10)
        if ack and frame.type in ("view", "delta"):
            client.send(Frame("ack", {"rev": frame.data["rev"]}))
    return frames


def test_b_sees_a_move_and_never_receives_other_private_name(game: HeadlessServer) -> None:
    a = game.connect({"user_id": 1, "handle": "AlphaSecretName界"})
    b = game.connect({"user_id": 2, "handle": "Beta"})
    left, right = display(game, a), display(game, b)
    game.step()
    receive(game, a, left)
    receive(game, b, right)
    assert len(right.body["actors"]) == 2
    actor_id = a.session.player_id
    for _ in range(3):
        a.send(Frame("key", {"k": "down", "t": 0}))
        game.step(2)
        receive(game, a, left)
        packets = receive(game, b, right)
        assert any(frame.type == "delta" for frame in packets)
    other = next(actor for actor in right.body["actors"] if actor["id"] == actor_id)
    assert (other["x"], other["y"]) == (6, 8)
    assert "AlphaSecretName" not in json.dumps(right.body)
    assert left.body["me"]["name"] == "AlphaSecretName界"


def test_hidden_actor_objects_memory_and_night_sight(game: HeadlessServer) -> None:
    a = game.connect()
    model = display(game, a)
    game.step()
    receive(game, a, model)
    assert model.body["tiles"][5][16] >= 0
    assert "wake-terminal" not in {obj["id"] for obj in model.body["objects"]}
    actor = game.core.world.actors[a.session.player_id]
    zone = game.core.world.zones[actor.zone]
    zone.template = replace(zone.template, meta=replace(zone.template.meta, sight_radius_night=5))
    game.clock.epoch = datetime(2026, 1, 1, 20, 30, tzinfo=timezone.utc)
    game.step()
    receive(game, a, model)
    assert model.body["tiles"][5][16] == -2
    assert model.body["remembered"][5][16] >= 0
    assert model.body["me"]["clock"] == "20:30"
    # Two nearby bodies separated by the corridor wall cannot see each other.
    b = game.connect({"user_id": 2, "handle": "Behind the wall"})
    game.core.world.enter(actor, zone.id, (19, 6))
    game.core.world.enter(game.core.world.actors[b.session.player_id], zone.id, (21, 6))
    game.step()
    receive(game, a, model)
    assert len(model.body["actors"]) == 1


def test_reconnect_replacement_and_old_transport_cannot_remove_successor(game: HeadlessServer) -> None:
    old = game.connect()
    game.step()
    old.send(Frame("intent", {"name": "move", "args": {"dir": "down"}}))
    game.step()
    old_id = old.session.player_id
    new = game.connect({"user_id": 1, "handle": "Renamed界"})
    assert new.session.player_id == old_id
    assert game.core.world.actors[old_id].position == (6, 6)
    assert game.core.world.actors[old_id].name == "Renamed界"
    game.core.sessions.disconnect(old.session)
    assert old_id in game.core.world.actors
    assert len(game.core.world.zones["vatside-wake-hall"].listeners) == 1
    game.core.sessions.disconnect(new.session)
    game.step(601)
    assert not game.core.simulation.avatars


def test_resync_lag_full_and_idle_sends_no_view(game: HeadlessServer) -> None:
    client = game.connect()
    model = display(game, client)
    game.step()
    receive(game, client, model, ack=False)
    kinds = []
    for _ in range(5):
        client.send(Frame("intent", {"name": "move", "args": {"dir": "down"}}))
        game.step(2)
        kinds += [frame.type for frame in receive(game, client, model, ack=False) if frame.type in ("view", "delta")]
    assert "delta" in kinds and "view" in kinds
    client.send(Frame("ack", {"rev": client.session.view_revision}))
    client.send(Frame("intent", {"name": "resync", "args": {}}))
    game.step()
    assert any(frame.type == "view" for frame in receive(game, client, model))
    game.step(20)
    assert not receive(game, client, model)


def test_server_maps_vi_and_sprints_and_same_tick_input_cannot_speed_hack(game: HeadlessServer) -> None:
    client = game.connect()
    client.session.keymap_id = "vi"
    game.step()
    for _ in range(4):
        client.send(Frame("key", {"k": "J", "t": 0}))
    game.step()
    actor = game.core.world.actors[client.session.player_id]
    assert actor.position == (6, 6) and actor.stamina == 68
    client.send(Frame("key", {"k": "j", "t": 0}))
    game.step()
    assert actor.position == (6, 7) and actor.stamina == 69


def test_camera_scroll_at_four_tiles_and_large_layout(game: HeadlessServer) -> None:
    client = game.connect()
    actor = game.core.world.actors[client.session.player_id]
    zone = game.core.world.zones["vatside-clinics"]
    actor.x, actor.y = 20, 15
    first = camera(actor, zone, 80, 24, None)
    assert (first["w"], first["h"]) == (55, 17)
    actor.x = 51
    moved = camera(actor, zone, 80, 24, first)
    assert moved["x"] == 1
    large = camera(actor, zone, 132, 50, None)
    assert (large["w"], large["h"]) == (80, 34)


def test_delta_budget_on_typical_walk(game: HeadlessServer) -> None:
    client = game.connect()
    model = display(game, client)
    game.step()
    receive(game, client, model)
    sizes = []
    for key in ["down"] * 8 + ["right"] * 10 + ["up"] * 6 + ["left"] * 10:
        client.send(Frame("key", {"k": key, "t": 0}))
        game.step(2)
        sizes += [len(encode(frame)) for frame in receive(game, client, model) if frame.type in ("view", "delta")]
    assert sorted(sizes)[len(sizes) // 2] <= 2048
    assert max(sizes) <= 16384


def test_queued_snapshot_remains_immutable_while_later_moves_publish(game: HeadlessServer) -> None:
    client = game.connect()
    game.step()
    snapshot = next(frame for frame in client.session.send_queue if frame.type == "view")
    original = encode(snapshot)
    for direction in ("down", "right", "down"):
        client.send(Frame("intent", {"name": "move", "args": {"dir": direction}}))
        game.step(2)
    assert encode(snapshot) == original
