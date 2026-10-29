# P1 — Verification foundation for presentation work

**Status:** in progress (CP437 acceptance decision pending in #76)
**Primary model:** Sonnet · **Reviewer:** automated review, technical lead
**Depends on:** none · **Milestone:** presentation track
**Issue:** https://github.com/Thiesi/Blacksite/issues/76

From `docs/plan/03-presentation-integration.md` §7.3 and the budgets in
§13.5, adopted by the owner on 2026-10-28 (D-T1).

## Goal

Make presentation changes measurable before any is made: what a change
draws, what it costs, and proof that it changed no game rule.

## Scope

- A golden regeneration flag.
- Style-aware goldens (glyph plus normalised style grid) for every
  existing golden, per colour tier, with a glyph-tier axis ready for V2.
- A mechanics fingerprint: a rule projection in world coordinates (tile
  ids, passable, opaque, cover, hazard, exits, object tiles per zone and
  sector) plus a scripted walk's rule fields, with harness seeds keyed
  by zone id and NPCs isolated.
- Baselines of bytes per full redraw and per delta at 80x24 and 132x50
  in three tiers, and a CPU-per-frame measurement for the door, so V1's
  budgets (step picture 100 ms p95, 16 KiB ceiling) have a harness.
- Shipped-door CPU per hour at both sizes under `v1-provisional`, per
  the [technical lead's addition][cpu]. Existing misses are baselined;
  P5 owns render optimizations.
- A CP437 round-trip check on every rendered golden cell (CP437 column
  only, per UI §1).
- A headless review packet builder: per-frame `.ans`, `.txt` and
  context JSON; optional PNG from a script outside the test path. This
  is also the capture source for the H5 owner look pass.
- A door-path native subset for PRs that touch only `door/` or content
  presentation; the full matrix stays for ready-for-review and merge.

## Out of scope

Any rendering or rule change.

## Tests

The tools test themselves. One deliberate rule change in a scratch
fixture must fail the fingerprint; one deliberate colour change must
fail a style golden and not the fingerprint.

## Acceptance

Automated review and technical review.

The existing authored U+2506 and wide caller fixture U+754C fail the
strict CP437 check. The [scope decision][cp437] remains pending; no
rendering correction or acceptance exception is part of this work.
Commands and evidence boundaries: [verification guide][guide].

[cpu]: https://github.com/Thiesi/Blacksite/issues/76#issuecomment-6478100282
[cp437]: https://github.com/Thiesi/Blacksite/issues/76#issuecomment-6483318963
[guide]: ../../ops/presentation-verification.md
