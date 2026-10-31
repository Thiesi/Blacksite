# A7 camera evidence, 2026-10-31

Execution head: `9b82a175aace457c95c8e071e109e7d11af9b8f0`.
Independently pinned source Git tree:
`03ac4e72f83af322ed5e0012e0888cf7e96147ef`.
Baseline: merged A6 `fd4020e7eaa413301145eca969333f2239a6cfcf`.
[Acceptance run](https://github.com/Thiesi/Blacksite/actions/runs/41199775074).

`origin()` is the only runtime change. Fitting axes centre the disclosed
zone and stay still. Larger axes retain the existing server crop and its
four-tile margin/clamps. Every map layer shares the origin. Server camera,
disclosure, content, rules, fixtures and switch-off goldens are unchanged.

## Native engine fixtures

NetBBS v7.45.0 Telnet -> registered native stdio, isolated source-matched
wheel, attached sized PTYs. All four dark/light x 80x24/132x50 jobs passed,
three tiers each: 12 cases, 48 captures. Every ANSI stream independently
replayed to identical glyphs/styles and every result-manifest SHA-256
matched. This packet retains 28 byte-preserved text captures. Raw ANSI and
full style snapshots remain in the four artifacts linked by manifest.

These are the existing P6 engine fixtures: `content.local`, explicit
initial placement (4,5), then ordinary walking keys. Fixture warning/notice
emissions test chrome. Wide character names use normal creation; BBS
handles stay genuine ASCII. They are not the shipped B1 walk and grant no
H1, fingerprint, presentation or S25 layout approval.

## Paired shipped-zone frame probe

The pinned authored data input is
`0c4b19db5152c159601fafe63d55743549cc2474`, copied as data only. Both arms
use the same P1/B2 `frames()` method: 80 ten-Hz ticks, 40 walking keys,
shipped NPCs/zone-id seeds, 30 warm-up ticks, identical disclosed starts
and ordinary/fully known knowledge. Only baseline/current `origin()` is
swapped. All 18 hosted Linux cases have identical walks and viewports;
the new origin never moves during these horizontal walks.

Aggregate maxima across three tiers and both knowledge states:

| Zone | Max delta before -> after (bytes) | Terrain cell calls before -> after |
|---|---:|---:|
| Meridian Plaza | 17,993 -> 2,514 | 136,800 -> 2,000 |
| Clinic Row | 16,968 -> 2,021 | 96,694-108,800 -> 1,785-11,264 |
| Sodium Row | 19,733 -> 3,059 | 119,910 -> 2,160 |

All after samples meet the 16,384-byte delta and 100 ms render-p95 limits.
Worst after render p95 is 27.768128 ms; worst instrumented terrain p95 is
24.624088 ms. `camera.json` retains all cases, terrain timings/counts and
the source report hash. Full report:
[artifact 13041459836](https://github.com/Thiesi/Blacksite/actions/runs/41199775074/artifacts/13041459836).

Terrain timing includes the cell-count wrapper and excludes the initial
draw. This paired frame probe is not hourly CPU acceptance. B2's full mix
and P5 CPU comparison remain for the post-owner-merge Part B continuation.

The existing P6 fixture CPU matrix also passes: 33.549-86.092 s/h. The
existing P5 matrix passes 44.295-115.612 s/h. Its fully known 132x50
16/256/truecolor values are 115.612/109.424/107.438, against historical
final P5 93.381/87.126/99.304. These increases remain a review finding.
The fitting generic map now draws the complete disclosed field instead
of the clipped player-centred portion. That is a scope-related explanation,
not an isolated causal measurement or a proven host-noise exemption.
The P5 source report and exact values are referenced in `camera.json`.

## Position-only goldens and tests

`p6_camera_diff.py` reproduces both baseline and candidate snapshots from
the same bodies by replacing only `origin()`. It checks that every other
runtime AST node is identical and every changed cell is inside the field.
Exactly three P5 132x50 zone and twelve P6 fixture goldens change:
4,950 cells. Every other golden is byte-identical. `golden-summary.json`
lists the positions/counts; the full per-cell report is in this run's
`p6-charted-budget` artifact as `p6-camera-cell-diff.json`.

Nine fitting/non-fitting/mixed-axis/Wake cases passed at both sizes.
Before PR creation, root pytest passed 2,162 on Linux and 2,161 plus one
skip on Windows (run 41198991201). Automated static review found no
actionable issues; actual model: `claude-sonnet-5-5`. It ran no tests.

Only the owner merges A7. The extra golden exception grants no delegated
merge authority. Final Part B captures wait for that merge. Then refresh
#126's baseline/frozen hashes/fingerprint candidate and stage guards,
remove its B1 hold, and create fresh B2 and native evidence. H1, P6b
fingerprint approval and S25 human layout approval remain NOT GRANTED.
