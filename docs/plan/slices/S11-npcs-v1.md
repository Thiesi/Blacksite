# S11 — NPCs v1: templates, spawners, behaviours, aggro by relations, Wardens

**Status:** planned
**Primary model:** Opus · **Reviewer:** Sonnet (test pass)
**Depends on:** S10 · **Milestone:** M1
**Issue:** https://github.com/Thiesi/blacksite/issues/11

## Goal

Populate the city: NPC templates spawn from zone spawners, run the
design's behaviours (idle, wander, patrol, guard, hunt, flee, vendor,
talker), pick fights by the faction relations matrix, and the Wardens
make safe zones safe with an escalating response and heat. After this
slice a lone player has a city that moves and shoots back, and the
Plaza punishes anyone who draws.

## Spec references

- `docs/design/00-game-design.md` §5.5 (behaviours, aggro by relations,
  Warden response 2 s, escalation, heat 10 min), §5.1 (spawners),
  §7.2 (relations matrix), §7.3 (Marked rule reads heat; Marked itself
  is S20).
- `docs/design/01-entities.md` §1.1 (`Spawner`), §1.8 (NPC template),
  §1.9 (faction relations), §3.1 (actor behaviour state).
- `docs/design/02-architecture.md` §6.1 (dormant zones, lazy wake,
  seeded RNG).
- `docs/world/01-gazetteer.md` spawner lists for the S08 hub zones;
  `docs/world/02-factions.md` (faction IDs, colours); `04-dramatis-
  personae.md` may still be in progress — name NPC template IDs by
  convention `npc_<faction>_<role>` and `npc_<name>` for named
  talkers, and leave dialogue to S27.

## Scope

- `src/blacksite/server/npcs/templates.py`: load `npcs.json` (entity
  §1.8) into templates; `factions.json` relations matrix loaded into a
  `relation(a, b) -> H|N|A` function (data from the design doc §7.2;
  full faction mechanics in S20 — here only the matrix and IDs).
- `src/blacksite/server/npcs/spawn.py`: spawner processing per zone:
  count, region or tile, respawn seconds, condition (`always`,
  `event:<id>` for S24, `per_player` for the Wake drone); lazy catch-up
  on zone wake (respawn timers computed from elapsed ticks, capped at
  count); despawn when a zone has been dormant 30 min (except named
  anchors).
- `src/blacksite/server/npcs/behaviours.py`: a small behaviour tree
  per actor: `idle` (stand), `wander` (random walk within a region,
  200–1000 ms pauses), `patrol` (waypoints, loop or bounce), `guard`
  (hold tile; aggro on hostile within sight; return when lost), `hunt`
  (chase target with the movement rules; give up after 20 s without
  sight), `flee` (below 20 % health, move away from the attacker,
  toward the nearest exit or vat), `vendor` and `talker` (stand; `E`
  opens a stub `MenuView` "Not yet." until S12/S27). Transitions
  driven by health, sight, and relations; each actor evaluates every 5
  ticks, staggered by id to spread load.
- Aggro rules: an NPC attacks actors whose faction is hostile to its own
  in `contested`/`open` zones; neutral and allied are ignored; Freelance
  players (no faction) are neutral to everyone except in `open` zones
  where `none`-lean zones' spawners (feral, drones) are hostile to all.
  A player who attacks an NPC becomes that NPC's target and hostile to
  its spawner group for 5 minutes.
- Wardens: patrol/response templates show a warning within 2 s for a
  refused safe-zone attack, recording 10 min heat. Safe/pocket actors
  cannot be damaged by Wardens or other NPCs. Outside safety, use design
  5.5's patrol/response behaviour and heat; Curfew doubles new heat only.
  An enemy's faction never overrides the physical safety label. Freelance
  residents are neutral to faction patrols unless an explicit unsafe
  perimeter or provocation rule applies. Perimeter danger is labelled
  before entry; the Landing pocket remains safe for everyone.
- Wake drone spawner moves onto this engine (`per_player`).
- NPC death: XP hook (value on the template; awarded in S16), loot
  table roll into a corpse cache (S10's cache with the NPC's table).
- `ZoneView.actors` gets `role: npc_<faction>` and the NEARBY list
  shows NPCs with a relation tag (`!` hostile, `~` neutral, `+`
  allied), always present as a glyph regardless of colour.
