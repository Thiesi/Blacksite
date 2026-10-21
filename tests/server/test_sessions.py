"""Design §14 limits, architecture §5.3 coalescing and §8.2 reconnects."""

from blacksite.server.protocol import Frame
from blacksite.server.sessions import QUEUE_LIMIT
from tests.harness import HeadlessServer


def intent(name: str = "move") -> Frame:
    return Frame("intent", {"name": name, "args": {}})


def test_rate_limit_inputs_20_per_s() -> None:
    server = HeadlessServer()
    client = server.connect()
    for _ in range(25):
        client.send(intent())
    assert len(client.session.input_queue) == 20
    server.step(10)
    client.send(intent())
    assert len(client.session.input_queue) == 1


def test_rate_limit_chat_4_per_5s() -> None:
    server = HeadlessServer()
    client = server.connect()
    for _ in range(6):
        client.send(intent("chat"))
    assert len(client.session.input_queue) == 4
    server.step(49)
    client.send(intent("emote"))
    assert not client.session.input_queue
    server.step()
    client.send(intent("chat"))
    assert len(client.session.input_queue) == 1


def test_market_1_per_second_and_input_queue_bounded() -> None:
    server = HeadlessServer()
    client = server.connect()
    for _ in range(3):
        client.send(intent("market.list"))
    assert len(client.session.input_queue) == 1
    # Don't drain ticks: a stalled consumer still cannot grow indefinitely.
    for _ in range(10):
        server.clock.advance(10)
        for _ in range(20):
            client.send(intent())
    assert len(client.session.input_queue) == QUEUE_LIMIT


def test_reconnect_within_60s_replaces() -> None:
    server = HeadlessServer()
    old = server.connect()
    old.session.player_id = "test-origin:player:1"
    old.send(intent())
    new = server.connect()
    assert new.session.player_id == old.session.player_id
    assert old.session.closed
    assert not old.session.input_queue
    assert server.frames_for(old)[-1].data["reason"] == "replaced"
    server.core.sessions.disconnect(old.session)
    assert new.session.id in server.core.sessions.active
    assert new.session.rate_counters["input"]


def test_expired_reconnect_does_not_inherit() -> None:
    server = HeadlessServer()
    old = server.connect()
    old.session.player_id = "old-player"
    server.core.sessions.disconnect(old.session)
    server.step(601)
    assert server.connect().session.player_id is None


def test_coalesce_after_3_revisions() -> None:
    server = HeadlessServer()
    client = server.connect()
    server.frames_for(client)
    session = client.session
    session.view_revision = 4
    full = Frame("view", {"rev": 5, "kind": "zone", "body": {}})
    delta = Frame("delta", {"rev": 5, "base": 4, "ops": []})
    assert session.publish_view(full, delta, 1)
    assert server.frames_for(client)[0].type == "view"
    assert not session.publish_view(full, delta, 1)
    session.acknowledge(999)
    assert session.ack_revision == 0
    session.acknowledge(5)
    assert session.ack_revision == 5


def test_bye_never_dropped() -> None:
    server = HeadlessServer()
    client = server.connect()
    server.frames_for(client)
    session = client.session
    for i in range(QUEUE_LIMIT):
        session.send(Frame("delta", {"rev": i + 1, "base": i, "ops": []}))
    assert not session.send(Frame("delta", {"rev": 65, "base": 64, "ops": []}))
    assert session.needs_full_view
    session.send(Frame("bye", {"reason": "maintenance", "text": "You disconnect."}))
    assert [frame.type for frame in server.frames_for(client)] == ["bye"]


def test_reliable_overflow_disconnects_and_next_snapshot_clears_old_deltas() -> None:
    server = HeadlessServer()
    session = server.connect().session
    session.send_queue.clear()
    for i in range(QUEUE_LIMIT):
        session.send(Frame("pong", {"t": i}))
    session.send(Frame("pong", {"t": 100}))
    assert session.closed and session.send_queue[0].type == "bye"

    other = server.connect({"user_id": 2, "handle": "Other"}).session
    other.send_queue.clear()
    other.send(Frame("delta", {"rev": 2, "base": 1, "ops": []}))
    other.needs_full_view = True
    other.publish_view(Frame("view", {"rev": 3, "kind": "zone", "body": {}}), None, 1)
    assert [frame.type for frame in other.send_queue] == ["view"]
