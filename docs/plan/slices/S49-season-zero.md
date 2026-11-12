# S49 — Season 0: the season frame, "Ninety-Nine" and the Old Works (the alpha)

**Status:** planned (filed 2026-11-12; the owner merges the filing)
**Primary model:** Claude Opus 5.5 (the engineer) · **Maps, people and lines:** creative lead · **Looks, layout and acceptance:** presentation lead · **Reviewer:** automated review, technical lead
**Depends on:** S48 (the first evening, H1), S47 (off-loop writer), S19, S20, S21 and S27 (all merged; the chain's contracts, faction site, relay and talkers are authored and dormant) · **Lands before:** S50 and S31 (S31's first release ships Season 0) · **Milestone:** the alpha
**Issue:** https://github.com/Thiesi/Karst41/issues/232

Canon: game design §13.1 and §13.6, story arcs "Season 0 — *The Door*"
and the Unmoored's "Ninety-Nine", the gazetteer's Old Works entries
(`oldworks-main`, `oldworks-drop`), and the bible. All of this was merged
in #219. Where this file and canon differ, canon wins.

## Why

On 2026-11-12 the owner accepted Season 0 as the alpha, after the
independent review. It's a small, finished season on the hubs that
already exist, rather than Season 1's full bundle of eight chains,
expeditions and the Blacksite (S26). It gives a SysOp something whole to
install and a handful of players something to finish together.

S26 is too broad to hold Season 0, so this slice is split out. S26 builds
Depth, the consoles, expeditions, ballots and settlement, and Season 0
has none of them (§13.6). What Season 0 needs from a season engine is
small: knowing which season is running, the operator's advance, and the
season's one ending. This slice builds that frame. S26 later extends the
same frame for Season 1 rather than building a second one.

## Goal

A node running Season 0:
- **The season:** the game knows it's Season 0, the operator can advance
  it, and nothing on screen promises a system that doesn't run.
- **The place:** players walk from Sodium Row down to Contractor Street,
  find the unmarked door to the Drop, and meet Ilka Strand at the
  Unmoored's terminal.
- **The chain:** they play "Ninety-Nine" to its end.
- **The ending:** step 5 opens `shaft-door-east` from the Lattice side,
  and Strand says "Forty-one years. Somebody had to." The way beyond
  stays closed until Season 1.

## Scope

### 1. The season frame

- A persisted **active season** (Season 0 on a new node), owned by a
  small season module in the simulation. No wall-clock reads (AGENTS
  §4).
- **The operator's advance**, through the admin CLI, following §13.1:
  - explicit and audited;
  - never automatic on a calendar;
  - advancing with no eligible completion requires the no-outcome
    acknowledgement and records no settled choice.

  What counts as Season 0's completion is open item 2.
- **A season-start hook** that later slices attach to: S50 re-evaluates
  the population switches there, S21's seasonal relay reset hangs off it,
  and S26 extends it for Season 1. Only the hook and its tests are built
  here, and no Season 1 behaviour.
- **Advancing out of Season 0** when no Season 1 bundle is installed
  parks progression between seasons (S26's existing rule). It never
  unlocks a missing map. Characters, progression and personal receipts
  carry over.

### 2. The Old Works maps

- **`oldworks-main`, Contractor Street** (110x34, contested,
  Unmoored), from the gazetteer:
  - the street exit up to `sodium-row`;
  - the freight-siding and `oldworks-yards` exits, drawn but closed in
    Season 0;
  - the unmarked door to the Drop, found by looking;
  - the four public terminals;
  - the Vat Nine squat (step 2);
  - Relay Zero's terminal and counter (`relay-zero`,
    `relay-zero-counter`).
- **`oldworks-drop`, The Drop** (40x20, pocket, Unmoored): the
  Unmoored's hall (`site-unmoored`), Strand at the Unmoored terminal,
  and the `oldworks-deep` vendor.
- **Who owns what.** The creative lead owns place purpose, inhabitants
  and layout intent. The presentation lead owns looks, signs and
  acceptance. The engineer builds both maps against the existing map,
  looks and validator rules.
- **Layout approval.** New maps come under the owner's layout approval,
  as S25c does. This slice doesn't grant that approval, and neither does
  any review.
- **Gazetteer exits not built in Season 0.** Draw them as closed or
  blocked, never as live exits to missing zones. The validator already
  rejects references to missing zones.

### 3. The chain and its Lattice

- **Activate exactly what "Ninety-Nine" needs** from the dormant bundles
  (`s19-season-one`, `s25-cores`, `s27-cast`), and nothing else:
  - the five `unm-s1-*` contracts;
  - the Sink sector cells of step 1, including the hidden black-core
    entrance;
  - the Silt below the Old Works sector (step 3);
  - the cores `lat-ninety-nines-drop` and `lat-outworks-seal`;
  - `lat-relay-zero`;
  - Strand and Ninety-Nine.

  Every other Season 1 reference stays dormant, and the validator proves
  it.
- **The Season 0 dormancies (§13.6):**
  - step 2's lock against `sab-s1-1-retrieval` stays dormant;
  - step 5's Halvard beacon report stays off.

  Both are content conditions, not engine branches.
