# S43 — Tick headroom: cheaper sight and grid rebuilds

**Status:** planned
**Primary model:** Codex · **Reviewer:** automated review, technical lead
**Depends on:** S11, S40 · **Milestone:** service health
**Issue:** https://github.com/Thiesi/Karst41/issues/194

Canon: architecture's performance table allows a tick p99 of 40 ms at 16
players and 6 active zones. S11's acceptance step 6 (tick p99 under
10 ms with every hub zone active) is a tighter gate of its own, and the
owner keeps it. Where this file and canon differ, canon wins.

## Goal

S11's 10 ms tick gate now passes with little room. Single ticks of pure
CPU work land near the line, and a PR with no runtime change can fail
it (#186 at `bf1cb84`: 10.059 ms at 132x50, with no commit and no GC).
This slice wins back headroom by making the most expensive common work
in a tick cheaper. It must not change what any player sees.

## Evidence

From the #194 diagnosis (Codex, comments on #194 and #186):

| Run | p99 at 132x50 (limit 10 ms) | Outcome |
|---|---|---|
| #186 at `bf1cb84` | 10.059 ms | fail, CPU, publishers 5.99 ms |
| main `7597dce`, run 1 | 9.028 ms | pass |
| main `7597dce`, run 2 | 6.200 ms | pass |
| pre-S42 `aef69d9`, run 1 | 8.593 ms | pass |
| pre-S42 `aef69d9`, run 2 | 10.160 ms | fail |

The margin was already thin before S42. A same-runner replay of one
fixed scene ([6739011979]) measured publisher thread CPU per
publication:

- Warm caches: about 2.4 ms. Sight and grid rebuilt: about 6.7 ms.
- With the rebuild forced, `Core.interaction_views` owns the
  `visible_tiles` calls, about 7.5 ms inclusive per publication under
  cProfile, with about 403 `line_of_sight` calls per publication.
  `zone_view.build` then reuses the warm cache, but still rebuilds the
  grid and looks (`looks.masked`, about 2.2 ms profiled).
- Warm, the cost sits in `ViewStore.publish` (delta, candidate sizing
  and JSON encoding, about 1.9 ms profiled) and `interaction_views`
  (about 1.0 ms).
- S42's cover lookup adds about 0.02–0.04 ms per publication. It is not
  the target.

These are profiled figures from one scene and one runner. They name the
work to look at; they don't bound every game state.

## Scope

1. **Measure first.** Using the #194 replay rig, or a test-only
   successor, count how often a tick invalidates sight or grid per zone,
   and what triggers each invalidation. Report it on #194 before
   changing code.
2. **Make the rebuild cheaper, or rarer.** Candidates, in the order the
   evidence suggests:
   - Sight: fewer or cheaper `line_of_sight` calls when the cache is
     invalidated, for example by computing visibility once per viewer
     origin and sharing it between `interaction_views` and
     `zone_view.build`, or by invalidating only what an event actually
     changed.
   - Grid and looks: reuse unchanged rows, as P6a A8 did for terrain.
   - Publication: avoid repeated encoding work in `ViewStore.publish`
     when a body or delta is unchanged.

   Pick from measurement. A candidate that needs a wider redesign comes
   back to #194 as a proposal first.
3. **Show the headroom.** Run the replay before and after on one runner,
   and run the unchanged S11 gate at both sizes on the final head.

## Acceptance

- Every frame and body a client receives is byte-identical. P3's frozen
  hash and case count, the mechanics hash and every golden stay
  unchanged. No golden is rebaselined.
- Game behaviour is unchanged: what an NPC or player can see, target or
  reach is the same in every existing test, plus new tests for the
  cached or shared sight results, including invalidation when a door,
  light or actor changes.
- The replay shows lower mean publisher CPU in the invalidated scenes
  and no regression in the warm ones, with the raw samples kept.
- The full Linux and Windows suites, S04, S05, S10, S11 and S24 pass at
  the final head. S11 runs unchanged: same limit, same nearest-rank
  p99, same sample count.

## Out of scope

- Raising the 10 ms limit, or changing how the p99 or its samples are
  taken. The diagnosis noted that at 99 samples the p99 is the maximum
  and at 100 it is the second-largest. Any proposal to change sampling
  goes to the owner through the technical lead, as a separate decision.
- The commit worker from S40's design note (the owner declined it).
- Reducing workload, content or NPC counts to pass the gate.
- Any change a player can see.

## Interim rule while this slice is open

The owner decided on 2026-11-09: a PR that changes no runtime code may
run S11 once more after a CPU-bound near miss. The failure stays on
record in the PR. A second failure blocks the PR. PRs that change
runtime code get no rerun; their CPU failures block, as before. The
technical lead's standing ruling for commit-stall failures is
unchanged.

[6739011979]: https://github.com/Thiesi/Karst41/issues/194#issuecomment-6739011979
