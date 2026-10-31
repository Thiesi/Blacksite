# P6b diagnostics before A7, 2026-10-31

These are pre-A7 engineering diagnostics, not final Part B acceptance.
The technical lead queued A7 on #115 (6542553660) and #82 (6542565665):
final B1 captures wait for the owner's A7 merge. H1, fingerprint approval,
presentation sign-off and S25 human layout approval remain NOT GRANTED.

Execution head: `b0e50a3d2f12f366dc3ff0d34709afb452558f30`.
Content-owner input: `0c4b19db5152c159601fafe63d55743549cc2474`.
Independently pinned `src/blacksite` Git tree:
`661b3299bfb9510c2fcc0c99cbedb0ad53acad7e`.
[Hosted run](https://github.com/Thiesi/Blacksite/actions/runs/41194677997).

## Native walk

All five jobs passed through NetBBS v7.45.0 Telnet, a registered native
stdio door, an isolated source-matched wheel and a sized attached PTY.
Configurations: 80x24 and 132x50 in 16/256 colours, plus 132x50 truecolor.
Every configuration walked all five checkpoints. All 25 ANSI streams
replayed to identical glyphs and styles; all result-manifest hashes
matched. The packet retains 22 byte-preserved text captures: every 16/256
checkpoint plus the requested truecolor Plaza and Tin Halo frontages.
Raw ANSI, full style JSON and key traces remain in the linked artifacts.

Ordinary character creation enters a wide character name. Genuine BBS
handles stay ASCII, without a local override. The route uses arrows,
the Wake's offered B skip, E to open the clinic door, and J to jack in
and out at its public terminal. After leaving, the terminal at (17,8)
must be remembered (`-2`) and outside current sight. Then the caller
walks the pharmacy frontage, the second Plaza terminal, the south exit,
Sodium Row's entry and the Tin Halo frontage without entering the Halo.
No pose, inventory, progression, actor, clock or memory fixture is used.

An additional local Windows attached-terminal 80x24/256 walk passed at
`4f77a07ab8c924cb42a4b8239766a7fad6051d88`, on the same runtime source
tree. Its files stay local; the committed packet uses hosted captures.

## Budget finding: blocked

All three B2 jobs failed the 16,384-byte delta ceiling. These exact
failed frame samples come from their completed job logs:

| Zone | 132x50 truecolor state | Max delta bytes | Delta render p95 ms |
|---|---|---:|---:|
| Clinic Row | fully known | 16,968 | 13.789557 |
| Sodium Row | ordinary | 19,243 | 21.220290 |
| Meridian Plaza | ordinary | 16,970 | 29.446163 |

Render latency passed for these samples. CPU also misses 120 s/h in
multiple 132x50 cases. For example, fully known 16/256 figures are
155.1109/165.9043 for Clinic Row, 268.8289/264.5911 for Sodium Row, and
276.0695/278.4373 for the Plaza. P5's accepted final known figures are
93.38065/87.12597/99.30392 for 16/256/truecolor, from run 41126237721,
artifact 13010629694. Exact nine-case values and provenance are pinned
in `tests/presentation/p6b-p5-reference.json`.

The P1 meter, provisional activity weights, ten-Hz deadlines, five-Hz
eight-tile walk, shipped NPCs and every-key-must-move assertion are
unchanged. Starts are disclosed: Plaza (41,26), Clinic Row (36,17),
Sodium Row (46,14). Knowledge is seeded only for the headless fully
known budget cases, identically in generic/looks arms. Different maps,
charting and looks make P5 a historical reference, not a causal control.
No host-noise explanation or budget acceptance is inferred.

The first report writer asserted before its end-only write. Thus those
three artifacts contain B3 reports but no complete budget JSON.
`budget-findings.json` preserves 22 completed CPU verdicts and the three
failed frame summaries parsed from the actual completed logs, with job
links. This is explicitly incomplete, not a 27-case pass. The support
tool now retains completed/failed measurements before exiting nonzero;
frame thresholds are unchanged. A7 is the next queued engine work.

## B3 candidate, pending owner approval

`changes.json` lists six P5 zone snapshots, frozen by exact candidate
SHA-256. Every other golden stays byte-identical to merged A6. The
candidate mechanics fingerprint changes from
`ced7a478341b858dd8ff704417d549c09ecf74b8c5cd44d312ca474dcf43996d`
to `09562f9cd4777467352032839849456af7a6b5b5c270593c765595276ca159f2`.
Only `charted` and `public` change for the three authored zones. Geometry,
rules, exits, objects and the deterministic mechanics walk stay equal.
Spawner regions are outside that projection. A7's separately authorised
position changes will require refreshing these candidates after merge.

The head's hosted full suite passed: Linux 2,154; Windows 2,153 with one
skip. The packet verifier's source/corruption/streaming/newline checks
also pass. These engineering results grant no owner or human gate.
