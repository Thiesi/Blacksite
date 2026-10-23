"""Pure travel timing and permission checks (game design §5.6, gazetteer)."""

from dataclasses import dataclass
from typing import Any

from blacksite.content.schema import Exit

# 01-gazetteer.md, Central Tram Hub; game design §5.6.
TRAM_INTERVAL_SECONDS = 90
TRAM_RIDE_SECONDS = 10
LIFT_SECONDS = 1
CABLE_SECONDS = 3
# S08 / future S15: bounded hold, then departure immunity.
MAX_HOLD_SECONDS = 30
HOLD_IMMUNITY_SECONDS = 120


@dataclass
class Travel:
    exit: Exit
    departure: float
    arrival: float
    departed: bool = False


class DepartureHolds:
    """S15 hook: one bounded platform hold, followed by immunity.

    UTC deadlines are suitable for S15's persisted control overlay. Merely
    waking a zone or repeatedly requesting a hold cannot extend it.
    """

    def __init__(self) -> None:
        self.deadlines: dict[tuple[str, str], tuple[float, float]] = {}

    def hold(self, platform: tuple[str, str], now: float, departure: float) -> bool:
        if now < self.deadlines.get(platform, (0, 0))[1]:
            return False
        until = departure + MAX_HOLD_SECONDS
        self.deadlines[platform] = until, until + HOLD_IMMUNITY_SECONDS
        return True

    def apply(self, platform: tuple[str, str], travel: Travel) -> None:
        until = self.deadlines.get(platform, (0, 0))[0]
        if not travel.departed and travel.departure < until <= travel.departure + MAX_HOLD_SECONDS:
            delay = until - travel.departure
            travel.departure += delay
            travel.arrival += delay


def schedule(exit: Exit, now: float) -> Travel:
    departure = ((int(now) // TRAM_INTERVAL_SECONDS) + 1) * TRAM_INTERVAL_SECONDS if exit.kind == "tram" else now
    duration = {"tram": TRAM_RIDE_SECONDS, "ladder": LIFT_SECONDS,
                "lift": LIFT_SECONDS, "cable": CABLE_SECONDS}.get(exit.kind, 0)
    return Travel(exit, departure, departure + duration)


def permitted(exit: Exit, access: dict[str, Any]) -> bool:
    requirement = exit.requirement
    if requirement is None:
        return True
    if requirement.kind == "faction":
        return access.get("standing", {}).get(requirement.ref, 0) >= (requirement.standing or 0)
    return requirement.ref in access.get("items", ())


def complete_paid_pass(progress: dict[str, Any], destination: str) -> bool:
    """Consume only the bound ticket for a journey that actually arrived."""
    trip = progress.get('paid_trip')
    if not trip or trip['target'] != destination:
        return False
    ticket = progress.get('paid_passes', {}).get(trip['key'])
    if ticket and ticket['id'] == trip['token']:
        progress['paid_passes'].pop(trip['key'])
    progress.pop('paid_trip')
    return True
