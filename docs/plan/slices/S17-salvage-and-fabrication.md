# S17 — Salvage and fabrication, Ring-fall salvage nodes, schematics, workshops

**Status:** planned
**Primary model:** Sonnet · **Reviewer:** none
**Depends on:** S12 · **Milestone:** M3
**Issue:** https://github.com/Thiesi/blacksite/issues/17

## Goal

Turn the sky into an economy. Salvage nodes spawn in the Scour rings
with grade distributions per ring, players harvest them, workshops turn
salvage plus a schematic into items with a Fabrication quality roll, and
intact salvage becomes the Custodian arc's contribution currency. The
Ring-fall event that spawns nodes in bulk is S24; this slice ships the
node objects, a baseline trickle spawner, and the whole crafting path.

## Spec references

- `docs/design/00-game-design.md` §8.4 (salvage grades and weight,
  fabrication at workshops with schematic, ±15 % quality roll by skill,
  intact = contribution), §3.3 (Fabrication line), §12 (Ring-fall
  effect: nodes spawn).
- `docs/design/01-entities.md` §1.7 (salvage, schematic blocks), §1.1
  (`workshop` object kind), §3.2 (zone instance `salvage nodes`).
- `docs/world/06-catalog.md` §9 (five grades, weights, base prices,
  yield by ring), §10 (18 schematics with salvage costs, skill minimums,
  sources), §12 (Landing Trade Post buys salvage at +20 %).
- `docs/world/01-gazetteer.md`: `scour-ring-1` to `-4`, workshops at
  Tramyard (Kestrel, public), the Landing (Ferrymen), Old Works
  (Unmoored: rigs and programs only), the Sink (Sable: chemical and
  melee only); Crash Relay +1 grade step in Ring Three (S21 hook).

## Scope

- `server/salvage.py`: `salvage_node` zone object with `grade`, `units`
  (1–6), harvest by `E` (2 s per unit, interruptible), yields
  `slv_<grade>` items by weight; baseline spawner: each Scour ring keeps
  2–6 nodes alive, respawning one every 10 min of elapsed time (lazy
  clock), grade weights per ring: ring 1 hull 90 / optics 10; ring 2
  hull 55 / optics 25 / power 20; ring 3 hull 35 / optics 25 / power 25 /
  compute 15; ring 4 adds intact 5 with the rest scaled. Hazard tile
  `meteor` around fresh nodes is S24's.
- `server/fabrication.py`: `workshop` object kind with a `makes`
  filter (`any`, `rigs_programs`, `chemical_melee`); `MenuView` kind
  `workshop` listing the player's schematics, the salvage required,
  what they carry, and the roll range; fabricate = consume inputs,
  create the output item with quality = 1.0 + (roll in ±0.15 scaled by
  (Fabrication / 100)); skill minimum enforced; Fabrication +1.0 per
  item; XP tier × 15; a 3 s craft channel.
- Schematics as items (`sch_*`, `schematic` class) consumed? No: a
  schematic is permanent once learned; `use` on a schematic item learns
  it (removes the item, adds to `player.schematics[]`), except
  `sch_*` marked `single_use` in content (none in the catalog today).
- Vendor integration (S12): Landing Trade Post buys salvage at +20 %;
  intact is unsellable to vendors (`no_vendor_sale` flag); Ferrymen and
  Old Works vendors sell tier-1 schematics per catalog §10 with standing
  gates via S12's restricted tier.
- Relay hook: `crash_relay_bonus` modifier read from S21 (until then
  false) adds one grade step to Ring Three nodes.
- Persistence: node state per zone (position, grade, units,
  respawn_at) so a restart does not reroll a half-harvested node;
  player schematics list.

## Out of scope

- The Ring-fall event, its bulk spawn, meteor hazards, and NPC
  convergence: S24.
- Contribution delivery of intact salvage: S26.
- Relay ownership effects: S21 (hook only).
- Yard Relay +5 % quality: S21 reads this slice's roll function.
- Scour zone maps themselves: S25 (this slice uses the fixture zone
  and a placeholder `scour-ring-1` stub if S25 has not landed).

## Data and content

- `content/salvage.json` (grades, per-ring weights, spawner
  parameters), schematic rows in `content/items.json`, `workshop`
  objects in the four zone files (S25 adds them; fixture has one).
- Text: harvest lines in voice ("Hull. Still warm."), craft success
  and failure lines.

## Protocol and view models

- `ZoneView.objects` gains `salvage_node` with `grade` and `units`;
  `me.channel {label, remaining}` for harvest and craft channels (shared
  with S15's cut-power channel).
- `MenuView` kind `workshop` rows: schematic, output, inputs (have /
  need), skill min, roll range; action `F` fabricate on cursor row.
- Log lines: harvest per unit, craft result with quality percentage.

## Tests

- `tests/test_salvage.py::test_ring_grade_weights_per_content`
- `tests/test_salvage.py::test_intact_only_ring_4_baseline`
- `tests/test_salvage.py::test_node_respawn_lazy_10min_elapsed`
- `tests/test_salvage.py::test_harvest_2s_per_unit_interruptible`
- `tests/test_salvage.py::test_node_state_survives_restart`
- `tests/test_fabrication.py::test_inputs_consumed_output_created`
- `tests/test_fabrication.py::test_quality_roll_scaled_by_skill_within_15pct`
- `tests/test_fabrication.py::test_skill_min_enforced`
- `tests/test_fabrication.py::test_workshop_filter_rigs_programs_only`
- `tests/test_fabrication.py::test_learn_schematic_removes_item_adds_permanent`
- `tests/test_fabrication.py::test_xp_tier_times_15_and_skill_plus_1`
- `tests/test_vendors.py::test_landing_buys_salvage_plus_20pct`
- `tests/test_vendors.py::test_intact_unsellable`
- `tests/test_sim_multi.py::test_two_sessions_harvest_same_node_units_split_not_duplicated`
- `tests/test_door_menus.py::test_workshop_menu_golden_80x24`

## Acceptance script

1. Caller A walks into the fixture Scour zone (or `scour-ring-1`), finds
   a salvage node, presses `E`, harvests three units of hull with a
   channel bar on the hint line; the inventory shows `slv_hull` ×3 and
   the weight total.
2. A buys `sch_ring_wrench` at the Landing Trade Post, uses it (learns
   it), goes to the Landing workshop, fabricates a Ring Wrench; the log
   reports quality (e.g. "97 %"); the item's stats in the inventory
   detail reflect it.
3. A sells hull at the Landing for 18 chits per unit (15 + 20 %).
4. Caller B tries to fabricate at Old Works with the wrench schematic:
   refused with a log line naming the workshop's filter.

## Definition of done

Roadmap §7, plus: every schematic in the catalog fabricates in a test
with its listed inputs.

## Implementer notes

- Baseline spawner numbers (2–6 nodes, 10 min, per-ring weights) are
  new; put them in `00-game-design.md` §8.4 in this PR.
- Quality applies to the item's main stat only (weapon damage, armour
  main value, implant primary effect); define `main_stat` per class in
  the loader rather than per item.
- Keep harvest and craft channels on the same `channel` mechanism S15
  introduces; if S15 has not merged, introduce it here and S15 reuses.
