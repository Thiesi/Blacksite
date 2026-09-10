# S16 — Progression: XP, grades, grade points, skill-by-use, implants and surgery, drugs and dependencies

**Status:** planned
**Primary model:** Opus · **Reviewer:** Astra or Fable (balance read of the numbers against the catalog before merge, per roadmap §4)
**Depends on:** S10, S12 · **Milestone:** M3
**Issue:** https://github.com/Thiesi/blacksite/issues/16

## Goal

Make characters grow. XP from every source in the design doc, grades 1
to 30 with grade points and +1 Vitals, twelve skill lines that rise by
use and by spending, attributes derived from skill groups, implants with
slots, tolerance and surgery at two kinds of clinic, resonance implants
and rig implants with their gates, and drugs with effects, crashes, and
dependency clocks. After this slice the Ninety-Day milestone exists and
the catalog's implant and drug tables do what they say.

## Spec references

- `docs/design/00-game-design.md` §3.1 (tolerance = Vitals / 10, min 4;
  native rig 0 tolerance; evasion Nerve / 3; carry), §3.2 (archetype
  uniques: Hardline +2 tolerance, Operator two drone slots), §3.3 (12
  lines, 10 skill points → +1 attribute; Vitals only by grade and
  implants), §3.4 (grades 1–30, 3 grade points and +1 Vitals per grade,
  grade 5 = Ninety-Day; XP sources), §8.5 (slots, one per slot except
  arms ×2, Sablier 2 % failure at list, black clinic 60 % and 15 %,
  resonance needs Cantor + Choir +20), §8.6 (drugs: effect, duration,
  crash for half, three doses in window = dependency, detox), §5.3
  (skill terms in to-hit and damage).
- `docs/design/01-entities.md` §1.7 (implant/resonance/rig/drug
  blocks), §2.1 (skills, grade, xp, implants, drugs_active,
  dependencies, legal_at).
- `docs/design/03-terminal-ui.md` §4 (character sheet, skills menu).
- `docs/world/06-catalog.md` §3 (31 implants incl. rig and resonance
  with effects), §4 (hymns/dissonance tiers gated by implants), §6 (11
  drugs), §14 (price ladder: grade 10 at ~4 h; tier 3 at grade 18+).

## Scope

- `server/progression.py`: XP ledger with sources `combat` (opponent
  grade scaled: base 20 × (1 + (their grade − yours) / 10), min 5),
  `run` (core tier × 40 on first data lift per core per day), `contract`
  (from S19 reward), `relay` (S21: capture 100, hold 10 per 10 min),
  `craft` (S17: tier × 15), `discovery` (zone 25, cell 5, first visit
  per character), `contribution` (S26). Grade thresholds: XP for grade
  n = 100 × n × (n + 1) / 2 cumulative (grade 5 at 1 500, grade 10 at
  5 500, grade 30 at 46 500); a test asserts grade 10 is reachable in
  the catalog's four-hour assumption at the fixture's earning rates.
- Grade-up: +3 grade points, +1 Vitals (recompute health max, keep
  current health ratio), grade title from a `content/grades.json` list
  (Wake, Ninety-Day, Resident, Citizen, Notable, Name, then six more
  in voice), `legal_at` set at grade 5, log line and toast.
- `server/skills.py`: twelve lines 0–100; skill-by-use hooks: each
  successful weapon hit +0.2 to the weapon's line, melee hit +0.3,
  damage taken with armour worn +0.1 Armour, stealth stance while an
  enemy is in sight +0.05/s Stealth, drone command +0.1 Drones, cell
  move +0.05 Lattice, program cast +0.15 Programs, fabrication +1.0 per
  item (S17), hymn/dissonance cast +0.15, hidden cell found +0.5
  Listening. Grade points spend 1 point = +1 skill in any line (menu).
  Attribute recompute: every 10 points summed across a group's three
  lines = +1 to that attribute above the archetype base; Vitals excluded.
- Hooks consumed by other slices: to-hit `+ skill / 2`, damage
  `× (1 + skill / 200)` (S10 reads via `player.skill(line)`), Programs
  scaling (S14), Fabrication quality (S17), Listening check for hidden
  cells (S13: chance = Listening / 100 per adjacent hidden cell per
  10 s).
- `server/implants.py`: slots `head, eyes, spine, arms×2, torso, legs,
  rig`; tolerance = Vitals / 10 (min 4) + Hardline 2 + temporary Chrome
  +1; installing checks slot free, tolerance, `requires` (Cantor and
  Choir standing +20 for resonance; Cortex 20 for rig implants; Hardline
  for Heavy Mount); effects applied as modifiers via a single
  `Modifiers` aggregator (attribute deltas, derived deltas, flags such
  as `secured_slots +1`, `sight +3 dark`, `cooldown −10 %`) that S10,
  S12, S13 read instead of reaching into implant lists.
- Surgery: `vendor` objects with `clinic: sablier` (list price + 20 %,
  2 % failure) or `clinic: black` (60 % list, 15 % failure); failure
  destroys the item and applies 30 s of shock 100; removal at any clinic
  returns the item at 50 % quality loss. Ghost native rig: present at
  creation at 0 tolerance, replaced when a rig implant is installed.
- Chrome: temporary +1 tolerance for 20 min; an implant installed under
  it is ejected (item kept, 30 s shock) when it wears off unless Vitals
  has since risen.
