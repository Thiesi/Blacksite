"""Architecture §5.3: additive server frames cannot trigger reconnect loops."""

import asyncio
import json
import logging
import struct
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from blacksite.door.client import run
from blacksite.door.connection import Connection, ServerFrames
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from blacksite.server.protocol import MAX_FRAME, Frame, ProtocolError, decode, encode, read_frame
from tests.door.test_display import welcome
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer


def wire(data: dict[str, Any]) -> bytes:
    payload = json.dumps(data, ensure_ascii=False).encode()
    return struct.pack("!I", len(payload)) + payload


def reader_for(data: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


def test_unknown_type_burst_logs_once_and_preserves_following_frame(caplog: pytest.LogCaptureFixture) -> None:
    async def scenario() -> None:
        policy = ServerFrames()
        reader = reader_for(wire({"type": "future", "arbitrary": [1, 2]}) * 1000
                            + wire({"type": "other-future"})
                            + encode(Frame("pong", {"t": 42})))
        assert await policy.read(reader) == Frame("pong", {"t": 42})
        # Once per door launch, including a replacement connection.
        assert await policy.read(reader_for(wire({"type": "future"})
                    + encode(Frame("pong", {"t": 43})))) == Frame("pong", {"t": 43})

    with caplog.at_level(logging.INFO, logger="blacksite.door.connection"):
        asyncio.run(scenario())
    assert [record.args for record in caplog.records] == [("future",), ("other-future",)]


@pytest.mark.parametrize("width,height", [(80, 24), (132, 50)])
@pytest.mark.parametrize("presentation", [False, True])
def test_unknown_view_keeps_screen_ack_and_recovers_on_known_full_view(
    info: DoorInfo, width: int, height: int, presentation: bool,
) -> None:
    async def scenario() -> None:
        model = Display(replace(info, width=width, height=height), presentation=presentation)
        model.connected = True
        model.receive(Frame("view", {"rev": 1, "kind": "text", "body": {"title": "Retained", "lines": []}}), 0)
        terminal = FakeTerminal(width, height)
        terminal.write(model.render(0)[0])
        before = terminal.screen_text()
        policy = ServerFrames()
        reader = reader_for(wire({"type": "view", "rev": 2, "kind": "future", "body": {"title": "Unrenderable"}})
            + encode(Frame("delta", {"rev": 3, "base": 2, "ops": [{"op": "replace", "path": "/body/title", "value": "Wrong"}]})) * 1000
            + encode(Frame("view", {"rev": 4, "kind": "text", "body": {"title": "Recovered", "lines": []}}))
            + encode(Frame("delta", {"rev": 5, "base": 4, "ops": [{"op": "replace", "path": "/body/title", "value": "Later"}]})))
        assert model.receive(await policy.read(reader), .2) == []
        for _ in range(1000):
            assert model.receive(await policy.read(reader), .2) == []
        assert model.connected and model.revision == 1 and model.body["title"] == "Retained"
        assert model.render(.2) == (b"", None)
        assert terminal.screen_text() == before and not model.resync_pending
        # A local repaint may still ACK only the last actually rendered view.
        model.key("ctrl-l", .3)
        repaint, ack = model.render(.3)
        terminal.write(repaint)
        assert ack == Frame("ack", {"rev": 1})
        assert terminal.screen_text() == before
        assert model.receive(await policy.read(reader), .4) == []
        assert model.receive(await policy.read(reader), .4) == []
        output, ack = model.render(.5)
        terminal.write(output)
        assert "Later" in terminal.screen_text() and ack == Frame("ack", {"rev": 5})
        assert not model.unsupported_view and not model.resync_pending

    asyncio.run(scenario())


def test_delta_introducing_unknown_kind_also_suspends_updates(info: DoorInfo) -> None:
    model = Display(info)
    model.receive(Frame("view", {"rev": 1, "kind": "text", "body": {"title": "Retained"}}), 0)
    model.render(0)
    assert model.receive(Frame("delta", {"rev": 2, "base": 1, "ops": [
        {"op": "replace", "path": "/kind", "value": "future"},
        {"op": "replace", "path": "/body/title", "value": "Wrong"}]}), .2) == []
    assert model.body["title"] == "Retained" and model.revision == 1
    assert model.receive(Frame("delta", {"rev": 3, "base": 2, "ops": []}), .3) == []
    assert model.unsupported_view and not model.resync_pending
    assert model.render(.4) == (b"", None)


@pytest.mark.parametrize("payload", [
    b'{"type":"pong","t":true}', b'{"type":"key","k":"e","t":0}',
    b'{"type":"view","rev":true,"kind":"future","body":{}}',
    b'{"type":"view","rev":2,"kind":"future","body":[]}',
    b'{"type":"view","rev":2,"kind":[],"body":{}}',
    b'{"type":"delta","rev":3,"base":2,"ops":false}',
    b'{"type":"future","x":NaN}', b'{"type":"future","x":1e999}',
    b'{"type":"future","x":1,"x":2}', b'[]', b'null', b'{', b'\xff',
])
def test_tolerance_keeps_all_other_wire_errors_strict(payload: bytes) -> None:
    async def scenario() -> None:
        with pytest.raises(ProtocolError):
            await ServerFrames().read(reader_for(struct.pack("!I", len(payload)) + payload))
    asyncio.run(scenario())


@pytest.mark.parametrize("size", [0, MAX_FRAME + 1])
def test_unknown_type_cannot_bypass_frame_size_limit(size: int) -> None:
    async def scenario() -> None:
        with pytest.raises(ProtocolError):
            await ServerFrames().read(reader_for(struct.pack("!I", size)))
    asyncio.run(scenario())


@pytest.mark.parametrize("data", [{"type": "future"}, {"type": "view", "rev": 1, "kind": "future", "body": {}}])
def test_shared_validation_encoding_and_service_read_remain_strict(data: dict[str, Any]) -> None:
    with pytest.raises(ProtocolError):
        decode(wire(data)[4:])
    with pytest.raises(ProtocolError):
        encode(Frame(data["type"], {k: v for k, v in data.items() if k != "type"}))
    async def scenario() -> None:
        with pytest.raises(ProtocolError):
            await read_frame(reader_for(wire(data)), "client")
    asyncio.run(scenario())


def test_service_core_rejects_unknown_client_frame() -> None:
    server = HeadlessServer()
    client = server.connect()
    server.frames_for(client)
    client.send(Frame("future", {"arbitrary": True}))
    assert not client.session.input_queue
    assert server.frames_for(client) == [Frame("bye", {"reason": "protocol", "text": "Invalid frame."})]


@pytest.mark.parametrize("response", [
    {"type": "future"}, {"type": "pong", "t": 1},
    {"type": "view", "rev": 1, "kind": "future", "body": {}},
    {"type": "welcome", "proto": 999, "server_version": "future", "player": None,
     "keymap": {}, "palette": {}, "motd": ""},
])
def test_handshake_does_not_tolerate_extensions(
    info: DoorInfo, monkeypatch: pytest.MonkeyPatch, response: dict[str, Any],
) -> None:
    class Writer:
        closed = False
        def write(self, data: bytes) -> None:
            pass
        async def drain(self) -> None:
            pass
        def close(self) -> None:
            self.closed = True
        async def wait_closed(self) -> None:
            pass

    async def scenario() -> None:
        writer = Writer()
        async def connect(install: Path) -> tuple[asyncio.StreamReader, Writer]:
            return reader_for(wire(response)), writer
        monkeypatch.setattr("blacksite.door.connection.connect", connect)
        (info.install / "secrets").mkdir()
        (info.install / "secrets" / "door.secret").write_text("00" * 32, encoding="ascii")
        connection = Connection()
        with pytest.raises(ProtocolError):
            await connection.open(info)
        assert writer.closed and connection.reader is None and connection.writer is None
    asyncio.run(scenario())


@pytest.mark.parametrize("width,height", [(80, 24), (132, 50)])
def test_supported_stream_renders_and_sends_identical_bytes(info: DoorInfo, repo_root: Path, width: int, height: int) -> None:
    async def scenario() -> None:
        strict, tolerant = (Display(replace(info, width=width, height=height)) for _ in range(2))
        frames = [welcome(repo_root),
            Frame("view", {"rev": 1, "kind": "text", "body": {"title": "Known", "lines": ["A vent hums."]}}),
            Frame("delta", {"rev": 2, "base": 1, "ops": [{"op": "replace", "path": "/body/title", "value": "Later"}]}),
            Frame("pong", {"t": 1})]
        data = b"".join(encode(frame) for frame in frames)
        a, b = reader_for(data), reader_for(data)
        policy = ServerFrames()
        for index in range(len(frames)):
            first, second = await read_frame(a, "server"), await policy.read(b)
            assert encode(first) == encode(second)
            assert strict.receive(first, index) == tolerant.receive(second, index)
            left, right = strict.render(index), tolerant.render(index)
            assert left == right
            assert strict.key("right", index) == tolerant.key("right", index)
    asyncio.run(scenario())


@pytest.mark.parametrize("malformed", [False, True])
def test_two_pumps_ignore_unknown_type_but_disconnect_for_invalid_known_frame(
    info: DoorInfo, repo_root: Path, monkeypatch: pytest.MonkeyPatch, malformed: bool,
) -> None:
    async def scenario() -> None:
        finished = asyncio.Event()
        class Link:
            def __init__(self) -> None:
                self.reader = None
                self.writer = None
                self.opens = 0
                self.sent: list[Frame] = []
                self.disconnected = False
            async def open(self, info: DoorInfo, timeout: float) -> Frame:
                self.opens += 1
                self.writer = object()
                data = wire({"type": "future"}) * 1000
                if malformed:
                    data += wire({"type": "pong", "t": False})
                else:
                    data += encode(Frame("view", {"rev": 1, "kind": "text", "body": {"title": "STREAM CONTINUES", "lines": []}}))
                self.reader = asyncio.StreamReader()
                self.reader.feed_data(data)
                return welcome(repo_root)
            async def send(self, frame: Frame) -> None:
                self.sent.append(frame)
            async def close(self) -> None:
                self.disconnected = self.writer is not None
                self.reader = self.writer = None
                if malformed:
                    finished.set()
        class Terminal(FakeTerminal):
            def enter(self) -> None:
                pass
            def write(self, data: bytes) -> None:
                super().write(data)
                if "STREAM CONTINUES" in self.screen_text():
                    finished.set()
            async def read(self) -> bytes:
                await finished.wait()
                return b""  # End the launch after the observed result.
            def leave(self, farewell: bytes) -> None:
                pass
        link = Link()
        monkeypatch.setattr("blacksite.door.client.Connection", lambda: link)
        terminal = Terminal()
        await asyncio.wait_for(run(info, terminal), 3)
        assert finished.is_set() and link.opens == 1
        if not malformed:
            assert "STREAM CONTINUES" in terminal.screen_text()
            assert Frame("ack", {"rev": 1}) in link.sent
        else:
            assert not any(frame.type == "ack" and frame.data["rev"] == 1 for frame in link.sent)
    asyncio.run(scenario())
