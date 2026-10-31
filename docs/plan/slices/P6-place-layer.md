# P6 — Place layer and representative locations

**Status:** planned
**Primary model:** Codex for P6a (engine) · the presentation lead for P6b (content), with Codex assisting · **Reviewer:** automated review, technical lead, presentation lead (co-reviewer and presentation gate)
**Depends on:** P0 (D1 to D3 in canon), P4, P5 · **Milestone:** presentation track
**Issue:** https://github.com/Thiesi/Blacksite/issues/115

From `docs/plan/03-presentation-integration.md` §7.3 (P6), §10.1
(class C; P6b also carries the human gate H1) and §11 notes 5 to 8,
adopted by the owner on 2026-10-28 (D-T1). The canon is:
- entities §1.1 (`charted`, `public`, pocket regions) and §1.21 (themes and looks);
- architecture §5.4 (view fields), §5.5.4 (disclosure), §5.5.5 (charted public ground) and §5.5.6 (rules never read presentation);
- terminal UI §2.2 and §2.3.

P0 (#81) merged this canon. Where this file and canon differ, canon
wins.

## Goal

Prove the direction in live play. The new chrome from P5 draws real
places: authored ground, walls, signs and floor marks over the
unchanged rule layer. Three representative zones show their public
layout on arrival. The owner judges those three zones at H1.

## Two parts

P6 lands as two PRs, in order.

- **P6a, engine.** Formats, validator, server masking, view fields and
  client drawing, proven on test fixtures. It adds no shipped theme or
  look and flags no shipped zone, so the shipped game, the switch-off
  output and the mechanics fingerprint stay unchanged. It is class C,
  with a creative check of fixture frames only, and can merge under
  technical review §7.1.
- **P6b, three places.** `themes.json`, the looks, the `charted` and
  `public` data, and spawner spread for Meridian Plaza (`core-plaza`),
  Clinic Row (`vatside-clinics`) and Sodium Row (`sodium-row`). Its
  gate is **H1** for these three zones, and the owner approves the
  fingerprint move in the PR. The owner merges P6b; §7.1 does not
  apply.

## P6a scope (Codex)

1. **Zone data (entities §1.1).**
   - Add `charted` (bool, default false) and `public` (a list of
     `Region`) to `ZoneMeta`.
   - Pockets become regions with `charted` (bool, default false). Old
     sidecars without these fields load unchanged.
   - Add `charted`, `public` and pocket `charted` to the mechanics
     projection (`tests/presentation/mechanics.py`) for zones that set
     them. With no zone set, the fingerprint must be byte-identical.
   - `lit` is **not** part of P6. It is a sight rule (game design 5.2,
     owner decision V0-3). It lands top-down, game design first, in the
     slice that first draws pocket scenes.
2. **Themes and looks (entities §1.21).**
   - Schema and loader for `themes.json` and `looks/<zone-id>.json`,
     including `content.local` overrides, which merge by id as palette
     roles do.
   - Every field in §1.21: `theme`, `regions` (`rect` or `circle`),
     `signs`, `marks`, `glints`, `names` and `ambient`.
   - `ambient` is validated and stored, never emitted: emission is P8.
   - Places, viewpoints, lights and set pieces are not in this record.
     They are V3.
3. **Validator.** The validator checks by tile **class** (opaque,
   passable, water, hazard), never by tile id (plan §11 note 8). It
   enforces:
   - every theme and role exists;
   - signs sit on wall-face tiles and use dressing letters only;
   - marks lie on plain passable floor;
   - glints lie on water;
   - no look glyph is a rule glyph (UI §2.2);
   - 16-colour backgrounds are 0 to 7;
   - ambient lines follow the voice rules;
   - **contrast, from each theme's own ground:**
     - Every band floor (`paint.BAND_STEP`; structure, things and
       people) is measured from the drawn ground of each theme **and
       of each region**, after tier mapping, not from black.
     - A light ground, from a `luma: light` theme or a light region
       role, is measured with `paint.light_distance`. Its people roles
       use their `_light` variants.
     - Any `_light` role P6 adds must exist in all three tiers and
       variants;
   - **signs are readable:** sign letters are a thing-band role and meet
     the thing floor against the wall face they sit on;
   - **charted (architecture §5.5.5):** the validator rejects any
     `public` region, or charted pocket rectangle, that:
     - contains a hidden exit or a passable tile next to one;
     - contains a passable tile reachable from unrestricted exits and
       spawn points only through a hidden exit, a required-pass exit
       or a lockable door;
     - overlaps a private interior (apartments, owner-door rooms);
     - belongs to an instanced zone.

     It rejects, never trims.
4. **Server.**
   - `zone_view` sends `charted` (the synthesised grid of legend
     indices for public-ground tiles in the viewport) and `looks`, per
     architecture §5.4.
   - Charting never writes the caller's memory. Nothing charted becomes
     remembered.
   - Looks follow architecture §5.5.4:
     - looks are sent only on known tiles (visible now, remembered or
       charted);
     - a partly known piece is clipped to its known tiles;
     - signs and other whole-only kinds are sent only when every tile
       is known;
     - `names` covers only tiles the caller may see;
     - nothing beyond what the view already discloses: no hidden exit,
       no object or actor without sight. Charted ground never reveals
       people, object state or hazards.
   - Byte cost: a look is resent only when its masked content changes.
     P6 must not add a full look to every delta.
5. **Client, new path only.**
   - `door/present/zone.py` draws the theme's ground and wall roles,
     the ground grain from `texture`, using a stable per-tile hash and
     never `zone.rng` or the wall clock.
   - It also draws regions, signs on wall faces, floor marks and glints.
   - At 16 colours, sign letters are drawn on the wall's background
     colour, never on `█` (UI §2.2: letter colour on black).
   - **People lift per ground.** `Paint` lifts a person role against the
     ground of the cell it draws on: the theme's ground, or a region's.
     The lift is cached per (role, ground), so there is still no
     per-cell LCh work. P5's non-raising fallback still applies.
   - Charted tiles are drawn as known (UI §2.3 dimming).
   - §2.2 still holds in every theme: a floor tile beside a wall face
     always carries grain, and walls follow the §2.2 tier table.
   - HERE uses `looks.names` for a visible adjacent cover tile when a
     name is sent, and otherwise P5's generic cover label. Each HERE
     entry leads with its thing's shape glyph (#114), for example
     `▒ barrels`, `+ Corridor door` or `» Clinic Row`. HERE still names
     only P3's focus and visible adjacent cover.
   - The header notice no longer shortens the zone name to `...` while
     cells at the right end stay empty (#114).
   - All colour goes through `Paint`, which already lifts people roles
     and falls back without raising (P5 TR-3).
   - The legacy renderer ignores the new fields.
6. **Fixtures.** Test-only themes and looks under `tests/fixtures` cover:
   - a dark theme and a light theme;
   - every look field;
   - a charted zone with a hidden exit, a gated room and a private
     interior next to its public region.

## P6b scope (presentation lead, with Codex assisting)

1. `themes.json` with the themes the three zones need.
2. `looks/core-plaza.json`, `looks/vatside-clinics.json` and
   `looks/sodium-row.json`, from the gazetteer.
3. `charted` and `public` data for the zones the presentation lead
   proposes to chart, among these three. That moves the mechanics
   fingerprint for those zones only. The PR lists the move, and the
   owner approves it there (plan §11 note 5).
4. **Charting proposal.** Meridian Plaza is charted (D1, #69 §8.1).
   The presentation lead proposes Clinic Row and Sodium Row in the
   same PR, listing each region against architecture §5.5.5, so the
   owner sees the whole fingerprint move in one place.
5. **Spawner spread.** Widen spawner regions so NPCs use the space, for
   example the Plaza civilians now held in x5 to 22, y3 to 8. This is
   content only. Spawner regions are not in the rule projection, so the
   fingerprint does not move for it. Walk and budget goldens that
   include live NPCs are regenerated and listed.
6. No geometry change. Room size, alleys and furniture-as-tiles belong
   to S25c under S25's withheld approval.

## Out of scope

- Geometry, other zones, and C1's hub records.
- Lights and the `lit` sight rule. These go to the pocket-scene slice.
- Places, fixed viewpoints and scene pieces (V3). The **private-interior
  viewpoint** is already settled in canon: a viewpoint never stands in
  a private interior (architecture §5.5.4). P6's charted validator
  makes the same private-interior check, so V3 can reuse it.
- Ambient emission (P8), the City Map (P9), and making the switch on
  by default (P10).
- Walking routes over charted ground (Auto's walks). These are not in
  `main`. When a walk feature lands, it routes only over the set the
  view sends (plan §11 note 9).

## Budgets

These are measured with P1's harness and P5's `scripts/presentation_p5.py`
method, switch on, on the hosted Linux reference.

- **Asserted:** render p95 at most 100 ms, and every delta frame at
  most 16 KiB, at 80x24 and 132x50 in three tiers. Report the look
  payload separately: its first send on zone entry, and its share of
  deltas while walking.
- **Recorded, with a verdict:** CPU against 120 CPU s/h, including a
  charted 132x50 walk.
  - P5's final fully known figures are the baseline: 93.4, 87.1 and
    99.3 s/h on the new path at 132x50 in 16, 256 and truecolor
    (reference run 41126237721). The earlier 73 to 80 s/h figures came
    before P5's last correction and are not the baseline.
  - A regression against P5 in the same state is a finding unless the
    PR explains it.

## Tests (P6a)

- Every validator rule, with a rejecting fixture for each. That
  includes each charted rejection, and a contrast failure on a dark
  theme and on a light theme.
- **Disclosure.** Using the fixture charted zone:
  - a look piece never appears on an unknown tile;
  - whole-only kinds appear only when fully known;
  - charted ground never shows actors, object state or hazards;
  - no hidden exit, nor the corridor behind it, is ever charted or
    named;
  - memory is unchanged after crossing a charted zone.
- Removing every theme and look changes no rule and no
  non-presentation view field (architecture §5.5.6).
- The fingerprint is unchanged for shipped content. A fixture zone
  flagged `charted` moves only its own projection entry.
- Style goldens of the fixture zone at 80x24 and 132x50 in three tiers,
  in dark and light themes. Band floors hold after the actual tier
  mapping, measured from each theme's ground and each region's ground.
- A person standing on a region ground lighter than its theme's ground
  meets the people floor against that region, and the lift is cached
  per (role, ground).
- Signs: the validator rejects letters below the thing floor against
  their wall face, and at 16 colours sign letters render on the wall's
  background colour, never on `█`.
- HERE leads each entry with its shape glyph, and the header notice
  keeps the zone name when there is room at the right end.
- §2.2's render test in every fixture theme: no bare floor beside a
  wall face.
- Grain is stable: the same tile gives the same grain across frames and
  runs, with no `zone.rng` or clock read.
- With the switch off, every existing golden and the hint row stay
  byte-identical.
- The P5 style goldens of zones without a look keep their tile drawing
  byte-identical. Only the rows that the two #114 corrections above
  change may move: the HERE entries, which gain their shape glyph, and
  the header, only where a notice shares it. Those goldens are
  regenerated in the P6a PR, which shows that no other row changed.

## Acceptance

**P6a:**
- automated review, then technical review;
- the presentation lead's sign-off from fixture captures;
- the full native matrix green with the switch off.

**P6b:**
- **Live walk.** Proposal #69's §8 walk, trimmed to P6's zones and
  extended to Sodium Row. It is reproduced live through NetBBS Telnet
  with the switch on, with no teleports and no local handle override
  (plan §11 note 6):
  1. Wake Hall to Clinic Row.
  2. In through a clinic to its public terminal, and back out. Jack in
     and out there; the Lattice frames are judged in P7.
  3. The boulevard outside the pharmacy (#69 §8.2).
  4. North into Meridian Plaza, stopping at its second public terminal
     (#69 §8.1).
  5. South through `to-sodium-row`, then east along Sodium Row to the
     Tin Halo door, without entering it. The Tin Halo interior is a
     separate zone, not part of P6b.

  Capture points, each at 80x24 and 132x50, in 256 and 16 colours:
  - the clinic interior after leaving it (known dimming);
  - the pharmacy frontage;
  - the Plaza terminal;
  - the Sodium Row entry;
  - the Tin Halo frontage.

  Text and style captures are committed under the evidence rule.
- **The presentation lead's sign-off.**
- **H1** by the owner for Meridian Plaza, Clinic Row and Sodium Row:
  - plan §10.3 criteria 1 to 7, judged by a reviewer who has not read
    the design;
  - the record names the reviewer, date, commit, terminal and
    transport.

  The Vatside sector part of H1 comes with P7.
- **Fingerprint approval.** The owner approves the fingerprint move for
  the charted zones in the PR.

No review, build or capture substitutes for H1. S25's human layout
approval stays withheld.

## Related work outside the slice

- **V1 measurements.** The presentation lead's V1 measurements (plan
  §13.7), now taken against the P5 frame. They come before the
  presentation lead's P6b sign-off and are attached to the P6b PR, so
  H1 sees them. They do not gate P6a, and they are not a merge gate.
- **#114 follow-ups.** HERE's leading shape glyph and the header notice
  width are in P6a (above). The tutorial line's length is server
  content and stays in #114.
