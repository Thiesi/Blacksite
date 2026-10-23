"""Game 8.3: pure listing, escrow and bounty state machines.

The world adapter operates on forks. Only its commerce commit installs a
fork alongside bank, item, impound and treasury changes.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from blacksite.server.rules.market import BOUNTY_MIN_CHITS, BOUNTY_MIN_TARGET_GRADE, BOUNTY_SECONDS, LISTING_EXPIRIES


@dataclass
class Listing:
    id: str
    seller: str
    item: str
    ask: int
    buyout: int | None
    created_at: float
    expires_at: float
    status: str = 'open'
    winner: str | None = None
    price: int = 0
    closed_at: float | None = None
    item_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class Bid:
    id: str
    listing: str
    bidder: str
    amount: int
    at: float
    status: str = 'held'


@dataclass
class Bounty:
    id: str
    poster: str
    target: str
    chits: int
    expires_at: float
    status: str = 'active'
    claimed_by: str | None = None


def positive(value: int) -> None:
    if type(value) is not int or value < 1:
        raise ValueError('Use a positive whole-chit amount.')


class Market:
    def __init__(self, origin: str, state: dict[str, Any] | None = None) -> None:
        state = state or {}
        self.origin = origin
        self.serial = state.get('serial', 0)
        self.listings = {row['id']: Listing(**row) for row in state.get('listings', [])}
        self.bids = {row['id']: Bid(**row) for row in state.get('bids', [])}

    def fork(self) -> 'Market':
        return deepcopy(self)

    def record(self) -> dict[str, Any]:
        return {'serial': self.serial, 'listings': [asdict(v) for v in self.listings.values()],
                'bids': [asdict(v) for v in self.bids.values()]}

    def next_id(self, kind: str) -> str:
        self.serial += 1
        return f'{self.origin}:{kind}:{self.serial}'

    def list_item(self, seller: str, item: str, price: int, buyout: int | None,
                  expiry: int, now: float) -> Listing:
        positive(price)
        if buyout is not None:
            positive(buyout)
            if buyout < price:
                raise ValueError('Buyout must cover the asking price.')
        if type(expiry) is not int or expiry not in LISTING_EXPIRIES:
            raise ValueError('Choose 24 hours, 72 hours or seven days.')
        if any(v.item == item and v.status == 'open' for v in self.listings.values()):
            raise ValueError('That item is already listed.')
        listing = Listing(self.next_id('listing'), seller, item, price, buyout, now, now + expiry)
        self.listings[listing.id] = listing
        return listing

    def active(self, lid: str, now: float) -> Listing:
        listing = self.listings.get(lid)
        if not listing or listing.status != 'open' or now >= listing.expires_at:
            raise ValueError('That listing is no longer open.')
        return listing

    def highest(self, lid: str) -> Bid | None:
        return max((b for b in self.bids.values() if b.listing == lid and b.status == 'held'),
                   key=lambda b: (b.amount, b.at, b.id), default=None)

    def bid(self, lid: str, bidder: str, chits: int, now: float) -> tuple[Bid, Bid | None]:
        listing = self.active(lid, now)
        positive(chits)
        if bidder == listing.seller:
            raise ValueError('You cannot bid on your own listing.')
        previous = self.highest(lid)
        if chits < (previous.amount + 1 if previous else listing.ask):
            raise ValueError('Bid above the highest bid and cover the asking price.')
        if listing.buyout is not None and chits >= listing.buyout:
            raise ValueError('Use buyout at that price.')
        bid = Bid(self.next_id('bid'), lid, bidder, chits, now)
        if previous:
            previous.status = 'outbid'
        self.bids[bid.id] = bid
        return bid, previous

    def buyout(self, lid: str, buyer: str, now: float) -> tuple[Listing, Bid | None]:
        listing = self.active(lid, now)
        if buyer == listing.seller:
            raise ValueError('You cannot buy your own listing.')
        if listing.buyout is None:
            raise ValueError('This listing has no buyout.')
        previous = self.highest(lid)
        if previous:
            previous.status = 'refunded'
        listing.status, listing.winner, listing.price = 'sold', buyer, listing.buyout
        listing.closed_at = now
        return listing, previous

    def cancel(self, lid: str, seller: str | None, now: float) -> tuple[Listing, Bid | None]:
        listing = self.active(lid, now)
        if seller is not None and listing.seller != seller:
            raise ValueError('Only the seller can cancel this listing.')
        previous = self.highest(lid)
        if previous and seller is not None:
            raise ValueError('A listing with an active bid cannot be cancelled.')
        if previous:
            previous.status = 'refunded'
        listing.status, listing.closed_at = 'cancelled', now
        return listing, previous

    def expire(self, now: float) -> list[tuple[Listing, Bid | None]]:
        results = []
        for listing in self.listings.values():
            if listing.status != 'open' or now < listing.expires_at:
                continue
            bid = self.highest(listing.id)
            if bid:
                bid.status = 'won'
            listing.status = 'sold' if bid else 'expired'
            listing.winner, listing.price = (bid.bidder, bid.amount) if bid else (None, 0)
            listing.closed_at = now
            results.append((listing, bid))
        return results

    def retire(self, pid: str, now: float) -> tuple[list[Listing], list[Bid]]:
        """Release retiring characters' obligations without reviving old bids."""
        returns, refunds = [], []
        for listing in self.listings.values():
            if listing.status != 'open':
                continue
            bid = self.highest(listing.id)
            if bid and (listing.seller == pid or bid.bidder == pid):
                bid.status = 'refunded'
                refunds.append(bid)
            if listing.seller == pid:
                listing.status, listing.closed_at = 'cancelled', now
                returns.append(listing)
        return returns, refunds


