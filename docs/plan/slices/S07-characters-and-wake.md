# S07 — Characters: the Wake, archetypes, attributes, skills, persistence

**Status:** planned
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
  = max(4, vitals//10)`, `evasion(nerve, cover) = nerve//3 + cover`,
  `carry_kg(frame) = frame/2`, shock decay 5/s out of combat, archetype
  start tables (Hardline 40/20/15/5/40, Ghost 15/40/35/10/20, Cantor
  10/20/25/45/25, Operator 20/30/30/5/30), skill lines (12), attribute
  raise rule (every 10 skill points across a line's group raises the
  attribute by 1; Vitals only via grade and implants), grade table
  (1–30 from cumulative XP, 3 grade points and +1 Vitals per grade,
  grade names), `legal_at` set at grade 5.
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
  digits, space, hyphen, apostrophe; uniqueness per node), screen 3
  Vantongeren's briefing (three `TextView`s from the story-arcs script),
  screen 4 the card rack menu (eight recruiter pitches plus "take no
  card"; sets standing +10 with the chosen faction), then placement at
  the Wake Hall spawn tile with the starter kit rows and 200 chits. The
  corridor drone and terminal steps are stubs that pass through until
  S10/S13 replace them ("The corridor is quiet today.").
- Skippable: a returning player with a character never sees the Wake;
  `intent {name: "delete_character"}` requires typing the character's
  name at a line prompt (the type-the-name exception in `AGENTS.md`
  §4) and then re-runs the Wake.
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

- `tests/rules/test_character.py::test_health_50_plus_2_vitals`,
  `::test_stamina_formula`, `::test_tolerance_min_4`,
  `::test_evasion_nerve_over_3`, `::test_carry_frame_over_2`,
  `::test_archetype_start_tables`, `::test_skill_group_raises_attribute_per_10`,
  `::test_grade_table_monotonic_and_30_max`, `::test_legal_at_grade_5`.
- `tests/server/test_players.py::test_one_character_per_bbs_user`,
  `::test_identity_origin_plus_user_id`, `::test_position_persists_across_restart`,
  `::test_sleeper_60s_then_safe_zone`, `::test_reconnect_within_60s_no_sleeper`,
  `::test_delete_requires_typed_name`.
- `tests/server/test_wake.py::test_full_wake_under_20_frames`,
  `::test_name_rules_and_uniqueness`, `::test_wide_name_display_width_24`,
  `::test_card_sets_standing_plus_10`, `::test_no_card_zero_standing`,
  `::test_starter_kit_and_200_chits`, `::test_returning_player_skips_wake`.
- `tests/door/test_wake_render.py::test_golden_archetype_menu_80x24`.

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