- `server/drugs.py`: `use` intent for drug items applies effect for
  `duration`, then crash for `duration / 2`; dose log per substance;
  three doses inside `window` → dependency (crash permanent) until detox
  at a Sablier clinic (400 chits, 10 min during which the player is
  safe-pocketed at the clinic and cannot act); Detox Gland halves crash
  and window; Ration Bar removes the Ring-dust crash; Lullaby, Deepwater
  and Static Lattice-side effects route through S13/S14 modifiers.
- Character sheet `MenuView` (S07 created it) gains: grade and title,
  XP to next, grade points, twelve skills with bars, attributes with
  base and bonus, implants by slot with tolerance used/total, active
  effects and crashes with timers, dependencies.
- Persistence: skills, grade, xp, implants map, drugs_active,
  dependencies, dose log (last 10 per substance); flush on grade-up,
  install, and dose.

## Out of scope

- Hymn and dissonance ability execution: S10 (they exist there; this
  slice gates tiers by implant).
- Drone slots and drone behaviour: S11 (this slice exposes
  `drone_slots` as a modifier: Operator 2, Drone Uplink +1 or 1).
- Fabrication rolls: S17 (reads Fabrication skill from here).
- Relay and contribution XP amounts are defined here and paid by S21
  and S26.
- Leaderboard by grade: S26.

## Data and content

- `content/grades.json` (30 titles, thresholds computed, asserted by
  test), `content/items.json` implant, resonance, rig, and drug rows
  already loaded by S12 gain behaviour here; `content/skills.json`
  (line names, groups, use-XP rates as above).
- Text: grade-up lines in voice (30), surgery success/failure lines
  (Sablier and black clinic variants), detox text.

## Protocol and view models

- `MenuView` kinds `character`, `skills` (spend grade points; cursor
  row + `+` action), `clinic` (install/remove with price, failure
  chance shown as a percentage, and a confirmation keystroke on the
  chosen row), `detox`.
- `ZoneView.me.effects[]` gains drug effects and crashes with remaining
  seconds; `me.grade`.
- Toasts on grade-up; log lines on dependency and on crash start.

## Tests

- `tests/test_xp.py::test_grade_thresholds_formula`
- `tests/test_xp.py::test_grade_10_reachable_in_four_fixture_hours`
- `tests/test_xp.py::test_combat_xp_scales_with_grade_gap_min_5`
- `tests/test_xp.py::test_discovery_xp_once_per_character`
- `tests/test_grades.py::test_grade_up_gives_3_points_and_1_vitals`
- `tests/test_grades.py::test_legal_at_set_on_grade_5`
- `tests/test_skills.py::test_use_rates_per_line`
- `tests/test_skills.py::test_ten_points_across_group_raises_attribute`
- `tests/test_skills.py::test_vitals_never_from_skills`
- `tests/test_skills.py::test_listening_check_chance_per_10s`
- `tests/test_implants.py::test_tolerance_vitals_over_10_min_4_hardline_plus_2`
- `tests/test_implants.py::test_ghost_native_rig_zero_tolerance_replaced_by_implant`
- `tests/test_implants.py::test_arms_two_others_one_per_slot`
- `tests/test_implants.py::test_resonance_requires_cantor_and_choir_20`
- `tests/test_implants.py::test_sablier_2pct_black_15pct_failure_seeded`
- `tests/test_implants.py::test_failure_destroys_item_shock_100_30s`
- `tests/test_implants.py::test_chrome_ejects_implant_unless_vitals_grew`
- `tests/test_implants.py::test_modifier_aggregator_secured_slots_and_cooldown`
- `tests/test_drugs.py::test_effect_then_crash_half_duration`
- `tests/test_drugs.py::test_three_doses_in_window_dependency`
- `tests/test_drugs.py::test_detox_400_chits_10min_safe_pocket`
- `tests/test_drugs.py::test_detox_gland_halves_crash_and_window`
- `tests/test_sim_multi.py::test_implant_cooldown_modifier_visible_in_fight_between_sessions`
- `tests/test_door_menus.py::test_character_sheet_golden_80x24`

## Acceptance script

1. A caller at grade 4 kills fixture drones until the grade-up toast
   for Ninety-Day appears; the character sheet shows +3 points and the
   new health maximum.
2. Spend 3 points on Kinetic in the skills menu; the sheet shows the
   line at +3 and, after enough spending, Frame +1.
3. Buy `imp_halvard_reflex_arm` at the Spire concourse, install at a
   Sablier clinic: the clinic menu shows price, 2 %, and tolerance used
   2/4; the weapon cooldown in the side panel reads 10 % lower.
4. Take Redline three times within 20 minutes: the third dose logs a
   dependency; the crash never ends until a detox at Vatside, during
   which the caller cannot leave the clinic pocket for 10 minutes.

## Definition of done

Roadmap §7, plus: every implant and drug row in the catalog has a
behaviour or is labelled "no effect yet" in the detail pane, and the
balance reviewer has signed off on the XP curve in the PR.

## Implementer notes

- The XP-per-grade formula and the per-use skill rates are **new
  numbers not in the design doc**; add them to `00-game-design.md`
  §3.3–§3.4 in this PR (roadmap §1 rule).
- The catalog's implant table says tolerance minimum 3; the design doc
  says 4 and wins. Fix the catalog line in this PR.
- All implant and drug effects go through the `Modifiers` aggregator;
  no other slice may query the implant map directly, or S24's event
  modifiers will have nowhere to compose.
- Detox pockets the player at the clinic: reuse S08's pocket regions,
  do not invent a new safety state.
