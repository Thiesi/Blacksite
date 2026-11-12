# S48 — The first evening: one whole evening of the real game

**Status:** planned (filed 2026-11-12; the owner merges the filing)
**Primary model:** Claude Opus 5.5 (the engineer) · **Lines and staging:** creative lead · **Layout and acceptance:** presentation lead · **Reviewer:** automated review, technical lead
**Depends on:** S44 (both PRs), P8 (the emitter for part 5), P12 (merged; the danger and fit rules part 5 tests against), the canon PR #219 (the Wake's new step order) and the opening design #220 · **Lands before:** S47 (S47 may start once this slice's PR merges; it doesn't wait for the H1 or novice sessions) · **Gate:** this slice's build is the **H1 session**
**Issue:** https://github.com/Thiesi/Karst41/issues/217

Canon: game design §4 (the Wake) and §9 (Vesper's first thing), the
bible, and plan 03 §10.3 (the H1 criteria). The Wake's step order
changes in #219, the canon PR that records the owner's 2026-11-12
decisions. The opening's staging is the approved design in #220
(`docs/design/proposals/first-ten-minutes.md`). This slice builds
against both and doesn't start before both merge.

**Geometry.** This slice changes no geometry: no wall, door or room
moves, in the Wake Hall or anywhere else. #220 meets "one obvious way
on" without moving a wall. If the evening needs a geometry change, it
becomes a finding for the technical lead, not part of this slice. Layout
belongs to S25c and its owner approval, which this slice doesn't grant.
Where this file and canon differ, canon wins.

## Why

An independent review on 2026-11-12 found that nobody has played one
complete evening of the actual game. S01–S24 merged in four days, and
every playtest since has been on the Row demo branch. On 2026-11-12 the
owner decided:
- this evening comes before S47;
- it is the H1 session;
- the novice tester plays it alone, so it includes a staged opening;
- the new presentation becomes the only renderer, in two steps, and
  this slice is step one;
- the Tenant's voice is tried here, as a small optional layer.

## Goal

A fresh caller, alone, plays one evening on `main` through NetBBS:
1. wake;
2. reach the Row;
3. take Vesper's first job and finish it both ways: by hand, and by
   jacking in;
4. get paid;
5. take one generated job;
6. die once;
7. log out.

They understand what to do at each step without being told. The owner
plays it first, then the novice. Everything after this slice is
re-ranked from what those two sessions show.

**Rule of the slice:** fix only what stops the evening or confuses a
first-time player. Add no new systems. Anything bigger becomes a finding
for the re-rank, not scope creep.

## Scope

### 1. The evening path

- Walk the path above on `main` and fix whatever breaks or dead-ends it.
  Include #216, the empty briefing page.
- Every hint line on the path fits at 80x24 (no cut-off `...` in a hint).
- Every symbol a first-time player has to use on the path can be
  identified on screen: a label, a look line, or the context line.
- The path works at 80x24 and 132x50, in all three colour tiers.

### 2. The opening as a scene

Game design §4, as amended by the canon PR:
- **You wake first.** The first screen is the vat room, and you can
  move.
- **Vantongeren speaks a line or two at a time,** in the log, while you
  move. The briefing texts are kept; they are staged, not rewritten,
  except where the voice pass changes them.
- **The room has one obvious way on.**
- **The archetype choice comes after** the drone and the terminal have
  shown what fighting and jacking in are.
- **The briefing pages get paragraph breaks** and use the frame's width.
- The Wake still completes in five minutes, and every lesson can still
  be skipped (§4).

The creative lead owns the lines and the staging. The presentation lead
owns the layout and accepts it from captures. Their voice pass also
removes rulings from the briefing and login lines. "Grade five can clear
the lease early" no longer holds under the calendar-only lease.

### 3. The new presentation by default (step one of two)

- The door client starts in the new presentation (`door/present/`) for
  every caller. Today it starts there only when
  `DOOR_KARST41_PRESENTATION=1` (`door/client.py:48`).
- The old renderer stays available as a fallback for this slice only,
  through the existing per-launch environment variable:
  `DOOR_KARST41_PRESENTATION=0` in the door's launch configuration
  turns the new presentation off. Only the exact value `0` selects the
  old renderer. Any other value, such as `false` or empty, keeps the new
  one and logs one line naming the value it ignored. No input key and no
  protocol field.
  The setting goes in the operator docs, along with a release note for
  SysOps that the default changed, so the owner, the novice or an
  operator can switch back if they hit a screen the coverage list
  missed.
- **List every screen the new presentation doesn't cover**, such as
  menus, the market, apartments or the Lattice view. Fix the ones on the
  evening path. List the rest in the PR for step two.
- Step two is a separate cleanup PR after the owner has played: delete
  the old renderer and its captures. It is not part of this slice.

### 4. The hub cast is switched on

- **Owner decision, taken by merging this filing:** the hub cast is
  switched on in this slice, ahead of plan 03's P4/P8/S25c sequence for
  speaker placement (the Row proposal's Q6). Talkers go only on existing
  walkable tiles. A talker whose spot S25c later moves is re-placed in
  S25c, and that's accepted. If the owner declines, this part is dropped
  and the cast stays dormant.
- Switch on the named talkers in `s27-cast.json` who stand in the ten
  built areas: place them and switch them to active, so the Wake Hall
  orderlies and the hub people speak.
- Content only. Each one passes the S42 reach rules and the P12 fit
  checks. A talker who would need new geometry or a new system stays
  dormant and is listed.

### 5. A voice in the walls (optional layer)

- About 30 trigger-and-line pairs in the Wake Hall and on the Row,
  through P8's emitter. Examples: walking into a wall three times,
  standing idle, the first death, the first jack-in.
- The creative lead writes the lines.
- **Unattributed:** no speaker name. The Custodian may answer now and
  then. The mystery stays unresolved, as the bible requires.
- **Rare by design:**
  - each line fires at most once per character;
  - a caller gets at most a few lines per evening, using P8's budget;
  - the layer is never suppressed in a way that hides danger.
- One content switch turns the whole layer off, so it can be removed
  after the playtest with no code change.

### Open items this slice must settle

The slice proposes each of these in its PR, and the technical lead rules
on it:
- **Skipping the terminal (from #219's review).** The decant record is
  the one required step before the street, but the terminal lesson that
  lifts it can be skipped. Say where a caller who skips reaches the
  record. It still opens only on a key the caller presses.
- **Reserved names (from #219's review).** Existing characters whose
  normalised name matches `No.` followed by digits: either they keep it,
  or they're asked to rename at next login. Gurney numbers are checked
  against names already taken. This goes together with the #221
  migration.
- **The S24 empty focus and the cache beside the exit (#211).** Fix them
  if the evening path meets them.

## Out of scope

- Season 0's maps (Contractor Street, The Drop) and the Ninety-Nine
  chain: a later slice.
- The population switches, the calendar lease and the Signatory grant:
  the canon PR and their own slices.
- S45 and S46 (the Row's drawn weapon, posts and crowds).
- New systems of any kind.

## Tests

- **A headless walk** of the whole evening path through the production
  Core. It fails if any step dead-ends.
- **Every briefing page shows text,** at both sizes (#216).
- **Opening:**
  - movement works on the first screen;
  - the archetype is chosen after the drone and terminal lessons;
  - every lesson can be skipped;
  - the Wake completes in five minutes on the walk.
- **The new presentation is the default,** and
  `DOOR_KARST41_PRESENTATION=0` restores the old one; any other value keeps the new one and logs the ignored value.
- **Voice:**
  - each trigger fires once per character;
  - the per-evening cap holds;
  - the off switch silences the layer;
  - it never pushes a danger line out of view (P8 and P12 rules).
- Hint-line fit and symbol labels along the path.

## Definition of done

Roadmap §7, plus native evidence through NetBBS at 80x24 and 132x50, in
all three tiers, of the whole evening. The presentation lead accepts it
from the captures, against plan 03 §10.3.

Then the owner plays it alone. **This is the H1 session.** H1 is granted
or withheld by the owner alone, after playing. It isn't granted by this
slice, its tests, its captures or any review. The S25 layout approval is
not part of this slice and isn't granted by it.

After the owner, the novice plays it alone, and the technical lead
re-ranks the plan from both sessions' findings.
