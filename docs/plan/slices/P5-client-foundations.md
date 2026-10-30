# P5 — Client foundations

**Status:** planned
**Primary model:** Codex (the plan's owner) · **Reviewer:** automated review, technical lead, presentation lead (co-reviewer and presentation gate)
**Depends on:** P0, P2, P4 (P3 for HERE) · **Milestone:** presentation track
**Issue:** https://github.com/Thiesi/Blacksite/issues/106

From `docs/plan/03-presentation-integration.md` §7.3 (P5), §10.1
(class C) and §11, adopted by the owner on 2026-10-28 (D-T1). The canon
is terminal UI §2 to §8 and architecture §5.5, merged in P0 (#81).

## Goal

One coherent new chrome for every view kind, behind a single client
switch that is off by default. Players see no change until P10's
cutover. Reviewers and playtests turn the switch on.

## Source

Port the presentation lead's trial modules from
`origin/design/presentation-v1` at commit `1060c9d` (#80's head; for
these modules it matches #73's). Plan §11.1 applies: the trial lands in
reviewed pieces, never by merging the design PRs. Porting the code does
not approve proposal #69. Where the trial and canon differ, canon wins,
and the PR lists each difference it resolved.

Port:

- `door/present/paint.py`: background roles, dimming, 16-colour reverse.
- `door/present/chrome.py`: frame by safety class, header segments with
  drop order, side panel sections and bars.
- `door/present/screen.py`.
- `door/present/context.py`: the context decider, a pure module driven
  by view bodies and a clock (plan §12.2 row P5). At `1060c9d` it is
  the Auto decider, choosing between the map, an F5 eye-level look and
  the scene view. P5 ports no scene or street renderer, and Auto's rules
  stay provisional until PT1 (D8). So in P5:
  - port it with its tests, allowed to select only the zone map;
  - bind no F5 or F10 key;
  - mark its rule order and its `HOLD` constant provisional in the
    module docstring.
- `door/present/zone.py`: the zone renderer, rule layer only. There are
  no place records until P6.
- The matching parts of the trial's `tests/door/test_present.py`.
- A trimmed `door/present/__init__.py`.

Do not port `lit.py` (P6), `lattice.py` (Lattice drawing is excluded),
`street.py`, `scene.py`, `inspect.py` (later paradigm slices), or any
ambient or `Toast.full` code (P8).

## Scope

- **The switch.** One client switch covering every view kind (plan §7.1
  principle 3, D-T5). It is off by default. Each sysop sets it per door
  launch, and the old renderers stay untouched. There is no protocol
  field, because client and server ship together. Do not bring over the
  trial's F9 key (plan §11.3): F9 opens services at a public terminal.
- **Chrome,** drawn from P2's `Layout` and chrome entry points. There is
  no second geometry.
  - Palette background roles and dimming.
  - The frame by safety class, and the hit flash on the frame.
  - Header segments with their drop order.
  - Side-panel sections and bars.
  - Log gutters, line coalescing and the XP merge, keyed by P4's log
    `kind`.
  - 16-colour reverse.
  - Full-width text views.
- **New chrome for** menu, text, dead, Wake and title screens, and the
  talker menu S27 added (`kind: talker`).
- **The zone renderer replacement** (`door/present/zone.py`), drawing
  the rule layer from the existing view.
- **The hint row stays P3's.** Its fitter and its order (prompt, channel,
  objective, E/J, help; canon UI §11) are the reference. The new chrome
  hosts that output and does not redraw or reorder it.

## Corrections the port must make

1. **Walls follow terminal UI §2.2,** the canon merged in P0, not plan
   §11.2's earlier note.
   - At 256 and truecolour, a wall face is a blank cell on the facade
     background, and a roof is blank near black.
   - At 16 colours a wall face is `█`.
   - Walkable and blocked ground differ by shape: a floor tile beside a
     wall face always carries grain, even in a theme whose ground is
     otherwise bare.
   - Check the trial against this table and correct any difference. Do
     not bring in a wall glyph that canon doesn't have. Shaped walls at
     256 and truecolour would need a canon change and the owner's
     approval first.
2. **No trial key** (above).
3. **No second hint row** (above).

## Out of scope

- Place records, themes, looks and charting. These are P6.
- Lattice drawing (P7), ambient emission (P8), and the City Map view.
- Flipping the default, and removing the old renderers. These are P10.
- Any server, rule or protocol change. If the port needs a server field
  that P4 did not supply, stop and ask; do not add it here.

## Budgets

These are measured with P1's harness (`scripts/presentation_baseline.py`,
`v1-provisional`, hosted Linux reference), switch on against switch off,
on the same workload and the same knowledge state.

- **Asserted:** render p95 at most 100 ms, and every delta frame at most
  16 KiB, at 80x24 and 132x50 in all three tiers.
- **Recorded, with a verdict:** door CPU against the 120 CPU s/h target.
- **Fully known ground.** A 132x50 walk with every viewport cell already
  known must also be measured.
  - Charting arrives in P6, but P1's TR-1 found that fully known ground,
    not the renderer, roughly doubles CPU: about 6.7 to 8.2 CPU s/min
    walking on the shipped renderer.
  - P5 must report the new renderer in that state, so P6 starts from a
    known cost.
- **If the new renderer is worse than the old one** in the same state,
  that counts as a finding, unless the PR explains and justifies the
  difference.

## Tests

- Style goldens for each view kind at 80x24 and 132x50, in three tiers,
  with a wide-character handle, with the switch on.
- With the switch off, every existing glyph and style golden stays
  byte-identical, and so does the P1 mechanics fingerprint.
- Contrast floors in every tier.
- §2.2's render test: no bare floor cell borders a wall face, in every
  tier and theme, for every opaque tile class. Wall faces and roofs
  match §2.2's terrain table in each tier.
- The context decider is pure: the same bodies and clock give the same
  result, and it never reads `zone.rng` or the wall clock directly.
- With the switch on, every walk-golden input makes the decider select
  the zone map.
- The hint row under the new chrome matches P3's fitter output for the
  same view.
- There is no second copy of layout geometry, focus or palette lookup
  (plan §10.2 item 5). P2's no-other-width test still passes.

## Acceptance

Class C (plan §10.1).

- Automated review, then technical review.
- The presentation lead's creative sign-off. They co-review the PR.
- **Real terminal, switch on:** NetBBS Telnet at 80x24 and 132x50, in 256
  and 16 colours, with a wide-character handle (plan §10.3). Walk the
  Wake, the Wake Hall and Meridian Plaza, fight
  the training drone, and open inventory, contracts and help.
- **Captures:** text and style captures of each step, committed under
  the evidence rule (technical review §4).
- **Presentation criteria:** §10.3 items 2 (partly), 4 and 8, on those
  hub zones without place records. The presentation lead checks these.
- The full native matrix stays green with the switch off.

No human gate is granted by P5. S25's human layout approval stays
withheld.
