# S14 — ICE and programs: cores, rooms, encounters, trace, black ICE, the Silt generator

**Status:** planned
**Primary model:** Opus · **Reviewer:** Astra (hacking-model critique before start; balance read after)
**Depends on:** S13 · **Milestone:** M2
**Issue:** (filled in when filed)

## Goal

Make the Lattice dangerous and rewarding: cores as room graphs behind
entrance cells, the 23 ICE classes with their triggers and behaviours,
the program catalog loaded into rig slots with real-time casts and
cooldowns, trace with its per-sector consequences, black ICE that hurts
the body, data lifting, runner-versus-runner burning, and the seeded
Silt descent with residuals. Controls and their meatspace effects are
S15.

## Spec references

- `docs/design/00-game-design.md` §6.2 (cores 3–12 rooms, tiers 1–5,
  hardware location), §6.3 (rig slots 3–7, program classes, cast
  0.5–2 s, trace outcomes at 100 by sector type, black ICE meat damage,
  lift/flip 3 s), §6.5 (the Silt: seeded, residuals, no trace, no crew
  finding), §5.4 (down/dead path for black-ICE deaths: S10's).
- `docs/design/01-entities.md` §1.4 (core), §1.5 (ICE template), §1.6
  (program template), §2.9 (core state), §3.4 (core instance), §3.5
  (Silt instance).
- `docs/design/02-architecture.md` §5.4 `LatticeView.room`, §6.1
  (deterministic RNG per sector), §10 (multi-session scenarios).
- `docs/design/03-terminal-ui.md` §3 (ROOM panel, black ICE border
  flash), §5.1 (keys 1–7 cast rig slot programs).
- `docs/world/03-lattice.md` §3 (core catalog: 28 named cores plus two
  templates, rooms, data, ICE rosters), §4 (ICE table), §5 (program
  catalog), §6 (Silt bands, residuals, contributions), §7 (trace table
  and consequences by sector type, worked run).
- `docs/world/06-catalog.md` §5 (program prices and the `prg_ow_*`
  IDs; see implementer notes on the conflict).

## Scope

- `server/lattice/cores.py`: load `content/cores/<id>.json` for every
  core in `03-lattice.md` §3 (owner, tier, hardware zone and object,
  rooms with neighbours, data specs with respawn, ICE roster, lore); the
  private-core and relay-uplink templates instantiate per apartment
  (S18) and per relay (S21). `CoreInstance` per `01-entities.md` §3.4.
- Entering a core: from its entrance cell, `lat.enter`; the runner is
  in room 1; `LatticeView.room` shows data, controls (rendered but inert
  until S15), ICE with integrity bars.
- `server/lattice/ice.py`: `content/ice.json` with all 23 classes and
  their numbers from §4; triggers `entry`, `touch`, `trace N`,
  `passage`, `always`; behaviours `static`, `roaming` (Mastiff loops
  rooms), `hunter` (Hound follows across cells for 3 min); black flag
  with `+meat` damage applied to the meat actor's health through S10's
  damage path (type `dissonance`-immune, armour ignored); class-specific
  effects listed in the table (Tripwire fires three times then +10
  trace/s, Ticker +1 trace/s, Bluecoat pin 4 s then Warden dispatch,
  Sandman strips stealth and doubles loader casts, Hornets 5×4, Liar
  fake rooms, Tar ×2 cast, Lockstep 10 s open per 60 s, Shiv reports the
  body's location to the owner faction, Suture heals 5/s, Cantillation
  scaled by Resonance, Mirror reflect then 5 s rest, Kiln, Blackglass,
  Silt classes Drift, Undertow, Chorister (dialogue hook, S27; until
  then a fixed two-answer prompt), Shade copies last cast, Sweeper).
- `server/lattice/programs.py`: `content/programs.json` with the 30
  programs of §5 (attack, shield, decoy, loader, key, stealth, utility)
  with tier, slots, cast, cooldown, effect; casting from rig slot keys
  1–7; cast timers and cooldowns on the sector tick; `Programs` skill
  scales attack damage by (1 + skill / 200) (S16 supplies the skill;
  read 0 until then).
- Data lifting (`lat.lift`, 3 s, −25 % with Ledger, Glasshouse must be
  broken first): chits, salvage data (sellable item), contribution
  (item tagged for S26), contract keys (S19), schematics (S17), text
  assets (opens `TextView`). Data respawns per spec.
- Trace: per-second by tier (+0.5/+1/+1.5/+2/+3), attack cast +5, lift
  +10, flip +10 (S15), burn +15 in civic/corporate, Tripwire +10/s,
  Ticker +1/s, Liar +15, Blackout +25; decoys per program; reset on
  jack-out; never rises in public cells, the Silt, or under Nobody.
  Consequences at 50 and 100 by sector type (civic, corporate, black,
  street) exactly per §7: Bluecoat wake, registry entry 10 min, all ICE
  wake, owner told, zone log line, Warden dispatch to body tile with 10
  min heat (S11 Wardens; S20 heat), Hound spawn, owner told exactly by
  name and sitrep for 5 min, forced jack-out with shock 60 and core lock
  5 min.
- Forced jack-out: integrity 0 → shock 100 and jack-out; if the last hit
  was black, meat damage already taken stays; death in the Silt leaves a
  fragment with the runner's name for the next season's band 1.
- Burning: `prg_ow_burn` / Burn against a presence in the same cell;
  integrity damage; +15 trace in civic and corporate sectors.
- `server/lattice/silt.py`: seeded generator (season, sector, nonce;
  crews share the nonce, S22) producing five bands of 8–20 cells with
  1–3 sinks down and one riser up, contents per §6.1's band table,
  residual fragments (text), Shades, one Sweeper on a loop in band 4,
  contribution data in bands 3–5; hidden sinks in bands 4–5; no trace.
  Descent requires a rig allowing it (Deepwater rig or Masterkey; see
  notes) and happens from the sector's descent cell.
- Ninety-Nine's Drop is a normal tier-2 core in Old Works whose dialogue
  is S27; here it holds its data and ICE only.
- `door/views/lattice.py`: ROOM panel, ICE integrity bars, cast progress
  on the hint line, red border flash for one frame on a black hit at
  every tier, trace threshold marks at 50 and 100.

## Out of scope

- Controls flipping meatspace objects, hardware, cut-power, core
  ownership by relay, private-core theft: S15.
- Warden NPC behaviour and heat mechanics: S11, S20.
- Skills (Programs, Listening) and rig implants: S16.
- Chorister and Ninety-Nine dialogue: S27.
- Contribution delivery and the Chronicle dead list: S26.
- Choir Surge mutation of ICE: S24.

## Data and content

- `content/cores/*.json` (30 files), `content/ice.json`,
  `content/programs.json`, `content/silt.json` (band table and
  generator parameters), `content/text/silt-fragment-*.md` (from
  `08-found-texts.md` Silt fragments and residual lines).
- Fixture world: one tier-1 core with Tripwire and Ticker, one tier-3
  corporate core with Glasshouse, Mirror, Kiln, and a Hound trigger.

## Protocol and view models

- `LatticeView.room`: `{core, tier, room, neighbours[], data [{id,
  kind, taken, shielded}], controls [{id, label, state}], ice [{id,
  name, class, integrity, max, state, black}]}`; `me.cast {program,
  remaining}`.
- Intents: `lat.enter`, `lat.room <id>`, `lat.cast <slot> [target]`,
  `lat.lift <data>`, `lat.leave`, `lat.descend`, `lat.answer <n>`
  (Chorister stub).
- Log lines for every trace threshold crossing, every ICE trigger, every
  hit with the numbers, lift complete, forced jack-out with the reason.

## Tests

- `tests/test_cores_content.py::test_all_cores_load_room_counts_3_to_12`
- `tests/test_cores_content.py::test_every_hardware_zone_object_exists`
- `tests/test_ice_content.py::test_23_classes_numbers_match_doc_table`
- `tests/test_programs_content.py::test_30_programs_numbers_match_doc`
- `tests/test_trace.py::test_per_second_by_tier`
- `tests/test_trace.py::test_public_cell_and_silt_never_rise`
- `tests/test_trace.py::test_nobody_freezes_trace_5s`
- `tests/test_trace.py::test_civic_100_dispatches_wardens_to_body_tile`
- `tests/test_trace.py::test_corporate_100_spawns_hound_follows_3min`
- `tests/test_trace.py::test_street_100_forces_jack_out_shock_60_lock_5min`
- `tests/test_trace.py::test_black_100_tells_owner_faction_by_name_5min`
- `tests/test_ice.py::test_tripwire_three_shots_then_trace`
- `tests/test_ice.py::test_glasshouse_blocks_lift_until_broken`
- `tests/test_ice.py::test_mirror_reflects_then_rests_5s`
- `tests/test_ice.py::test_kiln_meat_damage_bypasses_armour`
- `tests/test_ice.py::test_suture_heals_other_ice_5_per_s`
- `tests/test_ice.py::test_cantillation_zero_damage_to_cantor`
- `tests/test_ice.py::test_shade_copies_last_cast`
- `tests/test_programs.py::test_cast_time_and_cooldown_on_tick`
- `tests/test_programs.py::test_umbrella_absorbs_15_then_gone`
- `tests/test_programs.py::test_blackout_120_then_trace_plus_25_once_per_season`
- `tests/test_programs.py::test_lift_3s_ledger_minus_25pct`
- `tests/test_silt.py::test_same_seed_same_graph`
- `tests/test_silt.py::test_five_bands_8_to_20_cells_one_riser_each`
- `tests/test_silt.py::test_cannot_skip_band`
- `tests/test_silt.py::test_death_leaves_named_fragment_for_next_season`
- `tests/test_sim_multi.py::test_two_runners_burn_each_other_trace_only_in_civic`
- `tests/test_sim_multi.py::test_black_ice_hit_reaches_meat_body_seen_by_other_session`
- `tests/test_sim_multi.py::test_worked_run_gatehouse_east_matches_doc_numbers`
- `tests/test_door_lattice.py::test_room_panel_golden_80x24`
- `tests/test_door_lattice.py::test_black_hit_border_flash_16_colour`

## Acceptance script

1. Caller A (Ghost) jacks in at an Old Works terminal, enters the
   fixture or the Foundry core, sees Tripwire fire three times and the
   log show 8-ish damage each; casts Pick (`1`) until it dies; lifts a
   data item and sees TRACE tick up.
2. Caller B, in meatspace next to A's body, sees A's health drop when
   A touches Kiln-guarded data in a corporate core; A's screen border
   flashes red.
3. A lets trace reach 100 in a corporate core: a Hound appears and
   follows A into the next cell; A jacks out; integrity recovers 5/s.
4. A descends from a sector's descent cell with a Deepwater rig or
   Masterkey: five bands, a fragment text in band 1, the Sweeper visible
   in band 4; the same seed replays identically after a server restart.

## Definition of done

Roadmap §7, plus: the worked run in `03-lattice.md` §7.1 reproduces in a
test to the stated numbers, and every ICE class has at least one test.

## Implementer notes

- **Program catalog conflict.** `03-lattice.md` §5 lists 30 programs
  (tiers 1–5, e.g. Pick/Chisel/Drill/Umbrella/Smoke/Caffeine/Skeleton/
  Sneakers/Compass) while `06-catalog.md` §5 lists 16 `prg_ow_*` IDs with
  different numbers (and its "Shroud" is a shield, whereas the Lattice
  doc's Shroud is stealth). Build to `03-lattice.md` (the Lattice
  document is the higher canon for programs per AGENTS.md §2, item 4
  ordering within expansions being by subject); assign IDs
  `prg_<name>` and flag the catalog for reconciliation in the PR. Prices
  come from the catalog where a name matches, else tier × 400.
- Silt descent gating is not stated in the design doc: the catalog says
  the Deepwater rig allows descent and Masterkey opens descent cells.
  Implement both and note the gap.
- The Chorister's question must not require S27: use a two-line stub
  prompt with a deterministic "good" answer index from the seed.
- Hound follow across cells must survive the runner leaving the core;
  it is the only ICE that exists outside a core.
- Meat damage from black ICE goes through S10's `apply_damage` with a
  source of `black_ice` so death attribution and corpse rules work.
