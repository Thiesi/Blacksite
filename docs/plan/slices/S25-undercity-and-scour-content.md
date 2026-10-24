# S25 — Undercity and Scour content: all remaining zone maps, spawners, salvage rings

**Status:** in progress
**Primary model:** Gemini or Sonnet · **Reviewer:** Sonnet (validator plus a read of each zone), Human for `under-shaft-foot` and `scour-ring-4`
**Depends on:** S08, S11, S14, S17, S21, S24 · **Milestone:** M5
**Issue:** https://github.com/Thiesi/blacksite/issues/25

## Goal

Author every zone map the game still lacks after S08: the fourteen remaining
Spire, Tramyard, Sink, Chapel and Old Works zones, five Undercity zones and
five Scour zones, with their spawners, relays, terminals, hardware objects,
exits, and lore hooks, exactly as the gazetteer describes them. This is a
bulk content slice with the bounded physical-access support below.
Every file must pass the validator, and
every zone must be walkable end to end through its listed exits.

## Spec references

- `docs/world/01-gazetteer.md`: all 24 remaining ordinary zone entries,
  including the ten below, the sketch legend, and the overview table
  (sizes).
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
| `under-outworks` | 120 × 70 | open | exits `under-drowned`, `under-caverns`, `under-shaft-foot` (inner door); **Outworks Relay**; hardware terminal for the Outworks core (tier 5); Halvard survey markers (lore objects); spawners: Blacksite maintenance drones (guard) |
| `under-shaft-foot` | 60 × 60 | open | exit `under-outworks`, `spire-shaft-head` (shaft, requirement: story); hardware terminal for the Shaft core (tier 5, shared with Shaft Head, the one two-location core); the **season door** object (`descent_console` kind with a `season_door` param); spawners: maintenance drones (guard, many) plus an Exhale-conditioned spawner |
| `scour-landing` | 60 × 30 | pocket | exits `scour-ring-1` (causeway), `scour-ring-2` (Ferrymen track); Ferrymen terminal (Landing core, tier 2); anchors: Anouk, quartermaster, contract handler, salvage buyer; spawners: Ferrymen guards (warn only within the safe pocket; perimeter aggro outside) |
| `scour-ring-1` | 160 × 80 | open | exits `tramyard-wall-gate`, `scour-landing`, `scour-ring-2`; **Mile Relay**; the convoy road as a marked tile line with waypoint objects; spawners: Halvard patrols, Kestrel road crews, scavengers; Ring-fall region |
| `scour-ring-2` | 180 × 90 | open | exits `scour-ring-1`, `scour-landing`, `scour-ring-3`; **Beacon Relay**; Ferrymen way-camp with light objects; spawners: Ferrymen salvage crews (neutral), wildlife; Ring-fall region |
| `scour-ring-3` | 200 × 100 | open | exits `scour-ring-2`, `scour-ring-4` (bearing, no road); **Crash Relay** inside the largest wreck; wreck-field landmarks as cover clusters; spawners: wildlife packs, scavenger gangs, Halvard recovery; Ring-fall region |
| `scour-ring-4` | 200 × 100 | open | exit `scour-ring-3`; **Far Relay** on the telemetry mast with an orphan terminal; season artifact sites (`cache` objects, empty until S26 fills them); spawners: apex wildlife, Custodian drones (guard) |

Also:

- Day/night sight is content only here. S06 owns the sight fields and
  S24 their event composition; do not add engine branches in this slice.
- Also deliver every remaining Spire (3), Tramyard (3), Sink (3), Chapel
  Ward (2) and Old Works (3) map from the gazetteer. Place their named
  handlers, core hardware, relay objects, service work-order targets and
  both allocation layouts. This closes the original unmapped-city gap.
- Validate the complete 34-zone ordinary city as one connected bundle,
  including all eight halls, 16 relays, public uplinks, mission permits
  and every S19/S27 target. S26 supplies the separate finale instance.
- Each Scour ring has one `salvage_field` object with integer `ring`
  1-4. `salvage.json` owns the canonical outward-rising grade weights.
  Ring-fall impact regions are separate typed event regions; do not add
  the obsolete `salvage_regions` sidecar field (entities section 1.7).
- Every zone lists its `lore` assets: the zone atmosphere text
  (`zone-<id>`) plus any found text the gazetteer places there.
