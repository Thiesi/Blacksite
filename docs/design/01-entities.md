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

Every content file is decoded into the typed records of
`blacksite/content/schema.py`; JSON keys equal the field names below.
Unknown keys, missing required fields and values outside a closed set
fail at load with the file and, where it can be found, the line. Table
files are `{"schema": 1, "<kind>": [records]}`; one-record files
(`sectors/`, `cores/`, `dialogue/`, `seasons/`, `bundles/`) are named
after their id.

### 1.1 Zone (`zones/<id>.map` + `zones/<id>.json`)

| Field | Type | Notes |
|---|---|---|
| id | slug | `core-plaza` |
| name, district | str | |
| safety | enum | safe, pocket, contested, open |
| lean | faction id or null | |
| width, height | int | 40–200, 20–100; derived from the `.map`, not written in the sidecar |
| tiles | grid of TileRef | from the `.map` legend |
| sight_radius | int | |
| sight_radius_night | int, optional | Scour zones: used 20:00–06:00 node local time |
| spawn | Tile, optional | passable preview/initial entry tile |
| sector | sector id, optional | native/portable rig's district entry; terminals may override with `params.sector` |
| layouts | list of ZoneLayout, optional | named service/event geometry variants |
| exits | list of Exit | id, tile, target zone, target tile, kind (street, door, tram, ladder, lift, gate, cable), requirement (pass, key, faction), hidden |
| spawners | list of Spawner | id, tile or region, npc template, count, respawn seconds, condition |
| objects | list of ObjectSpec | id, tile, kind (door, terminal, vendor, vat, relay, cache, tram_stop, apartment_door, light, hardware, descent_console, workshop, bank, turret, camera, shutter, cable_car, pump, lift, patrol_beacon, gate, gantry), params, essential (clinic, public vat, public uplink) |
| pockets | list of Region | rectangles that are `pocket` safety inside a contested zone |
| lore | list of asset ids | ambient log lines, found texts |
| instanced | bool | Blacksite levels only |

`ZoneLayout` has `id`, `changes` (list of `{tile, tile_id}`),
`warning_tiles` (list of Tile) and `alternate_routes` (exit IDs).
Each variant must preserve access from spawn to essential services and
public outward exits. Hazard changes require warning tiles, cannot affect
safe zones or pockets, and warn for at least five seconds. Runtime
composition rechecks reachability from every physical body; an unsafe
closure waits. Layers expire independently and compose in source-ID order.
A door's optional `params.open` overrides its base tile's passability and
opacity; without it, the tile type supplies the initial state.

S06 preview actors use Hardline's starting attributes and derived pools
(game design 3.1–3.2: HP 130, STA 70). They are temporary bodies, not saved
characters. S07 supplies character creation and persistent state.

S18 adds `housing` on an `apartment_door`: `{class_id, room, origin,
sector, cell, doorstep, vestibule}`. The room ID resolves to a paired
`rooms/<id>.map` and `.json` blueprint. It defines a 6x4 floor grid,
local spawn and local objects (storage, apartment_safe, bed, terminal,
hardware, light). `origin` translates those positions into the containing
zone. `vestibule` is one local tile; `doorstep` is a public tile outside.
Every active anchor must resolve its class, room and sector cell and
match the commissioned zone floor. Visitors never acquire resident
permissions merely because the physical door is open.

`apartments.json` contains three class records: `{id, name,
storage_slots, core_tier, rent, key_item, core_upgrade_to, core_upgrade_price,
lock_tier, lock_upgrade_to, lock_upgrade_price, schema}`. Class IDs use
the catalog underscore form. Room blueprints are content, not new zones.

### 1.2 Tile type (`tiles.json`)

`id, char, glyph, colour, passable, cover (0–3), opaque, hazard
(damage per second, type), interaction (object kind or null), sound_line
(optional ambient log)`. `char` is the single character that stands for
the tile in `.map` files; `glyph` is a `glyphs.json` id used to draw it;
`colour` is a palette role whose per-tier values live in `palette.json`.

