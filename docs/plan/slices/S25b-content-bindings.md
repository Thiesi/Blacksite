# S25b — S25 content bindings and generator fixes

**Status:** planned
**Primary model:** Astra · **Reviewer:** automated review, technical lead
**Depends on:** S25a · **Milestone:** M5
**Issue:** https://github.com/Thiesi/Blacksite/issues/78

Split from S25 ([PR #66](https://github.com/Thiesi/Blacksite/pull/66)) by
D-T2 (`docs/plan/03-presentation-integration.md` §14). S25's human layout
approval stays **not granted**. This slice may ship maps that work, but
it does not claim their layout is approved; that is S25c's gate.

## Goal

Ship the city's working content (vendors, banks, cores, relays,
services, NPC profiles, homes) on maps that are correct and honest, and
fix the generator faults the technical review of #66 found, so that
S25c redoes geometry on a sound generator.

## Scope

- The 24 maps from #66, produced by `scripts/build_city_content.py`,
  with the content bindings from #66.
- Fixes from the technical review of #66
  ([record](https://github.com/Thiesi/Blacksite/pull/66#issuecomment-6401874198)):
  - **TR-1:** non-hidden exits use the exit tile (`>`); hidden exits
    draw as floor. Test: every non-hidden exit tile has the exit tile id.
  - **TR-4:** every door stands in a wall line and separates two
    regions; a validator rule enforces it. Re-run the Citadel lockdown
    case and assert it blocks a real route. Route credentials count as
    working only after this passes.
  - **TR-5:** S08 hubs are excluded from automatic wall cutting.
    Restore Core Precinct's west walls and Clinic Row's partition and
    the hubs' hardware names. Hub geometry changes go through C1 or
    S25c under D-T3's per-zone gate, not here.
  - **TR-6:** Shaft Foot's cage lift is a lift, not a hazard; the season
    console and the Halvard marker stand where the gazetteer puts them;
    Ring 4's artifact names match their sides (with a test); the Drop's
    hidden exit is inside a south-row house.
  - **TR-7:** the native matrix is green at the head, or each failure is
    explained from its artifact.
  - **TR-8, TR-9:** a load-tolerant timing bound for the hub validation
    test; the arrival toast wraps or uses the log at 80x24.
- Landing's `tramyard-wall-gate` exit is restored, unless the PR records
  a reason the owner accepts.
- The Outworks core's tier 5 is listed in the PR with its reason for the
  owner's decision. Until decided, keep the base tier.
- Three new vendors, checked against the gazetteer in review.

## Out of scope

- Location identity and room geometry (TR-3): S25c, after H1.
- Engine changes (S25a).

## Acceptance

Technical review per `docs/plan/04-technical-review.md`, plus the
acceptance steps of S25 that do not judge layout. The human layout
approval is not requested here.
