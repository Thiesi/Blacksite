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

    def refill(self, timestamp: float) -> None:
        hour = int(timestamp) // BUDGET_SECONDS
        if hour > self.hour:
            self.hour, self.remaining = hour, BUYBACK_BUDGET
