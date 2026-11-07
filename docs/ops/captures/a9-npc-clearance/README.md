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
