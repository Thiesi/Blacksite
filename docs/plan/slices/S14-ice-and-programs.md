# S14 — ICE and programs: cores, rooms, encounters, trace, black ICE, the Silt generator

**Status:** planned
**Primary model:** Opus · **Reviewer:** Astra (hacking-model critique before start; balance read after)
**Depends on:** S13, S10 · **Milestone:** M2
**Issue:** https://github.com/Thiesi/blacksite/issues/14

## Goal

Make every core encounter a readable real-time procedure: 35 programs,
23 ICE classes, trace, data lifting, black ICE and seeded Silt. A solo
runner can plan, act, retreat and learn without a dialogue answer quiz.

## Spec references

- Game design sections 5.3, 6.1-6.6 and 17.2-17.3 own all numbers,
  safety, slots, cast timing, acquisition and the canonical rosters.
- `docs/world/03-lattice.md` sections 3-7 supply core layouts, program
  identities, ICE behaviours, Silt bands and the worked route.
- Entity model sections 1.4-1.6, 3.3-3.5 and architecture section 15
  define typed effects, body/presence state and server-owned views.
- Terminal UI sections 3 and 11 define compact hazards and sampling.

## Scope

- Implement `server/lattice/cores.py`, `ice.py`, `programs.py` and
  `silt.py`, with data from `content/cores/`, `ice.json`,
  `programs.json` and `silt.json`. All content is a validated bundle;
  future city objects may appear only in inactive authoring bundles.
- Load the complete named core catalog and private/relay templates.
  Tutorial tier 0 is the single-room, nonlethal exception to ordinary
  tier 1-5 cores. The Shaft alone has two hardware locations.
- Implement all 23 ICE rows, triggers and counter behaviours. Their
  displayed phase, warning, attack and cooldown use simulation ticks.
  Liar may forge untrusted room labels, never controls, costs, warnings,
  journal observations or escape instructions. Hound follows across
  cells; a black hit applies to the single physical body via S10.
- Implement the single 35-program roster in game design section 17.2.
  Shroud is stealth; Umbrella is a damage budget shield. Shield budgets
  persist to exhaustion/jack-out and do not stack. Blackout is acquired
  once per season and then cast normally. Burn's 15 and Blackout's 25
  trace replace the ordinary attack increment. Program effects have
  typed targets; no generic dictionary can execute arbitrary actions.
- Data lifts take 3 s with documented modifiers and trace; use distinct
  kinds for items, schematics, contributions, contract keys and evidence.
  Core-owned data and per-mission keys have separate receipt scopes.
- Implement sector-specific trace thresholds and warnings from Lattice
  section 7. Safe-body protections and the explicit risky NPC-core
  exception remain enforced. Player burning uses physical-body safety,
  contested grade protection and indirect attacker attribution.
- Public jack-out is immediate; other jack-out follows design 6.1's
  bounded interruption. Integrity loss retains the existing shock/death
  path. A residual records an attributed run, never final identity death.
- All rigs may descend. Five seeded bands have 8-20 cells each, authored
  reachable risers, lower sinks only where a lower band exists, and
  visible bypasses for required routes. Deepwater improves performance;
  Passkey never becomes a mandatory purchase to enter the Silt.
- Implement `lat.survey` and `lat.sample`: Listening scan and the
  Chorister's labelled three-phase procedure in design 6.5-6.6. No
  `lat.answer`, hidden good answer, required conversation or exit buff.
  S27 adds optional prose. Sweeper warns before its bounded sweep.
- Same-instance crew descent uses a shared instance ID; remote crew
  beacons reveal nothing. S22 supplies social joining through the entry.
- Update the ROOM panel, trace/integrity bars, warnings, body safety,
  cast progress and escape action; retain a persistent black-risk label
  alongside the brief border flash.

## Out of scope

Control effects and hardware cuts are S15; progression/modifiers are
S16; crew invitations S22; contribution delivery S26; optional talker
prose S27; scheduled Surge variants S24. Their interfaces use the
entity model; no hardcoded provisional answer or divergent catalog.

## Data and protocol

Validate all 35 program IDs, 23 ICE classes, all active cores and the
seeded Silt generator. Add `lat.enter`, `lat.room`, `lat.cast`, `lat.lift`,
`lat.leave`, `lat.descend`, `lat.survey`, `lat.sample` using the existing
intent framing. Include target, cost, stage, warning and escape in views.

## Tests

- Assert every canonical program and ICE numeric row, including tick
  rounding, shield depletion, Blackout reuse and nonadditive trace costs.
- Verify every active core's hardware, rooms, data and control targets;
  exercise the training and Shaft exceptions explicitly.
- Step every ICE trigger/counter, all trace thresholds, black-body
  damage and forced jack-out through the deterministic harness.
- Burn across all body-safety/grade combinations; safe targets cannot
  be injured by remote presence combat or third-party hardware actions.
- Replay the Gate Nine operational route and assert its branch effects.
- Recreate identical Silt graphs from seeds; all bands have a reachable
  escape, any rig can enter and no correct prose answer gates progress.
- Survey/sample a Chorister with and without optional prose; compare
  identical gameplay results. Step a Sweeper warning and escape.
- Golden terminal views at 80x24/132x50 with a wide handle and 16 colours.

## Acceptance script

1. As a fresh Ghost, enter the training core with Pick and Umbrella,
   inspect the costs, defeat training ICE, lift data and leave safely.
2. At an unsafe physical terminal, enter a risky fixture core. A second
   caller sees the same body's black-ICE damage and warning attribution.
3. Let corporate trace trigger a Hound; retreat and jack out. Repeat
   the attempt with a safe body and confirm the exact design exception.
4. Descend solo using a public loan rig. Survey a hidden branch, sample
   a Chorister by its visible labels and evade a warned Sweeper. No lore
   page or typed answer is needed. Repeat using the same seed.
5. Run the documented Gate Nine route with one then two callers; compare
   operational receipts, not an invented old timing transcript.

## Definition of done

Roadmap section 7, complete roster and behaviour coverage, reachable
seeded escapes, and the required model critique and balance review.
Record measured timings and remaining human balance concerns honestly.
