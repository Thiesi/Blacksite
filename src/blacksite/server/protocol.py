"""Bounded, strict JSON frames (02-architecture.md §5).

Unknown additive fields survive decoding. Unknown frame types do not.
The envelope is immutable; payloads are validated before use by the core.
"""

import asyncio
import json
import math
import struct
from dataclasses import dataclass, field
from typing import Any, Literal, NotRequired, TypedDict

from blacksite.version import PROTOCOL_MAJOR

MAX_FRAME = 256 * 1024  # Architecture §5.1, bytes excluding header.

FrameType = Literal[
    "hello", "resize", "key", "intent", "line", "ack", "ping", "bye",
    "welcome", "view", "delta", "log", "prompt", "toast", "pong",
    "admin.status", "admin.who", "admin.stop", "admin.lattice.who", "admin.lattice.reveal",
    "admin.relay.list", "admin.relay.set",
    "admin.market.list", "admin.market.cancel", "admin.bounty.list", "admin.bounty.refund",
]


class Caps(TypedDict):
    width: int
    height: int
    tier: str
    unicode: bool


class Hello(TypedDict):
    proto: int
    door_info: dict[str, Any]
    hmac: str
    client_version: str
    caps: Caps


class Resize(TypedDict):
    width: int
    height: int


class Key(TypedDict):
    k: str
    t: int


class Intent(TypedDict):
    name: str
    args: dict[str, Any]
    request_id: NotRequired[str]
    expected_revision: NotRequired[int]


class Line(TypedDict):
    id: str
    text: str


class Ack(TypedDict):
    rev: int


class Ping(TypedDict):
    t: int


class Pong(Ping):
    pass


class Bye(TypedDict):
    reason: str
    text: NotRequired[str]  # Required in the server-to-client direction.


class Welcome(TypedDict):
    proto: int
    server_version: str
    player: dict[str, Any] | None
    keymap: dict[str, Any]
    palette: dict[str, Any]
    motd: str


class View(TypedDict):
    rev: int
    kind: Literal["zone", "lattice", "menu", "wake", "dead", "text"]
    body: dict[str, Any]


class Delta(TypedDict):
    rev: int
    base: int
    ops: list[dict[str, Any]]


class LogLine(TypedDict):
    id: NotRequired[str]
    channel: str
    text: str
    role: str
    at: str


class Log(TypedDict):
    lines: list[LogLine]
    replay: NotRequired[bool]


class Prompt(TypedDict):
    id: str
    kind: Literal["key", "line"]
    label: str
    max_len: int


class Toast(TypedDict):
    text: str
    role: str
    seconds: float


class AdminStatus(TypedDict):
    pass


class AdminWho(TypedDict):
    pass


class AdminStop(TypedDict):
    pass


class ProtocolError(ValueError):
    pass


def _integer(value: Any, low: int = 0, high: int = 2**63 - 1) -> bool:
    return type(value) is int and low <= value <= high


def _text(value: Any, limit: int = 4096) -> bool:
    return isinstance(value, str) and len(value) <= limit


def _need(data: dict[str, Any], key: str, valid: bool) -> None:
    if key not in data or not valid:
        raise ProtocolError(f"invalid or missing {key}")


