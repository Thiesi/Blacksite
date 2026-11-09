# S43 step 1: invalidation counts before runtime changes

Base `282caa29d84cc7d398715abf2ee88806a2c5a852`. Runtime tree
`3cc647ceb05a066feabda4424450d1eb7771c7fa`. Implementer: Codex (GPT-6).
No runtime implementation, timing-gate change or golden update is in
this measurement checkpoint.

## Method

`scripts/measure_s43_invalidations.py` is a test-only successor to the
frozen publisher rig in issue #194, comment 6739011979. The method was
declared in comment 6743551898 before measurement.

Twenty independent scenes use the production Core and ManualClock:
one caller per hub, stationary or ordinary 5 Hz right/left input. All
ten zones are active, as in S11's activation setup. Each scene has ten
warmup ticks followed by fifty measured ticks. Sodium starts at (16,5),
matching the earlier replay; other hubs use their available spawn.
World seeds are the harness's sorted-zone ordinal seeds. NPCs retain
their ordinary simulation, counts and movement. Actual successful
moves are counted, including one blocked input in the Tin Halo.

A test-only function-call observer counts queries, misses and consumers.
Temporary attribute observers count explicit cache clears and zone
revision writes, preserving the original assignments. Each observed
scene is paired with a fresh unobserved execution. All twenty encoded
frame streams, encoded body streams and actor traces match their
controls exactly, without normalization. The observers are restored
after each scene.

This is a bounded count experiment, not a CPU benchmark, native S11 run
or acceptance pass. No sockets, database access, sleeps or wall timers
are involved. HeadlessServer's zero timing entries are not gate data.
Raw counts, per-tick events and output fingerprints are retained in
[invalidations-before.json.gz](captures/s43/invalidations-before.json.gz).

## Counts

Each stationary fifty-tick window has 100 sight queries and fifty grid
queries, with **zero sight, grid or look rebuilds**. The table below is
the corresponding fifty-tick walking window. The sight and grid rebuild
counts are equal; every miss is attributed to a changed viewer origin.

| Viewer zone | Moves | Sight/grid rebuilds | Look rebuilds | Sight rays |
|---|---:|---:|---:|---:|
| core-plaza | 25 | 25 | 25 | 5295 |
| core-precinct | 25 | 25 | 0 | 5295 |
| core-tram-hub | 25 | 25 | 0 | 5295 |
| sodium-row | 25 | 25 | 25 | 10075 |
| sodium-tin-halo | 24 | 24 | 0 | 2628 |
| terraces-blocks | 25 | 25 | 0 | 4707 |
| terraces-lobby | 25 | 25 | 0 | 4144 |
| vatside-clinics | 25 | 25 | 25 | 4907 |
| vatside-vat-row | 25 | 25 | 0 | 3556 |
| vatside-wake-hall | 25 | 25 | 0 | 6156 |

Across 1,000 observed ticks: 2,000 sight queries, 249 sight misses,
1,000 grid queries, 249 grid rebuilds, 75 look rebuilds and 52,058 sight
rays. Source call order places the first query in
`Core.interaction_views`; `zone_view.build` then uses the same actor
cache. This agrees with the earlier caller-edge attribution. The count
rig records consumers and misses separately, rather than presenting
their ownership as a new profiler result. Sodium has 403 rays per
rebuild, matching the earlier fixed-scene diagnosis.

All ten active zones' events are retained for every scene, not only the
viewer zone. Ordinary NPC/combat revision writes do not invalidate the
stationary viewer's sight/grid keys in these windows. There are no
explicit sight/grid clears or geometry revisions during measurement.
These statements describe the declared windows, not all gameplay.

## Trigger inventory from source

- Sight key: zone ID, viewer position, effective radius and geometry
  revision. `World.enter` also clears the entering actor's sight key.
- Door changes go through `ZoneInstance.set_door`; geometry layers go
  through `ZoneInstance.compose`. Both advance the geometry revision
  when the effective geometry changes. `Interlock.compose` advances it
  when a controlled object's state changes, including lights.
- Effective radius includes night settings, local light state, actor
  sight modifiers and dark-sight effects. A radius change misses the
  sight cache even without an explicit clear.
