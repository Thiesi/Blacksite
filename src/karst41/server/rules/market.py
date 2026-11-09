"""Game 8.3 and 14: exact market money and bounty limits."""

from fractions import Fraction

MARKET_FEE = Fraction(5, 100)  # Game 8.3: five percent, rounded up.
LISTING_EXPIRIES = (24 * 3600, 72 * 3600, 7 * 24 * 3600)  # Game 8.3.
BOUNTY_MIN_CHITS = 100  # Game 8.3.
BOUNTY_MIN_TARGET_GRADE = 5  # Game 8.3.
BOUNTY_SECONDS = 7 * 24 * 3600  # Game 8.3: seven days.
MARKET_ACTION_SECONDS = 1  # Game 14: one market/bounty action per second.


def fee(price: int) -> int:
    """Game 8.3: integer ceiling without floating-point money."""
    if type(price) is not int or price < 1:
        raise ValueError('Use a positive whole-chit price.')
    return (price * MARKET_FEE.numerator + MARKET_FEE.denominator - 1) // MARKET_FEE.denominator