def validate(kind: str, data: dict[str, Any], direction: str | None = None) -> None:
    client = {"hello", "resize", "key", "intent", "line", "ack", "ping", "bye",
              "admin.status", "admin.who", "admin.stop", "admin.lattice.who", "admin.lattice.reveal",
              "admin.relay.list", "admin.relay.set", "admin.market.list", "admin.market.cancel",
              "admin.bounty.list", "admin.bounty.refund"}
    server = {"welcome", "view", "delta", "log", "prompt", "toast", "pong", "bye"}
    allowed = client if direction == "client" else server if direction == "server" else client | server
    if kind not in allowed:
        raise ProtocolError("unknown or wrong-direction frame type")
    if kind in ('admin.market.cancel', 'admin.bounty.refund'):
        key = 'listing' if kind == 'admin.market.cancel' else 'bounty'
        _need(data, key, _text(data.get(key), 256) and bool(data.get(key)))
    elif kind == 'admin.relay.set':
        for key in ('relay', 'faction'):
            _need(data, key, _text(data.get(key), 128) and bool(data.get(key)))
    elif kind == "admin.lattice.reveal":
        for key in ("player", "sector", "cell"):
            _need(data, key, _text(data.get(key), 256) and bool(data.get(key)))
    elif kind == "hello":
        _need(data, "proto", type(data.get("proto")) is int)
        if data["proto"] != PROTOCOL_MAJOR:
            raise ProtocolError("unsupported protocol major")
        info = data.get("door_info")
        _need(data, "door_info", isinstance(info, dict))
        # NetBBS calls this user_id. Accept the documented normalized name too.
        identity = info.get("bbs_user_id", info.get("user_id"))
        if not (_integer(identity) or (_text(identity, 128) and bool(identity))):
            raise ProtocolError("invalid door_info user_id")
        if "bbs_user_id" in info and "user_id" in info and str(info["bbs_user_id"]) != str(info["user_id"]):
            raise ProtocolError("conflicting user identity")
        _need(info, "handle", _text(info.get("handle"), 256))
        _need(data, "hmac", _text(data.get("hmac"), 64) and len(data.get("hmac", "")) == 64)
        _need(data, "client_version", _text(data.get("client_version"), 128))
        caps = data.get("caps")
        _need(data, "caps", isinstance(caps, dict))
        validate("resize", caps)
        _need(caps, "tier", caps.get("tier") in ("16", "256", "truecolor"))
        _need(caps, "unicode", caps.get("unicode") is True)
    elif kind == "resize":
        _need(data, "width", _integer(data.get("width"), 80, 1000))
        _need(data, "height", _integer(data.get("height"), 24, 1000))
    elif kind == "key":
        _need(data, "k", _text(data.get("k"), 64) and bool(data.get("k")))
        _need(data, "t", _integer(data.get("t")))
    elif kind == "intent":
        _need(data, "name", _text(data.get("name"), 128) and bool(data.get("name")))
        _need(data, "args", isinstance(data.get("args"), dict))
        for key in ("request_id", "expected_revision"):
            if key in data:
                _need(data, key, _text(data[key], 128) if key == "request_id" else _integer(data[key]))
        if data.get("name") in {"menu_select", "market.action", "market.list", "market.bid", "market.buyout",
                               "market.cancel", "market.collect", "bounty.post", "contract.accept", "finale.choose", "work_order.allocate"}:
            _need(data, "request_id", _text(data.get("request_id"), 128) and bool(data.get("request_id")))
            _need(data, "expected_revision", _integer(data.get("expected_revision")))
    elif kind == "line":
        _need(data, "id", _text(data.get("id"), 128))
        _need(data, "text", _text(data.get("text")))
    elif kind in {"ack", "view", "delta"}:
        _need(data, "rev", _integer(data.get("rev")))
        if kind == "view":
            _need(data, "kind", data.get("kind") in {"zone", "lattice", "menu", "wake", "dead", "text"})
            _need(data, "body", isinstance(data.get("body"), dict))
        if kind == "delta":
            _need(data, "base", _integer(data.get("base"), 0, data["rev"]))
            _need(data, "ops", isinstance(data.get("ops"), list) and all(isinstance(op, dict) for op in data["ops"]))
    elif kind in {"ping", "pong"}:
        _need(data, "t", _integer(data.get("t")))
    elif kind == "bye":
        _need(data, "reason", _text(data.get("reason"), 128))
        if direction == "server" or "text" in data:
            _need(data, "text", _text(data.get("text")))
    elif kind == "welcome":
        _need(data, "proto", type(data.get("proto")) is int and data["proto"] == PROTOCOL_MAJOR)
        _need(data, "server_version", _text(data.get("server_version"), 128))
        _need(data, "player", data.get("player") is None or isinstance(data.get("player"), dict))
        for key in ("keymap", "palette"):
            _need(data, key, isinstance(data.get(key), dict))
        _need(data, "motd", _text(data.get("motd")))
    elif kind == "log":
        _need(data, "lines", isinstance(data.get("lines"), list))
        for line in data["lines"]:
            if not isinstance(line, dict):
                raise ProtocolError("invalid log line")
            for key in ("channel", "text", "role", "at"):
                _need(line, key, _text(line.get(key)))
    elif kind == "prompt":
        for key in ("id", "label"):
            _need(data, key, _text(data.get(key)))
        _need(data, "kind", data.get("kind") in {"key", "line"})
        _need(data, "max_len", _integer(data.get("max_len"), 1, 4096))
    elif kind == "toast":
        for key in ("text", "role"):
            _need(data, key, _text(data.get(key)))
        value = data.get("seconds")
        _need(data, "seconds", type(value) in (int, float) and math.isfinite(value) and 0 < value <= 3600)


@dataclass(frozen=True)
class Frame:
    type: FrameType
    data: dict[str, Any] = field(default_factory=dict)

    def object(self) -> dict[str, Any]:
        return {**self.data, "type": self.type}


def encode(frame: Frame) -> bytes:
    validate(frame.type, frame.data)
    try:
        payload = json.dumps(frame.object(), ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("invalid JSON payload") from exc
    if not 0 < len(payload) <= MAX_FRAME:
        raise ProtocolError("frame exceeds 256 KiB")
    return struct.pack("!I", len(payload)) + payload


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate JSON key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ProtocolError("non-finite JSON number")


def _float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ProtocolError("non-finite JSON number")
    return number


def decode(payload: bytes, direction: str | None = None) -> Frame:
    if not 0 < len(payload) <= MAX_FRAME:
        raise ProtocolError("invalid frame size")
    try:
        obj = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs,
                         parse_constant=_constant, parse_float=_float)
        if not isinstance(obj, dict) or not isinstance(obj.get("type"), str):
            raise ProtocolError("frame must be a typed object")
        kind = obj.pop("type")
        validate(kind, obj, direction)
        return Frame(kind, obj)
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise ProtocolError(str(exc)) from exc


class Decoder:
    """Incremental framing for byte-at-a-time transports and tests."""

    def __init__(self, direction: str | None = None) -> None:
        self.buffer = bytearray()
        self.direction = direction

    def feed(self, chunk: bytes) -> list[Frame]:
        self.buffer.extend(chunk)
        frames: list[Frame] = []
        while len(self.buffer) >= 4:
            size = struct.unpack("!I", self.buffer[:4])[0]
            if not 0 < size <= MAX_FRAME:
                raise ProtocolError("invalid frame size")
            if len(self.buffer) < size + 4:
                break
            frames.append(decode(bytes(self.buffer[4:4 + size]), self.direction))
            del self.buffer[:4 + size]
        return frames


async def read_frame(reader: asyncio.StreamReader, direction: str | None = None) -> Frame:
    size = struct.unpack("!I", await reader.readexactly(4))[0]
    if not 0 < size <= MAX_FRAME:
        raise ProtocolError("invalid frame size")
    return decode(await reader.readexactly(size), direction)