- Grid key: the sight key, viewport rectangle and scouted tile set.
  `ZoneSimulation.reset_view` explicitly clears it on its reset paths.
- Looks key: template/look identity, grid revision and chart key. Thus
  a grid rebuild regenerates masked looks in the three authored-look
  zones exercised above.

Door/light changes, travel/reset, resize and drone scouting were not
stimulated in these ordinary five-second windows. Source review names
their paths; later cache/visibility tests must exercise them. This
experiment gives no measured natural frequency for those events and
does not reconstruct the original native p99 tick.

The shared-root graph was ready at generation 2026-11-09T14:41:10Z.
Coverage reported no recorded issue for the relied-on runtime paths;
Git comparison verified their runtime source matches this base.
Dynamic callback edges were checked in source rather than treating the
graph's caller list as exhaustive. The new measurement file is outside
that root index and was inspected and exercised directly.

## Disposition before implementation

Sharing a same-origin sight calculation already happens in these
windows. Narrowing invalidations on ordinary NPC movement would not
remove these misses. The first bounded candidate is cheaper sight rays:
avoid allocating a complete Bresenham list for each visibility query,
while retaining its canonical tie choices and endpoint semantics. This
changes no cache key, disclosure rule, workload or output. It needs
reference-equivalence tests before any performance conclusion.

No optimization has been applied. The next stages remain: implement
the measured candidate, prove byte equivalence and unchanged frozen
values, compare before/after replay CPU on one hosted runner with raw
samples, then run unchanged final-head S11 at both sizes and the other
required checks. Runtime-changing PRs get no CPU near-miss rerun.

## Harness failure retained

The first two-tick smoke's stationary case passed, but its walk case
closed the session and the harness then raised KeyError looking for a
view. The key input was missing the protocol's required `t` field. Only
the test envelope was corrected. The corrected two-tick smoke passed
both control comparisons, then all twenty predeclared windows passed.
No native or canonical gate was run or retried.

H1 and S25 layout approval remain NOT GRANTED. These counts grant no
technical review, presentation acceptance or owner approval.

## S43 implementation candidate

Implementation ownership passed from t6 to t4 under technical-lead
acceptance comment 6744095432 on #194. Main `25b0ca6` was merged normally;
no rebase or force was used. The approved scope is only cheaper
`line_of_sight` traversal, with no cache-key or shared-cache redesign.

Tests were committed first at `9fed56c`. On the unmodified runtime,
29 focused checks passed in 14.19 seconds: frozen reference rays,
door/light/actor invalidation, real light-control expiry, resize/scouting
and all twenty committed frame/body/actor fingerprints. The exhaustive
small-grid check covers every ordered endpoint pair and every possible
single blocker in its bounding box, plus longer rays. Endpoints remain
ignored; canonical tie cells remain identical in both directions.

The candidate streams the same canonical integer Bresenham cells and
returns at the first opaque interior cell. It avoids the complete list,
reverse and slice. `line()` itself is unchanged for callers that need
its list. No other runtime file changes. Cache keys, content, workload,
S11 scripts, its gate and its sampling are untouched.

After the candidate, 86 focused checks passed in 54.17 seconds, including
the mechanics fingerprint and the complete P3 interaction matrix. The
P3 count remains 10,704 and SHA-256 remains
`05213f386e4ca644479f8ff80d43ca4e27ebd0acd0013e644b2072a9b9c59185`.
No frozen value, golden or pre-implementation capture was rewritten.
These focused checks are not the full suite or native acceptance.

### Predeclared hosted comparison

`replay_s43_publishers.py` is a current-namespace successor of the
`6d6fc30` publisher rig. The fixed before head is
`6bf5d94ddc804008edca8264f78f8658f34ecac0`; after is the exact event head.
One hosted runner executes before1, after1, after2, before2 in separate
interpreters. Each arm preserves all three frozen target scenes and
both warm/invalidated modes: 50 warmup publications, 1,000 unprofiled
wall/thread-CPU samples and a separate 200-publication cProfile.
The same declared HP parity input forces ordinary publication/deltas.
Scene and two reference-body fingerprints must match across all arms.

