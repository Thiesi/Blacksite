# S26 — Seasons: Depth meter, descent consoles, leaderboards, the Chronicle, Blacksite level 1 (instanced zone and sector)

**Status:** planned
**Primary model:** Opus · **Reviewer:** Fable (level design and finale review before merge)
**Depends on:** S21, S19, S24 · **Milestone:** M5
**Issue:** (filled in when filed)

## Goal

Build the season loop: contributions raise a node-wide Depth meter,
leaderboards rank factions and players, the season's Blacksite level
opens as an instanced crew raid when the meter fills, the crew leader's
final choice is written to the Chronicle and moves the Custodian/Tenant
balance, and the season rolls over without resetting characters. Ship
Season 1, *The Exhale*, with Blacksite Level 1, *The Outworks Door*.

## Spec references

- `docs/design/00-game-design.md` §13 (Depth 100 000, contributions,
  leaderboards, instanced level for crews of 3–5, Chronicle, season end
  rules), §11 (Chronicle readable by all), §7.4 (relay influence feeds
  the season tally), §12 (Curfew weight after a Seal).
- `docs/design/01-entities.md` §1.13 (season definition incl. finale
  choices with `condition`, `relations_override`), §2.8 (season and
  chronicle rows), §3.2 (instanced zone suffix), §3.4 (core instance).
- `docs/design/02-architecture.md` §2.3 (`season status`, `season
  advance`, `chronicle append`, `export leaderboard`), §6.2 (immediate
  flush on season change), §9 (per-authority season state).
- `docs/design/03-terminal-ui.md` §4 (descent console, chronicle menus),
  §7 (TextView).
- `docs/world/05-story-arcs.md` Season 1: premise, Depth-meter flavour
  and console text, "Blacksite Level 1 — The Outworks Door" (layout,
  scripted encounter, the three choices Seal / Leave it open / Answer it
  with their costs and gains, Chronicle templates, balance after),
  world-event announcement voices.
- `docs/world/01-gazetteer.md` `under-shaft-foot` (season door),
  `blacksite-l1` placeholder; `docs/world/08-found-texts.md` Chronicle
  prologue; `docs/world/03-lattice.md` Shaft core and the instanced
  sector (tier 4, eight rooms).

## Scope

- `src/blacksite/server/seasons.py`: `SeasonService` holding the
  active season row, `contribute(player, item)` (accepts `contribution`
  data, intact salvage, Undercity keys with weights from
  `seasons/1.json`; credits the player's faction's `depth_contributed`
  and the player's stats), `depth()`, `open_level()` at 100 000,
  `finale(crew, choice)`, `advance()` (season end: freeze leaderboards,
  relays to neutral, balance step, Chronicle write, next season load).
- Descent console object (`descent_console`) in every faction hall and
  at the season door: menu listing carried contribution items with
  `[D]eliver`, a Depth bar with percentage and the story-arcs console
  text, and the current faction ranking.
- Leaderboards (`MenuView`): factions by influence and depth; players
  by grade, kills, runs, contributions; per-season, frozen snapshots
  kept for past seasons; `export leaderboard` for the admin.
- Chronicle (`TextView`): the prologue from the found texts, then one
  rendered paragraph per completed season from the chosen template with
  `{crew}` and `{name}` resolved; `chronicle append` for the SysOp.
- Instancing: `ZoneInstance` and `CoreInstance` with an instance suffix
  per crew (`blacksite-l1#<crew id>`), created when a crew of 3–5 with
  all members in `under-shaft-foot` interacts with the season door while
  the level is open; torn down 10 minutes after the last member leaves or
  on finale; at most 4 live instances per node.
- Blacksite Level 1 content: `content/zones/blacksite-l1.map/.json`
  (ring gallery, control gallery, vent stack, shaft head platform, the
  sealed east door for season 2, per the story-arcs sketch),
  `content/sectors/blacksite-l1.json` and
  `content/cores/blacksite-l1-shaft.json` (tier 4, eight rooms, ICE that
  does not attack until touched, control `shaft-lamps`, data
  `activation-log-last-page`).
- Scripted encounter: on the data node lift, flip all gallery lights,
  spawn the ownerless *warden* ICE in the core and the maintenance drone
  on the platform, and play the alternating CUST/TEN lines from the
  story-arcs document as talker lines with the `CUST`/`TEN` tags (S27's
  engine; if S27 is not merged, deliver them as fixed log lines and note
  it).
- Finale console: `MenuView` with the three options for the crew leader
  only, others see the options read-only; option 3 opens a name line
  prompt defaulting to the leader's character name. Applying an option:
  standing deltas to all crew members, balance step, Chronicle write,
  the option's persistent world effect flag (Seal: Undercity spawn
  multiplier next season and Curfew weight halved; Open: unlock zone
  `undercity-shaft-gallery` as permanently open, mapped Silt descent;
  Answer: ambient Vatside line, Sablier −30, Listening +5 for the crew).
  Persistent effects are read by the relevant subsystems from
  `season.finale_choices` at start; the `undercity-shaft-gallery` zone
  itself is a follow-up content slice and is created here only as a
  placeholder that the flag can unlock.
