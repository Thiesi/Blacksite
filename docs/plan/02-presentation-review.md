# Player-facing presentation review

Status: review required. [Issue #68](https://github.com/Thiesi/Blacksite/issues/68).
S25 human layout approval is **not granted** following the user's review
on 2026-10-24. This brief records the hold and review scope. It adopts no
new visual design or gameplay rules.

## The reported problem

The supplied terminal material is not sufficiently comprehensible for a
meaningful human design review. Undifferentiated floor characters,
isolated symbols and large empty areas do not communicate recognizable
locations. The City Map supplies lists rather than useful geographical
context. The user cannot assess coherence, navigation, atmosphere or
enjoyable exploration, or recognize the written Shaft Foot and Far Ring
in the presented environments.

This affects the connection between Blacksite's world and the caller's
experience across the project. It is not confined to decoration in two
zones. S33 district art is not assumed to solve it.

Preserve the simulation, gameplay mechanics, engineering fixes and
retained evidence. Do not undertake an ad hoc visual overhaul or silently
revise canon. Passing content validation, navigation tests or mechanical
acceptance does not establish acceptable visual design.

## Separate comprehensive review

Review the candidate implementation against the [world bible](../world/00-bible.md),
[Gazetteer](../world/01-gazetteer.md), [terminal UI](../design/03-terminal-ui.md)
and [asset specification](../design/04-assets.md), in canon order.

The review must:

- Trace where location identity is lost between the written place,
  spatial authoring, camera/scale, rendering and geographical overview.
- Examine local views, landmarks, paths, thresholds, structures, empty
  space, symbols, colour roles and information hierarchy. Include the
  relationship between the physical city and Lattice views.
- Cover the ordinary districts, using Shaft Foot and Far Ring as concrete
  cases. Establish what a caller can recognize and understand at 80x24
  and 132x50, with wide names and the supported palette variants.
- Review the materials used for human approval as well as the actual
  terminal. Provide representative colour captures and understandable
  geographical context alongside the relevant worldbuilding. Plain-text
  extracts and engineering receipts alone are insufficient.
- Propose a coherent direction with reviewable examples and explicit
  human acceptance criteria. Identify any proposed canon/spec changes
  and their reasons; do not treat proposals as adopted changes.
- Identify the work owned by S25, S27, S30, S31 and S33, rather than
  assuming isolated map edits or an art pack settle the problem.

Implementation of a new presentation direction follows that review.
Renewed layout approval requires an explicit user review of material
that supports a meaningful judgment. Automatic code review cannot grant
the withheld human approval.

## Independent acceptance work

| Work | What may continue | What it cannot establish |
|---|---|---|
| Existing simulation and persistence | Determinism, storage/reconnect, transactions, fairness, security and data-integrity checks | Acceptable visual design or enjoyable exploration |
| Existing native mechanics | Purchases, source custody, work orders, allocations, permissions, payment and return receipts | Comprehensible routes, atmosphere or layout approval |
| Performance and packaging | Startup/tick measurements, repeat samples, wheel/source/content identity, archive hashes and CRC | Human product acceptance |
| Backend dialogue/referrals | Committed facts, prerequisite checks, consent, reward ownership and atomic introductions | Approved dialogue presentation or NPC placement |
| Terminal correctness | Width, corner, glyph, protocol and input-dispatch tests | Legibility or a recognizable world |
| Factual pacing measurements | Record travel/earning costs and times with fixtures disclosed | A verdict that the loop is entertaining or suitably paced |

Hold visual-design and navigation-comprehension sign-off, new map,
renderer, overview, NPC-placement, onboarding or art direction, and
presentation-dependent usability/pacing judgments. S25 cannot complete
or merge around its missing approval. Dependent season/release
completion must retain that gate. Backend work is subject to each
slice's existing merged dependencies; this classification waives none.

## Preserved engineering checkpoints

At S25 code/content commit `1224c3007069391a8fa341e01b08bcc0b8a7b752`,
root CI passed 1573 Linux tests and 1572 Windows tests plus one skip.
The native workflow completed 65/65 jobs. These are engineering results,
not visual or human acceptance. Local installed-wheel native cases
passed at 132x50 (Relay Zero reserve, real gate activation/walking,
2.485-second startup) and 80x24 (Sump common, 2.547-second startup).
Fixtures and remaining acceptance scopes are retained in
[the acceptance record](../ops/s25-acceptance.md) and
[PR #66](https://github.com/Thiesi/Blacksite/pull/66).

S27's separate branch preserves unfinished dialogue/referral work.
Focused tests cover its backend behavior, input/rendering correctness
and combat/safety invariants. Its caller-facing completion and spatial
placement remain on hold; no full-slice or visual acceptance is claimed.

The original captures and failed attempts remain evidence. They are not
an approval package that has been accepted by the user.
