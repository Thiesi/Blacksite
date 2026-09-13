# Blacksite — Entity Model

The technical mirror of `00-game-design.md`. Every persistent or simulated
thing in the game is one of the entities below. The server owns all of
them; the client only ever sees **view models** derived from them
(`02-architecture.md` §5). Slices implement entities in the order the
roadmap gives; a slice that adds a field adds it here in the same PR.

Conventions:

- IDs are strings. Content IDs (zones, items, ICE, factions) are slugs
  fixed by the content files. Instance IDs (a specific player, a dropped
  item, a spawned NPC) are `<origin>:<kind>:<n>` where `origin` is the
  node's stable identifier (§9) so that a future federation slice can merge
  two nodes' worlds without collisions.
- Times are UTC ISO-8601 strings in storage and monotonic tick counters in
  simulation.
- Every entity has `schema` (integer) so content and save migrations are
  explicit.
- **Persistent** entities live in SQLite. **Live** entities live only in
  server memory and are rebuilt from content and persistent state on
  start.

---

## 1. World and content (loaded from files)

### 1.1 Zone (`zones/<id>.map` + `zones/<id>.json`)

| Field | Type | Notes |
|---|---|---|
| id | slug | `core-plaza` |
| name, district | str | |
| safety | enum | safe, pocket, contested, open |
| lean | faction id or null | |
| width, height | int | 40–200, 20–100 |
| tiles | grid of TileRef | from the `.map` legend |
| sight_radius | int | |
| sight_radius_night | int, optional | Scour zones: used 20:00–06:00 node local time |
| exits | list of Exit | tile, target zone, target tile, kind (street, tram, ladder, lift, gate, cable), requirement (pass, key, faction) |
| spawners | list of Spawner | tile or region, npc template, count, respawn seconds, condition |
| objects | list of ObjectSpec | tile, kind (door, terminal, vendor, vat, relay, cache, tram_stop, apartment_door, light, hardware, descent_console, workshop, bank), params |
| pockets | list of Region | rectangles that are `pocket` safety inside a contested zone |
| lore | list of asset ids | ambient log lines, found texts |
| instanced | bool | Blacksite levels only |

### 1.2 Tile type (`tiles.json`)

`id, glyph, colour (per tier), passable, cover (0–3), opaque, hazard
(damage per second, type), interaction (object kind or null), sound_line
(optional ambient log)`.

### 1.3 Sector (`sectors/<id>.json`)

`id, district, cells[]` where a cell is `id, kind (public, gated, hidden,
core_entrance, descent), neighbours[], requirement, label, core_id
(optional), lore`.

### 1.4 Core (`cores/<id>.json`)

`id, name, owner (faction id or "private"), tier 1–5 (0 only for the Wake
training core), hardware (list of one or two (zone id, tile) locations; two
only for the Shaft core that spans Shaft Head and Shaft Foot, and the
validator rejects any other multi-location core), rooms[]` where a room is
`id, neighbours[], data[] (DataSpec), controls[] (ControlSpec), ice[] (ice
template ids), lore`.

- DataSpec: `id, kind (chits, salvage_data, contribution, contract_key,
  schematic, text asset), amount or asset id, respawn seconds`.
- ControlSpec: `id, label, target (zone id, object id), action (open,
  close, disable, enable, toggle, call), reset seconds, scope (public,
mission, private_vestibule, expedition), permission, safety_policy,
owner_policy, warning seconds, alternate_route, revision`.

A control cannot invent arbitrary code. Its action and permission are
closed enums; safe-zone hazards, private storage access and essential
service denial fail validation. Expiry is independent of relay ownership.

### 1.5 ICE template (`ice.json`)

`id, name, class, tier, integrity, attack, cast_seconds, cooldown_seconds,
trigger (entry, data, trace >= n, timer), behaviour (static, roaming,
hunter), black (bool), meat_damage, counters[] (program classes), lore`.

### 1.6 Program template (`programs.json`)

`id, name, class, tier, slots, cast_seconds, cooldown_seconds, effect
(typed record), source, price, acquisition_requires, cast_requires,
trace_cost, target_class, duration, stacking_group`. The 35 records are
game design section 17.2; no parallel catalog aliases. Acquisition and
continued use are distinct requirements.

### 1.7 Item template (`items.json`)

