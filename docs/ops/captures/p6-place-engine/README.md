# P6a live fixture evidence

Execution head: `70b346c0b6090694c8fc6dfe442e7f55c2f1ae39`.
The later evidence commit adds this packet and verifier checks; it does
not change the runtime captured here. `manifest.json` records the source
Python-tree hash checked against each isolated native-client wheel.
The captured `src/blacksite` Git tree is
`326175c624a9b6ad3a3bbc5f495de80bcd7e9874`.

[Native run 41159079066](https://github.com/Thiesi/Blacksite/actions/runs/41159079066)
plays twelve cases: dark/light themes, 80x24/132x50, and
16/256/truecolor. NetBBS v7.45.0 Telnet runs a registered native stdio
door on a sized attached PTY. The wide game name is entered through
ordinary character creation; the genuine BBS handle stays ASCII.

The test-only `content.local` fixture starts at `(4,5)` in Fixture hall.
It then uses ordinary walking keys. This explicit placement is engine
evidence, not P6b's shipped-place walk. The
[playable scenario](../../p6-place-engine.md#playable-fixture-scenario)
states the starting point, keys and expected results.

Each case captures four checkpoints:

| Checkpoint | What to inspect |
|---|---|
| `charted-and-here` | Public layout dimming, wall/sign/grain, locked `≡`, terminal shape and distinguishing `(Plaza)` suffix at 80 columns. |
| `authored-cover` | One step right; HERE reads `▒ barrels`. |
| `light-region-and-here` | Walk to `(9,5)`; player contrast on light ground and distinct `(Clinic)` suffix. |
| `notice` | Typed fixture danger plus service notice; header retains Fixture hall. Look ambient is never emitted. |

All 48 full raw streams and style snapshots remain in the four named CI
artifacts linked by `manifest.json`. All capture/result-manifest hashes
were checked. Each stream was replayed independently and matched both
the captured text and every semantic style cell. Replay starts at the
door's alternate-screen marker, exactly as the native harness does;
the pre-door NetBBS/Telnet negotiation remains in the hashed raw stream.
The manifest records each start offset.

To stay within the review policy's approximately 200 KB repository
limit, the packet commits both terminal checkpoints in all twelve
cases, plus cover/notice at dark 80/256 and light 132/truecolor: 28
byte-preserved text files. Hashes and artifact paths cover all 48;
the omitted twenty repeat cover/notice in the other combinations.

To reproduce the packet, download the four `p6-fixture-*` artifacts into
separate named directories, save that run's artifact metadata, and run:

```text
python scripts/presentation_p6_packet.py --artifacts-root <downloads>
  --metadata <artifacts.json> --run 41159079066
  --head 70b346c0b6090694c8fc6dfe442e7f55c2f1ae39
  --output <new-directory>
```

The command rejects incorrect provenance, path components, hash or
replay mismatches, missing checkpoints and oversized packets before
writing. Verification remains active under `python -O`.

`performance.json` records the Linux 12-second paired reference, its
separate server-only large-ring probe, and the shipped P5 workload
comparison. The P6 stress fixture is not the shipped P5 baseline. It
also identifies the local Windows latency diagnostic, which grants no
Linux CPU verdict. Full source-head pytest passed: Linux 2,102;
Windows 2,101 plus one platform skip. The local presentation/cell suite
passed 343 tests; the updated local attached 80x24 dark native walk
passed all three tiers. The PR handoff records final-head CI separately.
`p5-here-row-diff.json` proves that only row 2 changes in each of the
six authorized P5 zone goldens; all other glyph/style cells are equal.

Automated capture/replay is engineering evidence. The technical review
and presentation lead's fixture sign-off are separate decisions. This
packet grants no H1, P6b fingerprint approval or S25 human layout
approval, and does not mark any shipped place accepted.
