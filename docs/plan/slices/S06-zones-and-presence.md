# S06 — Zones: map loading, movement, sight, multi-player presence, ZoneView

**Status:** planned
**Primary model:** Opus · **Reviewer:** Sonnet (test pass)
**Depends on:** S02, S03, S04 · **Milestone:** M1
**Issue:** https://github.com/Thiesi/blacksite/issues/6

## Goal

The first thing two callers can do together: stand in the same zone,
walk around at the design's speeds, see the tiles line of sight allows,
and see each other move. This slice builds zone instances in the
server, the movement and sight rules, the `ZoneView` view model with
deltas, and the client's zone renderer, using the Wake Hall map as the
first real zone. No combat, no NPCs, no chat yet.

## Spec references

- `docs/design/00-game-design.md` §2 (session shape; sleeper rule is
  S07), §5.1 (zones and tiles), §5.2 (movement and sight), §15 (tiers).
- `docs/design/01-entities.md` §1.1–§1.2 (zone, tile), §3.1 (actor),
  §3.2 (zone instance), §4 (`ZoneView`).
- `docs/design/02-architecture.md` §5.3–§5.4 (view/delta, `ZoneView`
  body), §6.1 (tick, dormant zones, seeded RNG), §7 (rendering).
- `docs/design/03-terminal-ui.md` §2 (layout, viewport scrolling,
  remembered tiles), §5.1 (movement keys), §6.
- `docs/world/01-gazetteer.md`: `vatside-wake-hall` (40×20, pocket,
  sight 10) and `vatside-clinics` (80×34, contested, sight 12) entries
  and sketches.

## Scope

- `src/blacksite/server/world/zone.py`: `ZoneInstance` per entity §3.2
  (actors, objects with live state, listeners, seeded RNG from
  `meta.rng_seeds[zone]`, tick counter, dormant flag); `wake()` computes
  elapsed ticks lazily; `activate/deactivate` on first/last listener.
- `src/blacksite/server/world/actors.py`: `Actor` per entity §3.1 with
  kinds `player` (NPC and drone kinds are fields now, behaviour in S11).
- `src/blacksite/server/world/movement.py`: intents `move(dir)` and
  `sprint(dir)` with 200 ms/100 ms per tile (2 and 1 ticks), diagonal
  same cost, passability from tile type, actor blocking (players do not
  pass through players), zone edge clamp; stamina drain for sprint
  (`00-game-design.md` §3.1: stamina pool; drain 2 per sprint tile;
  regen 1/tick when not sprinting; at 0 stamina sprint falls back to
  walk).
- `src/blacksite/server/world/sight.py`: symmetric line-of-sight
  (Bresenham over `opaque` tiles) within `sight_radius`; per-actor
  visible set recomputed only when the actor or an opaque object
  changes; stealth stance halves the range at which others see you
  (stance exists; setting it is S10/S16).
- `src/blacksite/server/world/registry.py`: `World` holding zone
  instances built from S02 content on start; `enter(actor, zone,
  tile)`, `leave(actor)`; the invariant that an actor is in at most one
  zone.
- `src/blacksite/server/views/zone_view.py`: builds `ZoneView.body`
  per §5.4 for a session: viewport rectangle centred on the actor
  (scroll in whole-tile steps when within 4 tiles of an edge), `tiles`
  with `-1` unseen / `-2` remembered (remembered set kept per player
  per zone in memory, persisted in S07), `actors` visible with `glyph`,
  `role` (`player_self`, `player_neutral`; faction roles come in S20),
  `name` only when targeted or in crew (both later; for now name shown
  for self), `objects`, `me` (name, handle, hp/sta placeholders from
  the actor, zone, safety), `hint`.
- `src/blacksite/server/views/delta.py`: revisioned view store per
  session, JSON-patch-like ops (`set path value`, `del path`, `tiles`
  row replace), full `view` when the session is >3 revisions behind or
  the viewport moved.
- `src/blacksite/door/views/zone.py`: renders `ZoneView` into the cell
  buffer per `03-terminal-ui.md` §2: header (zone, safety word in its
  role colour, clock from `me.clock`), viewport with tile glyphs and
  role colours per tier, remembered tiles dimmed, actors over tiles,
  side panel with placeholders for TARGET/NEARBY/CREW and real vitals
  bars, log panel (empty), hint.
- Keys: movement (arrows and vi keymaps, diagonals via Home/End/PgUp/
  PgDn and `yubn`), sprint via shift-arrows/uppercase; the client sends
  `key` frames; the server maps by keymap to intents.
