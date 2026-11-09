# Issue 187: Row hunting diagnosis

Diagnosis only. No runtime, shipped content, ordinary test or script is
changed. The test here deliberately fails and is outside the repository's
normal `testpaths = ["tests"]`. Run it explicitly. No full local suite,
native acceptance or human approval is claimed.

## Builds and fixture

- Current `origin/main` at the start of diagnosis:
  `5416b5d611573a91bba09d445b8503a730dafd53` (S38 is present).
- Round 3 demo: `d30553795e048084dfd52131470d3e3e995eebde`.
- `row-demo.map` is a byte-for-byte copy of the demo's Sodium Row map.
  SHA-256: `68897e1e3d96c060e048242fcf53b2c02eb52eb5524da1e7fa464848088ca14f`.
- Main's shipped Row is open at these coordinates. Its one-step control
  remains visible and passes. To exercise an alcove with current main's
  engine, the failing test replaces only the in-memory Row grid with this
  declared demo fixture. Main's metadata, truce and NPC templates remain.
- The demo comparison loads the actual demo code and content from a
  verified checkout whose `src` and `tests` match `d305537`. Its import
  location is asserted. Bytecode writes are disabled there. The diagnostic
  driver stays in this worktree; the demo checkout is not edited.

Ambient spawners are disabled in memory. The caller is declared Unmoored,
the neutral regular waits at `(11, 6)`, and the enforcer starts outside
Upstairs at `(15, 9)`. The caller fires a real, committed shot from
`(10, 6)`, including the ordinary warning and ammunition settlement. The
enforcer fires from its outside post. The caller then moves one tile left
to `(9, 6)`, out of the enforcer's sight.

Main's S38 keeper responds to the shot. The old demo has no S38 truce
keeper; its Sable enforcer is already hostile to the declared Unmoored
caller. This activation difference is explicit, rather than pretending
that the demo contains S38. The reported playtest did not identify a bar,
tile or caller faction; this is a deterministic reproduction of its
symptom, not a reconstruction of the owner's exact inputs.

## Cause

The hunter does not immediately clear its target. It stays in `hunt`,
with legal combat and a live hostility reason, for the normal 20-second
lost-sight window. It fails to route to its remembered position.

Current-main references:

- `server/npcs/engine.py:371-398`: `evaluate` retains the remembered
  target until legality, hostility or the lost-sight deadline changes.
- `server/npcs/engine.py:438`: the hunt calls `step_toward` with
  `last_position`; no spawn-region argument is supplied.
- `server/npcs/behaviours.py:12-32`: movement greedily tries the larger
  coordinate difference first, horizontal on a tie. It accepts the first
  legal step and remembers only eight previous positions. It does not
  find a route through a doorway.

For the remembered goal `(10, 6)`, the actual first positions are
`(15, 9) -> (14, 9) -> (13, 9) -> (12, 9)`. At `(13, 9)`, left and up
both reduce Manhattan distance; left wins, so the hunter walks past the
open doorway at `(13, 8)`. It then cycles outside the wall instead of
entering the bar. A read-only reachability oracle finds an eight-move
legal route from the post through that doorway to the last seen tile.
The oracle never moves or directs the production hunter.

The same pursuit failure occurs after the reserved/avoid set is replaced
with an empty set in the diagnostic. The doorway is passable and admits
the hunter, combat remains legal, and hostility stays active. Thus an
avoid entry, a guard's spawn region and a safety refusal do not explain
this reproduction. After 20 seconds the normal decision loop drops the
target and the guard's base behavior starts returning it home. That is
the consequence of the failed approach, not an immediate post-step reset.

The demo uses the same `step_toward` algorithm. Its hunt call is at
`server/npcs/engine.py:369`; its timeout logic is at lines 302-329. The
demo's added `keep_reach` helper is for wandering, not this hunt branch.

## Focused results

| Run | Result |
|---|---|
| Initial main shipped-grid control | 1 passed in 1.08 s |
| First valid main alcove test, ordinary/empty avoid | 2 expected failures in 2.04 s |
| First actual-demo comparison, ordinary/empty avoid | 2 expected failures in 2.13 s |
| Final archived test on main, control plus alcove pair | 2 expected failures, 1 passed in 2.10 s |
| Final archived test on actual demo, alcove pair | 2 expected failures in 1.74 s |

Both final failing runs reach `assert reacquired`, after all shot,
one-tile movement, visibility, legal-combat, hostility, short-path and
pre-timeout target-retention checks pass. Final main state is tick 260,
last seen 55, target `None`, state `base`. Demo state is tick 240, last
seen 35, target `None`, state `base`. The 20-tick offset is the different
keeper/initial-hostility timing, not a different pursuit failure.

The first test draft produced two setup failures: its path oracle ran
before the caller moved, so it treated the remembered goal as occupied.
That diagnostic error was corrected by checking after the one-tile step.
The oracle was then refined to use the original post explicitly, without
assuming the production hunter's first move. The final runs validate
that archived test. The later failures above are the intended pursuit
assertions. No
production assertion or gate was weakened, and no unchanged failed gate
was retried to obtain a pass.

## Reproduce

From this diagnostic worktree, PowerShell:

```powershell
$env:PYTHONPATH = 'src;.'
../../.venv/Scripts/python.exe -m pytest docs/ops/diagnostics/issue187/test_row_hunt.py -q --basetemp=.test-tmp/pytest
```

This is the final combined main run in the table above. The initial
control and alcove pair were selected separately during diagnosis.

For the demo comparison, use a verified checkout at `d305537`:

```powershell
$demoSource = (Resolve-Path ../demo-review).ProviderPath
$env:BLACKSITE_187_SOURCE = $demoSource
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = $demoSource + '/src;.'
../../.venv/Scripts/python.exe -m pytest docs/ops/diagnostics/issue187/test_row_hunt.py::test_game_5_5_hunter_reaches_bar_trail_before_lost_sight_timeout -q --tb=short --basetemp=.test-tmp/pytest
```

## Smallest proposed correction, not implemented

Give the hunt's approach to `last_position` deterministic, bounded route
selection through ordinary legal tiles, instead of relying on greedy
wall sliding. Keep the remembered goal, ordinary movement/cooldowns,
collision and avoidance checks, hostility, safety and 20-second timeout.
Cache/invalidate a route as appropriate rather than flood-filling the
city for every actor every tick. Keep this scoped to the hunt approach;
do not retune wander/patrol behavior to fix a particular bar.

This fixes reaching an already known position. What a hunter does after
reaching that position without seeing the caller is the separate new
search rule for the owner to approve in the Row rules slice. No such rule
or runtime fix is added here.

H1 and S25 layout approval: NOT GRANTED.
