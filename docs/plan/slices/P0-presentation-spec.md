# P0 — Presentation spec decisions into canon

**Status:** done (PR #81; canon text approved by the owner 2026-10-28)
**Primary model:** Opus (presentation lead drafts the design sections; technical lead drafts the engineering contracts) · **Reviewer:** technical lead and presentation lead, each on the other's sections
**Depends on:** owner decisions D1 to D7 (#68, #69) · **Milestone:** presentation track
**Issue:** https://github.com/Thiesi/Blacksite/issues/75

From `docs/plan/03-presentation-integration.md` §7.3, adopted by the
owner on 2026-10-28 (D-T1).

## Goal

Write the presentation direction into canon top-down, so every later P
slice implements a contract instead of a proposal.

## Scope

- `03-terminal-ui.md` §1, 2, 3, 8, 10; `04-assets.md` §3, 9;
  `01-entities.md` zone and NPC records, for the decisions the owner has
  taken on D1 to D7.
- `02-architecture.md` §5.4 view fields, plus the engineering contracts
  from the plan: one layout geometry; the focus contract (with D-T4:
  HERE names a hidden passage only on its tile); log `kind` and
  `speaker`; disclosure rules for looks, charted ground, focus, and
  presented class (D-T8).
- The Auto canon (UI §2 camera, §4 view kinds, §5 keys) if the owner
  has accepted that direction's S-decisions by then. A1 to A6 stay
  tunable defaults until real play (plan §12.3).
- V0-3, if it lands here: game design states that sight covers the
  whole room inside lit pockets.

## Out of scope

D8 beyond the owner's decided default (the place card on entry; strip
modes and the dashboard are decided by PT1), City Map geography (D-T7, its own
proposal), any code.

## Acceptance

The owner approves the canon text. Technical review checks that the
contracts are consistent with each other and with the plan.