- Content: `zones/vatside-wake-hall.map` + `.json` and
  `zones/vatside-clinics.map` + `.json` authored from the gazetteer
  entries (objects and exits placed; exit *behaviour* is S08, the exit
  tiles render now), plus a temporary `--spawn-zone` server flag so a
  session without a character (S07) enters `vatside-wake-hall` at its
  spawn tile as a placeholder actor named after the handle.
- Bot: `blacksite.bot` walks a random path in the zone (used in S29).

## Out of scope

- Characters, persistence of position, the Wake (S07).
- Zone transitions, safety enforcement (S08).
- Chat and the log content (S09).
- Combat, targets, NPCs (S10, S11).

## Data and content

- `zones/vatside-wake-hall.{map,json}`, `zones/vatside-clinics.{map,json}`
  validated by S02; tile IDs from the shipped `tiles.json`.
- `text/zone-vatside-wake-hall.md`, `text/zone-vatside-clinics.md`
  (atmosphere paragraphs copied from the gazetteer) shown once on first
  entry as a toast-length excerpt (full display via the map overview in
  S08).

## Protocol and view models

- `view {kind: "zone"}` and `delta` per §5.4; `key {k}` for movement;
  `intent {name: "resync"}` handled.
- `me.clock` is a server-local `HH:MM` string (timezone from upstream 04
  when present, else node local).

## Tests

- `tests/world/test_movement.py::test_walk_200ms_per_tile`,
  `::test_sprint_100ms_and_stamina_drain`, `::test_diagonal_same_cost`,
  `::test_wall_blocks`, `::test_actor_blocks_actor`,
  `::test_sprint_at_zero_stamina_walks`.
- `tests/world/test_sight.py::test_radius_10_in_wake_hall`,
  `::test_opaque_wall_blocks_los`, `::test_symmetric`,
  `::test_stealth_halves_range_to_be_seen`.
- `tests/world/test_zone_instance.py::test_dormant_until_listener`,
  `::test_lazy_wake_elapsed_ticks`, `::test_seeded_rng_deterministic`,
  `::test_actor_in_one_zone_only`.
- `tests/views/test_zone_view.py::test_viewport_centred_56x17`,
  `::test_scroll_within_4_tiles_of_edge`, `::test_unseen_minus1_remembered_minus2`,
  `::test_two_sessions_see_each_other`, `::test_delta_then_full_after_3_behind`.
- `tests/door/test_zone_render.py::test_golden_wake_hall_80x24`,
  `::test_golden_wake_hall_132x50`, `::test_wide_handle_self_name`.
- `tests/harness/test_two_players.py::test_b_sees_a_move` (headless: A
  moves 3 tiles, B's next delta shows the new position).

## Acceptance script

1. Server with `--spawn-zone vatside-wake-hall`; two callers enter the
   door from two NetBBS sessions (Telnet and SSH) at 80×24.
2. Both see the Wake Hall, their own `@` (self role colour), and the
   other's glyph. Walking with arrows moves at a visibly steady 5
   tiles/s; sprinting is faster and the STA bar drains.
3. Walk behind the corridor wall: the other player disappears; the
   tiles you saw stay dimmed.
4. One caller at 132×50: viewport larger, same world.
5. Idle 60 s: server `admin status` shows tick p99 under 5 ms.

## Definition of done

- Roadmap §7 holds.
- The two zone maps pass the validator and match the gazetteer's exits
  and objects by ID.
- Golden screens committed.

## Implementer notes

- Server-authoritative movement: the client never moves the glyph
  before the server's delta; on a 150 ms Telnet link this reads as a
  slight lag, which is the design (`00-game-design.md` §1.2).
- Keep `ZoneView` deltas small: send only rows of `tiles` that changed
  and actor entries that moved; the 2 KiB typical budget
  (`02-architecture.md` §11) is measured in the tests.
- Width safety in the header: the handle may be wide characters; the
  cell buffer truncates with `…`.
- Two callers may share one NetBBS node with `max_sessions` ≥ 2; the
  registered profile must have that raised (S04 acceptance step 1).
- Never read wall time in `movement.py` or `sight.py`; ticks only.

## Lore review integration

Implement day/night sight fields and typed state-dependent geometry now,
including service layout variants, warning tiles and alternate routes.
These are generic content capabilities consumed by S19/S24/S25. Safety
checks include delayed and indirect damage, forced movement, physical
bodies left at terminals and pocket boundaries. The view has compact
objective, hazard, service-expiry and escape fields (architecture 15).
