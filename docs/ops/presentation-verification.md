# Presentation verification (P1)

P1 adds tools around the shipped door. It changes no renderer, rule,
palette, map or caller flow. Prerequisite #86 merged in PR #89; P1 now
awaits technical review under the decision in [issue #76][cp437]. No
human approval follows from a packet or a test result.

## Baselines and explicit regeneration

From the repository root, with the test extra installed:

```sh
pytest -q
pytest -q tests/door tests/presentation --update-goldens
```

The second command intentionally writes baselines. Review every changed
baseline before committing. Never use regeneration to make an unexplained
failure green. Ordinary pytest runs only compare.

All 33 existing glyph goldens retain their original `.txt` files. Each
also has a semantic snapshot under
`tests/door/golden/styles/cp437/{16,256,truecolor}/`. Schema 1 records the
size, glyph rows, a normalized SGR style table and run-length encoded
style-index rows (`[count, index]`). Style covers foreground, background
and attributes. Incremental SGR and resets resolve to the same state;
escape-string spelling is not the comparison. Wide glyph continuation
cells retain a style. The glyph-tier axis currently accepts only
`cp437`; V2 must add and exercise its actual modern renderer.

`tests/presentation/mechanics.json` contains a world-coordinate projection
and a scripted walk, hashed together. It includes tile rules, every
zone's tile IDs and initial passability/opacity overrides, exits, object
tiles, object parameters, layouts, pockets, sight and sector topology and
rule fields. Only object `params.name` (inspection copy) is excluded;
unknown future parameter keys remain in the projection. The walk records
position, health, stamina, shock, stance, cooldowns, sight,
cover and hazard. Seeds derive from the zone ID, not catalog order.
Spawners are removed from a deep-copied test fixture; shipped content is
untouched. Both viewport sizes must produce the same walk. Scratch
regressions prove a changed cover rule changes the fingerprint and a
changed palette fails the style golden while preserving the fingerprint.
This is a defined projection, not proof of every game rule or interaction.

## Review packets and the CP437 gate

```sh
python scripts/presentation_packet.py --output .test-tmp/p1-review --strict-cp437
```

Choose a new output directory for each run. The builder runs all existing
golden scenarios through the shipped renderer, compares glyph and style
baselines and requires exactly 99 scenario/colour combinations. It emits
each actual byte frame as `.ans`, the replayed screen as `.txt`, and
context JSON with size, style, frame order and per-cell CP437 diagnostics.
Replay `.ans` files in order, beginning at `0000`; later frames may be
deltas. Artifacts are headless captures, not screenshots or live NetBBS
play. PNG generation is optional and is not part of pytest.

The strict command returns 2 for a non-round-tripping authored cell. It
checks every frame. `tests/harness.py` declares the caller-input fixture
strings once. The golden harness tracks only caller-owned source fields:
the drop-file handle, zone avatar name/handle and Lattice peer names.
It rerenders the same display state with width-preserving substitutions
at those sources; comparing the two terminal grids identifies exactly
which cells came from those inputs, including wide continuation cells.
Primary ANSI bytes and glyph/style snapshots are unchanged. No runtime
renderer or server rule is patched by this test-only provenance step.

Frame JSON lists the caller cells and their source declarations.
`caller_input_cell_count` is informational, separate from
`cp437_checked_cells` and `cp437_problems`; context and summary counts
sum cell observations across frames. Caller cells are neither CP437
passes nor failures. There is no code-point list or search that exempts
identical text in an authored field. A regression draws the exact same
wide string as caller input and authored body copy and proves only the
caller cells are excluded. Unprovenanced Unicode remains checked.

PR #89 fixes the authored Lattice U+2506 for #86. P1 rebases onto that
merged fix and regenerates 60 Lattice style snapshots (20 scenarios at
three colour tiers). Only their glyph rows change from U+2506 to `:`;
styles are unchanged. The #86 fix leaves mechanics unchanged; P1's
technical-review follow-up separately expands fingerprint coverage to
object parameters without changing world data or the scripted walk. The
strict packet passes all 99 combinations. P1 makes no replacement choice or rendering
change. Omitting `--strict-cp437` collects evidence but does not turn
reported failures into a passing gate.

## CPU and byte measurements

```sh
python scripts/presentation_baseline.py --output .test-tmp/p1-baseline.json
```

The default records both sizes and all three colour tiers, measuring
four activities for 12 real seconds each. It uses `v1-provisional`:
10 minutes walking in a scene place, 20 walking where there is no scene,
15 standing and 15 in menus/text/help (sampled as local help). The weights,
starts follow the V1 harness on #80. Both walking
categories use the shipped map renderer. No trial overlay is loaded.
Shipped NPC spawners remain enabled, with 30 warm-up ticks after placing
the caller, as in V1. Only the mechanics fingerprint isolates NPCs.
These differences are recorded in the report; this is
a reproducible shipped-content baseline, not a repeat of trial V1 play.
The `p1-closed-walk-v3` workload uses closed eight-tile horizontal walks
in both zones. Its absolute ten-Hz tick deadlines include processing
time; walking keys arrive every two ticks (five Hz). Every key must
produce a move, including the last sampled key. Reports include actual
moves per minute, key steps, render calls and nonempty output frames.
V1's server-tick, input, update/render order is preserved. Keys near the
sample's end are issued only if another sampled tick can execute them;
this avoids a pending final key without coalescing input and its reply
into one render opportunity.
This corrects the earlier scene route, which hit walls, and relative
sleep scheduling, which added processing time to every tick. The session
weights are unchanged. The standing sample is shorter than its
20-second step interval, as in V1. `--seconds` allows a smoke run; only
12 seconds is the reference.

CPU measures `process_time_ns` around `Display.receive`, `key`, `update`
and `render`. This matches V1's method boundary, but records actual process
CPU instead of method wall duration. It excludes warm-up, the server,
harness, protocol codecs, I/O pumps, terminal replay and sleeping. Thus
"door CPU/hour" means these measured door methods, not a whole native
process trace. Wall render latency is recorded separately. Windows
process CPU can quantize to scheduler ticks, making sums of short method
calls noisy or biased: Windows CPU reports are diagnostic only
(`cpu_budget_reference: false`) and `cpu_120s_per_hour_pass` is null.
Use the hosted Linux workload as the CPU budget reference; other hosts
remain diagnostic until their CPU clock is validated.

The deterministic frame route records actual full/delta byte counts,
render wall time and update/render CPU, including each raw sample and
p50/p95/max. It rejects a run without movement or either output class.
Walking activity samples reject any unsuccessful step and samples too
short to observe an input. Standing and help intentionally retain
V1's published 12-second sample and 20-second step interval; their idle
sampling limitation is part of that provisional workload, not a measured
real-play hour. P1 does not silently change the technical lead's mix.
The report identifies head, dirty state, host, interpreter, mechanics
hash, sample duration and call counts. Budget results (100 ms p95,
16 KiB per delta and 120 CPU seconds/hour) are recorded, not asserted:
P1 establishes the baseline, including existing misses. P5 owns render
improvements. The CI artifact `p1-shipped-door-baseline` is the hosted
Linux reference for its exact checked-out revision; local reports remain
host-specific. A green recording job does not mean all targets passed.
The packet and baseline workflow runs for source, tests, verification
tools and packaging changes, and on manual dispatch. Unrelated docs-only
PRs do not run the activity samples. Compare hosted reports with other
hosted reports from the same workload; the local Windows record is a
separate reference, not a CI threshold.

### Reconciling P1 and V1 (technical review TR-1)

The [paired Linux report][paired] runs both harnesses on one hosted
runner, Python 3.12.15, for 12 seconds of no-scene walking at 132x50 in
truecolor. The first four rows use the identical V1 runtime at
`1060c9df2ac6b140db932b4e888989d192502b20`. P1's measurement code is at
`00470f9a448cda7f7c459836c0b38d9694f70692`; the last row uses its own
runtime. The V1 script is unedited and its SHA-256 is checked. CPU and
wall time cover the same method calls; render calls include empty
returns, while frames count only nonempty output.

| Harness and renderer | CPU s/min | Wall s/min | Moves/min | Renders | Frames |
|---|---:|---:|---:|---:|---:|
| P1, shipped, on V1 runtime | 3.312 | 3.323 | 295.0 | 120 | 73 |
| V1, proposal map | 9.032 | 9.033 | 234.3 | 97 | 96 |
| V1, shipped control | 10.045 | 10.046 | 229.3 | 95 | 94 |
| P1, shipped, trial charting | 8.187 | 8.199 | 295.0 | 120 | 75 |
| P1, current shipped runtime | 2.795 | 2.806 | 295.0 | 120 | 69 |

The gap has observed causes:

- **Known ground.** Both use a 100x30 source viewport. P1 starts with
  516 visible and 2,484 unknown cells. V1's trial starts with 271 visible
  and 2,729 remembered cells, with none unknown. Its trial geography is
  charted on arrival. The shipped renderer skips unknown cells, but
  draws remembered ones. Enabling trial charting in P1 while retaining
  its fixture and the shipped renderer raises total CPU from 3.312 to
  8.187 s/min, about 2.47 times. Render CPU rises from 2.287 to 7.154;
  receive CPU changes only from 1.019 to 1.026. This control preserves
  all 59 successful moves and nearly the same number of output frames.
- **Output count and cadence.** Unmodified V1 adds processing time to
  each 100 ms sleep. It executes 47 of 48 keys in the proposal case and
  46 of 47 in the shipped control, leaving the final key pending. P1
  executes all 59 keys on absolute deadlines. Its tick order matches
  V1, but render gating still gives different nonempty output counts.
  In the two charted shipped controls, total method CPU divided by
  output frames is 21.8 ms for P1 and 21.4 ms for V1: a similar cost per
  output frame, with 75 versus 94 outputs. This quotient includes all
  measured methods; it is not a render-only timer.
- **Clock units.** V1's original result is method wall time. The paired
  clock shows that CPU and wall time are close on this runner. Clock
  units do not explain the factor-of-two gap here. Windows remains
  diagnostic because its per-call CPU clock quantizes to scheduler ticks.

P1's original scene route also hit walls (23 moves for 57 keys), and
its relative sleep lowered the achieved cadence. The corrected reference
uses closed routes, absolute deadlines and complete-step checks. The
provisional mix weights are unchanged; its standing/help limitation
remains as documented above.

The old 53.5-96.6 CPU s/h figures and intermediate workload versions are
superseded. The new reference describes shipped exploration state, not
V1's charted map. Even the charted P1 control's 20 no-scene minutes alone
cost about 164 CPU seconds, above the whole-hour 120-second target.
A fresh-arrival P1 pass therefore says nothing about the charted
presentation meeting that target. P5 must compare the same renderer,
known-ground state, achieved movement and output counts. This correction
changes measurement and coverage only, not a renderer, rule or target.

To reproduce, use a separate checkout of the pinned V1 revision:

```sh
python scripts/presentation_compare_v1.py --v1-root /path/to/v1-checkout \
  --output .test-tmp/p1-v1-comparison.json
```

The existing `presentation-verification.yml` workflow also accepts
`compare_v1=true` on manual dispatch. It checks out that exact V1 SHA and
runs the comparison and full six-case reference on the same runner.
The [hosted run][paired-run] retains the comparison and baseline artifacts.

[paired]: baselines/p1-v1-comparison-00470f9.json
[paired-run]: https://github.com/Thiesi/Blacksite/actions/runs/40829008369

An early clean-head [Windows diagnostic][local] records commit `325576b`,
Python 3.12.10, Windows 11 and an Intel Family 6 Model 186 host. This is a
local measurement with NPCs isolated, not the shipped-NPC baseline,
hosted Linux reference or native acceptance. The original sampler reused
the mechanics fixture; the shipped-NPC sampler above corrects that.
Diagnostic CPU seconds per hour, before rounding activity contributions:

| Size | 16 colours | 256 colours | Truecolour |
|---|---:|---:|---:|
| 80x24 | 97.9 | 88.8 | 61.6 |
| 132x50 | 128.9 | 150.7 | 144.1 |

The Windows CPU totals carry no 120-second budget verdict. On its frame
route, full redraw maxima range from 4,143 to 15,086 bytes, delta maxima
from 1,010 to 2,075 bytes, and worst render p95 is 22.2 ms. These sampled
routes do not bound every screen or gameplay activity.

[local]: baselines/p1-windows-325576b.json

## Native scope in CI

Draft PRs changing only the display modules (`model`, `cells`, `screens`,
`layout`, `palette`, `log` and `views/`), Markdown/plain text, art or
palette/glyph content, with supporting tests, run S04's registered
native stdio door at 80x24 and
132x50 through Telnet, SSH and WebSocket. Scope is classified from the
trusted base revision. Missing classifiers, uncertain paths, non-draft
PRs and changes outside the allowlist retain the full existing matrix.
Other door code (transport, raw input, startup and drop-file parsing) and
structured text data retain the full matrix even in drafts.
The ready-for-review transition explicitly runs the full matrix. P1's
own workflow/tools changes use the full matrix. No label skips checks.
`model.py` also emits protocol intents: a draft subset pass does not
cover their integration with every gameplay system. That coverage comes
from the required full matrix on the ready-for-review head.

[cp437]: https://github.com/Thiesi/Blacksite/issues/76#issuecomment-6485149621
