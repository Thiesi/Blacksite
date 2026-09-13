# S12 — Items, inventory, equipment, vendors, bank, currency

**Status:** planned
**Primary model:** Sonnet · **Reviewer:** Opus (data model review before merge)
**Depends on:** S07 · **Milestone:** M1
**Issue:** https://github.com/Thiesi/blacksite/issues/12

## Goal

Give characters things: the item template table from the catalog, item
instances with ownership and quality, the inventory and equipment model
with secured slots and carry weight, faction and district vendors with
standing-modified prices and hourly buy-back budgets, and the Kestrel
bank. After this slice a Wake can buy a rifle in Tramyard, equip it,
bank chits, and die without losing what is banked or secured.

## Spec references

- `docs/design/00-game-design.md` §3.1 (carry = Frame / 2 kg), §5.4
  (secured slots, corpse cache rule is S10's), §8.1 (chits, banked
  chits), §8.2 (vendors: −20 % at +80, +30 % at −50, buy-back budget),
  §14 (one market action per second is S23's; item rate limits here).
- `docs/design/01-entities.md` §1.7 (item template), §2.1 (player
  inventory, equipment, chits), §2.2 (item instance).
- `docs/design/02-architecture.md` §5.4 `MenuView`, §6.2 (flush on
  trade and item transfer).
- `docs/design/03-terminal-ui.md` §4 (menus: inventory, equipment,
  vendor, bank).
- `docs/world/06-catalog.md` §1–§2, §5 (portable rigs only), §7, §8, §9,
  §11 (starter kit), §12 (vendor inventories), §14 (price ladder).

## Scope

- `src/blacksite/content/items.json`: every row of the catalog's
  weapons, ammunition, armour, consumables, drones (as items; drone
  behaviour is S11/S16), salvage, portable rigs, passes, keys, and the
  `arm_wake_coverall`. Implants, resonance, drugs, schematics, and
  programs are loaded by the same loader but their behaviour is S16, S17,
  S14. The loader (`server/content/items.py`) validates class-specific
  blocks per `01-entities.md` §1.7.
- `server/items.py`: `ItemInstance` creation with quality 0.85–1.15
  (fabrication sets it in S17; vendor items are always 1.0), stacking by
  `stack_max`, weight totals, `secured` flag with three default secured
  slots per player (implant bonuses in S16).
- `server/inventory.py`: add, remove, move to secured, split stack,
  drop to floor (creates a world cache object at the tile that expires
  in 5 min; S10 reuses it for corpse caches), pick up, equip/unequip by
  slot (`weapon_main`, `weapon_side`, `melee`, `head`, `torso`, `legs`,
  `arms`, quick slots 1–5). Equipping enforces archetype `heavy` rule
  (Hardline only) and weight: over carry weight, movement tile time
  doubles (hook for S06's mover).
- `server/vendors.py`: vendor objects from `content/vendors.json`
  (`04-assets.md` table) with inventory IDs, price tier (`list`,
  `member`, `restricted` with a standing gate), sell price =
  base × quality × standing modifier (linear between −50 → +30 % and
  +80 → −20 %, clamped), buy-back at 40 % of list within an hourly
  budget of 2 000 chits per vendor refilled on the hour, ammunition
  auto-stocked for the weapons sold.
- `server/bank.py`: Kestrel branch objects (`bank` object kind) in
  `core-tram-hub`, `tramyard-market`, and every faction hall; deposit,
  withdraw, balance; apartment safes reuse this in S18. Banked chits are
  a separate column and never touched by S10's clone debt.
- Starter kit issuance at the end of the Wake (S07 calls
  `grant_starter_kit(player)`), per catalog §11 including archetype
  extras (all starters learn Pick and Umbrella, executable in S14; Cantor First Ear
  and Operator mule are granted as items and take effect in S16/S11).
- `door/` renders `MenuView` kinds `inventory`, `equipment`, `vendor`,
  `bank`, `cache`; all server-driven per `03-terminal-ui.md` §4, with
  `Esc`/`B` leaving without side effects.
- Intents: `inv.open`, `inv.equip`, `inv.unequip`, `inv.secure`,
  `inv.drop`, `inv.pickup`, `inv.use` (consumables: instant, 10 s cooldown
  per class, effect table from catalog §7), `vendor.buy`, `vendor.sell`,
  `bank.deposit`, `bank.withdraw`, each validated server-side.
- Persistence: item instances table, player inventory/equipment/chits
  columns, vendor budget table with refill timestamp; immediate flush on
  every transfer per architecture §6.2.

## Out of scope

- Corpse caches on death and loot timing: S10.
- Implant install, tolerance, drug effects, dependencies: S16.
- Salvage nodes, fabrication, schematics behaviour: S17.
- Market board and bounties: S23.
- Apartment storage and safes: S18.
- Drone behaviour: S11 (NPC actors) and S16 (Operator slots).

## Data and content

- `content/items.json` (all catalog rows), `content/vendors.json` (the
  18 vendor inventories with zone and object anchors from the gazetteer),
  `content/tiles.json` gains nothing here.
- Fixture world (S02) gains one vendor and one bank object.
- Text: item descriptions from the catalog as `description` fields.

## Protocol and view models

- `MenuView` rows for inventory: name, qty, weight, secured flag,
  equipped slot; detail pane shows the catalog description and stats.
- Vendor `MenuView`: two tabs (buy, sell) as `page`, price column shows
  the standing-modified price and the budget remaining on sell.
- `me.chits` in `ZoneView` is chits on hand; the character sheet (S07)
  adds banked.
- Log lines for buy, sell, equip, drop with the channel `sys`.

## Tests

- `tests/test_items_content.py::test_every_catalog_id_loads`
- `tests/test_items_content.py::test_class_blocks_validate`
- `tests/test_inventory.py::test_carry_weight_frame_half`
- `tests/test_inventory.py::test_overweight_doubles_tile_time`
- `tests/test_inventory.py::test_three_default_secured_slots`
- `tests/test_inventory.py::test_heavy_requires_hardline`
- `tests/test_inventory.py::test_stack_split_and_merge_respect_stack_max`
- `tests/test_inventory.py::test_drop_creates_cache_expiring_300s`
- `tests/test_vendors.py::test_price_modifier_plus80_minus20pct`
- `tests/test_vendors.py::test_price_modifier_minus50_plus30pct`
- `tests/test_vendors.py::test_buyback_40pct_within_budget`
- `tests/test_vendors.py::test_budget_refills_on_hour`
- `tests/test_vendors.py::test_restricted_tier_gate_by_standing`
- `tests/test_vendors.py::test_selling_40_rifles_exhausts_budget`
- `tests/test_bank.py::test_deposit_withdraw_never_negative`
- `tests/test_bank.py::test_banked_column_separate_from_hand`
- `tests/test_consumables.py::test_class_cooldown_10s`
- `tests/test_starter_kit.py::test_each_archetype_kit`
- `tests/test_sim_multi.py::test_two_sessions_pick_up_same_cache_only_one_gets_item`
- `tests/test_persistence.py::test_item_transfer_flushes_immediately`
- `tests/test_door_menus.py::test_inventory_menu_80x24_golden`

## Acceptance script

1. Two callers enter the door on a NetBBS node at 80×24; both finish or
   skip the Wake.
2. Caller A walks to the Tramyard Depot Counter, presses `E`, sees the
   vendor menu with prices, buys `wpn_halvard_hv7` and a stack of
   `ammo_9x`, equips it from the inventory menu; the side panel shows
   the new weapon on target.
3. Caller A sells the starter baton; the sell price is 40 % of list and
   the budget line drops.
4. Caller A drops a med patch; caller B walks over and picks it up
   within 5 minutes; A's inventory no longer shows it.
5. Caller A banks 100 chits at the tram-hub branch; the character
   sheet shows hand and bank separately.
6. `Esc` from every menu returns to the zone view with nothing changed.

## Definition of done

Roadmap §7, plus: every catalog ID loads, the four archetype starter
kits match catalog §11, and no vendor sells an item whose class
behaviour is unimplemented without a "not yet usable" label in the
detail pane.

## Implementer notes

- The catalog still says tolerance "minimum 3" in §3; the design doc
  is the source and says 4. Do not encode tolerance here at all; S16
  owns it.
- Vendor budgets are per vendor object, not per template; two Sablier
  clinics have two budgets.
- Prices are integers; round the standing modifier to nearest chit,
  minimum 1.
- Keep `items.json` in catalog order so diffs against the doc are
  reviewable.
- The `use` intent for drugs must exist but route to a stub that logs
  "S16" until that slice lands; do not implement effects here.

## Lore review integration

Main design 8.2/17.1 owns resale and stock; essential supplies have no
finite buy-back budget dependency. Recovery loan items and service-job
supplies are bound, cannot be traded/cached/crafted and use receipt-based
replacement. Store learned programs and schematics separately from loose
inventory. Public terminal loan rigs support every archetype (S13).