class Bounties:
    def __init__(self, origin: str, state: dict[str, Any] | None = None) -> None:
        state = state or {}
        self.origin = origin
        self.serial = state.get('serial', 0)
        self.rows = {row['id']: Bounty(**row) for row in state.get('rows', [])}

    def fork(self) -> 'Bounties':
        return deepcopy(self)

    def record(self) -> dict[str, Any]:
        return {'serial': self.serial, 'rows': [asdict(v) for v in self.rows.values()]}

    def post(self, poster: str, target: str, grade: int, chits: int, now: float) -> Bounty:
        if grade < BOUNTY_MIN_TARGET_GRADE:
            raise ValueError('Nobody pays for a Wake.')
        positive(chits)
        if chits < BOUNTY_MIN_CHITS:
            raise ValueError('A bounty starts at 100 chits.')
        self.serial += 1
        row = Bounty(f'{self.origin}:bounty:{self.serial}', poster, target, chits, now + BOUNTY_SECONDS)
        self.rows[row.id] = row
        return row

    def claim(self, target: str, killer: str, now: float, hostile_zone: bool) -> list[tuple[Bounty, str]]:
        if not hostile_zone:
            return []
        results = []
        for row in self.rows.values():
            if row.target != target or row.status != 'active' or now >= row.expires_at:
                continue
            row.status = 'refunded' if killer == row.poster else 'claimed'
            row.claimed_by = killer
            results.append((row, row.poster if killer == row.poster else killer))
        return results

    def expire(self, now: float) -> list[Bounty]:
        expired = []
        for row in self.rows.values():
            if row.status == 'active' and now >= row.expires_at:
                row.status = 'refunded'
                expired.append(row)
        return expired

    def refund(self, bid: str) -> Bounty:
        row = self.rows.get(bid)
        if not row or row.status != 'active':
            raise ValueError('That bounty is no longer active.')
        row.status = 'refunded'
        return row

    def retire(self, pid: str) -> list[Bounty]:
        rows = []
        for row in self.rows.values():
            if row.status == 'active' and pid in (row.poster, row.target):
                row.status = 'refunded'
                rows.append(row)
        return rows
