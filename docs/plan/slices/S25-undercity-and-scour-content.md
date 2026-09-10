# S25 — Undercity and Scour content: all remaining zone maps, spawners, salvage rings

**Status:** planned
**Primary model:** Gemini or Sonnet · **Reviewer:** Sonnet (validator plus a read of each zone), Human for `under-shaft-foot` and `scour-ring-4`
**Depends on:** S08, S11, S17 · **Milestone:** M5
**Issue:** (filled in when filed)

## Goal

Author every zone map the game still lacks after S08: the five Undercity
zones and the five Scour zones, with their spawners, relays, terminals,
hardware objects, exits, and lore hooks, exactly as the gazetteer
describes them. This is a bulk content slice: no engine code, every
file must pass the validator, and every zone must be walkable end to
end through its listed exits.

## Spec references

- `docs/world/01-gazetteer.md`: the ten zone entries below, the sketch
  legend, and the overview table (sizes).
- `docs/design/01-entities.md` §1.1 (zone file fields), §1.2 (tile
  types), §5 (invariants: exits resolve, objects on passable tiles,
  spawner regions non-empty, hardware tiles for cores).
- `docs/design/00-game-design.md` §5.1 (sizes 40–200 × 20–100, safety
  classes), §5.2 (sight radius; Undercity 5 unless lit), §7.4 (Scour
  relays pay triple), §8.4 (salvage grades), §12 (Ring-fall rings).
- `docs/world/03-lattice.md` core catalog for the hardware locations of
  the Drowned, Outworks, Shaft, Landing, and relay-uplink cores.
- `docs/world/04-dramatis-personae.md` "The Undercity" and "The Scour"
  minor cast (anchor NPC slugs).
- `docs/design/04-assets.md` §3 (map authoring rules).

## Scope

Deliver, for each zone, `content/zones/<id>.map` and
`content/zones/<id>.json`:

| Zone | Size | Class | Must contain |
|---|---|---|---|
| `under-service` | 120 × 50 | open | exits to `vatside-vat-row` (ladder), `chapel-towers` (drain stair), `under-drowned`, `under-caverns` (breach); two orphan terminals; Unmoored dead drop object; spawners: rogue maintenance drones (hunt), feral dogs (hunt) |
| `under-drowned` | 100 × 60 | open | water tiles over ≥ 30 % of the map; exits `under-service`, `under-outworks` (sealed bulkhead, requirement: Undercity key); hardware terminal for the Drowned core (tier 3); Ferrymen corpse object (one-time map); spawners: water hunters from water tiles |
| `under-caverns` | 150 × 80 | open | exits `under-service`, `sink-floor` (Sump grate), `under-outworks` (fissure); **Cavern Relay** with orphan terminal; Ferrymen way-station vendor; spawners: feral things (several templates), blind swarms |
| `under-outworks` | 120 × 70 | open | exits `under-drowned`, `under-caverns`, `under-shaft-foot` (inner door); **Outworks Relay**; hardware terminal for the Outworks core (tier 4); Halvard survey markers (lore objects); spawners: Blacksite maintenance drones (guard) |
| `under-shaft-foot` | 60 × 60 | open | exit `under-outworks`, `spire-shaft-head` (shaft, requirement: story); hardware terminal for the Shaft core (tier 5, shared with Shaft Head, the one two-location core); the **season door** object (`descent_console` kind with a `season_door` param); spawners: maintenance drones (guard, many) plus an Exhale-conditioned spawner |
| `scour-landing` | 60 × 30 | pocket | exits `scour-ring-1` (causeway), `scour-ring-2` (Ferrymen track), `tramyard-wall-gate` per gazetteer; Ferrymen terminal (Landing core, tier 2); anchors: Anouk, quartermaster, contract handler, salvage buyer; spawners: Ferrymen guards (aggro on Halvard and Kestrel) |
| `scour-ring-1` | 160 × 80 | open | exits `tramyard-wall-gate`, `scour-landing`, `scour-ring-2`; **Mile Relay**; the convoy road as a marked tile line with waypoint objects; spawners: Halvard patrols, Kestrel road crews, scavengers; Ring-fall region |
| `scour-ring-2` | 180 × 90 | open | exits `scour-ring-1`, `scour-landing`, `scour-ring-3`; **Beacon Relay**; Ferrymen way-camp with light objects; spawners: Ferrymen salvage crews (neutral), wildlife; Ring-fall region |
| `scour-ring-3` | 200 × 100 | open | exits `scour-ring-2`, `scour-ring-4` (bearing, no road); **Crash Relay** inside the largest wreck; wreck-field landmarks as cover clusters; spawners: wildlife packs, scavenger gangs, Halvard recovery; Ring-fall region |
| `scour-ring-4` | 200 × 100 | open | exit `scour-ring-3`; **Far Relay** on the telemetry mast with an orphan terminal; season artifact sites (`cache` objects, empty until S26 fills them); spawners: apex wildlife, Custodian drones (guard) |

