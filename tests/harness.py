"""Socket-free clients exercising the production Core and manual ticks."""

from dataclasses import asdict, dataclass
from typing import Any

from blacksite.server.auth import Authenticator, sign
from blacksite.server.clock import ManualClock
from blacksite.server.core import Core
from blacksite.server.protocol import Frame, ProtocolError
from blacksite.server.sessions import Session
from blacksite.version import PACKAGE_VERSION, PROTOCOL_MAJOR
from blacksite.content.loader import ContentTree
from blacksite.server.world.registry import World

DOOR_SECRET = b"d" * 32
ADMIN_SECRET = b"a" * 32


@dataclass(frozen=True)
class CallerInput:
    """Declared caller-supplied fixture text, never an authored glyph."""
    id: str
    text: str


WIDE_HANDLE = CallerInput('wide-handle', 'Wide\u754c')
LATTICE_PEER = CallerInput('lattice-peer', 'Runner\u754c')
ENCOUNTER_PEER = CallerInput('encounter-peer', 'Guest\u754c')
CALLER_INPUTS = (WIDE_HANDLE, LATTICE_PEER, ENCOUNTER_PEER)


def hello(info: dict[str, Any] | None = None, secret: bytes = DOOR_SECRET,
          width: int = 80, height: int = 24) -> Frame:
    info = info if info is not None else {"user_id": 1, "handle": WIDE_HANDLE.text, "node_name": "test"}
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
    def __init__(self, content: ContentTree | None = None, spawn_zone: str | None = None,
                 character_state: dict[str, Any] | None = None, clock: ManualClock | None = None,
                 zone_seeds: dict[str, int] | None = None) -> None:
        self.clock = clock or ManualClock()
        world = World(content, zone_seeds if zone_seeds is not None else
                      {zone: index for index, zone in enumerate(sorted(content.zones))}) if content and (spawn_zone or character_state is not None) else None
        self.core = Core(self.clock, "test-origin", Authenticator(DOOR_SECRET, ADMIN_SECRET),
                         asdict(content.keymaps) if content and content.keymaps else {},
                         asdict(content.palette) if content and content.palette else {},
                         content=content, world=world, spawn_zone=spawn_zone, character_state=character_state)
        # Match Server.start: commit startup reconciliation before callers.
        self.commit_commerce()

    def commit_characters(self, error: bool = False) -> list[dict[str, Any]]:
        game = self.core.characters
        effects = []
        while game and game.outbox:
            effect = game.outbox.pop(0)
            effects.append(effect)
            game.committed(effect, error=error if effect["action"] in ("create", "delete") else False)
        return effects

    def connect(self, door_info: dict[str, Any] | None = None, *,
                frame: Frame | None = None, width: int = 80, height: int = 24) -> FakeClient:
        try:
            session = self.core.connect(frame or hello(door_info, width=width, height=height))
            return FakeClient(self.core, session, [])
        except (ValueError, TypeError) as exc:
            return FakeClient(self.core, None, [Frame("bye", {
                "reason": "protocol" if isinstance(exc, ProtocolError) else "auth", "text": "Connection refused."})])

    def commit_commerce(self, error: bool = False) -> list[dict[str, Any]]:
        commerce = self.core.commerce
        effects = []
        while commerce and commerce.outbox:
            effect = commerce.outbox.pop(0)
            if not commerce.can_commit(effect):
                commerce.committed(effect,False)
                continue
            effects.append(commerce.prepare(effect))
            commerce.committed(effect, not error)
        return effects

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
