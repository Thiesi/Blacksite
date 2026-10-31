# A5 public door-face fixture evidence

Execution head: `7653e272fca0f55917e46ecfa42ff8c17f76862e`.
Pinned runtime Git tree: `a111702ad858dd9a2ebd78f2ae4ded7a164ee278`.
The manifest independently binds the native Python digest to this tree.
The publishing commit adds evidence and the slice status only; it does
not change the captured runtime.

Run [41179173660](https://github.com/Thiesi/Blacksite/actions/runs/41179173660)
supplies four named artifacts, linked individually in `manifest.json`:
dark/light at 80x24 and 132x50, all three colour tiers. All twelve
native cases passed. NetBBS v7.45.0 Telnet reaches a registered native
stdio door using an isolated source-matched Blacksite wheel. Sized
attached PTYs receive genuine terminal output. All 48 streams were
independently replayed for glyphs and rendition; 28 selected text files
are preserved byte for byte. Raw ANSI and full style snapshots remain
in the linked artifacts.

## A5 scenario

The harness copies the committed P6 fixture into the test service's
`content.local` and adds only the existing gate face `(20,5)` to its
public region. The room behind it is not added. No committed fixture,
shipped zone or golden input changes.

The caller starts explicitly at `(4,5)` with a genuine ASCII handle
and wide-character name. In `charted-and-here`, the gate at `(20,5)`
is outside sight and memory. The harness asserts chart marker `-3`,
painted ground, no door/terminal glyph and no void rendition. The
fixture then walks with ordinary keys to `(5,5)` (`authored-cover`)
and `(9,5)` (`light-region-and-here`), revealing the Clinic terminal.
The gate remains unseen. `notice` exercises the existing server notice
path. Setup and emitted fixture notices are explicit engineering
fixtures, not an ordinary shipped-place journey.

The focused fake-terminal regressions additionally compare complete
door-open, door-closed, terminal and required-exit frames at the same
cell, at both sizes/all tiers, on base and region ground. They prove
memory and chart stability, blocked rooms/chained barriers and retained
hidden/private exclusions. They do not substitute for native captures.

`per-cell-proof.json` reports zero changed existing golden cells. Its
named `(10,5)` Clinic map correction belongs to the already-merged
Part A baseline; A5 makes no further fixture change. Historical P6a
and Part A packets remain untouched.

## Reproduce

Download the four `p6-fixture-*` artifacts into separate named folders,
save their GitHub artifact metadata, then run:

```text
python scripts/presentation_p6_packet.py --artifacts-root <downloads>
  --metadata <artifacts.json> --run 41179173660
  --head 7653e272fca0f55917e46ecfa42ff8c17f76862e
  --source-tree a111702ad858dd9a2ebd78f2ae4ded7a164ee278
  --output <new-packet-directory>
```

The source pin comes from Git, not from an artifact's claim. The
verifier rejects mismatches before writing and preserves existing
packets. `summary.json` records the native and replay checks only;
reference budgets and service checks are separate workflow results.

No human gate or presentation approval is granted by this packet.
H1, P6b fingerprint approval and S25 human layout approval remain
NOT GRANTED. Part B waits for A5's merge.
