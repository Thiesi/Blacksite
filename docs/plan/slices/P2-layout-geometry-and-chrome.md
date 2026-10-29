# P2 — Layout geometry and chrome

**Status:** in progress
**Primary model:** Sonnet · **Reviewer:** automated review, technical lead
**Depends on:** P1 · **Milestone:** presentation track
**Issue:** https://github.com/Thiesi/Blacksite/issues/93

From `docs/plan/03-presentation-integration.md` §3.4, §4 Refactors 1 and
3, and §7.3, adopted by the owner on 2026-10-28 (D-T1). The canon is
architecture §5.5.1.

## Goal

One layout geometry for client and server, and one chrome module. This
removes obstacles 1 and 3 so that later presentation slices can change
the screen in one place. Nothing on screen changes.

## Scope

- A pure layout module that computes named rectangles (header,
  viewport, side, log, hint, text area, overlay) from terminal size and
  a layout tier. Only the current tier is defined.
- `door/layout.py`, the server camera (`server/views/zone_view.py`) and
  every server-side width import it. The known copies are in plan §3.4:
  - the Wake briefing;
  - City Map pages;
  - contract panels;
  - encounter text;
  - private-core text;
  - the client menu page size.

  Find and convert any further copy, and list it in the PR.
- A chrome module draws the frame, header, side-panel shell, log and
  hint from `Layout`. View renderers draw only their content
  rectangles.
- A test that no server module computes a width from the terminal size
  outside the shared module (architecture §5.5.1).

## Out of scope

- New layout tiers, the dashboard, and full-width text. Those belong to
  P5 and later.
- Any visible change.
- Any protocol field. Client and server ship in one package.

## Tests

- Every glyph golden and every P1 style golden is byte-identical, in
  all three colour tiers. "Tier" here means colour tiers, not layout
  tiers, of which P2 defines only one. There is no rebaseline.
- The P1 mechanics fingerprint is unchanged.
- The no-other-width test fails on a deliberately added copy in a
  scratch module.

## Acceptance

Automated review and technical review. The full native matrix stays
green. Because nothing is meant to change, any golden difference is a
defect, not a rebaseline.
