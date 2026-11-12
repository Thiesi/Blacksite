# S44 — The Row's truce rules: hunted, the Halo's refusal, settling the debt

**Status:** planned (filed 2026-11-11; the owner merges the filing)
**Primary model:** Claude Opus 5.5 (the engineer) · **Reviewer:** automated review, technical lead, presentation lead (presentation acceptance)
**Depends on:** S38, S42 for parts 1–4; P12 (#204) for parts 5 and 6 only. Parts 1–4 may start before P12 merges. · **Milestone:** interaction
**Issue:** https://github.com/Thiesi/Karst41/issues/207

Canon: game design 5.5 and 7.3, architecture (`me.hunted?`), terminal
UI 2.1 and 2.5, and the gazetteer's Row and Halo entries. #203 (e7c5d50)
wrote the rules there, marked "planned, S44". The implementation
removes those marks. Where this file and canon differ, canon wins.

## Goal

S38 built the truce: an attack on the Row breaks the peace, Marks a
player attacker, and brings Sable's enforcers. The owner then decided
what the truce costs afterwards (#170: 6700329493, 6700422611,
6700602227; 2026-11-11: 6806566489) and played it on the round 3 and
round 4 demo branches. On `main` none of it exists yet. The enforcers
also lose a player who steps into a bar (#187, round 4 finding 1).

This slice brings the decided rules to `main`. The demo branches
(`demo/sodium-row-round3` at d305537, `demo/sodium-row-round4` at
fd63b6f) are a guide, not a patch: they use demo switches and an
overlay, and `main` has S42 and S43 since.

## Scope

### 1. Hunted

- A player is **hunted** while a truce keeper's guards answer them:
  five minutes (`PROVOCATION_SECONDS`) from the breach. One predicate
  serves the header, the Halo's refusal and the log; nothing derives it
  twice.
- **The predicate reads only the stored keeper record** (below), never
  `Npcs.provocations`. That dict also holds ordinary faction reactions
  for any NPC attack, keyed per spawner group and by body and
  controller ids. Shooting a non-truce NPC elsewhere must not make a
  player hunted or shut the Halo. The record is written by the truce
  keeper's response (`keep_truce`) and keyed by the responsible
  player's body, resolving a drone or burn to its controller's body as
  `keep_truce` already does.
- It holds wherever the body is, online or offline. It runs on the
  injected clock (AGENTS.md §4).
- **It survives a restart.** Today the keeper's provocation is
  memory-only (`Npcs.provocations`, `npcs/engine.py:47`, never
  persisted), so a restart would silently drop hunted and the Halo
  would admit a player the keeper still answers. Ruling (technical
  lead): persist the keeper's answer per player as a UTC expiry with
  its keeper and zone, beside `Player.marked_until` and saved the same
  way. On load, a live expiry restores both hunted and the guards'
  provocation; an expired one is dropped. The NPC-side provocation
  dict stays the in-memory engine for everything else. Any storage
  migration and any P3 or fingerprint movement this causes are listed
  in the PR.
- **The record exists whether or not a guard is present.** The answer
  is the keeper's, not one guard's: every breach writes it, even when
  every guard is dead or absent. A keeper guard that spawns or wakes
  while the record is live takes up the answer. So killing the
  enforcers first doesn't buy a clean breach (technical lead's ruling).
- **A truce-breaking Mark is told apart from any other Mark.**
  `Player.marked_until` is a bare timestamp written from several causes
  (combat, the Lattice channel). Persist a second expiry,
  `truce_marked_until`, set with the Mark whenever the Mark comes from a
  truce breach, to that Mark's expiry. A later Mark of another cause
  extends `marked_until` by the existing rules and leaves
  `truce_marked_until` alone. A later truce Mark refreshes both. The
  Halo's door reads `truce_marked_until`; Vesper and everything else
  read `marked_until`. Both survive a restart, with the same migration
  note.
- The view carries `me.hunted` (additive; absent when false).

### 2. Pursuit to the last seen position (#187)

- The keeper's guards pursue a hunted player through the street and
  its bar alcoves to `last_position`, give up 20 s after losing sight
  (`LOST_SIGHT_SECONDS`, unchanged), and never cross a zone exit.
- Replace the greedy step for **hunt** with routing that is
  deterministic, bounded and cached: a shortest path over the zone's
  passable tiles to `last_position`, under the ordinary movement,
  cooldown, collision and avoidance rules, recomputed only when the
  goal or the blocking set changes. No `zone.rng` draws. It must fit
  the CPU budget: #186 shows per-NPC server cost already matters.
- Bring t6's failing reproduction (`diagnose/187-row-hunt` at 087aa96,
  `docs/ops/diagnostics/issue187/`) into `tests/` as a passing test.
  Add the round 4 case: a hunted player leaves a bar, and the guard
  follows them out instead of waiting for line of sight.