- Hub content: spawners and templates for the S08 zones per the
  gazetteer (Wardens, civilians, courier drones on the Plaza; Kestrel
  staff and commuters at the hub; Sablier orderlies; Sable enforcers,
  crowds, plainclothes Wardens on Sodium Row; regulars and a bouncer in
  the Halo; residents on Block Street).

## Out of scope

- Dialogue and named NPC lines (S27); vendors' inventories (S12).
- Marked, faction membership, standing changes from kills (S20).
- Event-conditioned spawners' events (S24), Undercity/Scour fauna (S25).
- Drones as Operator tools (S16).

## Data and content

- `npcs.json` with the hub templates and `npc_wake_drone`; `factions.json`
  with IDs, short names, colours and the relations matrix (declared
  asymmetries list empty — the factions doc keeps them narrative);
  spawner lists added to the ten hub zone sidecars.

## Protocol and view models

- `ZoneView.actors[].role`, `ZoneView.nearby[].relation`,
  `me.heat_until`, header heat word; no new intents.

## Tests

- `tests/npcs/test_spawn.py::test_count_and_respawn`,
  `::test_lazy_catchup_capped_at_count`, `::test_despawn_after_dormant_30min`,
  `::test_per_player_spawner`.
- `tests/npcs/test_behaviours.py::test_wander_stays_in_region`,
  `::test_patrol_loops_waypoints`, `::test_guard_aggro_on_hostile_in_sight`,
  `::test_hunt_gives_up_after_20s`, `::test_flee_below_20pct`,
  `::test_eval_every_5_ticks_staggered`.
- `tests/npcs/test_aggro.py::test_hostile_matrix_attacks`,
  `::test_neutral_ignored`, `::test_freelance_neutral_in_contested`,
  `::test_open_none_lean_hostile_to_all`, `::test_attacker_becomes_target_5min`.
- `tests/npcs/test_wardens.py::test_warning_within_2s_in_safe_without_damage`,
  `::test_safe_warning_never_escalates_to_damage`, `::test_heat_10min_persisted`,
  `::test_heat_engaged_on_sight_in_contested`,
  `::test_no_pursuit_into_pocket`.
- `tests/harness/test_plaza.py::test_fire_in_plaza_summons_wardens`.
- `tests/content/test_hub_spawners.py::test_hub_spawners_validate`.

## Acceptance script

1. Enter Meridian Plaza: Wardens patrol, civilians wander, a courier
   drone crosses. NEARBY shows `~` tags.
2. `Tab` a civilian, `F`: refused (S10), and within 2 s two Wardens
   arrive and issue a warning. Repeated refused shots cannot injure you
   or the civilian; heat appears in the header.
3. Walk into Clinic Row with heat: a Warden patrol engages on sight.
   Ten minutes later it does not.
4. On Sodium Row, attack a regular: Sable enforcers, not Wardens,
   respond.
5. Leave a zone for 35 minutes (or use a manual-clock test): the
   dormant actors are rebuilt from their spawners on return.
6. `admin status` tick p99 under 10 ms with all hub zones active.

## Definition of done

- Roadmap §7 holds; step 6 recorded in the PR.
- The relations matrix in `factions.json` equals `00-game-design.md`
  §7.2 (a test compares the table to the doc's fixture copy).

## Implementer notes

- NPC pathing is greedy step-toward-target with wall sliding; no A*
  in this slice (zones are small and NPCs give up); note it for S29 if
  profiling says otherwise.
- Behaviour evaluation must be deterministic per zone RNG so the
  Plaza test is stable.
- Everything NPCs do is visible to callers as `ZoneView` deltas; many
  NPCs wandering is the first real bandwidth test — keep the wander
  pause distribution wide so deltas stay under budget.
- `RLIMIT_NPROC` and process limits are irrelevant here (single
  server process), but the tick budget is not: staggered evaluation
  is required, not optional.

## Lore review integration

Mission NPCs have scoped ownership and consent/subdue states; removing a
mission guard never kills the city's permanent handler. Implement generic
warned maintenance drones and bounded spawners from main design 18.
Test safe-clinic availability, willingness on escort, nonlethal subdue,
public service fallback and indirect harm attribution. No essential
vendor, vat or story contact can be permanently removed by another player.
