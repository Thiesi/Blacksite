# P6 A5 public door faces

Tracks #115 comments 6540000208 and 6540002602. Base:
`3902092c02fc4cec8972248e4eb6f63bb060a919`, the merged Part A (#129).
This class C follow-up changes no shipped data, game rules, golden or
mechanics baseline. Part B and #126's content edits wait for its merge.

## Contract and regression proof

Architecture 5.5.5 permits a non-hidden barrier face next to reached
passable ground. The flood fill still stops before every door, gate,
shutter, apartment door and requirement exit. The face is an exception
to the final region check, never another flood-fill seed. Thus a room
behind it and a chain of barrier faces remain rejected. Hidden exits,
their passable neighbours and private interiors remain excluded.

The chart uses ground-only `-3` for the face. A requirement exit may
have plain floor and no object binding, so the server includes these
exit tiles explicitly. No live door state or credential is read.

The regressions cover all four door classes as objects and interaction
tiles, plus a requirement exit on plain floor; the enclosed room and
second barrier; private overlap; every hidden-exit neighbour, including
diagonals; and no memory writes. Whole rendered glyph/style frames are
equal for a door in either state, a terminal and a requirement exit at
the same cell, at 80x24 and 132x50, all tiers, on base and region ground.

```text
python -m pytest -q tests/presentation/test_places.py
python scripts/p6_cell_diff.py --output <per-cell-proof.json>
```

The per-cell proof and the Git diff must show no existing golden change.
The older Part A Clinic fixture correction remains historical context;
A5 changes no committed fixture map or sidecar.

## Native scenario

Run `scripts/accept_p6_netbbs.py` through the registered native stdio
door on NetBBS v7.45.0, using its isolated source-matched wheel. The
script adds only `(20,5)` to the test service's local public region,
at the existing fixture gate. It never adds the room behind it. This
test setup is separate from shipped content and golden inputs.

From the explicit initial fixture position `(4,5)`, inspect the gate
face at `(20,5)`: it starts outside sight and memory, carries `-3`, and
draws ground/grain with no door or terminal glyph and no void style.
The ordinary-key walk to `(5,5)` and then `(9,5)` still reveals the
Clinic terminal. The gate remains outside sight. Captures retain the
existing charted/HERE, cover, region/HERE and notice scenarios, now
with the disclosed public gate face. Native results name that cell.

The native matrix covers both terminal sizes, all three tiers and dark
and light themes. Raw ANSI stays in CI artifacts; the source-pinned
packet supplies byte-preserved text and replay hashes. Fake-terminal
parity is a regression check, not a substitute for these live captures.

Technical and presentation sign-offs are separate from the owner's H1,
P6b fingerprint approval and S25 human layout approval. Those gates are
NOT GRANTED. Codex grants no approval and performs no merge.
