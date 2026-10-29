# Presentation verification (P1)

P1 adds tools around the shipped door. It changes no renderer, rule,
palette, map or caller flow. Its current work is incomplete pending the
CP437 decision in [issue #76][cp437]. No human approval follows from a
packet or a test result.

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
tiles, layouts, pockets, sight and sector topology and rule fields. The
walk records position, health, stamina, shock, stance, cooldowns, sight,
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

The strict command returns 2 for a non-round-tripping cell. It checks
every frame and every cell, including user text. Existing goldens contain
the authored Lattice glyph U+2506 and the wide caller-name fixture U+754C.
Both currently fail. Nothing in P1 exempts them, picks a replacement,
changes canon or waives acceptance. The dedicated CI packet job remains
red until the owning decision and correction are made. Without
`--strict-cp437`, the builder still reports `cp437_pass: false`; that mode
is evidence collection only, not a passing CP437 gate.

## CPU and byte measurements

```sh
python scripts/presentation_baseline.py --output .test-tmp/p1-baseline.json
```

The default records both sizes and all three colour tiers, measuring
four activities for 12 real seconds each. It uses `v1-provisional`:
10 minutes walking in a scene place, 20 walking where there is no scene,
15 standing and 15 in menus/text/help (sampled as local help). The weights,
starts, keys and schedule follow the V1 harness on #80. Both walking
categories use the shipped map renderer. No trial overlay is loaded and
NPCs are isolated. These differences are recorded in the report; this is
a reproducible shipped-content baseline, not a repeat of trial V1 play.
The standing sample is shorter than its 20-second step interval, as in
V1. `--seconds` allows a smoke run; only 12 seconds is the reference.

CPU measures `process_time_ns` around `Display.receive`, `key`, `update`
and `render`. This matches V1's method boundary, but records actual process
CPU instead of method wall duration. It excludes warm-up, the server,
harness, protocol codecs, I/O pumps, terminal replay and sleeping. Thus
"door CPU/hour" means these measured door methods, not a whole native
process trace. CPU clock granularity is host-dependent. Wall render
latency is recorded separately; Windows per-frame CPU can be quantized.

The deterministic frame route records actual full/delta byte counts,
render wall time and update/render CPU, including each raw sample and
p50/p95/max. It rejects a run without movement or either output class.
The report identifies head, dirty state, host, interpreter, mechanics
hash, sample duration and call counts. Budget results (100 ms p95,
16 KiB per delta and 120 CPU seconds/hour) are recorded, not asserted:
P1 establishes the baseline, including existing misses. P5 owns render
improvements. The CI artifact `p1-shipped-door-baseline` is the hosted
Linux reference for its exact checked-out revision; local reports remain
host-specific. A green recording job does not mean all targets passed.

## Native scope in CI

Draft PRs changing only `door/`, text/art or palette/glyph content, with
supporting tests, run S04's registered native stdio door at 80x24 and
132x50 through Telnet, SSH and WebSocket. Scope is classified from the
trusted base revision. Missing classifiers, uncertain paths, non-draft
PRs and changes outside the allowlist retain the full existing matrix.
The ready-for-review transition explicitly runs the full matrix. P1's
own workflow/tools changes use the full matrix. No label skips checks.

[cp437]: https://github.com/Thiesi/Blacksite/issues/76#issuecomment-6483318963
