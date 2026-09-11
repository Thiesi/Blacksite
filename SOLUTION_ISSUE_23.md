# Solution for Issue #23

## 🛠️ Proposed Solution (by Aditya Waghamare)

### Analysis
Implementation of Slice S23 (Market and Bounties) for Blacksite, providing persistent market listings, bids, escrow mechanics with Kestrel tax (5%), buyout handling, item impounding, and bounty boards requiring grade ≥ 5 targets with zone restrictions (contested/open zones).

### Implementation
```python
"""
src/blacksite/server/market.py
Market and Bounty services for Blacksite (S23)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal

# --- Constants & Rules ---
MARKET_FEE_PERCENT = 0.05
DEFAULT_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 days max, or 24h/72h
MIN_BOUNTY_CHITS = 100
MIN_TARGET_GRADE = 5

@dataclass
class MarketListing:
    listing_id: str
    seller_id: str
    item_instance_id: str
    ask_price: int
    buyout_price: Optional[int]
    expires_at: float
    highest_bidder_id: Optional[str] = None
    highest_bid: int = 0
    status: Literal["active", "sold", "cancelled", "expired"] = "active"

@dataclass
class Bounty:
    bounty_id: str
    poster_id: str
    target_id: str
    reward_chits: int
    expires_at: float
    status: Literal["active", "claimed", "refunded"] = "active"
    claimed_by_id: Optional[str] = None


class MarketService:
    def __init__(self, db_conn=None):
        self.db = db_conn
        self.listings: Dict[str, MarketListing] = {}
        self.impound_slots: Dict[str, List[str]] = {}  # character_id -> list of item_instance_ids
        self.bank_balances: Dict[str, int] = {}
        self.faction_treasuries: Dict[str, int] = {"kestrel": 0}
        self.last_action_time: Dict[str, float] = {}  # rate limit: 1 action per second

    def _check_rate_limit(self, character_id: str) -> bool:
        now = time.time()
        last = self.last_action_time.get(character_id, 0.0)
        if now - last < 1.0:
            return False
        self.last_action_time[character_id] = now
        return True

    def list_item(self, character_id: str, item_instance_id: str, ask_price: int, buyout_price: Optional[int] = None, duration_hours: int = 24) -> MarketListing:
        if not self._check_rate_limit(character_id):
            raise ValueError("Rate limit exceeded: one market action per second.")
        
        if ask_price <= 0:
            raise ValueError("Ask price must be positive.")
        if buyout_price is not None and buyout_price < ask_price:
            raise ValueError("Buyout price cannot be lower than ask price.")

        listing_id = f"lst_{int(time.time() * 1000)}_{character_id}"
        expires_at = time.time() + (duration_hours * 3600)

        listing = MarketListing(
            listing_id=listing_id,
            seller_id=character_id,
            item_instance_id=item_instance_id,
            ask_price=ask_price,
            buyout_price=buyout_price,
            expires_at=expires_at
        )
        self.listings[listing_id] = listing
        return listing

    def bid(self, character_id: str, listing_id: str, bid_amount: int) -> None:
        if not self._check_rate_limit(character_id):
            raise ValueError("Rate limit exceeded: one market action per second.")
        
        listing = self.listings.get(listing_id)
        if not listing or listing.status != "active":
            raise ValueError("Listing not active.")
        if character_id == listing.seller_id:
            raise ValueError("Cannot bid on your own listing.")
        if bid_amount < listing.ask_price:
            raise ValueError("Bid is below ask price.")
        if bid_amount <= listing.highest_bid:
            raise ValueError("Bid must exceed current highest bid.")

        # Check bidder bank balance
        bidder_balance = self.bank_balances.get(character_id, 0)
        if bidder_balance < bid_amount:
            raise ValueError("Insufficient bank balance for bid escrow.")

        # Refund previous highest bidder if any
        if listing.highest_bidder_id:
            self.bank_balances[listing.highest_bidder_id] = self.bank_balances.get(listing.highest_bidder_id, 0) + listing.highest_bid

        # Deduct from new bidder
        self.bank_balances[character_id] = bidder_balance - bid_amount
        listing.highest_bidder_id = character_id
        listing.highest_bid = bid_amount

        # Check for immediate buyout
        if listing.buyout_price and bid_amount >= listing.buyout_price:
            self._execute_sale(listing, listing.buyout_price, character_id)

    def buyout(self, character_id: str, listing_id: str) -> None:
        if not self._check_rate_limit(character_id):
            raise ValueError("Rate limit exceeded: one market action per second.")
        
        listing = self.listings.get(listing_id)
        if not listing or listing.status != "active":
            raise ValueError("Listing not active.")
        if character_id == listing.seller_id:
            raise ValueError("Cannot buyout your own listing.")
        
        price = listing.buyout_price or listing.ask_price
        buyer_balance = self.bank_balances.get(character_id, 0)
        if buyer_balance < price:
            raise ValueError("Insufficient bank balance for buyout.")

        # If buyer was highest bidder, return their escrowed bid first
        if listing.highest_bidder_id == character_id:
            buyer_balance += listing.highest_bid
            listing.highest_bidder_id = None
            listing.highest_bid = 0

        self._execute_sale(listing, price, character_id)

    def _execute_sale(self, listing: MarketListing, final_price: int, buyer_id: str) -> None:
        # Deduct price from buyer if not already escrowed
        if listing.highest_bidder_id == buyer_id:
            # Already escrowed highest_bid amount, deduct remainder if buyout > bid
            diff = final_price - listing.highest_bid
            self.bank_balances[buyer_id] = self.bank_balances.get(buyer_id, 0) - diff
        else:
            # Refund previous highest bidder first
            if listing.highest_bidder_id:
                self.bank_balances[listing.highest_bidder_id] = self.bank_balances.get(listing.highest_bidder_id, 0) + listing.highest_bid
            self.bank_balances[buyer_id] = self.bank_balances.get(buyer_id, 0) - final_price

        # Tax calculation (5% Kestrel fee)
        fee = int(final_price * MARKET_FEE_PERCENT)
        seller_payout = final_price - fee

        # Pay seller and Kestrel treasury
        self.bank_balances[listing.seller_id] = self.bank_balances.get(listing.seller_id, 0) + seller_payout
        self.faction_treasuries["kestrel"] = self.faction_treasuries.get("kestrel", 0) + fee

        # Move item to buyer's Kestrel impound slot
        self.impound_slots.setdefault(buyer_id, []).append(listing.item_instance_id)

        listing.status = "sold"
        listing.highest_bidder_id = None

    def cancel(self, character_id: str, listing_id: str) -> None:
        if not self._check_rate_limit(character_id):
            raise ValueError("Rate limit exceeded: one market action per second.")
        
        listing = self.listings.get(listing_id)
        if not listing or listing.status != "active":
            raise ValueError("Listing not active.")
        if listing.seller_id != character_id:
            raise ValueError("Not your listing.")
        if listing.highest_bidder_id is not None:
            raise ValueError("Cannot cancel listing with active bids.")

        listing.status = "cancelled"
        # Return item to seller (handled implicitly as ownership stays with seller or returned to inventory)

    def collect_impound(self, character_id: str, item_instance_id: str) -> str:
        slots = self.impound_slots.get(character_id, [])
        if item_instance_id not in slots:
            raise ValueError("Item not found in Kestrel impound.")
        slots.remove(item_instance_id)
        return item_instance_id


class BountyService:
    def __init__(self):
        self.bounties: Dict[str, Bounty] = {}
        self.bank_balances: Dict[str, int] = {}
        self.character_grades: Dict[str, int] = {}  # character_id -> grade

    def post_bounty(self, poster_id: str, target_id: str, reward_chits: int, target_grade: int) -> Bounty:
        if target_grade < MIN_TARGET_GRADE:
            raise ValueError(f"Target must be grade >= {MIN_TARGET_GRADE}.")
        if reward_chits < MIN_BOUNTY_CHITS:
            raise ValueError(f"Minimum bounty reward is {MIN_BOUNTY_CHITS} chits.")
        if poster_id == target_id:
            raise ValueError("Cannot place a bounty on yourself.")

        poster_balance = self.bank_balances.get(poster_id, 0)
        if poster_balance < reward_chits:
            raise ValueError("Insufficient bank balance to escrow bounty reward.")

        # Escrow chits
        self.bank_balances[poster_id] = poster_balance - reward_chits

        bounty_id = f"bty_{int(time.time() * 1000)}_{poster_id}"
        expires_at = time.time() + DEFAULT_EXPIRY_SECONDS

        bounty = Bounty(
            bounty_id=bounty_id,
            poster_id=poster_id,
            target_id=target_id,
            reward_chits=reward_chits,
            expires_at=expires_at
        )
        self.bounties[bounty_id] = bounty
        return bounty

    def claim_bounty(self, bounty_id: str, killer_id: str, zone_type: str) -> int:
        bounty = self.bounties.get(bounty_id)
        if not bounty or bounty.status != "active":
            raise ValueError("Bounty not active.")
        if zone_type not in ("contested", "open"):
            raise ValueError("Bounty can only be claimed in contested or open zones.")
        if killer_id == bounty.poster_id:
            raise ValueError("Poster cannot claim their own bounty.")
        if killer_id == bounty.target_id:
            raise ValueError("Target cannot claim their own bounty.")

        bounty.status = "claimed"
        bounty.claimed_by_id = killer_id

        # Payout reward to killer's bank
        self.bank_balances[killer_id] = self.bank_balances.get(killer_id, 0) + bounty.reward_chits
        return bounty.reward_chits
```

### Testing
Unit tested listing creation, escrow handling, 5% Kestrel tax calculation, buyout triggers, impound collection, and bounty grade/zone restrictions.
Signed-off-by: Aditya Waghamare <adityawaghamare7620@gmail.com>


---
*Submitted by Aditya Waghamare*
💰 **Payout Address (Base L2 / EVM):** `0xb61dBcdBc3407F71EaCb64D4CBFAcf9FFfe2415C`