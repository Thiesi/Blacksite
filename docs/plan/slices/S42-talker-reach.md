# S42 — Talkers stay in reach, and the talk page lets you go

**Status:** in progress (implementation; filing merged in PR #183)
**Primary model:** Codex · **Reviewer:** automated review, technical lead, presentation lead (presentation acceptance)
**Depends on:** S38, S39, A9 (all merged) · **Milestone:** interaction
**Issue:** https://github.com/Thiesi/Blacksite/issues/182

This comes before P11 (#164). P11's `me.threat` disclosure test would
fail on `main` today because of the Warden tells in part 4.

Canon: game design 5.5 (NPCs), entities 1.8 (`poses_as`), architecture
5.5.4 (disguise reveal) and terminal UI 4 (overlays). The filing wrote the new rules there. The implementation removes their
"planned, S42" marks. Where this file
and canon differ, canon wins.

## Goal

On Sodium Row the owner found talkers hard to talk to. They wandered off
mid-sentence, a talk page held the player in place under fire, and a
first meeting could be lost for good. The demo branch fixed these for the
playtests (`demo/sodium-row-round3`, commits 54002ff and 44fd786). This
slice brings the same rules to `main` properly, together with two tells
that give away the plainclothes Warden.

The demo code is a guide, not a patch to copy. It hardcodes the door's
movement keys and uses demo-only switches, and `main` has since gained
A9's return-home rule and S39's resolver.

## Scope

### 1. Talkers stay in reach

- **A wander step never takes an NPC out of reach of a player beside it.**
  "Beside" means within one tile (Chebyshev), as for talking. When a
  player stands next to a wanderer, the step's candidate tiles that would
  leave any adjacent player out of reach are avoided. The NPC can still
  shuffle, and can stay put if no step qualifies.
- **It applies to every wanderer alike,** covered or not. Otherwise
  movement would tell the Warden from the regulars.
- **Only wander steps.** Flee, hunt, patrol, event motion and A9's
  walk home still move the NPC as today. If such a move takes a talker
  out of reach, the page closes as it does now.
- **A player who can't talk holds nobody:** down, dead, asleep or jacked
  in.
- **An idle player holds nobody either.** The hold counts only a player
  who moved or sent a key or intent in the last 30 seconds, or who has
  that NPC's talk page open. So an idle player, or two at a chokepoint,
  can't pin the crowd in place, and a griefer can't keep a regular by
  their side by standing still.
- **Counted in ticks.** "Last acted" is a tick number (300 ticks at 10 Hz),
  never a wall-clock read (AGENTS.md §4), so tests step it without
  sleeping.
- **Accepted residue:** a player who keeps pressing keys still holds the
  wanderers beside them. That costs little: they shuffle in place, exits
  stay clear, and flee, hunt and the walk home still move them.
- It uses no extra `zone.rng` draws. The random step is chosen as today
  and filtered.

### 2. Saying when someone walks off

- When a talk page closes because the person left, and the caller didn't
  move, the log gets `<name> walks off.` under the name the caller sees
  (the cover name for a covered NPC). It's a muted system line.
- No line when the caller walked away, the person died or went down, or
  the page closed any other way.

### 3. The talk page lets you go

The owner's rule, 2026-11-07.

- **A movement key of your keymap that neither an offer nor Back claims
  closes the page and moves you, in the same press.** An offer or Back
  wins over a movement key. In vi, an offer on `j` keeps `j`, and `b`
  (move down-left) is Back, so it closes the page without a step. In the
  arrows keymap, PgUp and PgDn walk on a talker page rather than page,
  since a talker page has no rows. In vi, arrow keys aren't movement keys
  and do nothing on a talker page.
- **A hit closes the page.** Any damage to the caller closes an open talk
  page on the next tick.
- **Only talker pages.** Shops, menus, Lattice dialogue and other
  overlays keep swallowing movement as today.
- **The door must not hardcode keys.** Which keys walk comes from the
  keymap the server sends in `welcome`, for the caller's selected keymap.
  On a talker page the door forwards a walking key that neither an offer
  nor Back claims; the server decides the rest.
- **The hint row says you can walk away.** The demo used "Move or Esc/B
  leaves". The presentation lead fits the final wording at both sizes and
  co-signs it; it doesn't name arrows, which vi doesn't use. A page with
  no offers doesn't ask you to choose one.

### 4. The plainclothes Warden reacts with its crowd (#179)

Rulings on #179, with the owner's decision of 2026-11-07. The rule is
keyed on **covered and unarmed**, so a later armed undercover character,
or a Warden acting through pickpocket detection, still reveals under the
canon "acts against a caller" rule.

1. **Group reaction, both ways.** A covered, unarmed NPC reacts with the
   one group it poses as. Shoot a regular and the Warden flees with the
   regulars. Shoot the Warden and the regulars flee too. The reaction
   ends together as well: the Warden and its group calm on the same tick.
   Today `provoked()` provokes by spawner group, and the Warden's group
   has one member, so the one person who doesn't run gives it away.
   - **The group is declared, not guessed.** The covered spawner names it
     with `poses_as` (entities 1.8), for example `poses_as:
     "sodium-regular"` on the plainclothes Warden's spawner. The engine
     must not react to every group that shares the cover name, because
     once the Row's crowd splits into several groups, the Warden would run
     while some of the people around it stay put.
   - **The validator** checks that `poses_as` names a spawner in the same
     zone whose template presents the same `cover_name` and class, and
     refuses a covered, unarmed spawner without one. A disguise with no
     crowd is unmasked by NEARBY anyway. The implementation adds
     `poses_as` to the shipped Warden spawner on the Row and moves nothing.
     Placement stays the creative consultant's.
2. **Fleeing doesn't reveal.** In `evaluate()`, picking up a target
   reveals a covered, unarmed NPC only if it will act against the caller
   (hunt), not if it will flee. In `provoked()`, the direct
   `combat.reveal(target, source)` follows the same rule. By the owner's
   decision, shooting a plainclothes Warden shows the shooter no sign and
   costs nothing beyond shooting any regular. It does cost exactly that:
   on the Row it breaks the truce, and the keeper answers, as for a shot
   at a regular. The reveal for local guards stays.
   - **Local guards answer as for the crowd.** `provoked()` also calls in
     every guard or warden of the target's faction in the zone. For a
     covered, unarmed target, that loop uses the faction of the group it
     poses as, not its own, so the guards who answer are exactly those who
     would answer a shot regular. Otherwise, in any zone with a Warden
     patrol, real Wardens would come for the shooter of a "regular".
   Architecture 5.5.4 now says "hunts" where it said "targets". Check
   every `combat.reveal` caller, including the Tab-target view, and
   say on the PR that none relied on targeting alone.
3. **No Warden detector for red names.** A covered, unarmed NPC doesn't
   take the Wardens' heat and Mark rule in `hostile()`, so a Marked or
   heated player in sight doesn't make one "regular" turn and run. It
   reacts only when its crowd does. `tests/npcs/test_truce.py` line 373
   pins the old behaviour and flips deliberately. Say so in the PR.
   Check `test_ui_2_1_tab_respects_warden_cover_and_distance` still
   holds.

The intended payoff, on record and not built here: pickpocket detection
(gazetteer, canon and unbuilt) is the moment the disguise should break.
Until something like it exists, the Warden is a figure in the crowd.

### 5. A first meeting that never showed doesn't count (#169)

- Today `open()` saves the talker in `met_talkers` before anything shows,
  and `show()` returns quietly if the person has gone by then
  (`dialogue_runtime.py`, `open` and `show`). The first-meeting line is
  then lost for good.
- If the page can't show, because the person left or another screen took
  over during the write, the meeting doesn't count and the first line
  stays owed. Use the commerce queue as the save did. If the queue is
  full, the player stays met, which only costs the first line; say so in
  the code.

### 6. A vendor from the `npcs` route yields to an exit underfoot

From the S39 review (record on #167). Game design 5.6 says a door underfoot
beats an adjacent vendor. S39 skips only `commerce` vendor choices, so a
vendor that `NpcEngine.interaction` supplies, as `('vendor', counter)`
on the `npcs` route, still beats the exit. Mark that choice so the
resolver skips it like a `commerce` vendor on an adjacent tile, and keep
the underfoot rule. No shipped layout triggers this today, so the test
uses a declared fixture.

## Out of scope

- The talk page's look (empty box, empty choice line, the redundant back
  label). That's the presentation lead's proposal after round 3, with
  #114 item 3.
- The other #114 items, and the Row rules (notices, Q7, HUNTED, death
  settling the debt), which go in the Row rules slice.
- Any new reveal mechanic, including pickpocket detection.
- NPC counts, spawns or layouts.

## Tests

- **Reach:** a wanderer beside a player never steps out of reach, over
  many ticks, from every neighbouring position. A covered wanderer
  behaves identically. A flee or hunt still takes the NPC away. A
  down, asleep or jacked player holds nobody, and neither does a player
  idle for 30 seconds without the NPC's page open. A held wanderer outside
  its region still walks home. `zone.rng` draws per tick
  are unchanged.
- **Walks off:** the line appears under the presented name when the
  person leaves, including a covered NPC's cover name. No line when the
  caller moved or the person went down.
- **Talk page:** in both keymaps, a movement key that neither an offer
  nor Back claims closes the page and moves the caller in the same press,
  including PgUp and PgDn in arrows. An offer on a movement key in vi
  keeps it, and vi `b` closes the page without a step. A hit closes the
  page. Shops, menus and Lattice
  dialogue still swallow movement. The door derives walking keys from
  the welcome keymap; a test changes the keymap and the door follows.
- **Warden, through real views:** shoot a regular and the Warden flees
  with the crowd, name unchanged. Shoot the Warden and the regulars flee,
  the shooter's view shows the cover, the keeper answers as for a shot
  regular, and nothing else follows. In a fixture zone with a Warden
  patrol and a guard of the posed faction, shooting the plainclothes
  Warden calls in the same guards as shooting a regular, and no Warden.
  The
  Warden and the regulars go back to wandering on the same tick. A second
  group with the same cover name in the zone doesn't react. The validator
  refuses a missing or mismatched `poses_as`. A Marked
  and a heated caller walking past change nothing. An armed covered
  fixture still reveals when it acts.
- **First meeting:** both triggers (the person steps away during the
  write, another screen opens) leave the talker unmet, and the next E
  shows the first line.
- **Vendor:** an exit underfoot beats an adjacent `npcs`-route vendor
  for E. A vendor underfoot keeps precedence. J and targeted talk don't
  change.
- **Frozen values:** the mechanics fingerprint and P3's 10,704-case
  digest may change only where a wanderer stands beside a player or a
  covered NPC is involved. The PR lists every changed case with the
  reason. Anything else moving stops the PR for a ruling.

## Definition of done

Roadmap §7, plus native evidence through NetBBS Telnet to native stdio
at 80x24 and 132x50, in all three tiers: on Sodium Row, open a regular's
page, walk away in one press, and see the hint row; a regular leaving
under flee logs "walks off". The presentation lead accepts from the
captures. S10, S11 and S24 still pass, with S11 handled under the
standing commit-stall ruling.

H1 and S25 layout approval are not part of this slice and aren't granted
by it.
