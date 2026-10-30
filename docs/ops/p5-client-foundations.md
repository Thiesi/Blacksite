# P5 client foundations

P5 ports the rule-layer presentation from trial
`1060c9df2ac6b140db932b4e888989d192502b20`. The integration base is
`22d4971fbc49aebc3553552e6a3f21c939cdaab8`, after the owner's merges of
the wall clarification (#108) and hint polish (#109).

## Launch switch

Set `DOOR_BLACKSITE_PRESENTATION=1` in the registered native door's launch
environment to enable P5. Leave it absent for the existing renderer.
The default is off. The switch covers every view kind, nested Wake
screens, dialogue menus and local help. There is no toggle key or
protocol field. F9 retains public-terminal services; F5, F7 and F10 gain
no presentation binding.

NetBBS's frozen profile contract permits custom environment keys only
under `DOOR_*`; the launch variable uses that namespace.

The client and server must use the same package, as before. This changes
no gameplay rule, simulation, persisted data, view contract or geometry.
The palette adds roles without changing existing role values. Both paths
use P2's `blacksite.layout`, P3's focus and hint fitter, and the existing
palette lookup and cell buffer. The old content renderers remain intact.
Text uses an additional full-width rectangle computed in the shared
layout; server pagination and existing rectangles remain unchanged.
Local help and disconnected screens keep the last server-reported body
safety; opening a local screen does not imply safe ground.

## Trial corrections

Canon is UI sections 1, 2, 4 and 11 and architecture section 5.5.
The [technical answer](https://github.com/Thiesi/Blacksite/issues/106#issuecomment-6524134331)
and [HERE addendum](https://github.com/Thiesi/Blacksite/issues/106#issuecomment-6524153930)
resolve the preflight differences without changing canon or server data.

| Trial behavior | P5 behavior |
|---|---|
| Walls depend on trial looks | UI 2.2: blank facade faces at 256/truecolor, `█` at 16; near-black blank roofs. Generic floor has grain; remembered floor retains grain beside opaque structure. No authored place themes yet. |
| Trial renderer/view keys | One default-off launch switch; no added key or intent. |
| Trial hint painter fits its own groups | P3 fits once; the new chrome draws its exact output, including prompt/channel priority. |
| Actor shape from trial `kind`; jacked is reverse | P4 `glyph_id`, presented `class` and `jacked`; own registered shape, dim while jacked, never reverse while jacked, including hostile bodies. You and hostiles otherwise retain reverse. NEARBY/CREW name jacked state. |
| Log classification from channel/text | P4's declared `kind`, `speaker` and `speaker_role`; canon gutters. Notices remain on P4's toast surface. |
| Cross-kind identical text can merge | Only identical same-kind lines coalesce within ten seconds. Reward lines merge within five seconds, retaining XP totals and other reward text. |
| New log lines can displace immediate danger | Recent danger/combat rows retain visible capacity for ten seconds after delivery, measured by the injected client clock. When protected rows themselves exceed capacity, newest protected rows win. |
| Auto infers threats and chooses other paradigms | Pure provisional map-only decider, no threat input, scene/look or clock read. Other Auto views need a later server contract. |
| HERE scans objects and exits | Only P3 focus/jack-focus labels and adjacent cover classes in nonnegative, sight-masked view tiles. No memory lookup, object/exit scan or hidden-exit inference. |
| Trial geometry and role lookup | Shared P2 rectangles and Palette lookup, including bounded background-role cache keys. No trial deep-camera formula. |
| Global dim-colour cache | Immutable xterm table and per-client Paint style cache. |

Lattice drawing remains the existing renderer until P7; its outer chrome
uses P5. Place records, themes, charting, street/scene/look rendering,
ambient emission, place cards and `Toast.full` are not ported.
Lattice control-label sentence case stays with P7. P3 focus-cost work
stays with S29.

The rule layer resolves each disclosed terrain index once per frame and
reuses its seen/remembered style. Cardinal-neighbour checks read those
resolved IDs. This removes repeated work on fully known ground; the P5
glyph/style goldens remain unchanged.

## Validation and acceptance

The new headless style goldens cover title, text, dead, menu, talker,
Wake, zone and Lattice at 80x24 and 132x50 in 16/256/truecolor, with a
wide-character handle. They live separately under
`tests/presentation/golden/p5`; the existing goldens are unchanged.
Regenerate only after reviewing a deliberate P5 presentation correction:

```
pytest tests/presentation/test_client_foundations.py --update-goldens
```

Run `pytest` at the root for regression checks, including the existing
off-path glyph/style goldens and P1 mechanics fingerprint. The new tests
also check wall/roof treatment, contrast in all palette variants,
adjacent grain for every shipped opaque tile class, jacked-hostile
precedence, HERE disclosure, map-only context, unchanged keys and the
hint row.

The first contrast floor uses a normalised mean sRGB step of at least
0.08 between ground and facade backgrounds at 256 and truecolor. The
16-colour gate checks the distinct floor/wall shapes. Palette variants
are all checked; P5 does not introduce place themes.

`scripts/presentation_p5.py --output PATH` compares switch off/on on
P1's `v1-provisional` closed-walk workload, with the same seeds, normal
NPCs and initial knowledge. It additionally measures fully known 132x50
terrain in both arms. That explicit knowledge fixture belongs only to
the budget workload; it is not charting or native play evidence.

Frame assertions are render p95 at most 100 ms and delta output at most
16 KiB. The script records CPU against 120 CPU s/hour and whether the new
path is worse. The reference is hosted Linux at twelve real seconds per
activity; short runs and Windows process-CPU totals are diagnostic only.
Any regression needs a measured explanation in the PR.

For native acceptance, build a clean committed wheel and install it into
an isolated interpreter. With NetBBS v7.45.0 installed for the runner:

```
python scripts/accept_p5_netbbs.py --root PATH --door-python PYTHON --size 80x24 --show
```

This runs ordinary Wake creation, a live training-drone fight, walking
through Wake Hall and the Clinic to Meridian Plaza, inventory, contracts
and help. The Blacksite character name contains a wide character entered
through ordinary creation. Released NetBBS account names are ASCII-only,
and its door API uses that username as `handle`: no wide BBS handle can
be tested natively without bypassing the host's supported contract. The
headless cases still exercise a synthetic wide BBS handle. This native
acceptance distinction is
[accepted for P5](https://github.com/Thiesi/Blacksite/issues/106#issuecomment-6526049298).
Short native test names keep the wide name and differing ASCII handle
visible together in full at 132x50. The live packet covers both sizes
in 16 and 256 colours as well as truecolor.
Both sizes run in all three tiers. The script registers the
default-off switch explicitly for this private node, verifies the new
safe frame and the installed wheel's Python tree, and records text,
style, ordered ANSI and hashes at each step. It changes no position,
inventory, funds, NPC, rule or clock state.

Resize the attached terminal to the selected size. Run a second packet
with `--size 132x50` after resizing. The receipt records the attached
terminal dimensions and checks them against the selected size.

The P5 Actions workflow runs this acceptance with `--show` through a
sized, attached Linux PTY, retaining the console stream and native
captures as artifacts. The full existing native matrix remains the
switch-off check. Neither workflow grants visual, creative or human
acceptance. The presentation lead co-reviews P5; the owner alone merges.
S25 layout and the full S27 human/presentation gates remain held.

The committed [native review packet](captures/p5-client-foundations/README.md)
contains all 48 untrimmed text captures, original capture hashes, attached
terminal receipts and the exact execution head. Raw ANSI and large style
snapshots remain in the linked CI artifacts. The packet records the wide
character-name / ASCII BBS-handle distinction and verifies both fields in
the same pinned row at 132x50. It grants no creative or human approval.
Those captures retain their actual v7.31.0 provenance. Following the
technical lead's floor-change notice on #82, P5's new native workflow now
pins v7.45.0; its fresh results are reported separately on PR #110. The
floor/canon PR #111 must be owner-merged before it is used as a new base.