The terminal tables beside it: `glyphs.json` (`glyphs`: glyph id to one
CP437 character), `palette.json` (`roles`: role to tier to variant to
value) and `keymaps.json` (`actions`: action id to context and label;
`keymaps`: id, label, bindings of action id to normalised key names).

### 1.3 Sector (`sectors/<id>.json`)

`id, district, cells[]` where a cell is `id, kind (public, gated, hidden,
core_entrance, descent), pos (grid position on the sector view),
neighbours[], requirement, label, core_id (optional), lore`. A sector also
names its public `entry` cell and `layout_size` (at most 8 by 6).
Its `trace_policy` names the district schedule; optional `trace_owner`
is the faction receiving named trace reports, not territorial ownership.

`access` optionally separates public/gated/hidden access from a functional
`core_entrance` or `descent` kind. An `uplink` names a sector, its cell and
an optional requirement; links are reciprocal and never name a file path.
Requirements are item/program IDs, or `item:<id>`, `program:<id>`, `program:<class>:<tier>`,
`faction:<id>`, `standing:<id>:<minimum>` and `event:<id>` credentials.
The server names the missing credential before changing a presence.
`gate_owner` is an optional faction ID for a gate. A completed Signet
may satisfy a Halvard gate's key-program requirement; it never replaces
an item, event, discovery or story requirement.

`core_placeholder: true` explicitly marks an unavailable entrance, with a
`planned_core` slug instead of a live `core_id`. This is declared staged
content, not a missing reference silently accepted by the loader. Normal
entrances still require a resolved core. Once the planned core is active,
validation requires replacing its placeholder. S14 activates hub cores;
future-map hardware remains staged until S25, preserving dependency order.
Core and Silt interaction remains unavailable in S13, while public movement
and jack-out remain usable by every archetype.

### 1.4 Core (`cores/<id>.json`)

`id, name, owner, owner_kind (faction, institution, neutral, npc, private,
relay, abandoned), affiliation (optional faction), trace_policy (civic,
corporate, black, street, none), tier 1–5 (0 only for the Wake
training core, which sets `training`), template, entry, hardware
(list of one or two (zone id, tile, object id, label) locations; two
only for the Shaft core that spans Shaft Head and Shaft Foot, and the
validator rejects any other multi-location core), rooms[]` where a room is
`id, label, pos [x,y], neighbours[], data[] (DataSpec), controls[]
(ControlSpec), ice[] (ICE template ids), ice_events (optional template ID
to event ID conditions), ice_patrols, descent, lore`.
`ice_patrols` optionally maps a room's defender template to a linked
closed room route including its origin. Default core patrols traverse
the linked graph without jumping an edge. Positions are
authored, unique in an 8x4 room layout; every room reaches the entry.
Listening Post alone has an authored internal descent.

Ownership is provenance, not extra faction membership. Civic Authority,
neutral enforcement and Vesper do not add joinable factions. Live relay
ownership remains separate. The private Wake has one room, no hardware
or live controls, and one nonblack Tripwire (10 integrity, damage 5).
Templates are inactive records with no cuttable hardware; instantiated
ordinary cores obey the ordinary limits. Future hardware may have an
unresolved tile only in inactive authoring records. An active hardware
reference resolves its actual object and tile; no stub map is implied.

