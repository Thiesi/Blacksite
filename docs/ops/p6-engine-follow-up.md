# P6 Part A engine follow-up

Scope: #115 comments 6538957810 and 6539068401. Base:
`4e5390b80463b59365cfca38049dee98b0744f91`. This PR changes the engine,
its tests and evidence tools. The presentation lead retains #126's
content; Part B waits for Part A's merge. No shipped content, rules,
balance numbers or mechanics baseline changes here.

## Contracts and regression checks

Run proof and measurement commands in the development environment with
`.[test]` installed. The native door uses a separate installed-wheel
interpreter.

- ANSI themes reuse P5's categorical people mapping, Halvard on 7 and
  jacked bodies on 8. Numeric band checks run only at 256/truecolor.
  Grey walls, legal backgrounds and readable sign letters remain
  checked at 16. Tests compare every person role in every variant with
  P5's normal and jacked styles.
- `charted` uses `-3` for every withheld static object, interaction or
  hazard cell. It carries no kind or passability and no live state.
  The client paints only dimmed ground/grain. Dressing that could name
  or classify a withheld cell is suppressed; sight and genuine memory
  still take precedence. Hidden/private areas remain excluded.
- A mark's space beside a wall is rejected with its coordinate. The
  other letters are allowed, as are spaces away from walls.

The old native fixture placed its Clinic terminal on a plain floor
tile, which could not expose the interaction-tile hole. Its existing
binding at `(10,5)` now uses the terminal tile. The native script checks
that this cell starts unseen, carries only the uniform marker and is
painted as dim ground, then reveals the terminal through ordinary keys.
No other fixture map cell changes. All twelve existing P6 goldens still
match; P5 and switch-off goldens are byte-identical. Run:

```text
python scripts/p6_cell_diff.py --output <per-cell-proof.json>
```

The proof compares semantic glyph/style cells with the merged baseline,
labels any permitted changes by cause, verifies the actual renderer,
and rejects other golden or fixture edits.

## Real geometry measurement

`tests/fixtures/p6-mask-geometry.json` snapshots only the region geometry
and theme patterns supplied at #126 head
`9b2c5da65f59dd725c083ab3d2d7d9724a4173c9`. Original look/theme/map hashes
are recorded. No unmerged content is installed in the shipped tree.

```text
python scripts/presentation_p6_masks.py --output <mask-report.json>
```

Eight cases cover the 90x40 Plaza (30x19 paving, two circles) and 100x30
Sodium Row (thirteen circles), both terminal sizes, wholly and partly
known. Sixty moving viewport masks are prepared outside the timer. The
report pairs an empty look with the supplied regions over 200 calls,
after five warmups. Only `looks.masked` is timed; view construction,
serialization and door CPU are excluded. Whole-only regions are checked
against their knowledge set. This grants no 120 CPU s/h door verdict.
The existing P6 door reference remains a separate required workflow.

## Pinned packet source

The packet command now requires `--source-tree <Git object id>` naming
the trusted execution head's `src/blacksite` tree. Supply that pin from
the reviewed checkout, not from an artifact:

```text
git rev-parse <execution-head>:src/blacksite
python scripts/presentation_p6_packet.py --artifacts-root <downloads>
  --metadata <artifacts.json> --run <run-id> --head <execution-head>
  --source-tree <pinned-source-tree> --output <new-packet-directory>
```

The command verifies that Git binds the head to that tree, reads its
Python blobs without extracting archive paths, and computes NativeProbe's
LF-normalised source digest. Every native-wheel digest must match it
before replay or output. A wrong tree or forged artifact digest fails
before writing. Existing raw-stream, glyph/style, filename and hash
checks remain active. Historical packets and their manifests are kept
unchanged; their old reproduction commands predate the required pin.

Native acceptance uses NetBBS v7.45.0 Telnet to registered stdio, sized
attached terminals, 80x24/132x50 and all tiers in dark/light themes. The
fixture scenario and explicit placement remain documented in
`p6-place-engine.md`. Captures are engineering evidence; the technical
and presentation leads make their own decisions at a head SHA.
The [Part A packet](captures/p6-engine-follow-up/README.md) names the
pinned execution source, original streams, semantic replays and the
separate measurement reports.

H1, P6b fingerprint approval and S25 human layout approval remain
NOT GRANTED. Codex grants no approval and performs no merge.
