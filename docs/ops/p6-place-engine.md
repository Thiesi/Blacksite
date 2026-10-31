# P6a place engine evidence

P6a implements the engine on test content. It installs no shipped theme,
look, charted flag or public rectangle. P6b is a separate content PR.
The presentation switch remains off by default.

## Scope and contracts

- Themes use the prototype's `themes.json` envelope, merged by theme id.
  Looks retain `id` matching their zone filename and replace by that id.
  Both support `content.local`. Ambient is stored and checked, never
  transmitted or emitted. Places, scenes, lights and `lit` are deferred.
- Public rectangles accept `[x,y,w,h]` and named coordinates. Pockets
  retain their old format with an optional `charted` flag. The mechanics
  projection omits default-false pocket flags and absent zone data. It
  includes populated zone flags, public rectangles and charted pockets.
- The validator rejects public regions; it never trims them. Flooding
  starts at unrestricted exits and spawn, with hidden exits, required
  exits, lockable doors and housing interiors removed.
- The server sends a template-terrain chart without memory writes.
  Looks contain resolved theme roles; grain regions are clipped into
  known row rectangles. Rings and text require their whole footprint.
  Names refer only to visible tile classes within the transmitted view.
  Ambient, undisclosed geometry and whole-piece origins are withheld.
- The existing revision/delta store suppresses unchanged looks. Server
  caches belong to a caller's perception; client caches belong to Paint.
  Mask-cache keys use the existing sight/grid and chart revisions; misses
  inspect only the published viewport, never the whole remembered map.
  No mutable global cache or simulation RNG is used. Non-ground tiles
  reuse P5's glyph, role and attribute rules before re-grounding colour.
- At 16 colours UI 2.2 maps floors to black and walls to grey blocks.
  Contrast and person lifting use that actual mapped ground. The
  higher tiers use each theme/region ground, including `_light` people
  roles. Jacked ANSI bodies retain UI 2.2's explicit dark-grey rule.

## Golden exception

The lead's [clarification on #115](https://github.com/Thiesi/Blacksite/issues/115#issuecomment-6536245124)
allows the six P5 zone goldens to change only in HERE rows and a header
row sharing a notice. `scripts/p6_golden_diff.py` decodes style runs and
asserts the six current changes affect only row 2, zero-based. The map,
hint, all other cells and every other existing golden stay unchanged.
No mechanics baseline regeneration is part of P6a.

## Reproducing checks

Run from the repository root with Python 3.12 and the test extra:

```
pytest -q
python scripts/p6_golden_diff.py --output here-row-diff.json
python scripts/presentation_p6.py --output charted-budget.json
```

`presentation_p6.py` uses P1's unchanged Meter, activities and provisional
mix. Its paired arms share a charted synthetic terrain fixture, palette,
object/exit bindings, visibility, keys and moves. One arm uses P5's
generic drawing and one uses P6 looks. Doors, private floors and hidden
exits are excluded from its validated public rectangles. Its CPU result
is a fixture comparison, not a replacement for the shipped P5 workload.
The existing P5 workflow still runs that workload. P5's final reference
is run 41126237721: 93.4 / 87.1 / 99.3 CPU s/h at fully known 132x50
(16 / 256 / truecolor). Regressions require an explicit verdict.

The P6 workflow separately records look payload bytes at first send and
during a real headless revision/delta walk. It asserts ANSI delta size
and render latency, and records CPU against 120 CPU s/h on hosted Linux.
The 132x50 cases include a fully explored large zone as well as charted
ground without seeded memory. A short local Windows run is diagnostic
only.

## Native fixture captures

The P6 workflow checks out NetBBS v7.45.0 and installs a source-matched
Blacksite wheel in a separate venv. Each size/theme job runs all three
tiers under an attached, sized PTY through a registered native stdio
door and Telnet node. `accept_p6_netbbs.py` uses test-only content.local
and explicitly places the freshly created caller in that fixture.
Walking afterwards uses ordinary keys. This is not a shipped-place
walk. Captures cover charted ground, dark/light regions, HERE labels
`Public terminal (Plaza)` / `(Clinic)` at 80 columns, and a header notice
beside the zone name. The result records execution head, wheel source
hash, fixture policy and SHA-256 hashes of the captured bytes.

The full switch-off native matrix remains required. Automated review,
technical review and the presentation lead's fixture sign-off remain
separate gates. No capture grants H1, P6b fingerprint approval or S25
human layout approval. All three remain withheld.
