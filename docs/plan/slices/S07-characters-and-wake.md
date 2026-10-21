# S07 — Characters: the Wake, archetypes, attributes, skills, persistence

**Status:** done (PR #46)
**Primary model:** Opus · **Reviewer:** Astra (Wake flow and onboarding read)
**Depends on:** S06 · **Milestone:** M1
**Issue:** https://github.com/Thiesi/blacksite/issues/7

## Goal

Give every caller a persistent character: the Wake creates one in under
five minutes (archetype, name, recruiter card), attributes and skill
lines exist with their derived values, and the character's state and
position survive logout and server restart under the sleeper rule.
After this slice a returning caller lands where they left off with the
right numbers on the side panel.

## Spec references

- `docs/design/00-game-design.md` §2 (session shape, sleeper rule,
  reconnect), §3 (attributes, derived values, archetypes, skill lines,
  grades), §4 (the Wake, steps 1–4 and 7; steps 5–6 land in S10/S13),
  §14 (one character per BBS user).
- `docs/design/01-entities.md` §2.1 (player), §3.6 (session).
- `docs/design/02-architecture.md` §4 (identity keyed on origin +
  bbs_user_id), §6.2 (flush cadence), §8.2 (reconnect within 60 s).
- `docs/design/03-terminal-ui.md` §7 (Wake screens).
- `docs/world/05-story-arcs.md` (Wake briefing script, three screens)
  and `02-factions.md` (recruiter pitch texts).
- `docs/world/06-catalog.md` §11 (starter kit; items granted here as
  inventory rows, equipment semantics arrive in S12).

## Scope

- `src/blacksite/server/rules/character.py`: pure functions with the
  design doc's numbers: `health_max(vitals) = 50 + 2*vitals`,
  `stamina_max(nerve, frame) = 30 + nerve + frame//2`, `tolerance(vitals)
  = max(4, vitals//10)`, `evasion(nerve, equipment) = nerve//3 + equipment`
  (cover remains separate per design 3.1),
  `carry_kg(frame) = frame/2`, shock decay 5/s out of combat, archetype
  start tables (Hardline 40/20/15/5/40, Ghost 15/40/35/10/20, Cantor
  10/20/25/45/25, Operator 20/30/30/5/30), skill lines (12), attribute
  raise rule (every 10 skill points across a line's group raises the
  attribute by 1; Vitals only via grade and implants), grade table
  (1–30 from cumulative XP, 3 grade points and +1 Vitals per grade,
  grade names), `legal_at` set at grade 5 or after 90 real days, whichever is earlier.
- `src/blacksite/server/players.py`: `Player` (entity §2.1) creation,
  lookup by `(origin, bbs_user_id)`, one character per BBS user
  (SysOp-raisable cap stored in `meta`), load on `hello`, attach to the
  session, place into the world (last zone/tile; safe zone → as saved;
  otherwise the sleeper rule: 60 s as a sleeper actor then moved to the
  nearest safe zone, with clone-debt penalty only if flagged in-combat
  by S10), detach on `bye` or disconnect.
- Reconnect: a `hello` for the same identity within 60 s reuses the
  player and skips the sleeper rule.
- `src/blacksite/server/wake.py`: the Wake state machine as a sequence
  of `TextView` and `MenuView` frames: screen 1 archetype cards (four
  rows, detail pane with the one-paragraph card), screen 2 name line
  prompt (default the BBS handle; 2–24 columns display width; letters,
  digits, space, hyphen, underscore, apostrophe; uniqueness per node), screen 3
  Vantongeren's briefing (three `TextView`s from the story-arcs script),
  screen 4 the card rack menu (eight recruiter pitches plus "take no
  card"; sets standing +10 with the chosen faction), then placement at
  the Wake Hall spawn tile with the starter kit rows and 200 chits. The
  corridor drone and terminal steps are stubs that pass through until
  S10/S13 replace them ("The corridor is quiet today.").
- Skippable: a returning player with a character never sees the Wake;
  `intent {name: "delete_character"}` requires typing the character's
  name at a line prompt behind the chosen delete action, then re-runs
  the Wake. Esc cancels before deletion.
- Persistence: `players` table columns per entity §2.1; dirty on every
  change; flush cadence 5 s and immediate on logout; remembered tiles
  per zone stored as a compact bitmap blob.
- `ZoneView.me` now carries real `hp, hp_max, sta, sta_max, shock,
  chits, grade` and the character sheet `MenuView` (`P` key): attributes,
  derived values, skill lines, grade and XP to next, unspent grade
  points (spending arrives in S16).
- `admin.who` shows character names.

## Out of scope

- Equipment, inventory UI, vendors (S12).
- Combat, the corridor drone, death (S10).
- The tutorial terminal and jack-in (S13).
- Skill-by-use XP and grade point spending (S16).
- Hint system and help pages (S30).

## Data and content

- `text/wake-briefing-1.md`, `-2.md`, `-3.md` and `text/wake-archetype-
  <id>.md` from the story-arcs and bible texts; `text/faction-<id>-
  pitch.md` × 8 from the factions doc.
- `items.json` gains the starter kit item templates by their catalog
  IDs if S12 has not landed first (coordinate; the templates are data).

## Protocol and view models

- `welcome.player` becomes the summary `{name, handle, archetype,
  grade, faction: null}` or `null` (Wake follows).
- `view {kind: "wake"}` wraps the Wake's `TextView`/`MenuView` frames
  so the client can show the Wake Hall art (`art/wake-hall.ans`, text
  fallback) beside them.
- `MenuView` for the character sheet; `intent {name: "menu_cursor",
  args: {dir}}`, `{name: "menu_select"}`, `{name: "menu_close"}`.

## Tests

- `tests/characters/test_rules.py`: exact starts and derived rules,
  twelve skill lines, grade/lease thresholds, normalized name width and
  uniqueness keys, and starter weapon schema boundaries.
- `tests/characters/test_lifecycle.py`: identity, commit-before-reward,
  failed-write retry, starter grants, name ownership, reconnect/rename,
  saved terrain, sleepers and restart, idle-online crash grace, typed
  deletion and retained identity history, character caps, briefing
  resume, all skill rows, grade benefits, shock and schema migration.
- `tests/door/test_wake_render.py`: committed archetype goldens, nested
  menu inputs, wide self name and BBS handle, all three tiers, character
  sheet scrolling, lease days and discharge XP at both terminal sizes.

## Acceptance script

1. New caller enters the door: title, then the Wake. Pick Ghost, keep
   the handle as the name, read three briefing screens with any key,
   take the Unmoored card. Arrive in the Wake Hall with 200 chits on
   the side panel and a Ghost's numbers on `P`.
2. Walk into Clinic Row (exit tiles pass through as of S06; behaviour
   in S08 — if S08 is not merged, stay in the Hall), `Ctrl-X` out,
   re-enter: same tile, same numbers.
3. Restart the server while logged out; re-enter: same.
4. Log out from Clinic Row (contested): re-enter after 2 minutes → in
   the Wake Hall pocket (nearest safe/pocket), no penalty (not in
   combat).
5. Under five minutes from title to the Hall for a first-time caller,
   timed.

## Definition of done

- Roadmap §7 holds; step 5 timed and recorded.
- Design doc §3 numbers asserted by tests exactly.

## Implementer notes

- Identity is `bbs_user_id`; the handle can change on the BBS and must
  not be a key. Names are display-width-bounded (24 columns), not
  code-point-bounded.
- The Wake obeys the §3.5 rule: every screen shows content first;
  `Esc`/`B` on the card rack means "no card", not a dead end; only the
  delete flow types a name.
- Keep the Wake's frames as ordinary `TextView`/`MenuView`s so S04's
  renderers need no change.
- Persist remembered tiles compactly; a 200×100 zone is 20 000 bits.

## Lore review integration

The lease clock and XP target are separate visible fields. Decanting,
deleting/recreating a character, changing factions or season advance
cannot reset identity-scoped receipts; grade protection remains separate.
All starters learn Pick and Umbrella. Tutorial combat/ICE are private,
nonlethal practice with bound loan equipment, and cannot injure another
resident. Vesper's card leads to S19's playable two-route first job.

## Implementation notes

Implemented by Codex rather than the named Opus primary; review follows
the automated Claude workflow in AGENTS.md. The existing renderers now
unwrap a Wake menu/text body, scroll a selected row into view, and keep
the name prompt and movement input separate. Briefing prose paginates
at the negotiated size; S skips it, and disconnect saves its exact place.

World schema 2 adds Unicode-folded name uniqueness, player progress and
identity records. Creation returns an outbox proposal, and the I/O layer
commits player, starter items and identity before exposing rewards.
Deletion cannot be undone by a stale write-behind snapshot. Calendar
lease, legal discharge, receipts and debt survive deleting/recreating.
Compact memory retains a 20,000-bit visibility map plus old tile IDs.

The ordinary service now starts the saved-character M1 development flow.
The temporary spawn flag still selects S06 bodies for movement probes.
Future exits, services, membership, equipment use and combat remain
inactive; the existing authoring bundle is not activated. A raised
character cap is configured by the offline admin command and exposes
selection on login. Grade labels beyond the explicitly named Wake and
Ninety-Day use the numeric grade; the design supplies no further rank
thresholds yet.

The technical schema accepts the catalog's `head` implant slot and null
melee ranged-accuracy field, rather than inventing a missing combat
number. S10 consumes melee and training actors. Existing balance values
are unchanged. Design 3.2 now makes the previously unspecified native rig
capacity explicit at three starting slots, matching the public loan rig.
S07 creates the listed equipment/ability rows; S12/S16 apply their effects.
The Ghost's native rig uses the same three initial slots as the public
loan rig, with Pick and Umbrella loaded. S13 owns rig execution/upgrades.

The real-node sleeper scenario uses explicit server-side placement in
Clinic Row because S08 travel is not merged. This checks the actual
physical body and a real 120-second logout interval, without claiming
exit behavior. Same-zone revision numbers cannot suppress a zone change:
the view cache includes zone ID as well as revision.

## Acceptance record (2026-10-21)

- Windows Python 3.12, NetBBS v7.31.0, registered native stdio door
  through the real Telnet picker. The complete probe runs with `--show`
  in a real 132x50 terminal and negotiates both 80x24 and 132x50 callers.
  Ghost creation, the default handle, all three briefing screens,
  Unmoored standing, kit/200 chits, P, same-tile re-entry, service restart
  and a real 120-second contested logout all pass.
- The driven title-to-Hall sequence takes 4.640 seconds. This measures
  automated inputs, not a human reading-time study. Final proof:
  `.test-tmp/s07-netbbs4/result.json` and its four ANSI captures.
- Deterministic tests cover first-decant/personhood, twelve skill lines,
  grade thresholds/benefits, all starter variants, name width/uniqueness,
  one-character defaults and raised caps, failed commits, stale queued
  deletion writes, logout retry, idle-online crash grace and compact
  last-seen terrain. The fake terminal covers both sizes and all tiers.
- Final local root gate on Windows Python 3.12:
  `pytest -q --basetemp=.test-tmp/s07-final-root -p no:cacheprovider`:
  494 passed, 1 platform skip. The shipped content validator passes.
- The delivered Claude review, product-impact triage and final Linux/CI
  acceptance are recorded in PR #46 before merge.
- Claude Sonnet 5.5's raised-cap reconnect finding reproduces beyond
  redundant saves: a chooser could undo safe recovery and later create a
  zoneless sleeper that stopped the tick loop. The chooser now clears
  inherited body ownership until selection. The focused post-fix gate is
  218 passed, 1 Windows platform skip. Re-review is required before merge.
- Linux installed-wheel acceptance passes in
  [run 39602781456](https://github.com/Thiesi/Blacksite/actions/runs/39602781456):
  full Wake, saved return, restart and actual 120-second recovery, plus
  the S05/S06 native-door/service checks. CI before the review fix is
  496 passed on Linux; 495 passed, 1 skipped on Windows.
