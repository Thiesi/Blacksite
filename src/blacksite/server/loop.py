"""Deterministic tick executor; scheduling and timing stay in the I/O layer."""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from blacksite.server.bus import Event, EventBus
from blacksite.server.clock import Clock
from blacksite.server.sessions import Session, Sessions


@dataclass(frozen=True)
class TickContext:
    tick: int
    clock: Clock
    bus: EventBus
    sessions: tuple[Session, ...]
    content: Any


class Subsystem(Protocol):
    def tick(self, ctx: TickContext) -> None: ...


class TickLoop:
    def __init__(self, clock: Clock, bus: EventBus, sessions: Sessions,
                 content: Any = None) -> None:
        self.clock = clock
        self.bus = bus
        self.sessions = sessions
        self.content = content
        self.subsystems: list[Subsystem] = []
        self.publishers: list[Callable[[TickContext], None]] = []
        self.timings: deque[float] = deque(maxlen=6000)
        self.last_tick = clock.now_tick()

    def step(self) -> None:
        tick = self.clock.now_tick()
        if tick <= self.last_tick:
            raise ValueError("advance the clock before stepping")
        self.last_tick = tick
        self.sessions.expire()
        sessions = tuple(s for s in self.sessions.active.values() if not s.closed)
        ctx = TickContext(tick, self.clock, self.bus, sessions, self.content)
        for session in sessions:
            while session.input_queue:
                frame = session.input_queue.popleft()
                self.bus.publish(Event("input", {"session": session, "frame": frame, "tick": tick}))
                if frame.type.startswith("admin."):
                    # Operator replies are views too: at most one per tick.
                    break
        for subsystem in self.subsystems:
            subsystem.tick(ctx)
        for publish in self.publishers:
            publish(ctx)

    def record_timing(self, seconds: float) -> None:
        self.timings.append(seconds * 1000)

    def timing(self) -> dict[str, float]:
        values = sorted(self.timings)
        if not values:
            return {"p50_ms": 0.0, "p99_ms": 0.0}
        return {f"p{p}_ms": values[min(len(values) - 1, (len(values) * p + 99) // 100 - 1)] for p in (50, 99)}
