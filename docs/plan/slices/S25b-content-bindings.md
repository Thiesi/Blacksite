# S25b — S25 content bindings and generator fixes

**Status:** in progress (engineering; district layout gates remain held)
**Primary model:** Sonnet · **Reviewer:** automated review, technical lead, owner (layout)
**Depends on:** S25a · **Milestone:** M5
**Issue:** https://github.com/Thiesi/Blacksite/issues/78

Split from S25 ([PR #66](https://github.com/Thiesi/Blacksite/pull/66)) by
D-T2 (`docs/plan/03-presentation-integration.md` §14). S25's human layout
approval stays **not granted**.

**Merge gate.** Work on this slice starts now, but its maps do not merge
around the layout hold (2026-10-24). A district's maps merge only with
the owner's layout approval for that district: H2 for the pilots, H3
for the rest. In practice S25b merges district by district together
with S25c. Content bindings inside the existing S08 hubs may merge
earlier, in their own PR.

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
  - **TR-4:** route-bearing doors stand between impassable neighbours
    on one axis, with passable tiles on the other. This is the chosen
    cheap deterministic load-time check from the [scope decision][doors].
    It covers `door`, `gate` and `shutter` targets of core controls,
    objects marked `control`, `open`-credential latches, and doors on
    required exits. Decorative doors are excluded by behaviour.
    Only the seven known `(zone, object)` debts in #92 produce named
    C1 warnings under D-T3. Every new violation is an error, including
    new doors inside S08 hubs. Re-run the
    Citadel lockdown case and assert it blocks a real route. Route
    credentials count as working only after this passes.
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
- Preserve the existing S08 apartment doors and 36-cell Terraces sector.
  The 24 physical homes and 48-cell sector expansion move together to
  C1/S25c under D-T3 ([housing decision][homes]). The S23 Terraces-home
  field receipt is a deferred acceptance item owned by S25c.

## Out of scope

- Location identity and room geometry (TR-3): S25c, after H1.
- Engine changes (S25a).

## Acceptance

Technical review per `docs/plan/04-technical-review.md`, plus the
acceptance steps of S25 that do not judge layout, and the owner's layout
approval for each district before its maps merge.

The engineering PR holds the generated 34-zone tree as a review
artifact; it changes no shipped map or content file. After the owner
merges #97, record engineering done, with generated content publishing
per district with S25c under H2/H3.

Deferred to district publication with C1/S25c:

- TR-4 route proof on the real district maps, beyond the wall-axis
  invariant and the engineering Citadel probe.
- The 24 homes, 48-cell Terraces register and S23 Terraces-home receipt.
- Per-map Undercity sight assertions against the canon, including the
  distinct 4/3/6/10 values; no global Undercity-radius substitution.
- H2/H3 owner layout approval for each district.

[doors]: https://github.com/Thiesi/Blacksite/issues/78#issuecomment-6491134281
[homes]: https://github.com/Thiesi/Blacksite/issues/78#issuecomment-6491941496