- DataSpec: `id, label, kind (chits, salvage_data, contribution,
  contract_key, schematic, text, item, program, evidence), amount, asset,
  respawn_seconds, scope (shared, identity, mission), chance, programs[]`.
  Asset resolves the kind's item/program/text/evidence table. Shared
  reward sources use remaining server uptime and a source generation;
  mission keys and personal records have separate receipt scopes.
  Core source IDs survive room rearrangement. Mission receipts include
  the active mission ID supplied by the contracts system; a lift binds
  that ID at start and refuses a changed mission at completion.
  A contribution needs at least 3600 s uptime. The Wake record is
  nonrewarding personal text. A stale revision cannot consume a new unit.
  An item source may contain a validated program payload, learned in the
  same transfer transaction (the dead rig's Skeleton, for example).
- ControlSpec: `id, label, target (zone id, object id), action (open,
  close, disable, enable, toggle, call), reset seconds, scope (public,
mission, private_vestibule, expedition), permission, safety_policy,
owner_policy, warning seconds, alternate_route, revision`.

A control cannot invent arbitrary code. Its action and permission are
closed enums; safe-zone hazards, private storage access and essential
service denial fail validation. Expiry is independent of relay ownership.
Permission is `public`, `contract`, `member`, `owner` or `resident`.
`safety_policy` is `none`, `route` (may close travel; must name an
`alternate_route` exit in the target zone) or `hazard` (never in a safe
zone or pocket; at least 5 s warning). `owner_policy` is refused on
route and hazard controls, which always expire.

S15 typed object parameters bind a turret or patrol beacon to local
`spawners` IDs. Route machines bind `exits` and preserve an independent
alternate. Pumps and gantries name an authored `layout`, or a closed
`work_order_layouts` list whose choice comes from S19's frozen order.
Machines never evaluate code from content. A `locked` physical door
refuses ordinary opening; its core or an authored egress operates it.
Private delivery doors share the width-safe live door state, but never
expose resident storage through a physical interaction.


### 1.5 ICE template (`ice.json`)

`id, name, class, role (gate, alarm, patrol, deception, displacement,
feedback), tier, integrity, attack, cast_seconds, cooldown_seconds,
trigger (entry, data, trace with `trigger_trace` n, timer, touch,
passage, always), behaviour (static, roaming, hunter), black (bool),
meat_damage, counters[] (program classes), counter_label, params,
tier_stats[] (tier, integrity, attack, meat_damage), variants[] (ICE a
Surge may swap in: non-black, equal or lower tier), lore`.
Parameters are bounded scalar inputs to the named bestiary behaviour;
they cannot execute arbitrary actions. Tier stats select the applicable
Glasshouse/Hound row, not an additional bestiary class. Training uses
the private weak Tripwire variant; ordinary counts remain 23 classes.

### 1.6 Program template (`programs.json`)

`id, name, class, tier, slots, cast_seconds, cooldown_seconds, effect
(typed record), source, price, acquisition_requires, cast_requires,
trace_cost, target_class, duration, stacking_group, description`. The 35 records are
game design section 17.2; no parallel catalog aliases. Acquisition and
continued use are distinct requirements.
Requirements are `archetype:<id>`, `standing:<faction>:<amount>`,
`once_per_season`, `bound_loan` or `bound_charge`. Cooldowns use program
IDs and persistent UTC deadlines; effects and active casts use ticks.
Residual Fragment consumes one bound charge, not a permanent free cast.

`silt.json` contains typed generation rules: cell/sink min/max,
hidden_fraction (at most one fifth), and five ordered bands. Each band
has `id, name, depth, ice[] (template, minimum, maximum, route)` and
DataSpec sources. A visible continuation and riser are mandatory;
randomness changes optional routes and encounters, never exit permission.

### 1.7 Item template (`items.json`)

Shared header: `id, name, class (weapon, armour, ammo, implant,
resonance, rig, drug, consumable, drone, salvage, schematic, key, pass,
data, misc), tier, weight, base_price, secured_default (bool),
description (the catalog line, inline), stack_max, maker,
quality {kind, key}, no_vendor_sale (default false), door_key (default
false)`. The item
carries exactly the block its class names (resonance and rig use the
implant block; key, pass, data and misc carry none). Class-specific
blocks:

- weapon: `range (none for melee), damage, cooldown, accuracy, ammo,
  damage_type, heavy, melee, stamina (melee), dot {per_second, seconds},
  shock`

S10 gives melee the design's fixed 1.0 s cooldown and base accuracy 75.
The authoring schema can retain unknown timing as null; consumers must
never execute that as a zero cooldown. Ranged weapons require accuracy.
Implant slots include `head`, matching First Ear in the starter schedule.
S16 owns player drone movement and tools; S11 owns city NPCs.
Drone `control_range` preserves the catalog range. The legacy nullable
`speed` is descriptive only; `move_ms` defaults to ordinary walking
(200 ms), `effects` carries typed tool values and `hunt` allows the
marked-target pursuit command. Embedded attack blocks retain drone
weapon stats. Weapon `hits`, `targets` and `cone` retain the
catalog's multi-hit/arc/cone annotations for S10.
`requires_archetype` carries the catalog's Cantor-only weapon restriction.
- armour: `slot, armour {kinetic, energy, chemical, dissonance}, evasion,
  heavy`
- ammo: `recharge_price` (energy cells only)
- implant / resonance / rig: `slot, tolerance, effects (dict of attribute
  or derived deltas), requires (archetype, standing), rig_slots,
  portable (default false)`. Only explicit portable rigs work while
  carried; implanted rigs require surgery.
- drug: `effects, duration, crash, addiction_window, addiction_doses`
- consumable: `effects, cooldown_class`
- drone: `health, weapon or tool, speed, sight`
- salvage: `grade`
- schematic: `output item/program id, inputs (salvage grade → count),
  skill_min, single_use (default false)`

Quality is a per-template selector, default `{kind: none, key: ""}` for
older local content. Kinds are `none`, `weapon_damage`, `armour`,
`implant_effect`, `drone_damage`, and `drone_effect`. `armour` names one
nonzero resistance in `key`; effect kinds name one permitted numeric
effect. Other kinds have an empty key. Validation rejects incompatible
blocks and protected effects (permissions, slots and durations). Shipped
templates explicitly declare their policy. Game design 8.4 defines the
shared calculation; trade and storage retain the instance's quality.

`salvage.json` declares grade weights for each numbered ring, the node
and unit bounds, harvest/craft seconds and respawn uptime seconds.
Commissioned Scour zones identify their ring with a `salvage_field`
object's `ring` parameter. Live `salvage_node` objects expose grade and
remaining units. Workshop objects declare `makes`: `any`, `rigs_programs`
or `chemical_melee` (including chemical-attack drones). Future
placements remain inactive until S25; S17
acceptance geography is explicitly a fixture.

S16 adds `grades.json` records `{id, grade, title, promotion}` for all
30 grades; thresholds remain the main design 3.4 formula. Its
`skills.json` records carry `{id, name, attribute, uses {action: gain},
maximum, daily_cap}` for the twelve game 3.3 lines. Their schedules are
validated against game 3.5; temporary modifiers never alter these rows.

### 1.8 NPC template (`npcs.json`)

`id, name, faction, grade, attributes, weapon, armour, behaviours[]
(with params), dialogue (talker id or null), vendor (inventory id or null),
loot[] (item, chance, count), xp, lore`.

An optional explicit `health` pool and embedded `attack` weapon block
support private training actors. `training` requires both and scopes
the actor to its server-assigned owner. Ordinary NPCs derive health
from attributes and use their authored equipment. Recovery quantities
live in each character start's `recovery_items` mapping. Hymn records
list `requires_one_of` implant IDs for tiers above one.

S11 behaviours include `wander` and `hunt` as well as the original kinds.
Patrol params hold `waypoints: [[x,y], ...]` and optional `bounce`; every
spawner validates these against its own map. `anchor: true` preserves a
named service attendant during dormancy; `hostile_all: true` is an explicit
unsafe threat rather than an inference from open ground. Embedded health
and attack also support the generic maintenance drone from design 18.
`per_player` spawners require private training templates. Canonical NPC
template IDs are hyphenated slugs (`npc-wake-drone`); item IDs retain their
existing underscore format.

Spawner slots retain absolute UTC respawn deadlines and a monotonic actor
serial in `meta.npc_state`. NPC death writes its slot deadline atomically
with corpse goods. Ordinary live NPC positions/HP rebuild on process
restart; this does not replay dead slots before their saved deadline.
Mission ownership, willingness and restraint channels are live hooks for
S19, which owns persistence and objective failure/completion receipts.

### 1.9 Faction (`factions.json`)

`id, name, short, colour (palette role), hall (zone id), vat (zone id,
tile), recruiter (npc id), relations {faction id → H/N/A}, ranks[]
(standing threshold, title), vendor inventory id, contracts[]`.
`factions.json` also holds `asymmetries`, the unordered pairs whose
relation differs by direction; it must equal the set the matrix has.

### 1.10 Contract template (`contracts.json`)

`id, faction or "vesper", type (fetch, hack, escort, clear, plant,
survey), stages[], params (ranges and pools), reward (chits range,
explicit standing deltas, xp, item pool), min_grade, crew_scaling,
story (bool), season, chain (next id), branch_group, branch (this
outcome's key in the group), permit_scope, publication_options[],
evidence_assets[] (evidence ids), unlock_conditions[]`.

A stage is `id, verb, target {kind, ...}, input, completion,
receipt_key, retry, resolution`. Receipt keys are unique across all
contracts, as is each `(branch_group, branch)`.

Each stage uses one of the six verbs, a resolved target and a completion
condition. Escort includes willing mission NPCs; clear declares lethal
or subdue resolution. Inspect, carry, interact and wait are explicit
input actions; no text parser or answer matching. A stage declares its
failure/retry state and receipt key. Story bundles declare all required
maps, NPCs, dialogue, cores, items and season IDs before activation.

### 1.11 Dialogue (`dialogue/<npc>.json`)

Talkers with ordered conditional lines, first match wins: `lines[]` of
`id, text (inline, at most 200 characters), when (conditions (a closed set: standing, grade, faction,
marked, contract state, season, event, season flag, legal status,
evidence, receipt, service state), offers[] (label,
hotkey, effect: contract offer, join, vendor, text asset), barks[],
tag (CUST, TEN, or none)`, plus `required` on lines the balance weights
may never skip and `machine_mind` on talkers that need a line in each
voice. The full shape, including terminal
talkers (the Dispatcher, Ninety-Nine) and the validation tests, is
"Dialogue system notes" in `docs/world/04-dramatis-personae.md`.
This contract and game design section 13.4 govern weighting and required
lines; flavour cannot remove a warning, objective or offered action.

### 1.12 Event template (`events.json`)

`id, name, where (zone ids or sector ids), duration, cooldown, weight,
basis (wall or uptime), effects[] (typed), variants[] (id, effects[]),
announce (asset ids: start, mid, end), route (optional route id)`.
An effect is `type (hazard, spawn_multiplier, entry_restriction,
ice_variant, salvage, route_hold, price_modifier, reveal, cache), zone,
region, sector, warning_seconds, exits_closed[] ("zone/exit"), params`. Routes (`routes.json`): `id, waypoints[] (zone id,
tile), speed`, used by the Convoy event's NPC crew.

### 1.13 Season definition (`seasons/<n>.json`)

`number, title, depth_target, contribution weights, level (zone id,
sector id), phases[] (expedition checkpoint ids), finale_choices[] (id,
label, chronicle asset, balance delta, standing, condition),
finale_lines[] (text asset, tag, guaranteed; one guaranteed line per
voice), relations_override[] (faction a, faction b, value), story
contract chains[]`.

### 1.14 Text asset (`text/<id>.md` or `.txt`)

Found texts, briefing scripts, MOTDs, item descriptions. Plain text or
minimal markup the client knows how to colour.

### 1.15 Art asset (`art/<id>.ans`)

ANSI art blocks with a JSON sidecar: `width, height, min_tier, palette
variants`. See `04-assets.md`.

### 1.16 Evidence record (`evidence.json`)

`id, asset (text asset), observation, source, claim, related_objective
(contract id)`. What a journal record shows when acquired; the source's
claim is a separate field, never the finding (`04-assets.md` §9).

### 1.17 Service node template (`services.json`)

`id, name, zone, core, target_objects[] (object ids in the zone),
allocations[]` with exactly one `common` and one `reserve` allocation,
each `id, label, effects[]` (event effect records). Live state is the
`ServiceNode` of §2.13.

### 1.18 Vendor and hymn tables (`vendors.json`, `hymns.json`)

Vendor: `id, name, tier (list, member, restricted), stock[] (item,
standing), faction, zone`. Hymn: `id, name, kind (hymn, dissonance),
tier, cast_seconds, cooldown_seconds, effect, description`.

S12 vendor records also name `object_id`, optional acquisition faction
and archetype gates, price/salvage multipliers, and daily rotation. Stock
rows can narrow faction/archetype access and set a price multiplier.
Program stock refers to `programs.json`; physical stock refers to items.
S16 adds optional `clinic: sablier | black`. This declares surgery at the
vendor's actual local counter; only Sablier offers detox. Clinic purchase
and installation use the clinic's disclosed 8.5 tariff, while ordinary
counter purchases remain carried, uninstalled items.
Before S20, existing S07 recruiter IDs identify pricing affiliations and
grant no faction membership. An authoring-bundle vendor never opens a
counter. S25 owns activation of the staged `s25-commerce` members.

### 1.19 Bundle (`bundles/<id>.json`)

`id, status (active, authoring), depends[] (bundle ids), members {kind →
ids}`. Content no bundle lists is base content and always active. A
record in an `authoring` bundle may hold unresolved references; active
content may reference only content that exists and is itself active,
and an active bundle depends only on active bundles.

### 1.20 Character starts and recruiter cards

`starts.json`: `id` (archetype), `items` (template ID to quantity),
`equipment` and `implants` (slot to granted template), `programs`, `hymns`,
`rig_slots`. The validator resolves all grants and rejects equipment that
the start does not grant. These records carry no equipment or combat
execution; the consuming slices supply those systems.

`wake_cards.json`: `id` (future faction ID), `name`, `pitch` (text asset).
The eight introductions set standing, not membership. They do not
activate incomplete faction content or handlers.

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
| name_key | NFC-normalized Unicode casefold; unique per origin |
| progress | unspent points, learned programs/hymns, seen zones, compressed terrain memory, offline timestamp |

The identity record, keyed by BBS user ID within the world's origin,
stores `first_decanted_at`, `legal_at`, receipts, carried clone debt and
resumable Wake progress. Character deletion removes its items and row,
and retains this record. Lease days use the identity's first decant;
character `created_at` is its own creation time. The world setting
`character_cap` defaults to one; raising it exposes an owned-character
selection menu on login. Only one body per identity is connected at once.

Remembered terrain stores a visibility bitmap (20,000 bits for a 200x100
zone), a tile-ID legend and the last-seen indices, compressed together in
a base64 blob in `progress`. It retains old terrain rather than revealing
current hidden geometry. A changed map extent invalidates its old bitmap.

### 2.2 Item instance

`id, template, owner (player id, cache id, apartment id, vendor id, or
null for world drop), quality (0.85–1.15), ammo, charges, secured, stack,
created_at`.

S16 adds optional integer `health` for a drone's current condition. New
drone instances start at their template maximum; old records without the
field represent unused hardware. Deployment removes the same owned item
from carried inventory and records its actor in `progress.drones` with
zone, tile, mode and target. Recall restores that instance with its
current health and quality. Item JSON stores the additive field without
a SQLite column migration. Destruction removes the item and deployment
record together; destroying equipment does not defeat its controller
for PvP XP.

S18 adds `key_for` (nullable tenancy ID) and `key_tier` (0 for non-keys,
1-3 for an issued apartment key). Only the server issues these fields;
the generic `key_apartment` template has fixed quality and no resale.
They persist in item JSON without a column migration. A key grants no
resident identity, storage, safe, bed, terminal or bank permission.

`bound` defaults false. Recovery and service-job producers set it for
goods that cannot be sold, dropped, transferred or fabricated. S12
enforces the transfer boundary; S10/S19 own those grants. SQLite world
schema 3 adds `vendor_budgets` (counter ID, UTC hour, remaining chits)
and `caches` (zone, tile, item IDs, expiry); item ownership and player
balances commit with these records in one transaction.

S10 adds cache victim/killer IDs and a first-recovery deadline. Clone
charge, identity debt and item transfer settle in that same transaction.
`progress.combat` holds durable down/dead phase and a UTC deadline;
combat cooldowns and temporary effects keep UTC expiries for reconnect
and restart. A zero stack is permitted only for an exhausted rechargeable
ammo container; the container remains carried until refilled or removed.

### 2.3 Apartment

`id, owner player id, zone, door object id, rent_paid_until, storage[] (item
instance ids), safe_chits, core_tier, last_hacked_at, hack_log[],
theft_receipts[], vestibule_access_until`.

S18 joins these fields to S15's existing `meta.interlock_state.apartments`
record (`resident`, `tier`, `door`, `hardware`, `light`, `sector`, `cell`).
It adds `class_id, unit, lapsed_since, lock_tier, safe_chits` and a unique
tenancy ID; a later resident never inherits an earlier private core.
`housing_serial` never reuses tenancy IDs. `unit_hacks[unit]` retains the
physical apartment's rolling theft watermark across surrender and
signing. `vestibule_access_until` maps visitor player IDs to UTC
deadlines. Invoices contain `{due, amount}`; `invoice` freezes the next
unpaid quote, and `last_invoice` records the most recent paid quote.
`impounds` are protected per-player item receipts with a per-item fee and
free chits. Rental payment, item ownership, safe, core and eviction state
commit in the same commerce transaction. Game design 8.7 defines stored
protection and carried protection as separate destination capacities.
Ownership strings are `apartment:<tenancy>` and `impound:<player>`;
`impounds[player]` holds `{items: {item_id: {fee}}, chits}`. S23 appends
fee-free market deliveries using the same proposal and item instances.
Character deletion releases its lease, core and impounded goods through
resumable cleanup after the deletion is durable.

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
data {data id → generation, remaining uptime, receipt, availability},
owner_faction (from relay)`. Street locks are identity/core UTC deadlines,
distinct from global offline state. Shared source availability, reward
and receipt commit in one storage transaction. Persist Silt descent
nonces before publication and contribution source uptime across restart.

S15 persists interlock records in world meta: independent control effects
with source core/control/revision, initiating player, start and UTC reset
deadlines; live owner assignments; per-core offline deadlines; per-platform
hold/immunity deadlines; and apartment storage IDs, the shared rolling
24-hour theft receipt, and at most 20 dated intrusion records. A flip,
power cut or theft commits before publication. Cuts save all affected
players' shock with the offline deadline; theft saves the transferred unit
with its apartment receipt. Rebuild composes surviving layers against
current content rather than restoring an old zone snapshot. An expired
layer cannot erase an event or another controller's newer layer.


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
target id, stance (normal, stealth, jacked, down, dead, sleeper), faction,
marked, visible_to (computed), behaviour state (NPCs), owner (drones)`.

### 3.2 Zone instance

`zone id (+ instance suffix for Blacksite), actors {}, objects {} with
live state (door open, terminal in use, relay progress), caches {},
salvage nodes {}, event effects[], rng, tick, listeners (session ids)`.

### 3.3 Presence (a jacked-in runner)

`player id, sector, cell, core (nullable), room (nullable), instance,
integrity, trace, rig slots with cooldowns, effects[], visible_to,
cast, escape, hit serial, NPC-risk consent`. Disconnected nonpublic
presences retain their exact physical actor through bounded escape;
reconnect must not create or move a second body. Maintenance shutdown
preserves durable player/source state without inventing feedback hits.

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