- **The door's own zone, `under-outworks`, isn't built.**
  - `lat-outworks-seal`'s `shaft-door-east` control targets an object in
    that zone, and the active-core validator requires control targets
    in built zones. The slice proposes how the control works without
    the zone, for example a season world flag as the control's target,
    and the technical lead rules on it.
  - The control's authored `reset_seconds: 300` mustn't undo the
    season's ending. The season flag is separate from the control's
    physical reset.

### 4. The ending

- **The step 5 flip.** It opens `shaft-door-east` from the Lattice side,
  and Strand says "Forty-one years. Somebody had to.", word for word.
  Who owns the flip, and what later finishers get, is open item 1.
- **The way beyond stays closed.** Nothing past the door is reachable in
  Season 0.

### 5. Nothing on screen promises what doesn't run

§13.1's contribution consoles, delivery XP and the Depth meter don't run
in Season 0. How they're kept out of sight is open item 4. Whatever the
answer, no Season 0 screen names Depth, a console, a ballot or an
expedition.

## Open items for the owner

Each comes with the technical lead's recommendation. None of them is
canon until the owner answers and a canon PR records it.

1. **The door flip.**
   - **Recommendation:** a one-time world flag.
     - The first player to finish step 5 opens `shaft-door-east` for
       everyone, and Strand's line plays for them.
     - Players who finish step 5 afterwards get a short variant line
       (the creative lead writes it) and full chain credit.
     - The door stays open for the rest of the season.
2. **Chronicle and advancing.**
   - **Recommendation:**
     - The flip writes one Chronicle record, "Season 0: the shaft door
       opened", with zero delta.
     - It counts as Season 0's completion for §13.1, so the operator
       isn't shown the no-outcome acknowledgement.
     - Advancing before the flip uses the acknowledgement as usual.
   - **Consequence if accepted:** this slice builds the smallest
     Chronicle that can hold the record (append-only, operator-readable),
     and S26 extends it.
3. **Season 1 reuse.**
   - **Recommendation:**
     - The door stays open into Season 1, and Season 1's "Ninety-Nine"
       entry chain starts from the open door.
     - A character who finished it in Season 0 keeps the credit and
       isn't asked to repeat the Season 0 steps.
   - This is recorded here so that S26 builds on it.
4. **§13.1's consoles, delivery XP and Depth meter in Season 0.**
   - **Recommendation:** hidden, not inert.
     - The consoles aren't placed.
     - The meter isn't shown.
     - No delivery XP is given.
   - That way nothing on screen promises a system that doesn't run.

## Open items for the technical lead

The slice proposes each of these in its PR:
- **`shaft-door-east` without `under-outworks`:** how the control and
  its validation work, and how the season flag survives the control's
  300-second reset (part 3).
- **The closed gazetteer exits** on Contractor Street: drawn as what?
  (Part 2; the creative lead and the presentation lead.)
- **The season-start hook's contract:** exactly what S50 and S26 can
  rely on.

## Out of scope

- Depth, contribution consoles, expeditions, ballots, settlement and the
  Blacksite: S26, for Season 1.
- The population switches themselves: S50. Season 0's three factions and
  three relays are S50's below-threshold set. This slice only makes sure
  the Unmoored's hall and Relay Zero exist for them.
- The other Season 1 chains and districts, `oldworks-yards`,
  `oldworks-dynamo-hall` and `under-outworks`.
- New systems beyond the season frame.

## Tests

- **The season frame:**
  - a new node starts in Season 0;
  - the operator's advance is audited and works exactly once;
  - the no-outcome acknowledgement is required when there's no
    completion;
  - advancing with no next bundle parks progression and keeps
    characters;
  - the start hook fires once per season start.
- **Maps:**
  - both zones load and validate;
  - Sodium Row ↔ Contractor Street works both ways;
  - the Drop's door is found by looking;
  - closed exits lead nowhere;
  - native walks at 80x24 and 132x50.
- **The chain:**
  - all five steps play end to end on the shipped maps through the
    production Core (headless);
  - step 2's Sablier lock and step 5's beacon report stay dormant;
  - every other Season 1 reference stays dormant (full-tree validator).
- **The ending:**
  - the flip and Strand's line, word for word;
  - the way beyond stays closed;
  - the behaviour chosen for open items 1 and 2, including a second
    finisher and a restart after the flip.
- **Nothing promised:** no Season 0 screen names Depth, a console, a
  ballot or an expedition.
- **Fingerprints:** P3 and the mechanics fingerprint don't move unless
  the PR names and justifies it. A move under an owner approval stops
  the slice until the owner decides.

## Definition of done

Roadmap §7, plus native evidence through NetBBS at 80x24 and 132x50, in
all three tiers:
- the walk from Sodium Row to the Drop;
- each chain step;
- the door opening and Strand's line;
- the operator's advance.

The presentation lead accepts it from the captures. The creative lead
confirms the places and lines. The owner's layout approval for the two
new maps is a separate gate, which this slice doesn't grant.

H1 and the S25 layout approval are not part of this slice and aren't
granted by it.
