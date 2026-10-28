# S25a — S25 engine fixes and accepted canon corrections

**Status:** planned
**Primary model:** Opus · **Reviewer:** automated review, technical lead
**Depends on:** S24 · **Milestone:** M5
**Issue:** https://github.com/Thiesi/Blacksite/issues/77

Split from S25 ([PR #66](https://github.com/Thiesi/Blacksite/pull/66)) by
the owner's decision D-T2 on 2026-10-28
(`docs/plan/03-presentation-integration.md` §14). S25's human layout
approval stays **not granted**; this slice neither needs nor grants it.

## Goal

Land the engine fixes and canon corrections that commissioning the city
exposed, without the 24 maps, so verified work stops going stale while
the geometry is redone (S25c). The owner's decision on each rule change
is in plan §14.2; this slice implements exactly those decisions.

## Scope

Engine, ported from `slice/S25-city-content` at `1224c30` (the code is
unchanged at `a97906b`). The `src/blacksite/server` diff there is about
165 lines:

- route credentials: typed member and story credentials, alternative
  requirements and a content refusal message on the existing travel
  path (game 5.6, entities 1.1);
- walled homes do not freeze unrelated public geometry controls;
- a permanent hazard does not interrupt every harvest attempt;
- a saved position in an expired passage recovers to public ground;
- a physical prop underfoot wins over adjacent telemetry for Interact,
  **with the side effect the automated review found fixed**: a `light`,
  `camera` or salvage marker underfoot must not stop E from jacking in
  at an adjacent terminal;
- a doorstep opens its door despite nearby dropped goods;
- same-spawner NPCs do not target each other; outsiders still do;
- water doubles destination movement time;
- Relay Zero's temporary credential permits only `worker_return`;
- hidden exits: Interact on the actual tile uses them, walking never
  auto-travels;
- the performance and diagnostic changes (content parsing, reflection,
  escape floods, idle work, checkpoint copies, tick and startup
  diagnostics) within unchanged budgets.

Canon, top-down, in this PR before the code that depends on it:

- game design: Gate Nine 60 s every 120 s; water ×2; spawner crews;
  Relay Zero `worker_return`; the NPC stat table (XP 20, respawn 60 s);
  gantry 5 dps; route credentials. Mark Gate Nine, the stat table and
  gantry damage **provisional, tuned at the pacing gate**;
- **game design §5.2 amended**: Undercity sight is set per zone by its
  lighting, using the gazetteer's values (Service 5, Drowned 4, Caverns
  3, Outworks 6, Shaft Foot 10). A carried light raises it to at least
  5. Existing light objects, switched-off lamps, Lowlight Eyes and Flare
  Sticks apply as now. Implement it and test each zone's base sight with
  and without a light;
- gazetteer: the hidden-exit note as S25 rewrote it (unmarked passages;
  Listening, programs and dialogue point them out); the Undercity sight
  lines keep their original values; the Terraces sector at 48 cells if
  S25b needs it for 24 homes.

## Out of scope

- The 24 new maps, vendors, NPC placements, hub map edits and the
  generator (S25b, S25c).
- The presentation-review documents and the S26 to S33 slice-file
  rewrites in #66's doc commits. Bring over only what this scope needs.
- Any rule change not listed in plan §14.2.

## Tests

- The regressions from #66 for each engine fix, rewritten against
  fixture zones or the current shipped maps where they relied on S25's
  new maps. Regressions that need the new maps move to S25b.
- `tests/world/test_route_credentials.py` from #66.
- The jack-in-with-prop-underfoot case above.
- Per-zone Undercity sight with and without a light.
- Root CI on Linux and Windows; the native matrix subset the roadmap's
  definition of done requires; NPC p99 and startup within budget.

## Acceptance

Technical review per `docs/plan/04-technical-review.md`. No human
layout gate applies, because no map changes.
