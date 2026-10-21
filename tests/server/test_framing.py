"""Architecture §5: malformed wire input never reaches simulation."""

import json
import struct
from pathlib import Path

import pytest

from blacksite.server.protocol import Decoder, Frame, MAX_FRAME, ProtocolError, decode, encode
from tests.harness import hello


def test_encode_decode_round_trip() -> None:
    for frame in (hello(), Frame("ping", {"t": 123}), Frame("bye", {"reason": "logout"})):
        assert decode(encode(frame)[4:]) == frame


def test_partial_frames_reassembled() -> None:
    decoder = Decoder("client")
    data = encode(hello()) + encode(Frame("ping", {"t": 1}))
    result = []
    for byte in data:
        result.extend(decoder.feed(bytes([byte])))
    assert [frame.type for frame in result] == ["hello", "ping"]
    assert not decoder.buffer


def test_oversize_frame_rejected() -> None:
    with pytest.raises(ProtocolError):
        Decoder().feed(struct.pack("!I", MAX_FRAME + 1))
    with pytest.raises(ProtocolError):
        encode(Frame("intent", {"name": "move", "args": {"x": "a" * MAX_FRAME}}))


@pytest.mark.parametrize("payload", [
    b'[]', b'null', b'{}', b'{"type":"ping","t":true}',
    b'{"type":"ping","t":NaN}', b'{"type":"ping","t":1,"t":2}',
    b'{"type":"ping","t":1,"future":{"value":1e999}}',
    b'{"type":"ping","t":-1}', b'{"type":"ping","t":1.0}',
    b'{"type":"welcome","proto":1}', b'{"type":"peer.hello"}',
    b'{"type":"resize","width":79,"height":24}', b'\xff',
    b'{"type":"intent","name":"market.action","args":{}}',
    b'{"type":"hello","proto":2}',
])
def test_invalid_client_frames(payload: bytes) -> None:
    with pytest.raises(ProtocolError):
        decode(payload, "client")


def test_additive_fields_allowed() -> None:
    assert decode(b'{"type":"ping","t":1,"future":true}', "client").data["future"] is True


def test_golden_frames(repo_root: Path) -> None:
    root = repo_root / "tests" / "fixtures" / "frames"
    assert {p.stem for p in root.glob("*.json")} == {"hello", "welcome", "bye", "ping", "pong", "invalid-major", "oversize"}
    for path in root.glob("*.json"):
        row = json.loads(path.read_text(encoding="utf-8"))
        if path.stem == "invalid-major":
            with pytest.raises(ProtocolError):
                decode(json.dumps(row).encode())
        elif path.stem == "oversize":
            with pytest.raises(ProtocolError):
                Decoder().feed(struct.pack("!I", row["length"]))
        else:
            assert decode(encode(decode(json.dumps(row).encode()))[4:]).object() == row


@pytest.mark.parametrize("frame", [
    Frame("resize", {"width": 132, "height": 50}),
    Frame("key", {"k": "up", "t": 0}),
    Frame("intent", {"name": "move", "args": {"dx": 1}}),
    Frame("line", {"id": "chat", "text": "Hello"}), Frame("ack", {"rev": 1}),
    Frame("view", {"rev": 1, "kind": "zone", "body": {}}),
    Frame("delta", {"rev": 2, "base": 1, "ops": []}),
    Frame("log", {"lines": [{"channel": "system", "text": "You wait.", "role": "muted", "at": "2026-01-01T00:00:00Z"}]}),
    Frame("prompt", {"id": "chat", "kind": "line", "label": "Say", "max_len": 128}),
    Frame("toast", {"text": "You wait.", "role": "muted", "seconds": 2}),
    Frame("admin.status"), Frame("admin.who"), Frame("admin.stop"),
])
def test_remaining_frame_contracts(frame: Frame) -> None:
    assert decode(encode(frame)[4:]) == frame
