# S24 — World events engine and the five events

**Status:** planned
**Primary model:** Opus · **Reviewer:** none
**Depends on:** S11, S13, S17 · **Milestone:** M5
**Issue:** https://github.com/Thiesi/blacksite/issues/24

## Goal

Make the city move on its own. A server-side event engine schedules
Ring-fall, Curfew, Choir Surge, Exhale, and Convoy by weight and
cooldown, applies their typed effects to zones and sectors, announces
them in voice at start, middle, and end, and lets the SysOp force or
cancel any of them. Events are content: the engine knows effect types,
not event names.

## Spec references

- `docs/design/00-game-design.md` §12 (event table with durations and
  effects), §7.4 (relays uncapturable during Curfew; Scour relays),
  §5.5 (Warden heat), §6.3 (ICE classes), §8.4 (salvage nodes).
- `docs/design/01-entities.md` §1.12 (event template), §3.8 (event
  instance), §3.2 (zone `event_effects`), §2.11 (event cooldowns in world
  meta).
- `docs/design/02-architecture.md` §2.3 (`event force`, `event cancel`),
  §6.1 (dormant zones wake lazily; timers), §5.3 (`toast`, `log`).
- `docs/world/05-story-arcs.md` "World-event announcements" (the exact
  start/mid/end texts and their placeholders `{ring}`, `{spoke}`,
  `{gate}`, `{route}`, `{waypoint}`, `{destination}`, `{losses}`).
- `docs/world/01-gazetteer.md` Scour rings (`scour-ring-1` … `-4`), the
  convoy road, the Core gates; `docs/world/03-lattice.md` for ICE class
  swaps and the Silt map reveal.

## Scope

- `src/blacksite/server/events.py`: `EventEngine` with a scheduler tick
  (once per 10 s), weighted random selection among templates whose
  cooldown has elapsed and whose `where` is not already under an event,
  at most two concurrent events node-wide, never two in the same zone.
- Typed effects (closed set; adding one is a slice change):
  `spawn_salvage {zone, count, grades}`, `spawn_npc_crew {zone, template,
  count}`, `hazard_tiles {zone, count, dps, type}`, `seal_zone {zone}`
  (exits refuse entry/exit; players inside are safe-class for the
  duration), `relay_lock {zones}`, `heat_multiplier {factor}`,
  `ice_mutate {sectors}` (random class swap per ICE instance, restored
  at end), `ability_bonus {archetype, percent}`, `silt_reveal`,
  `spawn_multiplier {zone, factor}`, `key_drop {zone, item, chance}`,
  `door_cell_reveal {sector}`, `auto_contract {template, factions}`,
  `npc_convoy {route zones, waypoints, template}`.
- The five templates in `content/events.json` with the design §12
  numbers: Ring-fall 20 min over one Scour ring (chosen at start; the
  announcement's `{ring}` is that ring's name), Curfew 60 min sealing
  the Core's three zones, Choir Surge 15 min over all sectors, Exhale
  30 min over the Undercity, Convoy 25 min along the road
  `tramyard-wall-gate` → `scour-ring-1` → `scour-ring-2` → `scour-landing`.
- Announcements: start/mid/end text assets delivered to every session's
  log as channel `system` and as a `toast`; mid fires at half duration.
  Header countdown (`ZoneView.event`) shows name and remaining time for
  sessions in affected zones or sectors; a short form for others.
- Effects are reversible: every applied effect records an undo; end or
  cancel runs the undos in reverse. Server restart mid-event restores the
  event from `world meta` with its remaining time and reapplies effects
  from the template (not from the undo log).
- Cooldowns persist in world meta (entities §2.11). Initial cooldowns
  are randomised at first start so a fresh world does not fire all five
  in the first hour.
- Admin endpoint commands `event list`, `event force <id> [zone]`,
  `event cancel <id>`; S28 wires the CLI.
- Wake dormant zones affected by an event (architecture §6.1) so
  salvage and NPC crews exist when a player arrives.

## Out of scope

- Salvage node pickup and grading (S17). NPC crew behaviours (S11).
  Relay capture rules (S21 checks `relay_lock`). Season contribution
  keys dropped by Exhale are items from S26's content.
- The Convoy's escort/raid contract templates (S19; this slice only
  calls `auto_contract`).
- The Curfew halving after a Seal finale (S26 applies a weight override).

## Data and content

- `content/events.json` per entities §1.12: `id, name, where, duration,
  cooldown, weight, effects[], announce {start, mid, end}`. Cooldowns:
  Ring-fall 90 min, Curfew 4 h, Choir Surge 3 h, Exhale 2 h, Convoy
  60 min; weights 5/2/2/3/4. These are initial values; record them in
  design §12 in the same PR (the table currently lists only durations).
- Text assets `event-<id>-start|mid|end` converted from the story-arcs
  document; placeholders resolved by the engine.
- `content/routes.json` for the convoy road (ordered zone ids with
  waypoint tiles).

## Protocol and view models

- `ZoneView.event {name, remaining}` and the same field on
  `LatticeView`; `toast` at start and end; `log` lines for all three
  beats.
- No new client intents.

## Tests

- `test_scheduler_respects_cooldown_and_weights` (seeded RNG)
- `test_no_two_events_in_same_zone`
- `test_max_two_concurrent_events`
- `test_ringfall_spawns_salvage_in_chosen_ring_only`
- `test_curfew_seals_core_exits_and_locks_relays`
- `test_curfew_players_inside_are_safe_class`
- `test_choir_surge_mutates_ice_and_restores_at_end`
- `test_choir_surge_cantor_bonus_30_percent`
- `test_exhale_triples_spawn_rate_and_reveals_door_cell`
- `test_convoy_walks_route_and_posts_auto_contract`
- `test_announcements_fire_start_mid_end_with_placeholders`
- `test_cancel_runs_undo_in_reverse`
- `test_restart_mid_event_restores_remaining_time_and_effects`
- `test_event_wakes_dormant_zone`
- `test_event_view_field_present_only_in_affected_zones`
- `test_events_json_validates_effect_types_closed_set`

## Acceptance script

1. Start the server with a fresh world; `blacksite admin event list`
   shows five templates with randomised cooldowns.
2. Log in at 80×24 in `core-plaza`. Run `blacksite admin event force
   curfew`. The log shows Brann's start line; the header shows
   "Curfew 59m"; walking to any Core exit is refused with "The gates
   are sealed."; a second caller in `sink-rim` sees a shorter header
   note and can be attacked by Wardens with doubled heat.
3. `blacksite admin event cancel curfew`: end line appears, gates open.
4. Force `ringfall`; walk to the named ring through Gate Nine; salvage
   nodes and NPC crews are present; at 10 minutes the mid line appears.
5. Force `choir-surge` while jacked in: ICE labels change class; a
   Cantor's hymn shows +30 % in its cooldown label; the Silt descent cell
   is drawn on the sector map.
6. Restart the server during `exhale`; on reconnect the header countdown
   continues from where it was.

## Definition of done

- Tests green; validator covers `events.json` and `routes.json`.
- Design §12 updated with cooldowns and weights.
- Slice file marked done with PR number.

## Implementer notes

- Effects touch other subsystems through small, explicit hooks
  (`zones.seal`, `relays.lock`, `ice.mutate`, `spawners.multiplier`);
  do not reach into their private state.
- Undo must be idempotent: a zone sealed twice by a bug is unsealed once
  and stays consistent.
- Placeholder resolution must never leave `{...}` in a log line; a test
  greps the rendered announcements.
- The engine runs on the tick loop's clock, not `time.time()`, so tests
  can step it (AGENTS.md §4 determinism).