Also:

- Day/night sight for the Scour: the `.json` carries `sight_radius` and
  `sight_radius_night` (gazetteer: 20:00–06:00 node-local); the engine
  side of that field is a one-line addition to S06's loader and is in
  scope here only if S06 did not ship it.
- Ring-fall regions: each Scour ring `.json` has a `salvage_regions[]`
  list with grade weights rising outward (ring 1: hull/optics; ring 4:
  power/compute/intact) per design §8.4 and the gazetteer.
- Every zone lists its `lore` assets: the zone atmosphere text
  (`zone-<id>`) plus any found text the gazetteer places there.
- A `docs/world/01-gazetteer.md` cross-check table appended to the PR
  (not the doc): zone, gazetteer size, authored size, exits verified.

## Out of scope

- Engine behaviour of relays (S21), salvage nodes (S17), spawners and
  behaviours (S11), the season door (S26), Blacksite Level 1 (S26).
- The city zones (S08). Sector and core files (S13/S14).
- ANSI vignettes for districts (S33).

## Data and content

- Map format: entities §1.1. `.map` is a UTF-8 grid of legend characters
  defined in `content/tiles.json` (S02/S06). Use only tile ids that
  exist; add a tile type only with a matching `tiles.json` entry and a
  glyph from `glyphs.json`.
- Object kinds available: door, terminal, vendor, vat, relay, cache,
  tram_stop, apartment_door, light, hardware, descent_console, workshop,
  bank (entities §1.1). Lore markers use `cache` with `lore` params.
- NPC template slugs come from `content/npcs.json` (S11); if a gazetteer
  spawner names a creature that has no template, add the template with
  the gazetteer's description and grade guess, and flag it in the PR.

## Protocol and view models

None. Content only.

## Tests

- `test_all_ten_zones_load_under_validator`
- `test_zone_sizes_match_gazetteer_targets_within_10_percent`
- `test_every_exit_resolves_both_ways` (each exit has a return exit in
  the target zone unless the gazetteer says one-way)
- `test_every_relay_has_control_terminal_and_core_hardware`
- `test_scour_rings_have_salvage_regions_with_rising_grades`
- `test_undercity_sight_radius_is_5_without_light_objects_nearby`
- `test_walkability_from_each_entry_exit_to_each_other_exit` (BFS over
  passable tiles)
- `test_no_object_on_impassable_tile`
- `test_spawner_regions_non_empty_and_templates_exist`
- `test_lore_assets_referenced_exist`
- `test_shaft_core_has_exactly_two_hardware_locations`

## Acceptance script

1. Start the server with the full content tree; `blacksite admin status`
   reports 35 zones loaded.
2. At 80×24, walk from `vatside-vat-row` down the ladder into
   `under-service`; the sight radius visibly drops to 5; find both orphan
   terminals; descend to `under-drowned` (water slows movement), then
   with an Undercity key through the bulkhead to `under-outworks`, and
   through the inner door to `under-shaft-foot`; interact with the season
   door and see the Depth text.
3. From `tramyard-wall-gate` walk `scour-ring-1` → `-2` → `-3` → `-4`,
   touching each relay's terminal (interaction shows its name) and the
   Far Relay's orphan terminal.
4. `blacksite admin event force ringfall scour-ring-3`: salvage nodes
   appear inside the ring's regions only.
5. Open the zone map overview (`M`) in `under-caverns` at 132×50: the
   whole 150 × 80 map renders without horizontal scroll artefacts.

## Definition of done

- Validator and tests green for all ten zones plus the fixture tree.
- Reviewer has walked each zone once; the two human-review zones signed
  off by the user.
- Slice file marked done with PR number.

## Implementer notes

- Author at the gazetteer's target size; the sketches are 1:3 to 1:5
  proportion guides, not tiles.
- Keep cover clusters (`%`) dense in the Scour rings so real-time combat
  has positions; wide open floor makes ranged tier-3 weapons dominant.
- Water tiles are passable, slow, no cover (legend); hazard tiles carry
  `dps` and a damage type from `tiles.json`.
- `under-shaft-foot` and `spire-shaft-head` share one core: the loader
  must accept a `hardware` list of two locations for exactly that core
  and reject it elsewhere (gazetteer note; test above).
- Large maps (200 × 100) must still load under the architecture §11
  3-second start budget; keep the `.json` lean (regions, not per-tile
  entries).
- A Gemini batch should be split per zone and each file validated before
  the next is generated; do not accept a batch that fails walkability.
