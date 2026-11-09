"""Injected time; only the real I/O clock reads wall and monotonic time."""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# 02-architecture.md §6.1.
TICK_HZ = 10


class Clock(Protocol):
    def now_tick(self) -> int: ...
    def now_utc(self) -> datetime: ...
    def now_local(self, name: str | None = None) -> datetime: ...


class RealClock:
    def __init__(self) -> None:
        self.started = time.monotonic()

    def now_tick(self) -> int:
        return int((time.monotonic() - self.started) * TICK_HZ)

    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def now_local(self, name: str | None = None) -> datetime:
        if name is not None:
            try:
                return self.now_utc().astimezone(ZoneInfo(name))
            except (ZoneInfoNotFoundError, ValueError):
                pass
        return self.now_utc().astimezone()


@dataclass
class ManualClock:
    tick: int = 0
    epoch: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now_tick(self) -> int:
        return self.tick

    def now_utc(self) -> datetime:
        return self.epoch + timedelta(seconds=self.tick / TICK_HZ)

    def now_local(self, name: str | None = None) -> datetime:
        if name is not None:
            try:
                return self.now_utc().astimezone(ZoneInfo(name))
            except (ZoneInfoNotFoundError, ValueError):
                pass
        return self.now_utc()

    def advance(self, ticks: int = 1) -> None:
        if ticks < 0:
            raise ValueError("clock cannot go backwards")
        self.tick += ticks
