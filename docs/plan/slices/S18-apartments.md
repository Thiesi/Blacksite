# S18 — Apartments: rent, storage, safe, private core tier, eviction, impound

**Status:** planned
**Primary model:** Sonnet · **Reviewer:** none
**Depends on:** S12, S15, S16 · **Milestone:** M3
**Issue:** https://github.com/Thiesi/blacksite/issues/18

## Goal

Give characters a home. Three apartment classes in the Terraces rented
per real-time week from the bank, with storage, a safe, a terminal, a
door lock, and a private core that S15 already knows how to hack; rent
lapse, eviction, and the Kestrel impound. After this slice a grade-5
character can rent a Terrace Cell and log out knowing where their
things are.

## Spec references

- `docs/design/00-game-design.md` §8.7 (rent per week from bank,
  storage 40, safe, terminal, private core tier 1 upgradeable to 3,
  eviction after two weeks lapsed, impound with fee), §3.4 (grade 5
  required to rent), §6.4 (private core theft rule: S15).
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
  doors across the three classes; S25/S08 place them; fixture has 3);
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
  half of `storage[]`.
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

- `tests/test_apartments.py::test_legal_discharge_required_grade_or_calendar`
- `tests/test_apartments.py::test_one_apartment_per_character`
- `tests/test_apartments.py::test_rent_charged_lazily_bank_then_hand`
- `tests/test_apartments.py::test_two_weeks_lapsed_evicts_to_impound`
- `tests/test_apartments.py::test_impound_reclaim_10pct_of_list_value_chits_free`
- `tests/test_apartments.py::test_storage_capacity_per_class`
- `tests/test_apartments.py::test_safe_chits_survive_death`
- `tests/test_apartments.py::test_private_core_created_and_removed_with_tenancy`
- `tests/test_apartments.py::test_flat_core_upgrade_2000_chits_tier_3`
- `tests/test_apartments.py::test_lock_upgrade_800_blocks_tier1_passkey`
- `tests/test_apartments.py::test_bed_logout_is_safe`
- `tests/test_apartments.py::test_block_relay_rent_minus_10pct_hook`
- `tests/test_sim_multi.py::test_non_owner_cannot_enter_without_key_owner_can`
- `tests/test_sim_multi.py::test_hacked_item_missing_from_storage_and_log_shown`
- `tests/test_door_menus.py::test_apartment_menu_golden_80x24`

## Acceptance script

1. A grade-5 caller uses the lobby terminal, rents a Terrace Cell (300
   chits leave the bank), walks to the assigned door, presses `E`, is
   inside a small room; opens storage and moves a rifle in.
2. A second caller tries the door: "Locked. Tier 1." and nothing else.
3. The first caller logs out on the bed; on return they are in the
   apartment; the SysOp advances the clock 15 days with the admin CLI;
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
- Keep the private core's storage manifest as a view over `storage[]`
  filtered by `secured == False`; do not copy items.

## Lore review integration

Use game design 8.2 and 6.4 for rental and theft: legal discharge by
work or calendar, protected impound, at most one unsecured unit per
apartment per rolling 24 h, and a resident receipt. Interior permissions
are server-side on every action, including stale menus. Rent discounts
apply to the next invoice once; expiry cannot rewrite a paid invoice.
