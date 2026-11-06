# A8 CPU and unchanged-output evidence

## Current validated execution, 2026-11-05

Head: `4ab6470b10821f9fddbac718615af7d56c6048eb`.
Runtime tree: `2d7df79aedb20cc9510d888127442e3bca259469`.
Before-renderer baseline and data input:
`dd489f9ec7676b2c37b553fa7587c4d0a4ed6d56` (owner-merged P6b).
[Current hosted run](https://github.com/Thiesi/Blacksite/actions/runs/41966224396).
[All 27 shipped and 12 population-sweep pairs](https://github.com/Thiesi/Blacksite/pull/144#issuecomment-6649806032).

**18 of 18 required three-zone 132x50 cases reach <=108 CPU s/h.**
All 39 clean Linux, 12-second paired cases have matched workloads,
identical ANSI streams and passing frame budgets. Source/input hashes,
case membership and weighted CPU were independently checked. The P1/B2
activities, metering and mix are unchanged. Cross-run timings do not
establish isolated causation.

| Shipped zone | Maximum after, CPU s/h | Target cases <=108 |
|---|---:|---:|
| Plaza | 73.61531601685104 | 6/6 |
| Clinic | 94.00947392152614 | 6/6 |
| Sodium, 8 NPCs | 73.67200990171082 | 6/6 |

Measurement-only Sodium sweeps: 11 NPCs peak at 79.46195281783272
(0/6 over 108); 16 NPCs peak at 140.54296407888214 (6/6 over).
The two Sable posts and one Warden stay fixed; only regulars vary.
These results grant no shipped population decision.

Four attached-PTY fixture jobs cover both sizes, dark/light and all
three tiers through NetBBS v7.45.0 Telnet to registered native stdio.
All 48 glyph/style captures were independently replayed and their
manifest hashes and source-matched wheel checked. Raw captures remain
in the current hosted run; the historical files below are not relabelled
as current evidence. Local Windows: 2221 passed, one skipped. CI Linux:
2222 passed; Windows: 2221 passed, one skipped.

The full service matrix passed at this runtime, with the actual
600-second heat wait: final S11 p99 8.009 ms (80x24) and 8.069 ms
(132x50). No S11 retry or threshold change. The intermittent main stall
is still tracked separately in #158; this pass does not explain it.
[Service run](https://github.com/Thiesi/Blacksite/actions/runs/41966224407).

The owner approved the specific P6b fingerprint move in
[6649759185](https://github.com/Thiesi/Blacksite/pull/126#issuecomment-6649759185).
H1 and S25 layout approval remain NOT GRANTED. Technical review and
merge are separate gates. The renderer sign-off at 4ab6470 is recorded
in [6649998476](https://github.com/Thiesi/Blacksite/pull/144#issuecomment-6649998476),
with a workflow objection to resolve before merge.

The workflow follow-up changes only workflows and these evidence notes;
`src/` stays identical. `p6-a8-proof.yml` reproduces CPU and frozen-content
checks at the fixed reviewed head, including B3 at reviewed P6b fe89d32.
Later content, golden and rendering changes use ordinary root tests and
presentation review, with fingerprint approval reserved for the owner.

Historical misses and original artifact references follow unchanged in
meaning; `performance.json`, `manifest.json` and committed captures still
belong to the older executions described below.

## Historical second pass, 2026-10-31

Execution: `426b8c0dde5c05d0c12216c5abc595aa259b00f3`.
Door Git tree: `120067854c53aa4d9a736ba30e3fc434f0fb9232`.
Pinned author data: `f69541473704f1164cd5b5e8dbd315c2fa811504`.
[Historical hosted run](https://github.com/Thiesi/Blacksite/actions/runs/41224964416).

This packet records the second pass, not completed A8 acceptance.
Under the expanded Plaza/Clinic/Sodium target, 17 of 18 132x50 cases
reach <=108 CPU s/h; Clinic ordinary/256 misses at 111.3507. The
unchanged B2 method uses clean Linux, 12 seconds per P1 activity, the
provisional hourly mix, ten-Hz ticks and five-Hz walking. Metering
includes Display receive/key/update/render; it excludes server/codecs.

| Historical run | Max CPU s/h | Max delta bytes | Max render p95 ms |
|---|---:|---:|---:|
| Plaza | 101.5228 | 2412 | 6.224055 |
| Clinic | 111.3507 | 2121 | 40.451070 |
| Sodium, 8 NPCs | 55.7027 | 3163 | 3.564358 |
| Sodium, 11 NPCs | 113.1783 | 3146 | 24.938818 |
| Sodium, 16 NPCs | 137.1009 | 3454 | 5.394514 |

The 108 target applies to Plaza, Clinic and today's eight-NPC Sodium
population. Higher-count misses remain measurement-only. The sweep varies only
regulars (5/8/13), retaining two Sable posts and one warden. It changes
no shipped population and grants no population decision.

`performance.json` retains all 27 shipped plus 12 extra sweep cases
from both runs. The first implementation at `4f744cb` missed 108 in
four target cases; it is preserved with its failed historical-guard job.
The second pass changes code to reuse topology. Every paired case in
both runs matches workload and deterministic ANSI bytes and passes
frame budgets. Cross-run timings do not establish isolated causation.

Four fresh attached-PTY NetBBS fixture jobs cover dark/light, both sizes,
and all three tiers. All 60 original text SHA-256 values were verified;
18 representative charted/HERE and authored-cover texts are committed.
The complete texts, raw ANSI and styles remain in the linked artifacts.
Read-only export runs recover original bytes, without a composed frame.
`manifest.json` links the source, paths, hashes and export jobs.

Root CI at this execution: 2168 Linux passed; 2167 Windows plus one skip.
Goldens, fingerprint data, disclosure, budgets and A7 origin are unchanged.
The frozen A7 audit proves A7 only; A8 proof is the current root suite
and paired byte streams. At that execution H1, fingerprint approval and S25 human layout
approval were NOT GRANTED. Technical review and owner merge are separate.
