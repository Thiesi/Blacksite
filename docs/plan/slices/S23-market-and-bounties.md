# S23 — Market and bounties: listings, bids, fees, bounty rules

**Status:** done (PR #64)
**Primary model:** Sonnet · **Reviewer:** Opus
**Depends on:** S12, S18, S20, S21 · **Milestone:** M4
**Issue:** https://github.com/Thiesi/blacksite/issues/23

S18 is an explicit dependency because this slice delivers to personal
impound. Append market goods to `interlock_state.impounds[player]` in
the same commerce transaction, with zero reclaim fee. Reuse
`Apartments.impound` on proposal copies; retain instance IDs, quality,
charges, drone condition and secured status. The housing eviction fee
must not tax a paid market delivery. Collection at terminals rechecks
normal terminal access; visitors and crew members do not acquire an
apartment resident's permissions. See game design 8.7, entity 2.3 and
accepted [PR #38](https://github.com/Thiesi/Blacksite/pull/38).

S21 is an explicit dependency for the single faction treasury authority.
Join the Kestrel fee to its committed relay ledger in the same source
transaction as seller/buyer bank changes and impound delivery. Market
fees add treasury, not influence; do not create a second faction balance
or let a later relay checkpoint overwrite the fee. Season reset retains
earned treasury. See the [S21 handoff](../s21-relay-handoff.md).

## Goal

Implementation and evidence: [PR #64](https://github.com/Thiesi/Blacksite/pull/64)
and the [S23 acceptance record](../../ops/s23-acceptance.md). Future Sink
geography and ordinary earning/clinic/human pacing remain S25/S26 gates;
the disclosed transaction fixtures do not satisfy them.

Give players an asynchronous, Kestrel-taxed market for items and a bounty
board for names, reachable from any terminal. The market is the only
player-to-player trade that works while one side is offline; the bounty
board is the only sanctioned way to pay for a kill. Both are menus over
persistent rows, resolved by the server, with no new real-time mechanics.

## Spec references

- `docs/design/00-game-design.md` §8.3 (market, 5 % fee, bounties refused
  below grade 5), §7.3 (Marked; bounty claims only in contested or open
  zones), §14 (one market action per second), §11 (BBS handle beside
  character name).
- `docs/design/01-entities.md` §2.6 (Market and Bounty rows), §2.2 (item
  instance ownership), §4 (MenuView).
- `docs/design/02-architecture.md` §5.2 (`intent`), §5.4 (`MenuView`
  body), §6.2 (immediate flush on market action).
- `docs/design/03-terminal-ui.md` §4 (menus, action bars, no questions).
- `docs/world/06-catalog.md` §12 (vendor inventories; the market is not a
  vendor) and the Kestrel dossier in `docs/world/02-factions.md` (the fee
  is Kestrel's and pays into the Kestrel treasury).

## Scope

- `src/blacksite/server/market.py`: `Market` service with `list_item`,
  `bid`, `buyout`, `cancel`, `expire`, `collect`; `Bounties` service with
  `post`, `claim`, `expire`, `refund`.
- Listings: seller, item instance (moved to `owner = market` on listing),
  ask price, optional buyout, expiry (24 h, 72 h, 7 d), bids with the
  highest held in escrow (chits moved from the bidder's bank). Winning
  bid or buyout transfers the item to the buyer's **Kestrel impound**
  slot list (collect at any bank or terminal), pays the seller
  `price × 0.95` to the bank, and pays `price × 0.05` to the Kestrel
  faction treasury (`FactionState.treasury`).
- Cancel returns the item to seller inventory; cancel with an active
  bid is refused with a toast. Expiry with no bid restores inventory;
  with a bid, sells to it. Return may make the seller overweight, never
  discard the item or turn cancellation into a free impound deposit.
- Bounties: poster pays chits from the bank into escrow; target must be
  a grade ≥ 5 player on this origin; minimum 100 chits; expiry 7 d;
  refunded on expiry. A kill of the target by any player other than the
  poster, in a contested or open zone, pays the escrow to the killer's
  bank and posts a log line to both. A kill by the poster refunds the
  bounty and pays nothing. Multiple bounties on one name stack and pay
  together.
- Bounty visibility: the board lists target name, handle, total chits,
  and number of posters; posters are anonymous to everyone but the admin
  audit log.
- Menus (`MenuView`): **Market** (browse by class, sort by price/expiry,
  detail pane shows stats and quality, actions `[D] bid`, `[U]y buyout`,
  `[L]ist item`, `[M]y listings`, `[C]ollect`), **Bounties** (`[P]ost`,
  detail pane, `[B]ack`). Listing an item opens the inventory menu
  filtered to unsecured, non-equipped items, then a price line prompt.
- Terminal object interaction gains `[M]arket` and `[O]unties` actions
  wherever a `terminal` object exists (public, apartment, faction hall).
- Rate limit: one market or bounty action per second per session
  (design §14); excess is dropped with a toast.
- Persistence: every action flushes immediately (architecture §6.2).
- Admin CLI: `market list`, `market cancel <id>`, `bounty list`,
  `bounty refund <id>` (server-side implementations here; S28 owns the
  CLI surface and wires these).

## Out of scope

- Vendor buy/sell (S12). Faction treasury payout to members (S21).
- Crew loot rules (S22). Marked consequences of a bounty kill (S20: a
  bounty kill follows the normal Marked rule; the bounty does not exempt
  the killer).
- NetBBS-side notification of a bounty (upstream 05; not required).

## Data and content

- New tables per entities §2.6: `market_listings`, `market_bids`,
  `bounties`. Reuse S18's protected impound records in
  `meta.interlock_state`; do not create a second collection authority.
- Constants in `src/blacksite/server/rules/market.py`: exact
  `MARKET_FEE = 5/100`,
  `BOUNTY_MIN_CHITS = 100`, `BOUNTY_MIN_TARGET_GRADE = 5`,
  `LISTING_EXPIRIES = (24h, 72h, 7d)`, each with a comment citing design
  §8.3 and asserted by a test.
- Text assets: `text-market-help`, `text-bounty-notice` (the line both
  parties see: "A price has been put on {name}. {chits} chits.").

## Protocol and view models

- Intents: `market.open`, `market.list {item, price, buyout, expiry}`,
  `market.bid {listing, chits}`, `market.buyout {listing}`,
  `market.cancel {listing}`, `market.collect`, `bounty.open`,
  `bounty.post {target, chits}`; menu cursor intents from S04/S09.
- `MenuView` bodies for both menus per architecture §5.4; the detail
  pane text for a listing shows template stats, quality as a percentage,
  seller handle, expiry countdown, highest bid.
- Log lines with channel `system` for sale, outbid, expiry, bounty
  posted, bounty claimed.

## Tests

- `test_listing_moves_item_to_market_owner`
- `test_buyout_pays_seller_95_percent_and_kestrel_5_percent`
- `test_bid_escrows_chits_from_bank_and_refunds_outbid_bidder`
- `test_cancel_refused_with_active_bid`
- `test_expiry_without_bid_returns_item_to_seller`
- `test_expiry_with_bid_sells_to_highest_bidder`
- `test_collect_moves_impound_items_to_inventory_respecting_carry`
- `test_bounty_refused_below_grade_5_target`
- `test_bounty_refused_below_100_chits`
- `test_bounty_claim_pays_killer_in_contested_zone`
- `test_bounty_not_paid_in_safe_zone_kill`
- `test_bounty_by_poster_kill_refunds_only`
- `test_stacked_bounties_pay_together`
- `test_bounty_expiry_refunds_poster`
- `test_market_action_rate_limit_one_per_second`
- `test_market_actions_flush_immediately` (harness: crash after action,
  restart, row present)
- `test_menu_view_market_detail_pane_shape`

## Acceptance script

1. On a NetBBS node with two callers (A and B) at 80×24, A opens a
   public terminal in `core-plaza`, presses `F9` then `M`, lists a starter pistol
   at 50 chits with a 100-chit buyout, 24 h expiry. The Market menu shows
   it under "My listings". Before `Y`, confirmation shows 47 net at ask
   and 95 at buyout, with the whole-chit fee explained.
2. B opens the market from the Tin Halo terminal, sees the listing with
   A's handle, bids 60. A's log shows "bid received". B then presses `U`
   for buyout; B's bank drops by 100, A's bank rises by 95, and
   `blacksite admin status` shows the Kestrel treasury up by 5.
3. B opens a bank menu and presses `C`, then confirms collection: the
   pistol arrives in B's inventory. Outside menus, `C` remains chat.
4. A (grade ≥ 5) posts a 200-chit bounty on B (grade ≥ 5). Both logs show
   the notice. A third caller buys ammunition at the real outfitter, then
   kills B on a commissioned contested hub
   tile: the killer's bank rises by 200 and the board no longer lists B.
   S25 retains the real `sink-rim` travel/location acceptance; the hub
   run does not prove that future geography.
5. Attempt to post a bounty on a grade-2 character: toast "Nobody pays
   for a Wake." and no chits move.

## Definition of done

- All tests above green; content validator unchanged.
- Roadmap definition of done satisfied; slice file marked done with the
  PR number.
- Design doc §8.3 unchanged, or changed with reason in the PR.

## Implementer notes

- Game 8.3 now specifies whole-chit ceiling for the existing 5% fee;
  the seller gets the remainder. Own bid increases and buyout reuse
  escrow instead of requiring the full price twice.
- Market impound entries carry `source: market`, with no collection
  fee. Accessible terminals collect those entries; ordinary impound
  access and fees remain unchanged. Preserve exact instance identity
  on collection, including stacks, charges and drone condition.
- Only purchases use protected delivery. Unsold returns restore seller
  inventory, so cancellation cannot bypass apartment storage tariffs.
- `B` and `Esc` leave/back throughout; use `D` for bid. The old `B`
  bid hotkey conflicted with AGENTS and the client's back binding.
- F9 opens public services beside a terminal, including a shared contract
  board. Preserve E for existing board/jack interaction and street M/O/C
  for map/drone/chat.
- Menu views contain at most 12 rows with cursor-driven paging. Operator
  list commands accept a positive `page`, default 1, with 100 records per
  page and `page/pages/total` metadata. Market operator pages include
  current held bids for their listings. Historical records remain stored.
- The pure state machines live in `market.py`, world proposals in
  `market_engine.py` and server menus in `market_views.py`. Schema 4
  adds the three tables; only the storage layer writes them.
- Retain held/refunded/won bid history, sale-time item snapshots and
  retirement cleanup. A failed source announces no success, and a
  restart never repeats a sale, refund or death payout.
- Keep a derived held-bid lookup, format the visible page and clone live
  financial records while sharing immutable closed history. S29 retains
  the full populated-world latency gate; a small local probe is not that
  acceptance. Listing confirmation shows actual net proceeds, including
  zero for a one-chit sale. No extra bounty tax or minimum price is added.
- Record grade/funding fixtures separately from actual native walking,
  terminal access, trading, firing and death. Retain S19/S25 actual
  earning and clinic pacing obligations.

- Escrow always moves **banked** chits, never chits on hand, so death
  cannot interact with an open bid (design §8.1).
- Item ownership transitions must go through the storage layer's single
  writer; never mutate `Item.owner` outside a transaction.
- The buyer receives via impound, not directly, so a full inventory or
  carry limit (design §3.1 carry) never blocks a sale.
- Bounty claims are checked in the death handler (S10) by a hook the
  market module registers; keep the hook synchronous and cheap.
- Handles may be wide or long; the menu column widths must truncate by
  display width (client rule, `03-terminal-ui.md` §6).

## S17 integration handoff

Retain the exact instance quality, ammo, charges and drone condition
through listings, bids, delivery and return. Display actual selected
stats with `server.quality.detail`; template base stats plus a quality
label alone are insufficient. Slots, permissions and durations stay fixed.

This carries the accepted [PR #38](https://github.com/Thiesi/Blacksite/pull/38)
findings 12/14 forward; see [S17](S17-salvage-and-fabrication.md).


### S20 faction integration handoff

Reference: [PR #38](https://github.com/Thiesi/Blacksite/pull/38) and S20.

Use S20 actual membership and active Marked deadlines when validating
bounties. Permission to post a bounty never grants a combat exemption. Sable
reservations apply only to optional NPC rotating stock; player market
delivery keeps S18 protected personal impound.

### S22 crew integration handoff

S22 [PR #61](https://github.com/Thiesi/Blacksite/pull/61) supplies the live
crew authority. Crew affiliation never bypasses combat legality,
actual-victim cache recovery, personal impound or market ownership.

<!-- s19-services:start -->
### S19 source and service handoff

Reference: [S19 PR #62](https://github.com/Thiesi/Blacksite/pull/62),
[acceptance record](../../ops/s19-acceptance.md) and
[PR #38](https://github.com/Thiesi/Blacksite/pull/38).

S19 supplies the implemented source interfaces, 68 authored contracts
and four service nodes. Full root pytest passed 1344 tests with one
skip. Installed native acceptance covers both sizes and allocations,
forks, repair reconnect and paid restart. Consume the merged PR;
S25/S27/S26 still own real geography, referrals and activation.

Mission supplies have instance/stage bindings and cannot enter listings,
storage transfers or fabrication. Reserve caches grant two ordinary power
units total, shared across workers. Consume the existing inventory boundary;
do not turn mission units or repeat reward receipts into market stock.
<!-- s19-services:end -->