- A `docs/world/01-gazetteer.md` cross-check table appended to the PR
  (not the doc): zone, gazetteer size, authored size, exits verified.

## Out of scope

- Engine behaviour of relays (S21), salvage nodes (S17), spawners and
  behaviours (S11), the season door (S26), Blacksite Level 1 (S26).
- Redesigning the ten initial hub maps. Add their real district exits,
  Terraces' 24 apartments, and the necessary service bindings while
  preserving existing public anchors. Commission sector/core bindings
  and the residence register; do not redesign their existing graphs.
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

The existing server travel path gains typed member/story credentials,
alternative requirements and a content refusal message, as specified in
game 5.6 and entities 1.1. This is required to commission the gazetteer's
standing-or-pass Atrium lift and membership/story service lift without
inventing credentials or admitting every friendly nonmember. The Shaft
cage stays closed until S26 supplies committed finale authorization.
No new protocol frame or client-side permission calculation is added.
Other mechanics remain the existing engines; this does not implement a
season. Missing NPC profiles use the initial game 5.5 balance table and
must be assessed on real routes, rather than claimed as tuned already.

The optional Drowned bulkhead accepts a carried key or its local
core-opened latch state. Ordinary Outworks-to-Shaft-Foot access stays
free of event/key prerequisites, following the higher-level game 12/13
rules. The lower Gazetteer consumption rule is corrected accordingly.
All Undercity base sight uses game 5.2's five tiles before carried-light
benefits. Explicit Interact can use a physically found hidden exit;
hidden travel never triggers merely by walking across its tile.

Commissioning also exposed three practical engine gaps: real walled
apartments must not freeze public geometry controls; salvage must not
spawn on a permanent hazard that interrupts every harvest; and a saved
position inside an expired passage must recover to reachable public
ground without entering a private room. The bounded fixes implement
game 5.2/8.4/8.7, with actual-map regressions. They add no new gameplay
system. The Shaft Relay's `requires_level` gate remains owned by S26;
16 sites exist physically, with 15 available before that level opens.

The Mezzanine's loan terminal and Far mast keep the normal network
gates in Lattice 2. Physical admission does not grant Citadel access,
and the Far mast does not bypass Static's Ring-fall requirement.

## Tests

- `test_all_24_remaining_zones_load_under_validator`
- `test_zone_sizes_match_gazetteer_targets_within_10_percent`
- `test_every_exit_resolves_both_ways` (each exit has a return exit in
  the target zone unless the gazetteer says one-way)
- `test_every_relay_has_control_terminal_and_core_hardware`
- `test_scour_fields_use_canonical_outward_rising_grade_weights`
- `test_undercity_sight_radius_is_5_without_light_objects_nearby`
- `test_walkability_from_each_entry_exit_to_each_other_exit` (BFS over
  passable tiles)
- `test_no_object_on_impassable_tile`
- `test_spawner_regions_non_empty_and_templates_exist`
- `test_lore_assets_referenced_exist`
- `test_shaft_core_has_exactly_two_hardware_locations`

## Acceptance script

1. Start the server with the full content tree; `blacksite admin status`
   reports 34 ordinary zones loaded; the 35th is S26's instanced finale.
2. At 80×24, walk from `vatside-vat-row` down the ladder into
   `under-service`; the sight radius visibly drops to 5; find both orphan
   terminals; descend to `under-drowned` (water slows movement), then
   with an Undercity key through the bulkhead to `under-outworks`, and
   through the inner door to `under-shaft-foot`; interact with the season
   door and see the sealed/pending-season status (S26 supplies live Depth).
3. From `tramyard-wall-gate` walk `scour-ring-1` → `-2` → `-3` → `-4`,
   touching each relay's terminal (interaction shows its name) and the
   Far Relay's orphan terminal.
4. `blacksite admin event force ring-fall scour-ring-3`: extra salvage
   appears in that ring's field only. Its saved impact footprint
   confines the impact warning and recovery encounter.
5. Open the zone map overview (`M`) in `under-caverns` at 132×50: the
   overview scales to its rectangle and the detailed map pans without
   clipping; a 150x80 map is not shown tile-for-tile on that terminal.

## Definition of done

- Validator and tests green for all 24 remaining zones plus the fixture tree.
- Reviewer has walked each zone once; the two human-review zones signed
  off by the user.
- Slice file marked done with PR number.
- Complete the S12 activation handoff below; pending S12 anchors cannot
  remain silently inactive in newly shipped zones.

