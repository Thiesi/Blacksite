# S08 — City graph: exits, transitions, safety classes, pockets, the Core and Vatside and Sodium Row maps

**Status:** planned
**Primary model:** Sonnet · **Reviewer:** Opus (map review of the hub zones)
**Depends on:** S06 · **Milestone:** M1
**Issue:** https://github.com/Thiesi/blacksite/issues/8

## Goal

Make the city walkable: exits move actors between zones (street, door,
tram with its timed ride), safety classes and pockets are enforced as
flags the combat slice will read, and the first hub of real zones
exists. After this slice a player can walk from the Wake Hall through
Clinic Row to Meridian Plaza, ride the tram, and reach the Tin Halo.

## Spec references

- `docs/design/00-game-design.md` §5.1 (safety classes, pockets), §5.6
  (interactions: exits, tram stops, doors), §2 (logout rules by zone
  class).
- `docs/design/01-entities.md` §1.1 (`Exit`, `Region`, `ObjectSpec`).
- `docs/design/03-terminal-ui.md` §5.1 (`M` map overview), §4 (menus).
- `docs/world/01-gazetteer.md`: `core-plaza` (90×40), `core-tram-hub`
  (80×30), `core-precinct` (50×24), `vatside-wake-hall` and
  `vatside-clinics` (from S06), `vatside-vat-row` (90×36), `sodium-row`
  (100×30), `sodium-tin-halo` (44×22), `terraces-blocks` (120×40),
  `terraces-lobby` (40×24), plus their exits and the tram note (a tram
  departs every 90 s, 10 s ride).
- `docs/design/04-assets.md` §3 (map authoring rules).

## Scope

- `src/blacksite/server/world/exits.py`: interact on an exit tile (or
  walking onto a `street` exit) moves the actor to the target zone and
  tile; kinds `street` (instant), `door` (instant, may be locked:
  requirement `key`, `pass`, `faction standing`, or a control state set
  by S15), `ladder`/`lift` (1 s), `gate` (requirement), `cable`
  (3 s), `tram` (board at a platform; departure every 90 s of the persistent service
  clock; 10 s ride shown as a `TextView` "The tram hums."; arrival at
  the destination platform); requirement failures post a log line and
  do nothing else.
- `src/blacksite/server/world/safety.py`: `safety_at(zone, tile)`
  returning `safe`, `pocket`, `contested`, `open` from the zone class
  and pocket regions; exposed on `ZoneView.me.safety` and used by
  S07's logout rule (safe and pocket → instant, else sleeper).
- Zone entry: first-visit discovery flag per player (XP in S16), the
  zone atmosphere excerpt as a toast, remembered tiles per zone.
- `M` map overview: a `TextView` listing the current district's zones,
  their class, known exits, and the atmosphere paragraph; a `MenuView`
  of visited zones with the class column.
- Content: the ten hub zone maps above, authored from the gazetteer
  sketches at the target sizes with every object, exit, terminal,
  relay, vendor anchor and pocket region placed by ID (behaviour for
  vendors, terminals and relays arrives in S12/S13/S21; they render as
  objects now). `text/zone-<id>.md` for each.
- Tram departures use the persistent clock. Waking a zone cannot reset
  its timetable. S15 may hold a departure for 30 s at most, then 120 s
  immunity; in-flight rides complete and outbound Core travel remains
  available during Curfew. Clinic service counters are safe pockets;
  the Cold Chain capture terminal remains in the contested street.

## Out of scope

- Remaining district, Undercity, Scour maps (S25).
- Combat consequences of safety classes and Marked (S10, S20).
- Locked-door hacking via controls (S15), passes as items (S12).
- Zone discovery XP (S16).

## Data and content

- `zones/{core-plaza,core-tram-hub,core-precinct,vatside-vat-row,
  sodium-row,sodium-tin-halo,terraces-blocks,terraces-lobby}.{map,json}`
  and the S06 pair updated with real exits; `text/zone-<id>.md` × 10.
- Every exit must be bidirectional unless the gazetteer says otherwise;
  the validator (S02) already checks resolution; add a bidirectionality
  warning here.

## Protocol and view models

- `intent {name: "interact"}` on exit objects; `view {kind: "text"}`
  for tram rides; `ZoneView.me.safety`; `ZoneView.event` unchanged.
- `MenuView` for the map overview.

## Tests

- `tests/world/test_exits.py::test_street_exit_instant`,
  `::test_door_locked_by_pass_logs_and_stays`, `::test_lift_1s`,
  `::test_tram_departs_every_90s_ride_10s`,
  `::test_tram_lazy_wake_departure`, `::test_exit_target_tile_passable`.
- `tests/world/test_safety.py::test_pocket_inside_contested`,
  `::test_safety_word_on_view`, `::test_logout_instant_in_pocket`.
- `tests/content/test_hub_maps.py::test_ten_hub_zones_validate`,
  `::test_exits_bidirectional`, `::test_sizes_match_gazetteer`,
  `::test_every_gazetteer_object_present_by_id`.
- `tests/harness/test_walk_city.py::test_wake_hall_to_tin_halo_path`
  (scripted: Hall → Clinic Row → Plaza → Neon Stair → Sodium Row → Tin
  Halo, asserting zone after each transition and the tram from the hub
  to `vatside-clinics` and back).

## Acceptance script

1. From the Wake Hall walk to the Wake door, `E`: Clinic Row. Header
   says `contested`. Walk Sablier Boulevard to Meridian Plaza: `safe`.
2. Tram hub: stand on a platform, `E`, wait for departure (≤ 90 s),
   "The tram hums." for 10 s, arrive at Clinic Row's platform.
3. Neon Stair to Sodium Row, the Halo's door: `pocket` in the header.
4. `M` shows the district overview with the zones you have visited.
5. A second caller in Meridian Plaza sees you arrive from the Boulevard.

## Definition of done

- Roadmap §7 holds; the Opus map review of the four hub zones (Plaza,
  Clinic Row, Sodium Row, Tin Halo) recorded in the PR.
- Gazetteer updated if a map had to deviate from its sketch.

## Implementer notes

- Zone transitions must not leak the old zone's remembered tiles into
  the new view: send a full `view` on every zone change.
- Zone maps are the largest content files; keep the `.map` files pure
  grids and all metadata in the sidecar so diffs stay readable.
- Tram rides are the first "the world does something without a key
  press" behaviour the client sees; the `TextView` must accept `Esc`
  as "look at the log" without cancelling the ride.
- Ten zones at up to 120×40 is ~50 000 tiles; the validator must stay
  fast (< 1 s) — precompute passability grids once.

## Active content boundary

The ten-zone hub is a complete playable bundle. Exits to S25 maps are
shown as unavailable construction boundaries until that bundle lands;
never load a dangling target or invent a fake copy of a future zone.
S25 joins every real exit into the full ordinary city and S26 activates
the season door. Baseline return routes remain visible and passable.
