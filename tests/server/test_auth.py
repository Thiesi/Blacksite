"""Architecture §4: HMAC, filesystem secrets, role and identity boundaries."""

import os
from pathlib import Path

import pytest

from blacksite.server.auth import load_secret, sign
from blacksite.server.protocol import Frame
from tests.harness import ADMIN_SECRET, DOOR_SECRET, HeadlessServer, hello


def test_hello_hmac_valid() -> None:
    server = HeadlessServer()
    client = server.connect()
    assert server.frames_for(client)[0].type == "welcome"


def test_hello_hmac_invalid_gets_bye() -> None:
    server = HeadlessServer()
    frame = hello()
    frame.data["hmac"] = "0" * 64
    assert server.frames_for(server.connect(frame=frame))[0].type == "bye"
    assert not server.core.sessions.active


def test_wrong_major_rejected() -> None:
    server = HeadlessServer()
    frame = hello()
    frame.data["proto"] = 2
    assert server.frames_for(server.connect(frame=frame))[0].data["reason"] == "protocol"


def test_operator_secret_sets_role() -> None:
    server = HeadlessServer()
    caller = server.connect()
    operator = server.connect(frame=hello(secret=ADMIN_SECRET))
    assert caller.session.role == "caller"
    assert operator.session.role == "operator"
    assert caller.session.closed is False  # Admin identity doesn't replace a caller.


def test_secrets_created_0600(scratch_dir: Path) -> None:
    path = scratch_dir / "door.secret"
    value = load_secret(path)
    assert len(value) == 32
    assert load_secret(path) == value
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


def test_signature_covers_identity_and_is_order_independent() -> None:
    one = {"user_id": 1, "handle": "界"}
    assert sign(one, DOOR_SECRET) == sign(dict(reversed(list(one.items()))), DOOR_SECRET)
    server = HeadlessServer()
    frame = hello(one)
    frame.data["door_info"]["user_id"] = 2
    assert server.frames_for(server.connect(frame=frame))[0].type == "bye"


def test_ban_hook_and_identity_conflict() -> None:
    server = HeadlessServer()
    server.core.auth.banned = lambda user: user == "1"
    assert server.connect().session is None
    frame = hello({"user_id": 1, "bbs_user_id": 2, "handle": "Name"})
    assert server.connect(frame=frame).session is None


@pytest.mark.parametrize("signature", ["界" * 64, "f" * 63, "a" * 65])
def test_malformed_signature_refused(signature: str) -> None:
    server = HeadlessServer()
    frame = hello()
    frame.data["hmac"] = signature
    assert server.connect(frame=frame).session is None


def test_caller_cannot_send_admin_or_peer() -> None:
    for kind in ("admin.status", "peer.hello"):
        server = HeadlessServer()
        client = server.connect()
        server.frames_for(client)
        client.send(Frame(kind))
        assert server.frames_for(client)[0].type == "bye"
