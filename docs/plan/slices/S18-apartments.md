# S18 — Apartments: rent, storage, safe, private core tier, eviction, impound

**Status:** done (PR #59)
**Primary model:** Sonnet · **Reviewer:** none
**Depends on:** S12, S15, S16 · **Milestone:** M3
**Issue:** https://github.com/Thiesi/blacksite/issues/18

## Goal

Give characters a home. Three apartment classes in the Terraces rented
per real-time week from the bank, with storage, a safe, a terminal, a
door lock, and a private core that S15 already knows how to hack; rent
lapse, eviction, and the Kestrel impound. This slice supplies the engine
and labelled native fixtures; S25 commissions the actual Terraces pool.
A legally discharged resident can then rent a Terrace Cell and log out
knowing where their things are.

## Spec references

- `docs/design/00-game-design.md` §8.7 (rent per week from bank,
  class storage/protected capacity, safe, terminal and class core tier,
  eviction after two weeks lapsed, impound with fee), §3.4 (legal
  discharge by grade or calendar), §6.4 (private core theft rule: S15).
- `docs/design/01-entities.md` §2.3 (apartment row), §1.1
  (`apartment_door` object kind).
- `docs/design/02-architecture.md` §6.1 (lazy clocks for rent).
- `docs/world/06-catalog.md` §13 (Terrace Cell 40 / tier 1 / 300,
  Terrace Flat 80 / tier 2 → 3 for 2 000 / 900, Corner Flat 120 / tier
  3 / 2 200; lock upgrade tier 3 for 800; impound reclaim 10 % of stored
  value).
- `docs/world/01-gazetteer.md`: `terraces-blocks` (Block Street),
  `terraces-lobby` (letting terminal), Block Relay effects (rent −10 %,
  +1 ICE slot: S21 hook).
- `docs/world/03-lattice.md` §2 (Terraces sector: one private-core
  entrance per rented apartment), §3.8 (private core template).

## Scope

- `server/apartments.py`: `content/apartments.json` (three classes);
  a pool of apartment door objects in `terraces-blocks` (at least 24
  doors across the three classes; S25 owns actual anchors; fixture has
  3). Keep future geography inactive or explicitly labelled as a native
  acceptance fixture, following accepted PR #38 findings 9/14;
  letting via the lobby terminal `MenuView` kind `letting` (legal_at set,
  one apartment per character, first week paid on signing from bank or
  hand).
- Rent: `rent_paid_until`; a lazy-clock check on login and on any
  apartment interaction charges due weeks from the bank first, then
  hand; unpaid → `lapsed_since`; two weeks lapsed → eviction: all
  storage and safe chits move to the Kestrel impound (a per-player
  impound record), the door is released, the private core is removed
  from the Terraces sector; reclaim at any Kestrel bank for 10 % of
  stored items' list value (chits reclaimed free).
- Door: `apartment_door` object; owner enters with `E`; the interior is
  a small pocket region inside `terraces-blocks` (a 6×4 room per
  apartment, `pocket` safety); non-owners face a lock (tier 1, upgrade
  to tier 3 for 800 chits) that a matching key/Passkey opens only into
  a 30 s vestibule. A visitor gets no access to storage, bank, bed or
  terminal. No breach charge can target an apartment door.
- Interior objects: storage (`MenuView` kind `storage`, move items both
  ways, capacity per class), safe (S12's bank API with the apartment as
  the account; banked chits, never lost to death), terminal (S13
  jack-in), a bed (logout here counts as safe zone logout).
- Private core: instantiate S15's template at the class tier on
  signing, register its entrance cell in the Terraces sector, upgrade
  tier 2 → 3 for 2 000 chits (Terrace Flat only), remove on eviction or
  surrender; the storage manifest exposed to hackers is the unsecured
  contents of `storage[]`. Half the listed capacity can be secured in
  place, separately from carried secured slots (game design 8.7).
- Surrender: `MenuView` action in the apartment menu with a
  confirmation keystroke; contents go to the impound with no fee.
- Block Relay hook: `rent_modifier` (−10 %) and `private_core_ice_slots
  +1` read from S21 (default none).
- Persistence: apartment rows, impound rows; flush on sign, pay,
  evict, reclaim.

## Out of scope

- Private core hacking, hack log content: S15 (this slice shows the
  log in the apartment menu using S15's data).
- Bank branches: S12.
- Placement of all door objects in the final Terraces map: S25.
- Block Relay capture: S21.

## Data and content

- `content/apartments.json`, apartment door objects in the Terraces
  zone file, interior room template (tiles) in `content/rooms/apartment.map`.
- Text: letting agent lines (Block Super, from the personae doc where
  present), eviction notice, impound receipt.

## Protocol and view models

- `MenuView` kinds `letting`, `apartment` (rent status, next due,
  storage, safe, core tier, lock tier, hack log, actions: upgrade core,
  upgrade lock, surrender), `storage`, `impound`.
- Toast on login when rent is due within 2 days or lapsed.

## Tests

- `tests/test_apartments.py`: grade/calendar discharge, one tenancy,
  failed-save rollback, queued rental races, bank-then-hand invoices,
  frozen discounts, all three capacities and protected halves,
  destination secured limits, safe/clone protection, eviction/reclaim,
  core/lock tariffs, visitor privacy, 30-second key/Passkey access,
  bed logout/reconnect, physical-unit theft cap, deletion cleanup,
  restored controls, active anchor validation and SQLite round-trip.
- `tests/lattice/test_private_cores.py`: existing real theft race,
  shared rolling allowance, quality-preserving ownership and hack logs.
- `tests/door/test_apartment_menus.py`: letting, apartment, storage,
  safe and impound rendered at 80x24/132x50 with wide caller names.
- `scripts/accept_s18_netbbs.py`: real native stdio through NetBBS,
  labelled placement/funding fixtures and a 22-day injected housing
  clock; S25 repeats these interactions on actual Terraces geography.

## Acceptance script

1. A grade-5 caller uses the lobby terminal, rents a Terrace Cell (300
   chits leave the bank), walks to the assigned door, presses `E`, is
   inside a small room; opens storage and moves a rifle in.
2. A second caller tries the door: "Locked. Tier 1." and nothing else.
3. The first caller logs out on the bed; on return they are in the
   apartment; a disclosed injected-clock fixture advances 22 days with
   no remaining rent funds (the first seven days were paid on signing);
   on the next login the eviction toast shows and the impound at the
   tram-hub bank lists the rifle with a 10 % fee.

## Definition of done

Roadmap §7, plus: eviction and reclaim round-trip every item instance
without duplication or loss in a persistence test.

## Implementer notes

- Rent is charged lazily; never a background timer. Charge on login,
  on any apartment interaction, and when S28's admin clock advance
  runs.
- The interior room is a pocket inside `terraces-blocks`, not a
  separate zone; do not add 24 zones.
- The impound is per player; multiple evictions append.
- S28 owns production clock/admin tooling. The native multi-week jump
  is a labelled fixture, not an interim production time-warp command.
- Storage can secure half its listed capacity in place, independently
  of carried secured capacity. Withdrawals still respect S16's current
  carried limit. This clarifies the planned unsecured half and avoids
  repetitive secure-and-deposit trips; class totals and fees do not change.
- Keep the private core's storage manifest as a view over `storage[]`
  filtered by `secured == False`; do not copy items.
- Signing issues a server-owned physical key with tenancy ID and lock
  tier. Residents enter without it. Upgrading the lock invalidates old
  keys and visitor grants; Passkey uses its actual tier (3). A fresh
  tenancy gets a new core and keys but keeps the physical home's daily
  theft watermark. Game design 8.7 defines these permissions.

## S18 consumer handoff

- S21 wires `rent_modifier(player, invoice_due_utc)` from historical
  Block Relay ownership. Issued invoices stay frozen. Its extra ICE
  slot adds one Tripwire; refresh commissioned cores when that benefit
  changes without undoing theft receipts.
- S23 depends on S18 and appends market items to the protected impound
  proposal with zero reclaim fee; keep original instance IDs and quality.
- S25 provides at least 24 resolved `housing` door anchors across the
  three classes, distinct safe 6x4 room floors and unallocated public
  Terraces sector cells, plus the real lobby letting terminal. Repeat
  the native rental/storage/visitor/bed/eviction/reclaim flow there at
  both sizes. The three Wake fixture anchors never ship as live content.
- S28 reconciles rent through `ensure_rent(player_id)` after authorized
  operator clock changes, draining transactions before success. The
  acceptance jump is 22 days with no rent funds, not 15 days after a
  paid first week. There is no production time-warp command in S18.
- S22/S30 keep crews and visitors outside resident permissions. Teach
  the separate safe account, storage protection and bank impound menu.
- S32 audits origin-scoped tenancy/key/impound authority and preserves
  the physical-unit theft receipt across tenancy changes.

These implement the accepted [PR #38](https://github.com/Thiesi/Blacksite/pull/38)
quality, geography and permission follow-ups without changing class
capacities, rents, upgrade tariffs or reclaim percentages.

## Lore review integration

Native provenance correction: the original local run used an older
installed client after NetBBS removed PYTHONPATH. The original separate
installed-wheel CI remains valid. S22 [PR #61](https://github.com/Thiesi/Blacksite/pull/61)
repeats signing, quality-preserving storage, visitor refusal, bed
reconnect, eviction and reclaim on version/source-verified 0.0.16 at
80x24 and 132x50, with wide names and 16 colours, through actual Windows
TTY NetBBS native stdio. `.test-tmp/native-s18-current16` retains passing
results. These are current-build regressions with the same explicit
housing/funding/clock fixtures, not a rerun of release 0.0.14.

Use game design 8.2 and 6.4 for rental and theft: legal discharge by
work or calendar, protected impound, at most one unsecured unit per
apartment per rolling 24 h, and a resident receipt. Interior permissions
are server-side on every action, including stale menus. Rent discounts
apply to the next invoice once; expiry cannot rewrite a paid invoice.

## S17 integration handoff

Preserve `ItemInstance.quality` through storage, safe access, eviction and
impound. S17 defines typed per-template quality in game design 8.4 and
entity 1.7; use `server.quality` for effective details. Rig permissions,
slots and tolerance stay fixed. Never reconstruct a stored item at
quality 1 or derive private-core tier from quality.

This carries the accepted [PR #38](https://github.com/Thiesi/Blacksite/pull/38)
findings 12/14 forward; see [S17](S17-salvage-and-fabrication.md).
