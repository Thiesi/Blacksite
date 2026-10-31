# A8 CPU and unchanged-output evidence, 2026-10-31

Execution: `426b8c0dde5c05d0c12216c5abc595aa259b00f3`.
Door Git tree: `120067854c53aa4d9a736ba30e3fc434f0fb9232`.
Pinned author data: `f69541473704f1164cd5b5e8dbd315c2fa811504`.
[Current hosted run](https://github.com/Thiesi/Blacksite/actions/runs/41224964416).

All 12 required Plaza/Sodium 132x50 cases reach <=108 CPU s/h. The
unchanged B2 method uses clean Linux, 12 seconds per P1 activity, the
provisional hourly mix, ten-Hz ticks and five-Hz walking. Metering
includes Display receive/key/update/render; it excludes server/codecs.

| Current run | Max CPU s/h | Max delta bytes | Max render p95 ms |
|---|---:|---:|---:|
| Plaza | 101.5228 | 2412 | 6.224055 |
| Clinic | 111.3507 | 2121 | 40.451070 |
| Sodium, 8 NPCs | 55.7027 | 3163 | 3.564358 |
| Sodium, 11 NPCs | 113.1783 | 3146 | 24.938818 |
| Sodium, 16 NPCs | 137.1009 | 3454 | 5.394514 |

The 108 target applies to today's eight-NPC Sodium population and Plaza.
Clinic and higher-count misses remain reported. The sweep varies only
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
and paired byte streams. H1, fingerprint approval and S25 human layout
approval remain NOT GRANTED. Technical review and owner merge are separate.
