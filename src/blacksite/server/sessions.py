"""Socket-free sessions, bounded queues and reconnect ownership."""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from blacksite.server.auth import Role, identity
from blacksite.server.clock import Clock, TICK_HZ
from blacksite.server.protocol import Frame

# Main design §14; architecture §5.3; S03's bounded input queue.
INPUTS_PER_SECOND = 20
CHAT_PER_WINDOW = 4
CHAT_WINDOW_SECONDS = 5
MARKET_PER_SECOND = 1
QUEUE_LIMIT = 64
MAX_REVISION_LAG = 3
RECONNECT_SECONDS = 60  # Architecture §8.2.


@dataclass
class Session:
    id: str
    role: Role
    door_info: dict[str, Any]
    caps: dict[str, Any]
    player_id: str | None = None
    subscribed: str | None = None
    input_queue: deque[Frame] = field(default_factory=deque)
    send_queue: deque[Frame] = field(default_factory=deque)
    rate_counters: dict[str, deque[int]] = field(default_factory=dict)
    pending_prompts: dict[str, Any] = field(default_factory=dict)
    last_input_tick: int = 0
    view_revision: int = 0
    ack_revision: int = 0
    needs_full_view: bool = False
    last_view_tick: int = -1
    closed: bool = False
    disconnected_tick: int | None = None
    notify: Callable[[], None] = field(default=lambda: None, repr=False)

    @property
    def user_id(self) -> str:
        return identity(self.door_info)

    def send(self, frame: Frame) -> bool:
        """Backpressure requests a snapshot after any dropped delta.

        A full queue of reliable messages disconnects a slow consumer with
        a final bye. This keeps memory bounded without silently losing it.
        """
        if self.closed:
            return False
        if frame.type == "bye":
            self.send_queue.clear()
            self.send_queue.append(frame)
            self.closed = True
            self.notify()
            return True
        if len(self.send_queue) >= QUEUE_LIMIT:
            if frame.type == "delta":
                self.needs_full_view = True
                return False
            for pending in tuple(self.send_queue):
                if pending.type == "delta":
                    self.send_queue.remove(pending)
                    self.needs_full_view = True
                    break
            else:
                self.send(Frame("bye", {"reason": "slow_consumer", "text": "Your link cannot keep up."}))
                return False
        self.send_queue.append(frame)
        self.notify()
        return True

    def allow(self, bucket: str, tick: int, count: int, seconds: int) -> bool:
        history = self.rate_counters.setdefault(bucket, deque())
        while history and history[0] <= tick - seconds * TICK_HZ:
            history.popleft()
        if len(history) >= count:
            return False
        history.append(tick)
        return True

    def enqueue(self, frame: Frame, tick: int) -> bool:
        if self.closed or len(self.input_queue) >= QUEUE_LIMIT:
            return False
        if not self.allow("input", tick, INPUTS_PER_SECOND, 1):
            return False
        name = frame.data.get("name", "")
        if frame.type == "line" or name in {"chat", "emote"}:
            if not self.allow("chat", tick, CHAT_PER_WINDOW, CHAT_WINDOW_SECONDS):
                return False
        if name.startswith("market") and not self.allow("market", tick, MARKET_PER_SECOND, 1):
            return False
        self.last_input_tick = tick
        self.input_queue.append(frame)
        return True

    def acknowledge(self, revision: int) -> None:
        if self.ack_revision <= revision <= self.view_revision:
            self.ack_revision = revision

    def publish_view(self, full: Frame, delta: Frame | None, tick: int) -> bool:
        if self.closed or self.last_view_tick == tick:
            return False
        lag = self.view_revision - self.ack_revision
        use_full = delta is None or self.needs_full_view or lag > MAX_REVISION_LAG
        if use_full:
            self.send_queue = deque(f for f in self.send_queue if f.type not in {"view", "delta"})
        chosen = full if use_full else delta
        if self.send(chosen):
            self.last_view_tick = tick
            self.view_revision = chosen.data["rev"]
            self.needs_full_view = False
            return True
        return False


class Sessions:
    def __init__(self, clock: Clock, origin: str) -> None:
        self.clock = clock
        self.origin = origin
        self.active: dict[str, Session] = {}
        self.retired: dict[str, Session] = {}
        self.serial = 0

    def connect(self, role: Role, info: dict[str, Any], caps: dict[str, Any]) -> Session:
        self.expire()
        user_id = identity(info)
        old = next((s for s in self.active.values() if s.role == "caller" and s.user_id == user_id), None) if role == "caller" else None
        if old is not None:
            old.send(Frame("bye", {"reason": "replaced", "text": "You connect from another session."}))
            self.disconnect(old)
        previous = self.retired.pop(user_id, None) if role == "caller" else None
        self.serial += 1
        session = Session(f"{self.origin}:session:{self.serial}", role, dict(info), dict(caps))
        if previous is not None:
            session.player_id = previous.player_id
            # Reconnect cannot reset abuse limits.
            session.rate_counters = previous.rate_counters
        self.active[session.id] = session
        return session

    def disconnect(self, session: Session) -> None:
        # A replaced transport must not retire or remove its successor.
        if self.active.pop(session.id, None) is None:
            return
        session.closed = True
        session.input_queue.clear()
        session.disconnected_tick = self.clock.now_tick()
        if session.role == "caller":
            self.retired[session.user_id] = session

    def expire(self) -> None:
        tick = self.clock.now_tick()
        self.retired = {key: s for key, s in self.retired.items()
                        if s.disconnected_tick is not None and tick - s.disconnected_tick <= RECONNECT_SECONDS * TICK_HZ}