- Season 1 definition `content/seasons/1.json` and contribution items in
  `items.json`: `telemetry-unit-warm` (intact salvage), `shaft-access-
  token` (Undercity key), and the `contribution` data kind on cores per
  the Lattice document.
- Admin: `season status`, `season advance --confirm`, `season set-depth
  <n>` (test and recovery aid, audit-logged).

## Out of scope

- Story-contract chains (S19 content). Relay influence accrual (S21).
  Event effects (S24). Dialogue engine (S27). Seasons 2 and 3 content
  (follow-up content slices after the first season runs on a real node).
- Cross-node season merge (S32 documents the rule).

## Data and content

- `seasons/1.json` per entities §1.13: `depth_target: 100000`,
  contribution weights (data 250, intact salvage 500, key 1000; initial
  values, record in design §13), `blacksite_level {zone: blacksite-l1,
  sector: blacksite-l1}`, three finale choices with chronicle asset ids
  and balance deltas.
- Text assets: `text-chronicle-prologue` (found texts), `chronicle-s1-
  seal|open|answer`, `text-descent-console-s1`, the encounter lines.
- New persistent rows per entities §2.8; `balance` in world meta as an
  integer (negative = CUST, positive = TEN, 0 = EVEN).

## Protocol and view models

- Intents: `descent.open`, `descent.deliver {item}`, `leaderboard.open
  {kind}`, `chronicle.open`, `season_door.enter`, `finale.choose {id,
  name?}`.
- `MenuView` for console, leaderboards, finale; `TextView` for the
  Chronicle; `toast` node-wide when the level opens ("The door in the
  concrete is open.") and at season end.

## Tests

- `test_contribution_weights_and_faction_credit`
- `test_depth_100000_opens_level_and_toasts_node_wide`
- `test_level_requires_crew_of_3_to_5_all_present_at_door`
- `test_instance_created_per_crew_and_torn_down_after_10_minutes`
- `test_max_4_live_instances`
- `test_scripted_encounter_lights_and_spawns_on_data_lift`
- `test_finale_seal_applies_halvard_plus_40_and_balance_cust`
- `test_finale_open_applies_minus_40_and_balance_ten_and_unlock_flag`
- `test_finale_answer_records_name_and_listening_plus_5`
- `test_finale_only_leader_can_choose`
- `test_chronicle_renders_template_with_crew_and_name`
- `test_season_advance_freezes_leaderboards_resets_relays_keeps_characters`
- `test_season_change_flushes_immediately`
- `test_seasons_json_validates_choice_ids_and_assets`
- `test_leaderboard_export_shape`

## Acceptance script

1. On a NetBBS node, deliver a `telemetry-unit-warm` at the Landing's
   descent console: the Depth bar rises by 0.5 % and the Ferrymen line
   moves on the faction board.
2. `blacksite admin season set-depth 99999`, deliver one data
   contribution: every caller sees the toast; `under-shaft-foot`'s season
   door now offers `[E]nter`.
3. With three callers in a crew standing at the door, enter: the level
   loads dark; lamps come on as the crew walks; the runner lifts the
   activation log and the whole gallery lights at once; the drone rises
   onto the platform and the two voices alternate in the log.
4. The leader chooses **Answer it** and accepts the default name: the
   Chronicle (`chronicle.open` from any terminal) shows the new paragraph
   with the crew and name; each member's sheet shows Listening +5 and
   Sablier −30.
5. `blacksite admin season advance --confirm`: leaderboards show
   "Season 1 (final)", relays are neutral, characters unchanged, the
   Chronicle keeps the paragraph, `season status` reports season 2
   pending content.

## Definition of done

- Tests green; validator covers `seasons/`, the new zone, sector, core.
- Fable review of the level and finale signed off in the PR.
- Design §13 updated with contribution weights.
- Slice file marked done with PR number.

## Implementer notes

- Instances must never share live state with the template zone: deep-
  copy objects and spawn fresh ICE per instance; the Shaft core's real
  (non-instanced) hardware in `under-shaft-foot` is not the instanced
  core.
- The finale is one transaction: standing, balance, Chronicle, flags.
  A crash between them must not leave a season half-finished.
- Season 2 content is deliberately not built here; `season advance`
  with no next definition parks the world in "between seasons" with
  contributions refused and a console line saying so.
- `{crew}` renders as the crew members' character names joined with
  commas and "and"; test with a wide-character name.
