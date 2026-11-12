# S50 — Population switches: features open as the node grows

**Status:** planned (filed 2026-11-12; the owner merges the filing)
**Primary model:** Claude Opus 5.5 (the engineer) · **Announcement lines:** creative lead · **Looks and acceptance:** presentation lead · **Reviewer:** automated review, technical lead
**Depends on:** S49 (the season frame and its season-start hook, and the Old Works sites Season 0's set needs), S20, S21 and S23 (all merged) · **Lands before:** S31 (the first release runs Season 0 below every threshold) · **Milestone:** the alpha
**Issue:** https://github.com/Thiesi/Karst41/issues/233

Canon: game design §13.5 (population switches) and §13.1 (the Depth
target follows the same rule), both merged in #219. Where this file and
canon differ, canon wins.

## Why

A node has a handful of players. Systems built for a crowd should open
as the crowd arrives, by rule, so no SysOp has to guess up front (owner,
2026-11-12). The owner ran a BBS: the hardest calls were the ones made at
setup that couldn't be undone. The game measures and decides, and the
SysOp doesn't.

## Goal

The game measures **weekly active players**: distinct BBS users who
played any character in the last seven days, so one person's alts count
once. Joinable factions, contested relays, market bids and escrow, and
the Depth target open from that measure under §13.5's rules. A new node
starts below every threshold: Sablier, the Wardens and the Unmoored
accept members, and Cold Chain, Block and Relay Zero are contested.

## Scope

### 1. The measure

- **Counting:** the I/O layer computes weekly active players once a day
  from last-seen data, counting distinct BBS users, not characters.
- **Into the simulation:** it hands the count in as an input frame. The
  simulation reads no clock for it (AGENTS §4).
- **Persistence:** the last measure is stored, so a restart doesn't
  reopen or re-close anything.
- **A new node:** S49's first season start (an initialisation) stores
  the first measure and every switch below threshold. No fallback
  effects run then, so a later season's re-evaluation always compares
  against initialised state.

### 2. The switches

- **Joinable factions:** three (Sablier, Wardens, Unmoored), more at
  about 15 with Red Sable first, and all nine at about 30.
- **Contested relays:** three (Cold Chain, Block, Relay Zero), six at
  about 15, and all sixteen at about 40.
- **Market:** plain listings, with bids and escrow at about 50.
- **Depth target:** small node, with standard and large at their
  thresholds (§13.1). The target is read by S26 when Season 1 runs. Here
  it's only the switch and its stored state.
- **Thresholds and set order are content,** not code constants, so
  playtests can tune them without a code change.
- **A faction that doesn't accept members** still offers work and
  standing, and keeps its place in the story (§13.5). Only joining is
  closed.

### 3. Opening and the season boundary

- **Within a season,** a switch only opens and never closes, even if
  the measure falls.
- **At a new season** (S49's season-start hook), every switch is
  re-evaluated from the measure.
- **When a new season finds the measure below a threshold that was
  open:**
  - existing members keep their membership, but that faction takes no
    new members;
  - relays that fall out of the contested set reset;
  - open market bids are refunded to the bidder's bank;
  - a member who leaves such a faction can't rejoin it until the
    population grows back past its threshold.

### 4. Announcements

- The city announces each opening in its own voice, in the place it
  concerns (§13.5). The creative lead writes the lines. They're
  delivered through the existing log kinds, never the operator's
  `notice` kind.
- Growth is something players notice, not a configuration screen.

### 5. Operator view

- The admin status shows the current measure and each switch's state,
  read-only.
- There's no operator setting that opens a switch early. If an override
  is ever wanted, it's a separate owner decision, as an override and
  never a prerequisite.

## Open items

The slice proposes each in its PR. The technical lead rules, and brings
anything that changes the economy to the owner.
- **A one-day spike** (from #219's review). A promo weekend can open a
  switch for the whole season, because switches only open within a
  season. Throwaway BBS accounts can do the same. That follows the
  owner's rule. Settle it before the build starts, because market bids
  and escrow opened too early are hard to undo within a season. A hold
  before a switch opens is one option, for example two consecutive daily
  samples above the threshold.
- **Market listings at a season change** (from #219's review). When a
  season change closes bids, open bids are refunded (canon). Still to
  settle:
  - what happens to the listing: buyout-only for its remaining time, or
    cancelled with the escrowed item returned;
  - the seller's fee;
  - a refund into a bank that is in clone debt.

## Out of scope

- Depth contribution, consoles and expeditions: S26.
- New factions, relays or market features. This slice gates what
  exists.
- An operator override.

## Tests

- **The measure:**
  - counts distinct BBS users, so alts count once;
  - the simulation reads it only from the input;
  - restart keeps it.
- **Opening:**
  - each switch opens at its threshold;
  - nothing closes within a season when the measure falls;
  - re-evaluation happens at a season start.
- **Fallback:**
  - membership is kept;
  - no new joins;
  - leaving blocks rejoining until the measure is back;
  - relays outside the set reset;
  - open bids are refunded exactly once.
- **Season 0:**
  - a fresh node's first season start initialises the measure and the switches with no fallback effects;
  - a new node accepts members only for Sablier, Wardens and Unmoored;
  - contests only Cold Chain, Block and Relay Zero;
  - other factions still offer work and standing.
- **Announcements:**
  - one per opening, in the right place;
  - never the `notice` kind.
- **Fingerprints:** P3 and the mechanics fingerprint don't move unless
  named and justified. A move under an owner approval stops the slice.

## Definition of done

Roadmap §7. Plus native evidence at 80x24 and 132x50:
- a closed faction's hall: work offered, joining refused with the
  reason;
- an opening announcement;
- the admin status.

The presentation lead accepts it. H1 and the S25 layout approval are not
part of this slice and aren't granted by it.