Shared header: `id, name, class (weapon, armour, implant, resonance,
rig, drug, consumable, drone, salvage, schematic, key, pass, data, misc),
tier, weight, base_price, secured_default (bool), description asset,
stack_max`. Class-specific blocks:

- weapon: `range, damage, cooldown, accuracy, ammo, damage_type, heavy,
  melee`
- armour: `slot, armour {kinetic, energy, chemical, dissonance}, heavy`
- implant / resonance / rig: `slot, tolerance, effects (dict of attribute
  or derived deltas), requires (archetype, standing)`
- drug: `effects, duration, crash, addiction_window, addiction_doses`
- consumable: `effects, cooldown_class`
- drone: `health, weapon or tool, speed, sight`
- salvage: `grade`
- schematic: `output item id, inputs (salvage grade → count), skill_min`

### 1.8 NPC template (`npcs.json`)

`id, name, faction, grade, attributes, weapon, armour, behaviours[]
(with params), dialogue (asset id or null), vendor (inventory id or null),
loot_table, xp, lore`.

### 1.9 Faction (`factions.json`)

`id, name, short, colours (tiers), hall (zone id), vat (zone id, tile),
recruiter (npc id), relations {faction id → H/N/A}, ranks[] (standing
threshold, title), vendor inventory id, contract templates[]`.

### 1.10 Contract template (`contracts.json`)

`id, faction or "vesper", type (fetch, hack, escort, clear, plant,
survey), stages[], params (ranges and pools), reward (chits range,
explicit standing deltas, xp, item pool), min_grade, crew_scaling,
story (bool), season, chain (next id), branch_group, permit_scope,
publication_options[], evidence_assets[], unlock_conditions`.

Each stage uses one of the six verbs, a resolved target and a completion
condition. Escort includes willing mission NPCs; clear declares lethal
or subdue resolution. Inspect, carry, interact and wait are explicit
input actions; no text parser or answer matching. A stage declares its
failure/retry state and receipt key. Story bundles declare all required
maps, NPCs, dialogue, cores, items and season IDs before activation.

### 1.11 Dialogue (`dialogue/<npc>.json`)

Talkers with ordered conditional lines, first match wins: `lines[]` of
`id, text asset, conditions (a closed set: standing, grade, faction,
marked, contract state, season, event, season flag, legal status,
evidence, receipt, service state), offers[] (label,
hotkey, effect: contract offer, join, vendor, text asset), bark (bool),
balance tag (CUST, TEN, or none)`. The full shape, including terminal
talkers (the Dispatcher, Ninety-Nine) and the validation tests, is
"Dialogue system notes" in `docs/world/04-dramatis-personae.md`.
This contract and game design section 13.4 govern weighting and required
lines; flavour cannot remove a warning, objective or offered action.

### 1.12 Event template (`events.json`)

`id, name, where (zone ids or sector ids), duration, cooldown, weight,
effects[] (typed), announce (asset ids: start, mid, end), route
(optional route id)`. Routes (`routes.json`): `id, waypoints[] (zone id,
tile), speed`, used by the Convoy event's NPC crew.

### 1.13 Season definition (`seasons/<n>.json`)

`number, title, depth_target, contribution weights, blacksite level
(zone id, sector id), finale choices[] (id, label, chronicle asset,
balance delta, condition), relations_override[] (faction a, faction b,
value), story contract chains[]`.

### 1.14 Text asset (`text/<id>.md` or `.txt`)

Found texts, briefing scripts, MOTDs, item descriptions. Plain text or
minimal markup the client knows how to colour.

### 1.15 Art asset (`art/<id>.ans`)

ANSI art blocks with a JSON sidecar: `width, height, min_tier, palette
variants`. See `04-assets.md`.

---

## 2. Persistent state (SQLite)

### 2.1 Player

