"""Pure combat arithmetic, game design 3.1, 5.3, 5.4 and 7.3."""

from math import ceil, hypot

from blacksite.content.schema import Tile

TICK_SECONDS = .1  # Architecture 6.1: 10 Hz.
MELEE_SECONDS = 1.0  # Game design 5.3 / catalog 1.5.
MELEE_ACCURACY = 75  # Game design 5.3: unlisted melee accuracy.
DOWN_SECONDS, DECANT_SECONDS = 5, 20  # Game design 5.4.
LOOT_PRIVATE_SECONDS, CACHE_SECONDS = 60, 300
COMBAT_SECONDS, WARNING_SECONDS = 10, 2  # Game design 5.3.
MARKED_SECONDS = 900  # Game design 7.3.
SHOCK_SLOW, SHOCK_KNOCK, SHOCK_RESET = 80, 100, 60
KNOCK_SECONDS, SHOCK_DELAY, SHOCK_DECAY = 2, 3, 5
REVIVE_FRACTION = .25  # Game design 5.4.
ABILITY_RANGE = 6  # Game design 5.3.


def ticks(seconds: float) -> int:
    return ceil(round(seconds / TICK_SECONDS, 8))


def cooldown_deadline(tick: int, seconds: float, previous: float = 0) -> float:
    """Game 5.2/5.3: bounded rounding credit keeps small modifiers real.

    Execution still waits for an integer tick. Only the previous tick's
    fractional remainder survives; idle time cannot accumulate a burst.
    """
    origin = previous if tick-1 < previous <= tick else tick
    return round(origin+seconds/TICK_SECONDS, 8)


def distance(a: Tile, b: Tile) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def range_penalty(distance_: float, range_: float) -> float:
    return max(0, distance_ - range_ / 2) * 5


def to_hit(accuracy: float, skill: float, evasion: float, cover: int = 0,
           range_penalty: float = 0) -> float:
    return max(5, min(95, accuracy + skill / 2 - evasion - cover * 10 - range_penalty))


def damage(base: float, skill: float, armour: float, melee: bool = False) -> int:
    return max(1, int(base * (1 + skill / 200) - armour * (.5 if melee else 1)))


def action_seconds(base: float, shock: float, jam: float = 1) -> float:
    return base * (1.5 if shock >= SHOCK_SLOW else 1) * jam


def clone_settlement(hand: int, grade: int, xp: int, floor: int, owed: int) -> tuple[int, int, int, int]:
    charge = hand * 5 // 100 + grade * 10
    paid = min(hand, charge)
    return hand - paid, owed + charge - paid, xp - max(0, xp - floor) * 2 // 100, charge


def earned_chits(award: int, debt: int) -> tuple[int, int]:
    """Only awards call this; principal transfers never service debt (5.4)."""
    payment = min(debt, award // 4)
    return award - payment, debt - payment
