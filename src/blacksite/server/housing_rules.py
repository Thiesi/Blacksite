"""Game 8.7 and catalog 17.1: pure rental and impound calculations."""

from collections.abc import Callable
from fractions import Fraction
from typing import Any

from blacksite.content.schema import ApartmentClass, ItemTemplate
from blacksite.server.items import ItemInstance
from blacksite.server.players import Player
from blacksite.server.vendors import rounded

WEEK_SECONDS = 7*86400  # Game 8.7: weekly real-time invoices.
LAPSE_SECONDS = 14*86400  # Game 8.7: two full weeks unpaid.
NOTICE_SECONDS = 2*86400  # S18 acceptance/UX: warn before the next due date.
VESTIBULE_SECONDS = 30  # Game 6.4/8.7: no resident privileges.
PROTECTED_DIVISOR = 2  # Game 8.7: half the class storage can be secured.
IMPOUND_FRACTION = Fraction(1, 10)  # Game 8.7: catalog value, chits free.


def charge(player: Player, amount: int) -> None:
    if player.chits_bank+player.chits_hand < amount:
        raise ValueError("You need more chits in bank or hand.")
    bank = min(player.chits_bank, amount)
    player.chits_bank -= bank
    player.chits_hand -= amount-bank


def rent_amount(definition: ApartmentClass, modifier: float) -> int:
    return max(1, rounded(Fraction(definition.rent)*Fraction(str(modifier))))


def reconcile(player: Player, lease: dict[str, Any], definition: ApartmentClass,
              now: float, quote: Callable[[float], int]) -> bool:
    """Mutate proposals; return eviction, preserving the first unpaid date."""
    if lease.get("lapsed_since") is not None and now >= lease["lapsed_since"]+LAPSE_SECONDS:
        return True
    while now >= lease["rent_paid_until"]:
        due = lease["rent_paid_until"]
        invoice = lease.get("invoice")
        if not invoice or invoice["due"] != due:
            invoice = {"due": due, "amount": quote(due)}
            lease["invoice"] = invoice
        if player.chits_bank+player.chits_hand < invoice["amount"]:
            lease.setdefault("lapsed_since", due)
            if lease["lapsed_since"] is None:
                lease["lapsed_since"] = due
            return now >= lease["lapsed_since"]+LAPSE_SECONDS
        charge(player, invoice["amount"])
        lease["last_invoice"] = dict(invoice)
        lease["rent_paid_until"] += WEEK_SECONDS
        lease["lapsed_since"] = None
        lease.pop("invoice", None)
    return False


def reclaim_fee(item: ItemInstance, template: ItemTemplate) -> int:
    pack = template.stack_max if template.class_ == "ammo" else 1
    return rounded(Fraction(template.base_price*item.stack, pack)*IMPOUND_FRACTION)