| Field | Notes |
|---|---|
| id | `<origin>:player:<n>` |
| bbs_user_id, bbs_handle | from `door_info.json`; user id is the identity key, handle is display |
| name | character name |
| archetype | |
| attributes {frame, nerve, cortex, resonance, vitals} | |
| skills {12 lines} | |
| grade, xp | |
| health, stamina, shock | saved at logout |
| chits_hand, chits_bank | |
| faction, standing {faction id → int}, marked_until, warden_heat_until | |
| zone, tile, facing | last position; sleeper rule applied at logout |
| implants {slot → item instance id} | |
| equipment {slots} | |
| inventory[] | item instance ids; `secured` flags |
| rig {slots[] → program ids} | |
| drugs_active[], dependencies[] | |
| apartment_id | nullable |
| crew_id | live only, not persisted |
| settings | keymap variant, palette, sitrep visibility, log verbosity |
| stats | kills, deaths, runs, contributions, relays; per season |
| clone_debt, recovery_kit_id, listened_enabled | debt survives decant; calibration is reversible |
| created_at, last_seen_at, legal_at | legal_at = earlier of grade-5 timestamp and created_at + 90 days |

### 2.2 Item instance

`id, template, owner (player id, cache id, apartment id, vendor id, or
null for world drop), quality (0.85–1.15), ammo, charges, secured, stack,
created_at`.

### 2.3 Apartment

`id, owner player id, zone, door object id, rent_paid_until, storage[] (item
instance ids), safe_chits, core_tier, last_hacked_at, hack_log[],
theft_receipts[], vestibule_access_until`.

### 2.4 Relay state

`relay id, zone, faction (or null), captured_at, captured_by (player id),
influence_paid_until`.

### 2.5 Faction state

`faction id, treasury, influence (season), depth_contributed (season)`.

### 2.6 Market

`listing id, seller, item instance, price, buyout, expires_at, bids[]`;
`bounty id, poster, target player id, chits, expires_at, claimed_by`.

### 2.7 Contracts

`contract instance id, template, player or crew, params (resolved),
progress, state (offered, active, complete, failed, turned_in),
expires_at, frozen_roster[], branch_group, stage_receipts[], permits[],
publication, reward_receipt`. One claim per eligible identity, atomically.
Story jobs have no overall expiry; bounded field steps may be retried.

### 2.8 Season and chronicle

`season number, started_at, depth_target, depth, level_open_since,
status (active, settled, archived), contribution_receipts[], ended_at,
leaderboard snapshot, settlement_id, winning_choice or null,
balance_before, balance_after, public_modifiers[]`.

`Ballot`: `origin, bbs_user_id, season, expedition_id, choice,
consenting_name or null, accepted_at, reward_receipt`. Unique on origin,
BBS identity and season, independent of character and crew changes.

`ChronicleEntry`: `season, kind (expedition, vote, settlement), source,
asset_id, rendered_text, at, settlement_id`. Expedition accounts are
attributed reports; only settlement changes public routes and balance.

### 2.9 Core state

`core id, offline_until, controls {control id → state, reset_at},
data {data id → taken_at}, owner_faction (from relay)`.

### 2.10 Admin

`bans (bbs user id, reason, until)`, `mutes`, `audit log (actor, action,
target, at)`, `reports (reporter, target, text, at)`.

### 2.11 World meta

`schema version, origin id, created_at, season pointer, event cooldowns,
rng seeds per zone, balance (-3..+3), committed_event_plans[],
next_event_roll_at, season_modifiers[]`.

### 2.12 Evidence and receipts

`JournalRecord`: `player, evidence_id, observed_at, location,
observation, source, claim, confidence_label, related_objective,
publication_state`. Confidence labels describe source status, never an
omniscient truth score. Journals hold no unseen maps or private ballots.

`ActionReceipt`: `id, identity, scope, action_key, accepted_revision,
result, rewards, committed_at`. A uniqueness constraint covers branch,
contribution, theft, daily perk and settlement claims. Retry returns the
same result. Journal, reward and authoritative state commit together.

### 2.13 Work order and service node

`ServiceNode`: `id, zone, core, target_objects[], state (normal, fault,
repairing, allocated), revision, next_fault_uptime, fault_expires,
order_id, allocation, allocation_expires, authored_route_variants[]`.

`WorkOrder`: `id, service_node, roster[], reserved_until, stage,
supplied_bound_items[], completed_actions[], allocation_vote,
reward_receipts[]`. The reserving player chooses the disclosed
allocation; the frozen roster sees it before accepting and shares the
reward. Departure of the whole roster releases the reservation. No
inventory supplies or money may be consumed twice on an interrupted step.

### 2.14 Expedition

`id, season, roster[], origin_instance, seed, checkpoint, phase,
completed_objectives[], decision_receipts[], empty_since, status`.
Roster locks at entry. Ordinary crew leadership never changes it.
Checkpoint recovery rebuilds mission hazards and places participants at
safe entry; it does not replay rewards. The FIFO entry queue is live,
while admitted expeditions and personal decisions are persistent.

