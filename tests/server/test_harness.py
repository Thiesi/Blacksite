"""The headless harness uses the real protocol application."""

import pytest

from blacksite.server.protocol import Frame
from tests.harness import ADMIN_SECRET, HeadlessServer, hello


@pytest.mark.parametrize("width,height", [(80, 24), (132, 50)])
def test_headless_connect_welcome(width: int, height: int) -> None:
    server = HeadlessServer()
    client = server.connect(width=width, height=height)
    assert server.frames_for(client)[0].data["player"] is None
    client.send(Frame("intent", {"name": "move", "args": {}}))
    server.step()
    assert server.frames_for(client)[0].type == "log"
    assert "界" in client.session.door_info["handle"]


def test_operator_status_who_stop_audited_and_private_to_operator() -> None:
    server = HeadlessServer()
    caller = server.connect()
    operator = server.connect(frame=hello(secret=ADMIN_SECRET))
    server.frames_for(caller)
    server.frames_for(operator)
    audit = []
    server.core.audit = audit.append
    for kind in ("admin.status", "admin.who", "admin.stop"):
        operator.send(Frame(kind))
        server.step()
        assert server.frames_for(operator)[0].type == "view"
    assert len(audit) == 3
    assert server.core.stop_requested
    assert server.frames_for(caller) == []


def test_operator_burst_emits_one_view_per_tick() -> None:
    server = HeadlessServer()
    operator = server.connect(frame=hello(secret=ADMIN_SECRET))
    server.frames_for(operator)
    operator.send(Frame("admin.status"))
    operator.send(Frame("admin.who"))
    server.step()
    assert len(server.frames_for(operator)) == 1
    assert len(operator.session.input_queue) == 1
    server.step()
    assert len(server.frames_for(operator)) == 1
