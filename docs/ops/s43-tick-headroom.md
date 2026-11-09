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