All raw samples, GC records, profiles and comparisons are retained.
The report shows each arm and every numerical mean change, including
warm increases; none is corrected, hidden or rerun for a favorable
value. Invalidated-scene mean CPU must decrease in all three scenes.
Warm-path noise and changed-function call counts are reported for
technical interpretation; a successful job alone grants no performance
acceptance. No local timing benchmark or full local suite was run.

Full hosted Linux/Windows suites, automated review and unchanged
final-head S04/S05/S10/S11/S24 remain required. A CPU failure in this
runtime-changing PR gets no rerun. H1/S25 remain NOT GRANTED.

### Hosted replay results

First execution [42648936644], job 129269703994, runner
`GitHub Actions 1000029077`, Python 3.12.16. Before is `6bf5d94`; after
is `b639dfb6e87848b0f0c94d9bcf59544bc1cea4c9`. All declared arms and
scene/reference-body fingerprints match. Each raw wall/thread-CPU
distribution and its mean, median, p99 and maximum were independently
recomputed, along with comparison arithmetic and the archive SHA-256.

Unprofiled mean publisher thread CPU, milliseconds, averaging the two
equal-size arms per version:

| Scene | Cache | Before | After | Change |
|---|---|---:|---:|---:|
| Sable target | warm | 2.495019 | 2.485721 | -0.373% |
| Sable target | invalidated | 7.313676 | 6.541520 | -10.558% |
| Covered target | warm | 2.492981 | 2.496110 | +0.126% |
| Covered target | invalidated | 7.349072 | 6.703237 | -8.788% |
| No covered actor | warm | 2.421774 | 2.424546 | +0.114% |
| No covered actor | invalidated | 7.287374 | 6.592071 | -9.541% |

Every invalidated scene saves 0.645835 to 0.772157 ms/publication. Both
candidate arm means are lower than both before arm means in each such
scene. This is a result for the declared fixtures, not a bound on all
states or a native gate pass.

The two positive warm shifts are retained: 3.129625 and 2.772536
microseconds. Their before/after arm ranges overlap, and the changed
`line_of_sight` has zero calls in all twelve warm cProfile phases. The
unchanged `line()` has one call/publication there. No warm phase has GC
after warmup. The author recommendation is neutral-control variation;
acceptance interpretation was requested on #194, comment 6744756546.
The technical lead ruled the warm criterion satisfied in comment
6744772541, based on the unchanged executed path and overlapping arm
ranges. This is the lead's ruling, not a pass selected by a threshold.
Every raw numerical increase remains unchanged in the packet.

All cold profiles retain 403 LoS calls/publication. Total `line()` calls,
including recursive reversal, drop from 120,200 to 200 per 200-call
profile, leaving the independent cover-list consumer. LoS inclusive
profile cost drops from about 7.15-7.36 to 4.59-4.63 ms/publication.
Profiler overhead and nested work are included; these values are never
added to other nested totals or substituted for unprofiled CPU or S11.

The compact [replay summary](captures/s43/replay-summary.json) retains
every arm's mean/median/p99/max, fingerprints, selected function counts
and GC counts. Raw samples, GC records, four full reports, 24 pstats and
comparison.json are in [artifact 13688864091], 824,329 bytes, ZIP SHA-256
`02a43ace29beed293969bea971f9d62a58cde6c77dcb8f7816859ed4a73a71fe`.
No measurement was repeated or corrected.

[42648936644]: https://github.com/Thiesi/Karst41/actions/runs/42648936644
[artifact 13688864091]: https://github.com/Thiesi/Karst41/actions/runs/42648936644/artifacts/13688864091

### Candidate full suites

Hosted root CI [42648936562] passed at `b639dfb`: Linux 2,584 tests,
Windows 2,583 tests and one skipped. Focused checks, the immutable
before-data and the performance packet above refer to this code head.
The final PR metadata/evidence commit changes no runtime, test or replay
code. Final-head CI and native acceptance remain required; no S11 result
is claimed yet. No full local suite was run.

[42648936562]: https://github.com/Thiesi/Karst41/actions/runs/42648936562