### 2.15 Committed event plan

`id, template, where, announced_at, starts_at, ends_at, seed,
variant_ids[], state (planned, active, complete, cancelled), revision,
cancel_reason, reward_receipts[]`. Forecasts read this record, never an
independent random roll. Persist both planned and active schedules.
Timers declare wall-time or uptime basis per game design section 12;
restart reconciles expired effects before sessions receive a view.

---

## 3. Live simulation state (memory only)

### 3.1 Actor

The common base for players, NPCs, and drones in a zone.

`id, kind (player, npc, drone), zone, x, y, facing, health, stamina,
shock, cooldowns {key → until tick}, effects[] (buff/debuff with expiry),
target id, stance (normal, stealth, down, dead, sleeper), faction,
marked, visible_to (computed), behaviour state (NPCs), owner (drones)`.

### 3.2 Zone instance

`zone id (+ instance suffix for Blacksite), actors {}, objects {} with
live state (door open, terminal in use, relay progress), caches {},
salvage nodes {}, event effects[], rng, tick, listeners (session ids)`.

### 3.3 Presence (a jacked-in runner)

`player id, sector, cell, core (nullable), room (nullable), integrity,
trace, rig slots with cooldowns, effects[], visible_to`.

### 3.4 Core instance

`core id, rooms with live ICE instances {id, template, integrity, state,
target}, data taken flags, control states, presences[]`.

### 3.5 Silt instance

`id, participant presence IDs[], seed, graph, depth, residual
encounters, contributions found, chorister_phase, scan_cooldowns`.
A solo descent has one participant. Joining crew members must enter the
same instance through its entrance; remote beacons do not grant sight.

### 3.6 Session

`session id, player id, transport info from door_info (width, height,
colour depth, node name), subscribed zone or sector, input queue, last
input tick, rate counters, pending prompts, view revision`.

### 3.7 Crew

`id, leader, members[], invites[], loot mode, beacon target, chat`.

### 3.8 Event instance

`committed_plan_id, template, started_at, ends_at, where, state,
effect_layers[], warning_deadlines`. No fresh random schedule on restart.

---

## 4. Derived view models (server → client)

Defined precisely in `02-architecture.md` §5. Summary of shapes:

- `ZoneView`: viewport rectangle, visible tiles (glyph id per cell),
  visible actors (id, glyph, colour role, name if targeted or in crew,
  stance), visible objects, own status block, target block, nearby list,
  crew list, event banner.
- `LatticeView`: sector cell graph in view range, presences, own
  integrity and trace, rig slots with cooldowns, current room contents
  (data, controls, ICE with integrity bars).
- `MenuView`: a modal list or form (inventory, vendor, market, contract
  board, character sheet, crew, sitrep, settings, dialogue).
- `LogLine`: channel, text, colour role, timestamp.
- `Prompt`: single-key or line prompt with label.

---

## 5. Invariants a test suite must hold

- A player has exactly one physical actor while connected and at most
  one Lattice presence. Jacking leaves the physical actor at its terminal;
  it never duplicates, moves or deletes that body.
- Chits never go negative; banked chits are untouched by death.
- Secured inventory never appears in a corpse cache.
- Every control in every core resolves to an existing zone object at
  content load, and every core's hardware tile is a `hardware` object.
- Every exit resolves to an existing target zone and passable tile.
- Every faction relation is defined for every pair, and the intended
  asymmetries are exactly the ones listed in the faction data file.
- Every text and art asset referenced by content exists at load.
- Entity IDs carry the origin prefix; two worlds with different origins
  have disjoint instance ID spaces.

- Safe-body harm checks apply at action acceptance and effect delivery,
  with indirect actions attributed to their initiator. Risky NPC-core
  black ICE uses the explicit opt-in exception, never player damage.
- Every completed objective, contribution and ballot has one receipt;
  resends, death, reconnect and a different crew cannot duplicate it.
- Essential clinic, public uplink and outward escape remain reachable in
  every control, service and event state, including stacked modifiers.
- Expiry, ownership and season layers do not overwrite each other's
  baseline. No apartment control exposes storage or impounded items.
- A season settlement runs once; a tie applies no world or balance delta.
