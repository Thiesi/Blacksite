"""Standing prices and per-object resale budgets (game design 8.1/8.2)."""

from dataclasses import dataclass
from fractions import Fraction

from blacksite.content.schema import Vendor, VendorStock
from blacksite.server.players import Player

BUYBACK_BUDGET = 2000  # Game design 8.2; S12 budget schedule.
BUDGET_SECONDS = 3600


def rounded(value: Fraction) -> int:
    return (value.numerator * 2 + value.denominator) // (2 * value.denominator)


def price(base: int | Fraction, quality: float, standing: int = 0, freelance: bool = False,
          multiplier: float = 1.0, resale: bool = False) -> int:
    # Game design 8.1: Freelance pays list; ordinary endpoint curve is
    # -50 -> +30%, +80 -> -20%, clamped. Resale is 40% of list.
    modifier = Fraction(2, 5) if resale else (Fraction(1) if freelance else Fraction(13, 10) - Fraction(min(80, max(-50, standing)) + 50, 260))
    value = Fraction(base) * Fraction(str(quality)) * modifier * Fraction(str(multiplier))
    return max(0 if resale else 1, rounded(value)) if base else 0


def permitted(player: Player, vendor: Vendor, stock: VendorStock | None = None) -> bool:
    standing = player.standing.get(vendor.faction or "", 0)
    if vendor.tier == "member" and (not vendor.faction or player.faction != vendor.faction):
        return False
    if vendor.requires_archetype and player.archetype != vendor.requires_archetype:
        return False
    if vendor.requires_factions and player.faction not in vendor.requires_factions:
        return False
    if stock:
        if stock.standing is not None and standing < stock.standing:
            return False
        if stock.factions and player.faction not in stock.factions:
            return False
        if stock.archetype and stock.archetype != player.archetype:
            return False
    return True


@dataclass
class VendorBudget:
    hour: int
    remaining: int = BUYBACK_BUDGET
    limit: int = BUYBACK_BUDGET
    spent: int = 0
    refilled_at: int | None = None

    def refill(self, timestamp: float, limit: int = BUYBACK_BUDGET, period: int = BUDGET_SECONDS) -> None:
        # Game 7.5 / 8.2: a temporary larger cap is not another refill.
        # Retain spending above the ordinary cap when an allocation ends.
        if self.remaining != max(0, self.limit-self.spent):
            self.spent = self.limit-self.remaining
        # Game 7.7: Depot uses UTC half-hours. Changing eligibility cannot
        # refill the same boundary twice or erase spending when it expires.
        previous = self.hour*BUDGET_SECONDS if self.refilled_at is None else self.refilled_at
        boundary = int(timestamp)//period*period
        if boundary > previous:
            self.hour, self.spent = int(timestamp)//BUDGET_SECONDS, 0
            self.refilled_at = boundary
        elif self.refilled_at is None:
            self.refilled_at = previous
        self.limit = limit
        self.remaining = max(0, limit-self.spent)

    def spend(self, amount: int) -> None:
        if amount < 0 or amount > self.remaining:
            raise ValueError('The counter cannot fund that purchase.')
        self.spent += amount
        self.remaining = max(0, self.limit-self.spent)