- **Other callers:** list every other `step_toward` caller (patrol,
  flee, A9's walk home, escort, contract scenes, drones) and say which
  share the doorway blindness. Don't switch them in this slice without
  a ruling.
- **Not in scope:** searching unseen tiles after reaching the spot.
  The owner never approved it (#187 6729514230 said it needs owner
  approval first). If the playtest finding can't be met without it,
  stop and ask.

### 3. The Halo's refusal, Vesper, and being shown out

- The Tin Halo refuses, at every entrance:
  - a hunted player, for as long as the answer lasts;
  - a player Marked for breaking the Row's truce, until the Mark ends.
- The bouncer's line gives the minutes left, rounded up so it never
  says 0, using the canon wording (terminal UI 2.1). When both apply,
  the longer time wins, in that condition's words, and the Mark's words
  on a tie.
- A player who becomes hunted or Marked while inside the Halo (a drone
  or burn sent out from there) is shown out through the street door
  with the same line.
- Vesper's work (board, counter, talk offers) closes to **any** Marked
  player, whatever earned the Mark, with her canon line. The Halo's door
  keeps to truce-breakers. The two differ on purpose (#170).
- Accepted work is kept: it can't be advanced at the Halo or with
  Vesper until the Mark ends. No deadline pauses.
- These are travel and service refusals through the existing refusal
  paths (S38's and the travel rules). No new movement mechanics.

### 4. Death settles the debt

- A death of the character's body, from any cause, clears that
  player's keeper provocation, the Halo's hunted refusal and hunted
  itself. The clone cost stands.
- **Settling writes the stored record** and clears the in-memory
  answer. It also stands down every keeper guard that holds that player
  as its target: target cleared, back to its post, no lingering hunt
  until the 20 s give-up. Otherwise a guard still in `hunt` kills the
  player again at the vat after "considers it settled".
- It applies whether or not the player is online. A body killed while
  its player is offline, after a combat logout, settles the same way,
  and a restart restores nothing.
- On respawn the log follows the vat's line with "<Keeper> considers it
  settled.", plus " The Mark stays." while a Mark runs.
- A combat logout is not a death and settles nothing.
- A Mark outlasts death: no Halo and no work for its 15 minutes, and
  Wardens still engage. The keeper's guards don't come back over the
  settled breach. A **new** breach after respawn starts a fresh
  five-minute answer, Mark or no Mark (owner, 2026-11-11).

### 5. Notices and the header (after P12)

- **The price, as notices** (terminal UI 2.1 and 2.5):
  - the arrival notice on a character's first arrival in a truce zone,
    from the existing first-discovery moment;
  - the first-target notice, once per session, chosen by the TARGET
    warning already shown.
  - Wording is canon's, word for word. Numbers come from the constants
    (`MARKED_SECONDS`, `PROVOCATION_SECONDS`), never literals.
- Price notices are exempt from the new-Wake five-minute quiet; node
  notices stay held.
- A price notice that first lands in the header because the player is
  threatened returns to the hint line when the threat ends. Its 8 s and
  its key press count from the return.
- HUNTED alone, like MARKED alone, is not a threatened state for notice
  placement.
- `HUNTED` shows in the header as a danger fact, beside `MARKED` when
  both apply, and drops no earlier than `MARKED` or heat.

### 6. Talk content for speakers already on `main`

Lands after P12, so the action list fits.

- **Sodium regulars** (`row-street-regular`): the approved Ask line,
  "Ask about the end" (#185 6755418093).
- **Sable enforcers:** `npc-sable-enforcer` gets the round 3 enforcer
  set (`row-enforcer`, from the demo), including its approved Ask line
  "Ask about the peace" and the reference line "Nobody draws on the Row.
  You can. Then you pay." Bring the test that a talking enforcer still
  presents as security, not service.
- Lines are the approved text, word for word, with each set's speaker.
  The other approved sets (card players, tout, haggler, Clause, Kestrel,
  choir, doorstep, off-duty, runner, Halo copies, and the Dolf and Mira
  Trade lines) arrive with their speakers in the creative lead's
  population PR, not here.

## Out of scope

- **Barks.** Ambient emission belongs to P8 (one emitter, a derived
  RNG, a per-caller budget; plan 03 §P8). The regulars' approved barks
  wait for P8. This slice adds no emitter.
- The drawn weapon (S45) and posts and crowds (S46), including the
  Clause doorway deadlock, which lives in demo-only post code.
- The Halo back door's locked line and the core room label: the door's
  target is still the owner's decision.
- Search at the last known spot (see part 2).
- NPC counts, spawns and layouts.

## Edge cases the PR must cover

From the #203 triage. Each needs a test or a stated reason:

- the persisted answer across a restart, against the injected clock: a live expiry restores hunted and the guards' answer, an expired one is dropped;
- the sequence Marked → die → respawn → shoot an unmarked player →
  the guards answer again;
- a combat logout during an answer: nothing settles, the timer runs on;
- the body killed while its player is offline, then a restart: nothing
  is restored, and the Halo admits the player;
- after a settling death, no guard still targets the player: respawn at
  the vat in the same zone and nobody attacks;
- shooting a non-truce NPC in another zone makes nobody hunted and
  leaves the Halo open;
- a drone or burn attack on the Row records the answer against the
  controller's body;
- a breach with no live guard writes the record; a guard spawning while
  it's live pursues;
- a Lattice-channel Mark shuts Vesper but not the Halo's door; a truce
  Mark followed by a non-truce Mark keeps the door shut until the truce
  Mark's own expiry; both expiries survive a restart;
- notice numbers taken from the constants;
- a fit test over every shipped keeper's short name at 80x24. The
  arrival and first-target lines fit only names of 7 cells or fewer, so
  the test fails any longer name;
- truncation uses ASCII `...`;
- a drone or burn sent from inside the Halo;
- the overlapping-refusal wording, including the change after a death
  settles the answer while the Mark runs on;
- Vesper refusing a non-truce Mark while the Halo door admits that
  player.

## Tests

- Hunted: the predicate, `me.hunted`, the header fact and its drop
  order, and restart behaviour through the injected clock.
- Pursuit: the #187 reproduction passes; the bar-exit case; routing
  makes no `zone.rng` draws; a path is recomputed only when its goal or
  blockers change; the guard never crosses an exit; the 20 s give-up is
  unchanged.
- Refusals: every Halo entrance, both conditions and their overlap, the
  shown-out case, Vesper's three surfaces, and kept work with a
  deadline that still expires.
- Death: each death cause settles; a combat logout doesn't; the respawn
  line with and without a Mark; the new-breach sequence.
- Notices: arrival once per character, first target once per session,
  the new-Wake exemption, the threat-then-return timing, goldens at
  80x24 and 132x50.
- Talk: the regulars' and the enforcers' Ask lines through real views,
  and enforcers still present as security.
- **Frozen values:** the mechanics fingerprint and P3's 10,704-case
  digest may change only where hunted, the refusals or the new talk
  actions are involved. The PR lists every changed case with the
  reason. Anything else moving stops the PR for a ruling.

## Definition of done

Roadmap §7, plus native evidence through NetBBS Telnet to native stdio
at 80x24 and 132x50, in all three tiers, on an isolated node:
- arrive on the Row and see the price notice;
- shoot a regular and see `HUNTED`, be followed into a bar and out
  again, and be refused at the Halo with the minutes;
- die and respawn to "Sable considers it settled.";
- open an enforcer's page and see "Ask about the peace".

The presentation lead accepts from the captures. S10, S11 and S24 still
pass. S11 is handled under #194's rule, and this is a runtime-changing
slice, so a CPU near miss blocks.

H1 and S25 layout approval are not part of this slice and aren't granted
by it.
