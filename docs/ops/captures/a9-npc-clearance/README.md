# A9: spawn clearance and interaction-fixture evidence

Scope and rulings are on
[#115](https://github.com/Thiesi/Blacksite/issues/115): gathered scope
6701521461, read-only investigation 6701810098, attribution 6701883761,
and accepted corrections 6701887236. H1 and S25 remain ungranted.

## Frozen interaction scene

The driver enumerates positions around objects, exits and NPCs. Its
creation sequence also steps ambient NPC spawners. At initial A9 head
`836d43cdecc3b0097a8370b8dc0ed01a6bc99130`, the clearance preference moves
the first Wake Hall orderly from (10,4) to (13,4); the second orderly at
(13,3) and the outfitter at (34,16) do not move. This changes the scene
and therefore the driver's input cases, without changing an E/J handler.

Compared with base bfd9a34, Wake Hall loses eight cases at each of (9,5),
(10,5), and (11,3), and gains eight at (14,5): net sixteen fewer. Each
eight is normal/jacked body x E/J x key/intent. Eight common normal-body
E outcomes also change around the relocated orderly. All other common
outcomes match. The complete case/outcome breakdown is in
[the attribution record](https://github.com/Thiesi/Blacksite/issues/115#issuecomment-6701883761).

Read-only diagnostic processes overlaid exact base methods in memory:

| Variant | Cases | Digest |
| --- | ---: | --- |
| All three base methods | 10704 | Original |
| Initial A9 head | 10688 | Changed |
| Revert spawn clearance alone | 10704 | Original |
| Revert return-home alone | 10688 | Changed |
| Revert shock floor alone | 10688 | Changed |
| All A9 code, base NPC positions pinned | 10704 | Original |

Original SHA-256:
`05213f386e4ca644479f8ff80d43ca4e27ebd0acd0013e644b2072a9b9c59185`.
Changed SHA-256:
`448aec5015e4e32c56036262642d43daec870627b3fd041627084d0c11388ad1`.

With only positions pinned in the temporary diagnostic, all 10,704
normalized outcome rows equal the base rows. The approved driver change
now explicitly places those three fixture NPCs in the original scene.
It does not alter any existing assertion, baseline file, hash, outcome
filter or resolver. The separate mechanics fingerprint stays unchanged.

## Small posts and caller impact

Hard adjacency rejection also starves the convoy fixture: its escorts
wait beside a free route-start tile, which is its sole spawn candidate.
The same rule prevents the shipped Halo bouncer at (4,3) from appearing
while an arriving caller remains at the public spawn (3,3). This is a
real spawn-rule problem, separate from the matrix's fixture dependency.

The accepted rule prefers tiles more than five Chebyshev tiles from all
players, then uses a farthest legal free authored tile. It permits an
adjacent fallback and always rejects a player-occupied tile. It does
not enlarge authored regions or change convoy receipts. Ambient NPC
positions can change for callers, including the seeded Wake Hall orderly
example above. Every fled wanderer walks home under the same rule,
including covered actors. Consumable shock remains within 0..100;
negative-shock consumption is a fixture test, not new shipped content.

## Validation ledger

The initial head's first root run is retained as **1 failed, 2325 passed,
3 skipped, 19 errors**, in 975.07 s. The failure is the matrix case
count; all 19 setup errors are the missing convoy. Both OS jobs on
[run 42334499105](https://github.com/Thiesi/Blacksite/actions/runs/42334499105)
report the same failure and setup errors. These outcomes are not waived.

After the accepted code and setup corrections, the focused command is:

```text
pytest -q tests/npcs/test_engine.py tests/server/test_event_convoy.py
  tests/presentation/test_interaction_focus.py::test_arch_5_5_2_predicted_equals_dispatched_and_pre_p3_behavior
  tests/presentation/test_foundation.py::test_mechanics_baseline
```

Result: **59 passed in 36.80 s**, with both frozen baselines unchanged.
The PR records subsequent exact-head root, CI, native and review results.
Native acceptance uses the canonical NetBBS Telnet/native-stdio matrix
at 80x24 and 132x50. Focused tests do not substitute for those runs.

## S10 evacuation correction

At corrected head ac606e3, root pytest passes 2346 tests with 3 skipped;
both hosted OS jobs pass. The service matrix finishes with 27 successful
jobs, one failed S10 combat job, and one intentional skip. Both S24 sizes
pass first run. Both S11 sizes pass actual heat expiry and local response;
their final p99s are 5.412 ms at 80x24 and 7.928 ms at 132x50.

S10's 80x24 winner dies to Warden pursuit while walking from the corpse
cache toward Plaza. The failed artifact is `s10-combat-proof`, ID
13560367998, on run 42337239960; its ZIP SHA-256 is
`910661f94c1d16df59cb2ad5ccd814d63c49b78248da560a7d6fd711ad499cfd`.
The winner has 18/108 HP after looting, versus 78/108 in the passing
near-base artifact 13553591387 on run 42320603678. The last failed Clinic
frame places the winner at (76,25), the Warden at (71,28), and the Plaza
exit at (77,2). The failure happens during the walk, before exit input.

The retained comparison and its limits are on
[#180, 6702434717](https://github.com/Thiesi/Blacksite/pull/180#issuecomment-6702434717).
The Warden uses patrol, so the added wander return-home branch does not
directly move it. A9 likely changes the zone RNG stream enough to expose
this existing pursuit race, but the retained captures do not prove that
attribution. They do not record every spawn, RNG state or unseen actor.

The lead accepts lawful pursuit and authorizes a deliberate route change
in [6702439669](https://github.com/Thiesi/Blacksite/pull/180#issuecomment-6702439669):
Clinic to Core tram hub to Plaza. From cache (27,25), the tram at (3,31)
is 30 movement steps away, versus 73 directly to Plaza. S10 keeps real
HP, Mark, live NPCs and the original second-death assertions. It adds a
local guard against a death/recovery being mistaken for a zone change.
The shared `NativeProbe.travel` bound stays unchanged.

The local tram wait reads the actual scheduled arrival. Trams depart on
90-second intervals and take 10 seconds; the allowance also covers the
existing bounded departure hold and original transition margin. The
actor remains on the contested platform until departure. **Remaining
risk:** the 30-step walk at low HP can still lose, and pursuit can also
reach a waiting passenger. A second failure is a new measurement to
report, not permission to retry or pin the Warden. That fixture is not
authorized.

**Curfew check:** S10 forces no event and changes no event state. Curfew
is eligible for automatic scheduling and restricts a Marked caller's
inbound Core entry. Ordinary plans start at least one hour after they
are reserved (`Scheduler.reserve`, `ADVANCE_SECONDS`). The canonical
fresh-root CI job has a 20-minute timeout, so an automatically planned
Curfew cannot start during it. A reused or long-lived world with an old
plan can close the hub; boarding refusal must fail the proof. S10 neither
clears Curfew nor supplies a pass nor suppresses its restriction.

## Approved route measurement and native captures

At source and acceptance head
`f21c97e542f7c3c9a3923eec4417088fa6c4ad46`, the approved route passes
its first measurement at both sizes. Both winners board with **8 HP and
Mark still set**, and reach Plaza without another death. At 80x24 the
actual departure wait is 67.5 s, ride 10 s and full evacuation 89.1 s;
at 132x50 those are 10.2 s, 10 s and 31.3 s. Combat artifact 13562450405
on service run 42340736162 retains the raw streams and result. Its ZIP
SHA-256 is
`771d1e2c539a1b280e7436a7d530a04fd61b1491484e262a77ec1bf2f1a09e22`.
This pass does not remove the remaining walk/platform risk.

Root CI at that head passes **2354 tests on Ubuntu**, and **2353 with
one skipped on Windows**, run 42340736256. Both S24 sizes pass their
first run. Both S11 sizes pass actual ten-minute heat expiry, local
response and the unchanged final p99 gate: **7.177 ms at 80x24** and
**7.692 ms at 132x50**. No S11 exception or retry was needed.

All 16 PR workflows finish successfully. Service run 42340736162 has
**28 successful jobs and one intentional skipped subset**, including S12
market, S10 combat, S11 NPCs, S24 events and the full encounter matrix.
The two written reviews, Claude Sonnet 5.5 (6702545545 and 6702631423),
have no actionable findings; triage is recorded in 6702573627 on #180.
The final documentation/evidence commit keeps this head's runtime,
scripts and tests byte-identical. Its fresh CI results and exact-head
technical request are retained on the PR rather than extending an
artifact/commit cycle. Only the lead can write the technical record;
the owner merges because game design 5.5 changes.

The six `truce-regular-warning-*.txt` files are unaltered live native
screen text from canonical S38 acceptance at this same source head:
80x24 and 132x50, each in 16 colours, 256 colours and truecolor. They
show the affected Sodium regular scene, with canonical S38 fixtures and
modern presentation. `manifest.json` names each scenario, exact source
member, source head, run, artifact, ZIP digest and capture digest. Raw
ANSI, including colour rendition, stays in those CI artifacts. Text
captures preserve glyphs, not colour. These are engineering evidence;
H1 and S25 layout approval remain ungranted.
The final blank cell on each capture's bottom row is intentional terminal
safety padding; it is retained verbatim, including trailing whitespace.

## Representative playable checks

These are review steps, not a claim of a separate human playtest. Use a
fresh test world through a registered NetBBS native door. Repeat at
80x24 and 132x50; do not weaken live rules to force an outcome.

1. Enter Wake Hall with a new caller, then visit Sodium Row and the Tin
   Halo. Observe nearby NPCs and ordinary movement. A spawn must not
   occupy a player tile. Broad posts prefer more than five tiles of
   clearance; small posts still populate at a farthest legal free tile,
   including the Halo bouncer beside its arrival point.
2. Observe a regular near the Plaza exit and a covered Warden near the
   Halo door. Wander and patrol steps must leave the exit usable. If
   an ordinary or covered wanderer flees beyond its authored region,
   let it resume ordinary behaviour: it should walk home without a
   teleport or a special faction rule. Deterministic tests cover these
   placements and the unchanged RNG draws; a live sighting alone cannot
   establish the spawn distance preference or every return path.
3. On a disposable test caller, use a shipped consumable from the normal
   inventory flow. Shock must remain within 0..100 and the item/receipt
   must agree with successful consumption. Negative-shock and failed
   commit cases are unit fixtures; no shipped item was added for them.
4. For the S10 scenario, use the canonical two-player combat proof:
   fight and loot in Clinic Row, then take the tram hub route to Plaza.
   HP, Mark and live pursuit remain real. Waiting must follow the actual
   schedule; another death or refused boarding must fail. The retained
   first measurement above exercises this sequence at both sizes.