## S12 vendor and bank activation handoff

S12 deliberately keeps the ten-zone hub (decision in issue #12). When
the real remaining maps land here, this slice must:

- Place and activate every deferred canonical vendor at its real zone
  anchor, including the Tramyard Depot Counter. Do not move hub vendors.
- Place bank branches in `tramyard-market` and every faction hall.
- Validate all vendor stock, object references, standing/member gates,
  public essential stock and per-object resale budgets in the full city.
- Run the original S12 live check at 80x24 and 132x50 through NetBBS:
  walk to the Tramyard Depot Counter, buy/equip `wpn_halvard_hv7` with its
  canonical `ammo_5x`, sell, exchange a dropped item between callers,
  bank chits and leave every menu with Esc/B without side effects.
- Include explicit scenario funding if needed; S12's 200-chit starter
  grant is less than the 340-chit rifle price. Do not change balance to
  make an acceptance scenario affordable.
- Assert no deferred vendor/bank anchor remains unresolved for any
  shipped ordinary zone. Record these activation results in the S25 PR.
  `tests/content/test_commerce_catalog.py` enforces this when a future
  zone is added: activate its vendor definitions, wire its objects, and
  place the canonical hall/Tramyard banks before the suite can pass.

## Implementer notes

S16 deferred field acceptance is also mandatory at both terminal sizes
through NetBBS: buy `imp_halvard_reflex_arm` at the real Spire concourse,
then install it at a Sablier clinic and verify the 10 percent weapon
cooldown reduction. S16's owned-item loan verifies surgery, not that
purchase or its district route. Exercise the real Sink black clinic's
60 percent price and 15 percent failure disclosure once its map exists.
Keep the canonical prices and disclose any scenario funding.

S13/S14 hardware handoff: give each new zone its canonical `sector` ID,
anchor and activate every ordinary core whose hardware now exists, and
replace the district entrance's `planned_core` placeholder with its live
`core_id`. All sixteen relay instances use game design 7.7's
`lat-relay-<slug>` IDs. Keep service cores separate; Shaft is the only
two-location core. When all 34 ordinary maps ship, no district core
entrance may remain a placeholder. This complements the existing vendor,
bank and clinic activation gate above; neither handoff supersedes the
other.

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

## Lore-to-layout acceptance

Walk each public-service variant and the permanent alternative route.
A shortcut must save travel or exposure visibly; its loss must not deny
food, water, cloning, public jobs or outward travel. Check gated routes
under Curfew, neutral relay ownership and expired controls. The world is
closed: the Far Road is a local ridge, never an exit from Karst. S26,
not this slice, activates season story flags after complete validation.

## S17 integration handoff

S17 deliberately ships no placeholder Scour map or live hub workshop.
Its real NetBBS proof uses explicitly labelled Wake-map fixtures. For
each real Scour ring, author one `salvage_field` object with integer
`ring` 1-4; event impact regions are separate authoring. Anchor workshops
at Tramyard/Kestrel and Landing/Ferrymen (`makes: any`), Old Works
(`rigs_programs`) and the Sink (`chemical_melee`). Activate their real
vendors and routes. Through native NetBBS at 80x24 and 132x50 with wide
names, repeat three-unit harvest, actual Landing schematic purchase and
learning, craft with visible effective stats, 18-chit hull sale and
Old Works refusal. Existing Tramyard rifle, Spire Reflex Arm purchase,
Sink clinic, Gate Nine, all ordinary cores/vendors/banks and crowded
Sweeper acceptance obligations remain mandatory. Preserve game 8.4
quality and seeded state when placing the content.

This carries the accepted [PR #38](https://github.com/Thiesi/Blacksite/pull/38)
findings 12/14 forward; see [S17](S17-salvage-and-fabrication.md).

## S18 housing handoff

Commission the actual Terraces lobby letting terminal (`params.letting:
true`) and at least 24 `apartment_door` anchors across all three housing
classes. Each `housing` block resolves a class, `apartment` room blueprint,
origin, sector/cell, public doorstep and local vestibule. Allocate a
distinct safe 6x4 floor and an unallocated public Terraces cell per home;
do not block public services or exits. S18 adds no live placeholder map.

Repeat native 80x24/132x50 acceptance with wide names on these actual
locations: first-week signing, quality-preserving rifle storage, visitor
rejection, bed logout/reconnect, eviction and fee-paying bank reclaim.
The disclosed clock jump is 22 days without remaining rent funds; 15
days is only eight days lapsed after the paid week. Half the listed
storage slots are protectable in place (20/40/60), independently of
carried secured capacity. Physical keys and Passkey grant only the
30-second vestibule. Preserve each unit's theft watermark across leases.
See game design 8.7, [S18](S18-apartments.md) and accepted
[PR #38](https://github.com/Thiesi/Blacksite/pull/38). All earlier commerce,
clinic, Scour, core, Gate Nine and Sweeper acceptance gates remain.


### S20 faction integration handoff

Reference: [PR #38](https://github.com/Thiesi/Blacksite/pull/38) and S20.

Commission all eight S20 faction_sites with real hall/counter/protected-vat
anchors; six bindings remain in the s25-faction-sites authoring bundle.
Unmoored hall/vat are Old Works Drop, public board/recruiter Old Works Main.
Do not activate a vat-less site or create aliases. Repeat S20 contested
combat on real Sink Terraces; its native proof uses shipped Clinic Row.
Preserve all existing S16-S18 commerce, housing and core gates.

### S22 crew integration handoff

S22 [PR #61](https://github.com/Thiesi/Blacksite/pull/61) adds remote crew
rosters and beacons. Exercise them in crowded actual maps without
revealing private interiors. All real city, relay, vendor, housing,
workshop and clinic acceptance obligations below remain required.

<!-- s19-services:start -->
### S19 source and service handoff

Reference: [S19 PR #62](https://github.com/Thiesi/Blacksite/pull/62),
[acceptance record](../../ops/s19-acceptance.md) and
[PR #38](https://github.com/Thiesi/Blacksite/pull/38).

S19 supplies the implemented source interfaces, 68 authored contracts
and four service nodes. Full root pytest passed 1344 tests with one
skip. Installed native acceptance covers both sizes and allocations,
forks, repair reconnect and paid restart. Consume the merged PR;
S25/S27/S26 still own real geography, referrals and activation.

Commission the four real service targets, allocation layers, safe return
routes, clinic counter, surplus vendor/cache and actual patrol/gate
bindings. Cold Chain changes installation service fees only. Depot cap
changes retain hourly spending. Keep all five program-source routes and the
actual affordability/native geography obligations from PR #38.
<!-- s19-services:end -->

S19 commissions fixed Tin Halo listings for Lance, Bunker, Signet and
Anchor and an identity-scoped Blackout image in the Reach. Keep these
usable without faction membership when expanding the city's shops;
additional faction sources supplement them. Permanent source guards and
current-season acquisition custody are shared by counters, lifts and
contract rewards. The full-city income/playtesting handoff still applies.

The [S19 content handoff](../s19-content-handoff.md) lists every named
story anchor, mission NPC, service layout and public patrol source to
bind. Preserve the hidden black-core entrance and both willing-template
destinations. Field-window acceptance must use the real landing-to-spoke
route; check the disclosed 180-second recovery against its actual travel
and hazards. Adjust canon and its tests together if measured play requires
a different window. Do not activate unresolved bundles to supply offers.

Follow the [S21 relay handoff](../s21-relay-handoff.md): activate fourteen
real relay/core/counter anchors, bind the actual Gate Nine and cable
exits and preserve their public free routes. Exercise all named benefits
on their real maps. Human pacing must measure unopposed relay idle time
and meaningful choices alongside the retained earning/clinic obligations.

S23 proves bounty settlement in a commissioned contested hub location;
S25 still owns the original real `sink-rim` travel and bounty-location
acceptance, at both native terminal sizes. Disclosed grade/funding setup
does not prove full-city earnings or acquisition pacing. Keep public
terminal and Kestrel bank access usable for protected market delivery;
`C` collects inside those menus and remains chat on the street. See
[S23](S23-market-and-bounties.md) and issue #23.

<!-- s24-handoff:start -->
### S24 event integration and acceptance handoff

Reference: [S24 #24](https://github.com/Thiesi/Blacksite/issues/24),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

Activate `s24-future-events` only after its actual Ring-fall regions,
salvage-field markers, recovery-crew sites, Exhale key site and optional
`exhale-shortcut` layout, and every Convoy waypoint resolve on real maps.
Validate paths and shelters under both ordinary and event geometry.
`key_undercity` is the physical key for the Drowned bulkhead and S26's
contribution; do not substitute a journal flag or duplicate its source.
Mile, Beacon and Far consume the same committed plan, not another roll.

Measure the two-tile/s Convoy, six-tile escort attendance, fixed 200-chit
and 100-XP jobs, one-hour completed-job return window, and actual travel,
combat, earning and return time. Beacon permits one reachable local
detour per leg, paid only by its committed consumption. It grants no
exclusive escort slot. Change canon and consumers if measured play
shows a dull or unaffordable loop. Keep the required human review of
Shaft Foot/Far Ring and the broader S25/S26 human pacing gate open.
Native event fixtures on hubs do not satisfy either gate.
<!-- s24-handoff:end -->


<!-- s24-review-policy:start -->
### S24 practical review follow-up

Reference: [PR #65](https://github.com/Thiesi/Blacksite/pull/65), retaining
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and #56.

Verify Convoy paths around actual walls and body traffic. A paid Beacon
diversion ends on arrival or after 60 seconds of wall time, then resumes the
committed leg. Include this limit and actual arrival/loss forecast updates
in travel/earning playtests; no stalled greedy walker may consume the whole
public escort window.
Assess public Beacon ambush/diversion counterplay on the actual route:
warning visibility, escort viability and repeated paid diversions. A
reachable hostile-allowed detour on a contested public objective is not
an escort-only permission boundary. Change the bounded rule only if
measured play warrants it; preserve this concern in S26 human pacing.
<!-- s24-review-policy:end -->

<!-- s25-city-decisions:start -->
### S25 commissioning decisions (in progress)

Reference: [S25 #25](https://github.com/Thiesi/Blacksite/issues/25),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

The draft uses game 5.6's carried key OR exact local open-latch state for
the optional Drowned bulkhead. Ordinary Outworks/Shaft Foot travel is
free; a key is retained, not consumed. Hidden physical exits allow
explicit Interact on their tile and never auto-travel on a walk. All
Undercity base sight is five before carried light. Whole-zone `pocket`
safety protects clinics, just as an authored pocket does.

The existing Terraces sector expands from 36 to 48 cells: a public
register wing supplies 24 distinct apartment addresses without reusing
entry/uplink cells or changing existing hidden/gated routes. Halvard's
member hall, vat and counter are in the Mezzanine; public recruitment,
care and banking remain in the Atrium. Three secondary ration/flare and
salvage counters bring ordinary vendors to 22; only Landing retains its
20% salvage premium. New NPC profiles and gantry damage are documented
initial values in game 5.5/6.4 and must pass actual-city pacing.

S25 must verify the actual 24-unit rental pool, 22 ordinary vendors, all
16 relays, clinic safety, real earnings and every service allocation in
the populated city. Draft validation is not native or human acceptance.

These are in-progress decisions, not a claim of merge, native acceptance
or completion of the Shaft Foot/Far Ring and broader human pacing gates.
The real walled apartments also exposed a geometry-admission bug:
a closed private door must not freeze unrelated public controls.
Housing supplies the occupant's explicit Interact-to-leave doorstep as
the escape origin; occupied tiles remain passable and private entry
permissions still apply. Retain that proof under tenants, visitors,
restart and overlapping effects. The Lobby's five inert private-door
props are replaced by the real 24-unit Block Street pool.

S25 places `ferrymen-corpse`, `choir-shrine`, `unmoored-dead-drop` and the
empty Far Ring artifact sites as physical source hooks. S27 owns the
corpse's one-time personal map and the shrine's daily claim receipt;
S26 owns season artifact activation. A prop label alone grants no reward.
Permanent hazards are excluded from salvage-node placement because
incoming damage interrupts the harvest channel. If an optional opening
closes over a saved position, reconnect recovers to the nearest free,
non-hazardous tile in the public spawn component, respecting housing
entry permissions. Include both in actual-city restart and event tests.

Mezzanine physical admission does not grant a Citadel network credential;
its loan terminal keeps the normal network gate. The Far mast uses the
Scour sector and cannot bypass Static's Ring-fall gate. All 16 relay
sites are mapped, but Shaft Relay retains `requires_level`; S26 must bind
its availability to the committed level phase, alongside the story-route
providers. Mapping never pretends that this seasonal gate is open.
<!-- s25-city-decisions:end -->
