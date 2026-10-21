"""Socket-free clients exercising the production Core and manual ticks."""

from dataclasses import dataclass
from typing import Any

from blacksite.server.auth import Authenticator, sign
from blacksite.server.clock import ManualClock
from blacksite.server.core import Core
from blacksite.server.protocol import Frame, ProtocolError
from blacksite.server.sessions import Session
from blacksite.version import PACKAGE_VERSION, PROTOCOL_MAJOR

DOOR_SECRET = b"d" * 32
ADMIN_SECRET = b"a" * 32


def hello(info: dict[str, Any] | None = None, secret: bytes = DOOR_SECRET,
          width: int = 80, height: int = 24) -> Frame:
    info = info if info is not None else {"user_id": 1, "handle": "Wide界", "node_name": "test"}
    return Frame("hello", {"proto": PROTOCOL_MAJOR, "door_info": info,
        "hmac": sign(info, secret), "client_version": PACKAGE_VERSION,
        "caps": {"width": width, "height": height, "tier": "256", "unicode": True}})


@dataclass
class FakeClient:
    core: Core
    session: Session | None
    rejected: list[Frame]

    def send(self, frame: Frame) -> None:
        assert self.session is not None
        self.core.receive(self.session, frame)


class HeadlessServer:
    def __init__(self) -> None:
        self.clock = ManualClock()
        self.core = Core(self.clock, "test-origin", Authenticator(DOOR_SECRET, ADMIN_SECRET))

    def connect(self, door_info: dict[str, Any] | None = None, *,
                frame: Frame | None = None, width: int = 80, height: int = 24) -> FakeClient:
        try:
            session = self.core.connect(frame or hello(door_info, width=width, height=height))
            return FakeClient(self.core, session, [])
        except (ValueError, TypeError) as exc:
            return FakeClient(self.core, None, [Frame("bye", {
                "reason": "protocol" if isinstance(exc, ProtocolError) else "auth", "text": "Connection refused."})])

    def step(self, n_ticks: int = 1) -> None:
        for _ in range(n_ticks):
            self.clock.advance()
            self.core.loop.step()
            self.core.loop.record_timing(0)

    def frames_for(self, client: FakeClient) -> list[Frame]:
        if client.session is None:
            result, client.rejected = client.rejected, []
            return result
        result = list(client.session.send_queue)
        client.session.send_queue.clear()
        return result
