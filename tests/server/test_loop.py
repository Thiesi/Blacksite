"""Architecture §6.1: manual ticks, ordered effects, no I/O in hooks."""

from blacksite.server.bus import Event
from blacksite.server.loop import TickContext
from blacksite.server.protocol import Frame
from tests.harness import HeadlessServer


def test_ten_ticks_per_second_manual_clock() -> None:
    server = HeadlessServer()
    start = server.clock.now_utc()
    server.step(10)
    assert (server.clock.now_utc() - start).total_seconds() == 1
    assert server.core.loop.last_tick == 10


def test_subsystem_order() -> None:
    server = HeadlessServer()
    client = server.connect()
    calls = []

    class Hook:
        def __init__(self, name: str) -> None:
            self.name = name

        def tick(self, ctx: TickContext) -> None:
            calls.append(self.name)
            ctx.bus.publish(Event("test"))

    server.core.loop.subsystems = [Hook("one"), Hook("two")]
    server.core.bus.subscribe("input", lambda event: calls.append("input"))
    server.core.bus.subscribe("test", lambda event: calls.append("event"))
    server.core.loop.publishers.append(lambda ctx: calls.append("views"))
    client.send(Frame("key", {"k": "up", "t": 0}))
    server.step()
    assert calls == ["input", "one", "event", "two", "event", "views"]


def test_tick_timing_recorded() -> None:
    server = HeadlessServer()
    for value in range(1, 101):
        server.core.loop.record_timing(value / 1000)
    assert server.core.loop.timing() == {"p50_ms": 50.0, "p99_ms": 99.0}
