# S37 — Dead drops: addressed item stacks and Kestrel returns

**Status:** planned (approved by the owner 2026-10-31)
**Primary model:** Codex for engine · presentation lead or Codex for drop-object placement · **Reviewer:** automated review, technical lead, presentation lead (views, wording and placement)
**Depends on:** S23, S35 · **Milestone:** asynchronous presence (#125)
**Issue:** filed on approval

Canon: game design §11.1, "Dead drops", from #128. Where this file and
canon differ, canon wins.

**Timing (owner, 2026-10-31):** starts after H1, beside C1 and S25c.
Until P10's cutover, every view is built in both presentations.

## Goal

A character can leave one small item stack at a dead-drop object for
one named character, who collects it later. Drops are never a bulk
transfer channel and never reveal an ignore or a retirement.

## Spec references

- Game design §11.1 (dead drops, every sub-bullet), §8.3 (market board:
  accepted items, 5 % Kestrel fee, collection, impound), §8.4 (salvage
  trading), §10.1 (retirement).
- Entities: item flags (equipped, secured, bound, mission), the
  authored object entity.
- Gazetteer: dead-drop objects, at least one per district.
- Architecture §6.2 (immediate flush on item transfer), §5.5.4
  (disclosure).
- Build notes on #125 (confirmation, refusal and return wording).

## Scope

- **Persistence.** A migration (numbered in merge order): drop (sender, sender
  identity, recipient, object, item instance, units, fee, left, state).
  A **name history** (name, first used), written at character
  creation, backfilled from existing characters by the migration, and
  never deleted at retirement: it is the only source for "a name that
  has existed on the node". Returned and withdrawn drops use S34's free
  Kestrel collection record; this slice adds no second one. Leaving,
  collecting, refusing and returning each commit immediately with the
  item transfer.
- **Leaving.** At an authored dead-drop object, to any name that has
  existed on the node, with the same result whether the recipient is
  active, retired or ignoring the sender. Only a never-used name is
  refused ("No one by that name."). One outgoing drop per character,
  one per identity per rolling 24 hours, at most 10 units, only items
  the market board accepts. The fee is 5 % of catalog base price times
  units, rounded up, at least 1 chit, paid on leaving and never
  refunded. Items with no catalog base price cannot be dropped and get
  the same refusal as other items the board won't take.
- **Withdrawal.** The sender withdraws a drop until it is collected:
  it returns as a free Kestrel collection, the fee is kept, the result
  is the same whether or not it arrived, and the 24-hour limit still
  counts it. Wording: "Withdraw your drop for Name? It goes to a
  Kestrel branch. The fee is not refunded. (y/n)".
- **Collecting and refusing.** Only the recipient sees the drop and
  can collect or refuse it. Refusal returns it.
- **Returns.** After 7 days uncollected, or on refusal, the same item
  instance returns to the sender as a free collection at any Kestrel
  branch. A drop blocked by an ignore returns only at expiry. The
  sender sees one line in every case: "Your drop for Name came back."
- **Retirement.** Recipient retired: returns at expiry. Sender retired:
  stays until expiry, then is deleted. Both retired: deleted. The
  sender's retirement confirmation lists drops in flight.
- **Away records.** Drops waiting and own drops returned, written to
  S35's store.
- **Content.** Dead-drop objects placed in each district's zones, never
  in safe zones or pockets, as the gazetteer names them. Placement
  that changes a zone's geometry waits for that district's human gate
  (S25c, H3); otherwise objects go on existing passable tiles.
- **Admin CLI.** `drop list`, `drop return <id>`.

## Out of scope

- Any change to the market board.

## Protocol and view models

- Every viewer sees the dead-drop object itself. Only the recipient of
  a waiting drop sees it in its "waiting" look and gets a HERE line for
  it; everyone else sees the object as usual.
- A drop view: leave (with "10 of N fit in a drop" and the fee
  confirmation), collect, refuse (one key).
- Kestrel collections show "kept until <date>".

## Tests

- Same result for active, retired, ignoring and ordinary recipients;
  refusal only for a never-used name. A retired, a deleted and a reused
  name are all accepted alike, from the name history.
- Limits: one outgoing per character, one per identity per 24 hours,
  10 units, market-accepted items only.
- Fee arithmetic, rounding, the 1-chit floor, can't-pay refusal, never
  refunded; an item with no catalog base price is refused.
- Withdrawal: same sender view whether delivered, ignored or not;
  the item reaches a Kestrel collection; the 24-hour limit still counts.
- Collect, refuse, expiry and ignore paths; the same item instance
  returns; the sender's view is identical in every return case.
- Retirement paths and the confirmation listing.
- The 30-day collection, then impound.
- A crash between leaving and commit leaves the item with the sender.
- Disclosure: no one but the recipient sees the drop.

## Acceptance script

1. A leaves 10 nutrient bars for B at a dead drop in Sodium Row and pays the
   fee. B, offline, sees it in the away report, walks there and
   collects it.
2. A leaves a drop for C, who ignores A. A sees "left", and after 7
   days "Your drop for C came back." A collects it at a Kestrel branch.
3. A tries a second drop the same day and is told how long to wait.

## Definition of done

Roadmap §7, plus: the item-transfer and disclosure tests pass, and the
presentation lead signs off views, wording and placement.

## Owner decisions

Decided 2026-10-31 and now in §11.1: senders may withdraw a drop, and
items with no catalog base price cannot be dropped.
