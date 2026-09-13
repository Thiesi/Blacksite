# The Lattice

Expands `00-bible.md` §5 and §6. Mechanics follow
`../design/00-game-design.md` §6 and use its numbers; where a number here
is new (an ICE's integrity, a program's cast time) it is the initial value
that the content data files must carry and the balance slice may tune.
Zone slugs referenced here are the canonical slugs the gazetteer uses.

---

## 1. Going down

You do not enter the Lattice. You go down. That is how everyone in Karst
says it, and it is not a metaphor: the city's network was laid in the
service galleries under the streets, and the first runners learned it by
following the cables into the dark. Forty-one years later the geography
stuck. The Core sector sits under the Core, Vatside under Vatside, and if
you are standing in the Sink's sector you are, in every way that costs
you, standing in the Sink.

Jacking in is a small ritual and everybody has their own. Public
terminals in the Core are chest-high steel pillars with a warm jack and a
scuffed rest for your forehead. In Old Works they are stripped cabinets
with a cable that someone has taped a hundred times. A rig implant makes
the terminal optional: you sit down somewhere you trust, or somewhere you
do not, and close your eyes. The city goes quiet the way a room goes quiet
when a fridge stops. Then the sector resolves.

It looks like this. A field of cells, laid out in a grid the old
engineers imposed on it, lit by whatever the sector's owner can afford:
Halvard's sector is amber and precise, the Sink's is red and half of the
lights are out. Cells you can enter are bright; cells that are gated have
a line through them; cells you have not found are not there yet. Cores
sit in the field like buildings, and they are the only things in the
Lattice with an inside. ICE is visible from outside a core's entrance if
you have the eyes for it, the way you can see a dog through a fence.

Moving between cells is a decision, not a walk. It takes about a second.
Everyone feels the delay as a held breath. Runners with a fast cortex
feel it less. Inside a core, rooms are close and the delay is the same,
but the walls listen.

Your presence in the Lattice has integrity, which is a number, and trace,
whose thresholds and next consequences the display always shows. Losing integrity feels
like losing your footing. Losing all of it throws you back up into your
body with your ears ringing and your hands shaking, shock all the way up,
and a crew member standing over you saying your name. If black ICE did
it, you are also bleeding. People have died in a chair in the Tin Halo
with their eyes open, and the Lattice recorded nothing.

Runners talk about it the way divers talk. You go down, you go deep, you
come up. The Silt is what is under the sectors, and the Silt is where you
do not come up from unless you are lucky, or somebody is listening for
you. Ninety-Nine went down in Year 17 and is still talking, so make of
that what you will.

## 2. Sectors

Every sector has a public entrance cell (where terminals in that district
drop you), a spread of public, gated, and hidden cells, its cores, and one
sector descent cell into the Silt; Listening Post has one additional
interior route to that same descent instance. Uplink cells join sectors
without jacking out. Public links remain open; gated service shortcuts can
require temporary credentials. A faction cannot lock every route to another
district.

| Sector | Cells | Public / gated / hidden | Notable cells | Descent cell |
|---|---|---|---|---|
| Spire | 24 | 6 / 14 / 4 | Lobby Register, Pass Office, Executive Lift Bus, Skywatch Feed | *Sump* (hidden, under the shaft telemetry) |
| Core | 40 | 28 / 8 / 4 | Plaza Exchange, Precinct Frontage, Tram Signal Bus, Civic Hall Annex, Bank Vestibule | *The Grate* (gated, Warden key) |
| Vatside | 28 | 14 / 10 / 4 | Wake Hall Node, Vatline Queue, Clinic Scheduler, Template Vault Approach | *Drain* (hidden) |
| Tramyard | 32 | 16 / 12 / 4 | Gate Bus East, Gate Bus West, Depot Floor, Convoy Staging, Dispatch Approach | *Sidings* (gated, Kestrel key) |
| The Sink | 30 | 12 / 8 / 10 | Cable Car Bus, Terrace Wards, Floor Market, Sable's Back Room | *The Drop* (hidden, deepest descent in a district) |
| Chapel Ward | 22 | 10 / 6 / 6 | Nave Node, Bell Gallery, Listening Post Approach | *The Well* (public; the Choir wants you to find it) |
| Old Works | 34 | 12 / 6 / 16 | Foundry Floor, Annex Records, Ninety-Nine's Drop, the Tape Room | *Cut Cable* (hidden) |
| Terraces | 36 | 20 / 12 / 4 | Block A Super, Block B Super, Outpost Feed, and one private-core entrance per rented apartment | *Basement Riser* (gated, resident key) |
| Sodium Row | 20 | 14 / 4 / 2 | House Lights, Tin Halo Back Bar, Sign Grid | *Stage Door* (hidden) |
| Undercity | 26 | 4 / 8 / 14 | Pumphouse Panel, Cavern Relay, Outworks Seal Approach | *The Seam* (public and unmarked; it does not need to hide) |
| Scour | 18 | 6 / 12 / 0 | one uplink cell per relay: Landing Uplink, Mile Relay, Beacon Relay, Crash Relay, Far Relay, Patrol Beacon | *Static* (gated, only during Ring-fall) |
| Silt | procedural | see §6 | — | — |

Notes:

- Hidden cells are found by a Listening scan (game design §6.5) on
  an adjacent cell, by the *Lantern* program, or during a Choir Surge,
  which maps the current band or sector for its duration.
- The Scour sector is thin by design: it exists only where a relay's
  uplink reaches. Losing relay ownership changes the uplink's owner and shortcut
  credential, not the existence of the cell. Neutral relays still run.
  A power cut takes its core offline but preserves an escape route.
- The Undercity sector has more hidden than public cells because nobody
  maintains the map. Runners who map it sell the map.

## 3. Cores

A core's **hardware location** is the zone and the object in that zone where
a crew can cut power (design doc §6.4). **Controls** are named in the form
`object @ zone-slug` and each maps to one meatspace object. Each core's ID
is given in parentheses after its name; every other document references a
core by that ID. **Data** is what a successful run lifts. ICE listed is what
the core runs at its base tier; owned relays and season state can add one
class.

### 3.1 Spire

**Halvard Citadel** (`lat-halvard-citadel`) — Halvard, tier 5, 12 rooms. Hardware: server hall
@ `spire-shaft-head`. Data: Site Zero construction fragments (season
contribution, story), executive correspondence (story contracts), pass
templates. Controls: `executive lift lockdown @ spire-atrium`,
`security doors 1–4 @ spire-shaft-head`, `sealed shaft camera @ spire-shaft-head`.
ICE: Tripwire ×2, Glasshouse ×2, Mirror, Blackglass ×2, Hound (at trace
100).

**Gatehouse** (`lat-gatehouse`) — Halvard, tier 3, 6 rooms. Hardware: lobby security desk
@ `spire-atrium`. Data: pass registry (a lifted pass admits one Freelance or
non-corporate crew to the public levels for 30 minutes), visitor logs.
Controls: `turnstiles @ spire-atrium`, `public lifts @ spire-atrium`.
ICE: Tripwire, Turnstile, Mastiff, Glasshouse.

**Skywatch** (`lat-skywatch`) — Halvard, tier 4, 7 rooms. Hardware: array control @
`spire-shaft-head`. Data: Ring-fall forecast (names the next Ring-fall ring and
its start within a 10-minute window; sells to Ferrymen for a lot),
patrol schedules. Controls: `patrol beacon dispatch @ scour-ring-2`
(diverts the next Halvard patrol NPC crew away from a ring for 15 min).
ICE: Sandman, Hornets, Glasshouse, Kiln, Mirror.

### 3.2 Core

**Precinct** (`lat-precinct`) — Wardens, tier 3, 8 rooms. Hardware: precinct
switch room @ `core-precinct`. Data: Marked registry (an evidence record;
cannot erase a live Mark), bounty ledger, Warden heat records. Controls:
`camera net @ core-plaza` (reveals a mission patrol recording; cannot
disable safety), `curfew shutters @ core-plaza`, `holding cell doors @
core-precinct`. ICE: Tripwire ×2, Ticker, Bluecoat ×2, Mastiff.

**Civic Ledger** (`lat-civic-ledger`) — Civic Authority, tier 2, 5 rooms. Hardware: records
annex @ `core-plaza`. Data: ration registry, personhood records (a story
contract forges a Ninety-Day early for an NPC; players cannot forge their
own). Controls: `hall doors @ core-plaza`. ICE: Tripwire, Turnstile,
Ticker.

**Tram Signal** (`lat-tram-signal`) — Kestrel on Civic lease, tier 2, 5 rooms. Hardware:
signal cabinet @ `core-tram-hub`. Data: timetable (nothing sells; the
control is the point). Controls: `tram hold @ core-tram-hub` (delays the
next departure for at most 30 s, followed by 120 s immunity; in-flight
journeys always finish), `platform gates @ core-tram-hub`.
ICE: Turnstile, Lockstep, Ticker.

**Kestrel Branch** (`lat-kestrel-branch`) — Kestrel, tier 3, 6 rooms. Hardware: vault door @
`core-plaza`. Data: transaction logs (contract objective only; banked
chits are never liftable, by design). Controls: `branch shutters @
core-plaza`, `impound manifest @ terraces-blocks` (reads what the impound
holds). ICE: Tripwire, Glasshouse ×2, Lockstep, Mastiff.

### 3.3 Vatside

**Wake Hall** (`lat-wake-hall`) — Sablier, tier 1, 3 rooms. Hardware: none (the tutorial
core cannot be cut). Data: your own decant record. Controls: `exit door @
vatside-wake-hall`. ICE: Tripwire (one, integrity 10, deals 5).

**Vatline** (`lat-vatline`) — Sablier, tier 4, 9 rooms. Hardware: vat
control @ `vatside-vat-row`. Data: decant queue, template archive index
(Cantor origin story arc; season contribution). Controls: `vat lockdown @
vatside-vat-row` (isolates a mission test vat; never delays or denies player
decants), `clinic doors @ vatside-clinics`. ICE: Tripwire, Glasshouse,
Suture ×2, Sandman, Kiln.

**Sablier Clinical** (`lat-sablier-clinical`) — Sablier, tier 3, 6 rooms. Hardware: scheduler
cabinet @ `vatside-clinics`. Data: implant schematics (fabrication),
surgery schedule (a contract objective: bump an NPC). Controls: `surgery
lock @ vatside-clinics`. ICE: Tripwire, Suture, Glasshouse, Mastiff.

### 3.4 Tramyard

**Gatehouse East** (`lat-gatehouse-east`) — Kestrel, tier 3, 7 rooms.
Hardware: gate control hut @ `tramyard-wall-gate`. Data: convoy manifests
(predict Convoy events and cargo), gate schedules. Controls: `Gate Nine
outbound @ tramyard-wall-gate`, `Gate Nine service latch @
tramyard-wall-gate`, `gate turret @ tramyard-wall-gate`. ICE: Tripwire,
Turnstile, Lockstep, Mastiff, Hornets.

**Depot Control** (`lat-depot-control`) — Kestrel, tier 2, 5 rooms. Hardware: depot office @
`tramyard-depots`. Data: ration allocations, warehouse inventory (fetch
contracts). Controls: `warehouse doors A–C @ tramyard-depots`, `forklift
drones @ tramyard-depots` (they stop, or they follow the runner's crew).
ICE: Tripwire, Turnstile, Ticker.

**Dispatch** (`lat-dispatch`) — Kestrel, tier 5, 10 rooms. Hardware: dispatch tower @
`tramyard-depots`. Data: convoy routing (season story), the Dispatcher's
voice logs (the arc that asks what the Dispatcher is). Controls: `convoy
route @ scour-ring-1` (moves the next Convoy event's route one ring
inward or outward). ICE: Lockstep ×2, Glasshouse ×2, Sandman, Tar,
Blackglass, Hound (at trace 100). The Dispatcher speaks to runners in the
last room. It is not ICE. It is not attackable.

### 3.5 The Sink

**Sable's Back Room** (`lat-sables-back-room`) — Red Sable, tier 4, 8 rooms, black core. Hardware:
the cable car's rack @ `sink-terraces` (it moves; cutting it means
boarding). Data: black market ledger (unlocks a hidden Sable vendor for
the runner for 24 h), bounty contracts, protection lists. Controls:
`turret bank @ sink-terraces`, `cable car brakes @ sink-terraces`,
`floor market lights @ sink-floor`. ICE: Shiv ×3, Liar ×2, Tar, Hornets,
Kiln.

**Terrace Wards** (`lat-terrace-wards`) — Red Sable, tier 2, 4 rooms. Hardware: ward panel @
`sink-terraces`. Data: protection roster. Controls: `ward doors @
sink-terraces`. ICE: Shiv ×2, Tripwire.

**Cable Car** (`lat-cable-car`) — Red Sable, tier 3, 5 rooms. Hardware: the car itself @
`sink-terraces`. Data: Sable's calendar (where Reyes will be; story
contracts). Controls: `cable car routing @ sink-terraces` (sends the car
to a chosen terrace). ICE: Shiv ×2, Liar, Sandman.

### 3.6 Chapel Ward

**Nave** (`lat-nave`) — Choir, tier 3, 7 rooms. Hardware: choir loft @ `chapel-nave`.
Data: Tenant recordings (season contribution for the Choir arc; listening
to one raises Listening skill), hymnal (Cantor abilities are unlocked
here, not lifted). Controls: `hall doors @ chapel-nave`, `bell gallery @
chapel-towers` (rings the bells: a 60 s hymn buff to every Choir member
in Chapel Ward). ICE: Cantillation ×2, Glasshouse, Sandman.

**Listening Post** (`lat-listening-post`) — Choir, tier 4, 6 rooms. Hardware: tower head @
`chapel-towers`. Data: Silt maps (a map lifted here reveals the top band
of the next descent), residual fragments. Controls: none. This core has
a descent cell *inside* it, the only core that does. ICE: Cantillation
×2, Mirror, Drift (it leaked up).

### 3.7 Old Works

**Ninety-Nine's Drop** (`lat-ninety-nines-drop`) — Unmoored, tier 2, 4 rooms. Hardware: the tape
cabinet @ `oldworks-drop` (service is mission-scoped; it cannot remove Ninety-Nine's public
advice or another player's story access). Data: Silt maps, Unmoored dead drops
(contract hand-offs). Controls: `drop lights @ oldworks-drop`. ICE: none
that belongs to anyone; Ninety-Nine runs a Liar as a joke and tells you
so.

**Foundry** (`lat-foundry`) — Unmoored, tier 3, 6 rooms. Hardware: gantry control @
`oldworks-yards`. Data: fabrication schematics (weapons, rigs), stolen
Halvard tooling. Controls: `yard lights @ oldworks-yards`, `gantry @
oldworks-yards` (drops a load: a hazard tile row for 30 s). ICE:
Tripwire, Sandman, Hornets, Mastiff.

**Site Zero Annex** (`lat-site-zero-annex`) — abandoned Halvard, tier 4, 9 rooms. Hardware: annex
substation @ `oldworks-yards`. Data: original construction records
(season contribution and the largest single story source about what Site
Zero was), Halvard tooling. Controls: `annex blast doors @
oldworks-yards`. ICE: Tripwire ×2, Glasshouse, Mirror, Kiln, Blackglass
(dormant until a Glasshouse breaks).

### 3.8 Terraces

**Private core (template)** (`lat-private-core`) — resident, tier 1 to 3, 3
to 5 rooms. Hardware: the apartment's wall panel @ the apartment's zone slug
(`terraces-blocks` (Block A or Block B)). Data: storage manifest; one
unsecured item may be lifted per successful run per apartment per day
(design doc §6.4). Controls: `apartment door` (opens the delivery vestibule
for 30 s, never the resident's occupied room or additional storage),
`apartment lights`. ICE: tier 1, one Tripwire; tier 2, Tripwire and
Turnstile; tier 3, Tripwire, Glasshouse, Mastiff. Residents pay for ICE
upgrades in chits.

**Block Super** (`lat-block-super`) — Kestrel property, tier 2, 5 rooms. Hardware: super's
office @ `terraces-blocks`. Data: rent ledger, impound manifest. Controls:
`block doors A @ terraces-blocks`, `block doors B @ terraces-blocks`,
`lift lock @ terraces-blocks`. ICE: Tripwire, Turnstile, Ticker.

**Terrace Outpost** (`lat-terrace-outpost`) — Wardens, tier 2, 4 rooms. Hardware: outpost desk @
`terraces-blocks`. Data: outpost log. Controls: `outpost cameras @
terraces-blocks` (delays Warden response in the Terraces by 20 s for 5
min). ICE: Tripwire, Bluecoat.

### 3.9 Sodium Row

**Tin Halo** (`lat-tin-halo`) — Vesper, tier 2, 4 rooms. Hardware: back bar cabinet @
`sodium-tin-halo`. Data: rumours (a lifted rumour names a committed event
plan and its forecast window; Vesper sells the same thing for
chits and prefers that), contract archive. Controls: `back door @
sodium-tin-halo`. ICE: Tripwire, Liar, Turnstile. Vesper knows when it has
been run and comments on it; prices still follow the documented vendor rules.

**House Lights** (`lat-house-lights`) — neutral, Sable-enforced, tier 3, 6 rooms. Hardware:
sign grid room @ `sodium-row`. Data: patron ledger (who visited the Row
and when; a contract staple). Controls: `Row lighting @ sodium-row`
(blackout for 30 s; stealth for everyone), `sign grid @ sodium-row`
(displays a runner-chosen 20-display-column message on every sign for 60 s;
the Row's favourite prank). ICE: Tripwire, Shiv, Liar, Glasshouse.

### 3.10 Undercity

**Pumphouse** (`lat-pumphouse`) — Civic, abandoned, tier 3, 6 rooms. Hardware: pump panel
@ `under-service`. Data: gallery maps. Controls: `flood tunnel 2 @
under-service`, `drain cistern @ under-caverns` (each opens one
passage and closes another; the Undercity's route changes for 10 min).
ICE: Tripwire, Tar, Drift, Mastiff.

**Outworks Seal** (`lat-outworks-seal`) — Halvard, tier 5, 12 rooms.
Hardware: seal plant @ `under-outworks`. Data: seal telemetry (the Exhale is
visible here first), Undercity keys. Controls: `seal blast door @
under-outworks` (optional shortcut during an Exhale; cannot gate pre-opening
story work), `shaft-door-east @ under-outworks` (the Season 1 story door).
Story rooms `shaft-monitor` and `shaft-lamps`; story data
`activation-log-last-page`. ICE: Tripwire ×2, Glasshouse ×2, Mirror,
Blackglass ×2, Sweeper (only during an Exhale), Hound (at trace 100).

### 3.11 Scour

**Relay Uplink (template)** (`lat-relay-uplink`) — held by whichever faction holds the relay,
tier 2 (Mile Relay), 3 (Beacon Relay), 4 (Crash Relay and Far Relay),
3 to 6 rooms. Hardware: the relay mast @ its zone (`scour-ring-1`,
`scour-ring-2`, `scour-ring-3`, `scour-ring-4`). Data: relay telemetry. Controls: `relay terminal
override` (the hack half of a capture, design doc §7.4), `relay vendor
lock`. ICE: at tier 2, Tripwire and Turnstile; at tier 3, plus Mastiff;
at tier 4, plus Hornets and one class chosen by the holding faction from
its own roster (Halvard adds Kiln, Ferrymen add Drift, Sable adds Shiv,
the Choir adds Cantillation, others add Glasshouse).

**Patrol Beacon** (`lat-patrol-beacon`) — Halvard, tier 3, 5 rooms. Hardware: beacon mast @
`scour-ring-2`. Data: patrol logs. Controls: `patrol recall @
scour-ring-2` (recalls the current Halvard patrol NPC crew to the wall).
ICE: Tripwire, Hornets, Mastiff, Lockstep.

The registry includes the named cores, the templates, and the additional
service cores below. Use IDs, not a manually maintained count.

### 3.12 Service cores and hardware registry

These close the gazetteer's previously unbound hardware references.
They use existing names and the same control model; no special engine.

| Core ID | Name | Tier / rooms | Hardware zone(s) | Controls / ICE |
|---|---|---|---|---|
| `lat-sump` | Sump | 2 / 4 | `sink-floor` | pump regions and grate; Tripwire, Turnstile |
| `lat-drowned` | Drowned | 3 / 6 | `under-drowned` | bulkhead and local pumps; Tar, Drift, Mastiff |
| `lat-shaft` | Shaft | 5 / 8 | `spire-shaft-head`, `under-shaft-foot` | maintenance cage and telemetry; Glasshouse, Mirror, Hound |
| `lat-landing` | Landing | 2 / 4 | `scour-landing` | local survey display; Tripwire, Turnstile |

`lat-shaft` alone has two hardware locations. The Halvard Citadel is a
separate server hall at Shaft Head. Neither is the instanced finale core.
Every relay additionally has a distinct instance of `lat-relay-uplink`
with a stable ID `lat-relay-<relay slug>`, including neutral relays.
Its hardware is the mast beside the physical capture terminal. Its
`relay_open` control targets that relay, not unrelated service hardware.
All relay instance IDs and tiers are game design §7.7.

### 3.13 Season cores

Defined by `05-story-arcs.md` and built with their Blacksite level; listed
here so the ID space stays in one place.

**Uplink Hall** (`lat-uplink-hall`) — Halvard, abandoned, tier 5, opens
with Blacksite Level 2 (`blacksite-l1` is Level 1's zone; Level 2's zone is
defined by the story arcs). Hardware: the patch frame in the level itself.
Data: the Year 0 severance procedure. Controls: none outside the level.
ICE: Blackglass ×2, Sweeper, Hound.

**Story data IDs** referenced by the story arcs, by core:
`lat-depot-control` — `routing-audit-y0`, `dispatch-channel-log`;
`lat-vatline` — `template-lineage`, `template-cantor-origin`,
`decant-audio-y41`; `lat-sables-back-room` — `sink-power-schedule`;
`lat-precinct` — `curfew-orders-y22`, `brann-private-ledger`; `lat-dispatch`
— `routing-authority-image`, `severance-procedure-y0`,
`sink-allocation-rule`, controls `dispatch-mute-1s`, `unmoored-mirror`;
`lat-uplink-hall` — `dispatch-echo`; the Silt — `silt-echo`,
`listener-3-residual`. A source record has one canonical source ID; mission
fetch copies and journal evidence refer back to it. `template-source-drive`
is at the archived Level 1 gallery, `brann-private-ledger` at the precinct
archive; neither is an unrelated second loot spawn. Validate all references.

## 4. ICE

Integrity is the ICE's own pool; attack is damage to the runner's
integrity per hit and the cast time between hits; **black** ICE also
deals meatspace health damage on each hit, listed as `+meat`. Trigger
names: *entry* (runner enters the room), *touch* (runner starts lifting
data or flipping a control), *trace N* (runner's trace reaches N),
*passage* (runner tries to leave through the cell it guards), *always*
(active from core entry).

| Name | Tier | Integrity | Attack | Trigger | Behaviour | Black | Counters |
|---|---|---|---|---|---|---|---|
| Tripwire | 1–2 | 20 | 8 / 1.0 s | entry | Fires three times, then only raises trace +10 per second it survives. | no | any attack; Sneakers delays it 3 s |
| Turnstile | 1–2 | 30 | none | passage | Blocks the room's exit until broken or keyed. | no | key programs open it without a fight |
| Ticker | 1–2 | 15 | none | touch | Adds +1 trace per second while it lives. Cheap, everywhere. | no | kill it first; decoys halve it |
| Bluecoat | 2–3 | 45 | 10 / 1.5 s | trace 50 | Warden ICE. Pins the runner in place 4 s, then dispatches Wardens to the body. | no | Slicker absorbs the pin; keys do nothing |
| Mastiff | 2–3 | 60 | 14 / 1.2 s | always | Patrols the core's rooms on a loop; attacks whatever it walks into. | no | stealth avoids; Tar-immune |
| Glasshouse | 2–4 | 50 / 80 / 110 | none | touch | Shields the room's data. Must be broken before anything can be lifted. | no | heavy attack programs; Mirror often sits behind one |
| Sandman | 2–3 | 40 | 6 / 1.0 s | entry | Strips stealth, doubles loader cast times while alive. | no | kill early; Nobody resists 5 s |
| Hornets | 3 | 35 | 4 ×5 / 2.0 s | entry | A swarm: five small hits per cast. Shields waste against it. | no | area attack (Mallet); Umbrella is useless |
| Liar | 3 | 30 | none | entry | Adds fake data rooms; a runner who takes the bait loses 10 s and +15 trace. | no | Compass shows the real map |
| Tar | 3–4 | 55 | 8 / 2.0 s | always | Every program's cast time ×2 while it lives. | no | Overclock cancels; kill first |
| Lockstep | 2–3 | 40 | none | passage | Kestrel gate ICE. Opens for 10 s every 60 s on a schedule visible in the room. | no | wait, or Locksmith |
| Shiv | 3 | 25 | 12 / 0.6 s | entry | Sable ICE. Fast, cheap, dies quick, and tells the core's owner where the runner's body is. | no | kill in one cast (Drill) before it reports |
| Suture | 3–4 | 50 | 3 / 0.5 s | always | Sablier ICE. Drains slowly and heals other ICE in the room 5 per second. | no | kill it first, always |
| Cantillation | 3–4 | 60 | 10–25 / 1.5 s | entry | Choir ICE. Damage scales down with the runner's Resonance; Cantors take none and hear a hymn instead. | no | Resonance; Wetsuit |
| Mirror | 4 | 70 | reflects | touch | Reflects the next attack program's damage back at the caster, then rests 5 s. | no | shield up before attacking; utility programs pass |
| Kiln | 4 | 90 | 25 +10 meat / 1.5 s | touch | Halvard black ICE. Burns the runner who touches the data. | yes | break Glasshouse from range first; Bunker |
| Hound | 3–5 | 80 / 120 / 150 | 20 / 25 / 30 (+15 meat at tier 5) / 1.0 s | trace 100 | Hunter. Spawns in corporate cores at trace 100 and follows the runner across cells until killed, jacked out, or 3 min pass. | tier 5 | Cutout breaks the follow once; jack out |
| Blackglass | 5 | 200 | 35 +20 meat / 1.5 s | touch | Halvard flagship. Sits on the best data in the city. | yes | a crew: one runner shields, one attacks; Blackout |
| Drift | Silt, 2 | 40 | 10 / 1.0 s | always | Unowned. Random-walks cells; some drift up into district sectors. | no | avoid; Anchor holds position against it |
| Undertow | Silt, 3 | 70 | none | entry | Pulls the runner one band deeper on a failed cast. | no | Anchor; Redline to out-cast it |
| Chorister | Silt, 3–4 | 60 | 15 / 2.0 s | entry | Responsive process. Shows a repeating signal. Use the labelled sampling procedure in design §6.6; no answer quiz. | no | survey its pattern; hold or withdraw |
| Shade | Silt, 4 | 80 | 20 / 1.2 s | entry | A hostile residual: a dead runner's habits with none of the runner. Copies the last program you cast. | no | do not cast attacks first; Umbrella |
| Sweeper | Silt, 4-5 | 250 | 40 +25 meat / 2.0 s | always | Attributed by some to the Custodian. Systematic, slow, cleans a band cell by cell. It is not interested in you until you are in its way. | yes | leave the band; nothing kills it in one run |

Twenty-three classes.

## 5. Programs

This roster mirrors game design §17.2. Thirty base programs plus Burn,
Hunter-killer, two Cantillations, and Residual Fragment: 35 total.
Programs are learned; loading respects slots, not one program per key.
Purchase prices are initial values. Any attack program may target only
its stated target class; Burn handles player presences under §6.1 safety.

| ID | Name | Class | Tier | Slots | Cast | Cooldown | Effect | Price |
|---|---|---|---|---|---|---|---|---|
| `prg_pick` | Pick | attack | 1 | 1 | 0.8 s | 1.0 s | 10 integrity damage | 150 |
| `prg_chisel` | Chisel | attack | 2 | 1 | 1.0 s | 1.5 s | 18 damage | 800 |
| `prg_drill` | Drill | attack | 3 | 1 | 1.2 s | 2.0 s | 30 damage; 45 against ICE with integrity ≤ 30 | 1200 |
| `prg_mallet` | Mallet | attack | 3 | 2 | 1.5 s | 3.0 s | 20 damage to every ICE in the room | 1200 |
| `prg_lance` | Lance | attack | 4 | 2 | 1.5 s | 2.5 s | 45 damage, ignores Mirror once per cast | 1600 |
| `prg_blackout` | Blackout | attack | 5 | 2 | 2.0 s | 30 s | 120 damage to one ICE; then the runner's trace +25 | 2000 |
| `prg_umbrella` | Umbrella | shield | 1 | 1 | 0.5 s | 4.0 s | absorbs the next 15 damage | 200 |
| `prg_slicker` | Slicker | shield | 2 | 1 | 0.5 s | 5.0 s | absorbs 25; absorbs a Bluecoat pin | 800 |
| `prg_wetsuit` | Wetsuit | shield | 3 | 1 | 0.8 s | 6.0 s | absorbs 40; Cantillation damage halved | 1200 |
| `prg_bunker` | Bunker | shield | 4 | 2 | 1.0 s | 8.0 s | absorbs 60 and all meat damage from the next black hit | 1600 |
| `prg_smoke` | Smoke | decoy | 1 | 1 | 0.5 s | 10 s | trace gain −25 % for 10 s | 200 |
| `prg_alibi` | Alibi | decoy | 2 | 1 | 0.8 s | 15 s | trace −10 now | 800 |
| `prg_understudy` | Understudy | decoy | 3 | 1 | 1.0 s | 20 s | for 8 s, ICE attacks the decoy instead (it has 30 integrity) | 1200 |
| `prg_cutout` | Cutout | decoy | 4 | 2 | 1.2 s | 60 s | breaks a Hound's follow once; trace −20 | 1600 |
| `prg_caffeine` | Caffeine | loader | 1 | 1 | 0.3 s | 15 s | next cast time −30 % | 400 |
| `prg_overclock` | Overclock | loader | 2 | 1 | 0.5 s | 20 s | all cast times −25 % for 10 s; cancels Tar for that time | 800 |
| `prg_redline` | Redline | loader | 3 | 1 | 0.5 s | 30 s | cell-to-cell moves 0.4 s for 10 s; costs 5 integrity per move | 1200 |
| `prg_skeleton` | Skeleton | key | 1 | 1 | 1.5 s | 5 s | opens a tier-1 gated cell or Turnstile | 200 |
| `prg_locksmith` | Locksmith | key | 2 | 1 | 1.5 s | 5 s | opens tier ≤ 2 gates and Lockstep off-schedule | 800 |
| `prg_passkey` | Passkey | key | 3 | 1 | 2.0 s | 8 s | opens tier ≤ 3 gates; opens a private core's door control without a fight | 1200 |
| `prg_signet` | Signet | key | 4 | 1 | 2.0 s | 10 s | opens any Halvard gate; Halvard ICE ignores the runner for 5 s after | 1600 |
| `prg_sneakers` | Sneakers | stealth | 1 | 1 | 0.5 s | 12 s | entry-triggered ICE fires 3 s late | 400 |
| `prg_shroud` | Shroud | stealth | 2 | 1 | 0.8 s | 20 s | Mastiff ignores runner for 6 s; Sandman is delayed 5 s | 800 |
| `prg_nobody` | Nobody | stealth | 3 | 2 | 1.0 s | 30 s | invisible to all ICE for 5 s; trace does not rise | 1200 |
| `prg_compass` | Compass | utility | 1 | 1 | 1.0 s | 30 s | shows the core's true room map; Liar rooms marked | 150 |
| `prg_ledger` | Ledger | utility | 1 | 1 | — | — | passive: data lift time −25 % | 400 |
| `prg_lantern` | Lantern | utility | 2 | 1 | 1.5 s | 30 s | reveals hidden cells adjacent to the runner | 500 |
| `prg_pulse` | Pulse | utility | 3 | 1 | 1.0 s | 20 s | crew members in meatspace see the runner's cell and trace for 20 s | 1200 |
| `prg_tourniquet` | Tourniquet | utility | 3 | 1 | 1.5 s | 25 s | restores 30 integrity | 1200 |
| `prg_anchor` | Anchor | utility | 4 | 1 | 0.5 s | 30 s | immune to Undertow and Drift displacement for 15 s | 1600 |
| `prg_burn` | Burn | attack | 2 | 1 | 0.8 s | 3 s | 18 integrity damage to a permitted runner; +15 trace replaces attack trace | 1200 |
| `prg_hunter_killer` | Hunter-killer | attack | 4 | 2 | 2 s | 15 s | 80 integrity damage to hunter ICE only | 4200 |
| `prg_choir_cantillation_1` | Cantillation I | attack | 2 | 1 | 0.8 s | 4 s | Cantor: 20 damage + Resonance / 5; normal attack trace | 1000 |
| `prg_choir_cantillation_2` | Cantillation II | attack | 3 | 1 | 1.2 s | 6 s | Cantor, Choir +50 to acquire: 40 damage + Resonance / 3; normal attack trace | 3600 |
| `prg_residual_fragment` | Residual Fragment | utility | 3 | 1 | 1 s | single use | +25 effective Programs until jack-out, capped 100; bound faction loan | 0 |

Attack casts add +5 trace; Blackout adds +25 instead, Burn +15
instead in civic/corporate space. Effects otherwise use the trace table.
Cooldown begins when casting completes. Shield absorbs successive hits
until its budget is exhausted, expires on jack-out, and does not stack
with another shield. Blackout's acquisition cap does not limit casting.

Old catalog IDs are pre-implementation renames, not saved-game aliases.
In particular Shroud is stealth; Umbrella is the starter shield. There
is no Masterkey that bypasses every gate or gates the whole Silt.

## 6. The Silt

### 6.1 Generation

Every descent generates a fresh Silt graph from a seed made of the season
number, the sector descended from, and a per-descent nonce. A crew who
descend together share the seed. The graph is a chain of five **bands**,
each 8 to 20 cells, connected downward by one to three **sinks** (cells that
lead to the next band) and upward by exactly one **riser** per band, which
is always the cell you arrived in. Undertow may displace a runner from the
arrival riser but cannot delete it or its return path. Find that path or use
emergency jack-out.

| Band | Name | Depth | Contains |
|---|---|---|---|
| 1 | Shallows | 0 | dead district cells (old sector layouts, rearranged), Drift, one residual fragment, common Silt data |
| 2 | Drift | 1 | Drift in numbers, Undertow, unowned Tripwires and Turnstiles left by nobody, a runner's dead rig with programs in it (1 in 3) |
| 3 | The Reach | 2 | Choristers, Shades, the first Tenant recordings, season-contribution data |
| 4 | The Floor | 3 | Shades, one Sweeper on a loop, Blacksite conduit cells that show the sealed levels' telemetry, rare contribution data |
| 5 | The Conduit | 4 | the Sweeper's origin cell, the Tenant's voice, one choice-bearing dialogue per season; emergency jack-out remains available without a buff |

A descent cannot skip a band. Sinks in band 4 are hidden; band 5 has no
deeper sink. Hidden routes need Listening or Lantern, with a visible
surveyed bypass for required routes. A Choir Surge maps the current band for
its duration.

### 6.2 Residuals

Residuals are what the Silt keeps of runners who lost all integrity down
there. Fragments (band 1) are text: a name, a last program, a few lines.
Shades (bands 3 and 4) are hostile and copy the runner's last cast.
Ninety-Nine is the only whole residual, and the only one that talks back.

**Ninety-Nine's dead drop** is a tier-2 core in the Old Works sector
(§3.7), not in the Silt; Ninety-Nine reaches it from below through the
Cut Cable descent cell. It answers questions about the current season's
Silt (what band the contribution data is in, what the Sweeper's loop
looks like), sells nothing, and remembers every runner who has visited by
their BBS handle. Its dialogue grows across seasons: each season it is a
little more certain what it is, and it does not like it.

### 6.3 Season contributions

Silt data tagged as contribution: **Tenant recordings** (bands 3 to 5;
the Choir arc), **conduit telemetry** (band 4; the Custodian arc; pairs
with intact salvage), and **residual names** (any band; lifting a
fragment's name and delivering it to the Chronicle console is worth a
small contribution and adds the name to the Chronicle's dead list). A
runner who dies in the Silt leaves a fragment with their own name in the
next season's band 1.

## 7. Trace

Trace runs from 0 to 100. It rises while the runner is inside a core, by
tier, and per hostile action; it never rises in public cells, in the Silt,
or while *Nobody* is active. It resets to 0 on jack-out. Decoys reduce it
as listed above.

| Source | Trace |
|---|---|
| inside a core, per second, by tier 1 / 2 / 3 / 4 / 5 | +0.5 / +1 / +1.5 / +2 / +3 |
| attack program cast | +5 |
| data lift started | +10 |
| control flipped | +10 |
| burning another runner | +15 (civic and corporate sectors only) |
| Tripwire surviving, per second | +10 |
| Ticker alive, per second | +1 |
| Liar bait taken | +15 |
| Blackout cast | +25 |

Consequences by sector type. Sector types: **civic** (Core, Terraces,
Vatside outside Sablier cores), **corporate** (Spire, Tramyard, Sablier
cores, Halvard cores anywhere), **black** (Sink, Sodium Row), **street**
(Old Works, Chapel Ward, Undercity, Scour), **Silt** (no trace).

| Trace | Civic | Corporate | Black | Street |
|---|---|---|---|---|
| 50 | Bluecoat activates where present; the runner's name enters the Precinct's registry for 10 min | the core's ICE all wake regardless of trigger | the core owner is told a runner is inside (not who) | the core's owning faction gets a zone log line |
| 100 | Wardens dispatched to the body's zone and tile; Warden heat 10 min | a Hound spawns and follows | the owner faction is told exactly where the body is, by name; every member's sitrep shows it for 5 min | forced jack-out with shock 60; the core locks for 5 min |

Meatspace consequences of a forced jack-out: shock as stated, and any
black-ICE meat damage already taken stays taken.

### 7.1 A worked operation: Gate Nine

The crew wants the optional outbound latch open before the next patrol.
Its Ghost uses a public loan terminal with Pick, Umbrella, and Skeleton;
its street member covers the terminal and watches the gate. Inspect the
core's published tier and patrol route before entering. Each program
cast has the cooldown in design §17.2 and the trace cost in §7; movement
rounds up to simulation ticks. No prose example overrides those rules.

The first room's Tripwire can be destroyed, avoided during a mapped
patrol gap, or isolated by a street member at mission hardware. Breaking
it is noisy; isolating it exposes the person at the cabinet. Skeleton
handles the tier-1 Turnstile, not every later lock. A three-second latch
flip opens the outbound service route and logs the event upstairs.
The gate's mandatory inward pedestrian route remains usable throughout.

A solo runner uses the same terminal and the 120 s mission latch, jacks
out, then crosses. A mixed-faction crew can cooperate, with the mission
permission naming its participants. Additional manifests lie past a
patrolling Mastiff: taking them costs exposure and trace. Leaving with
the latch receipt is a successful run, even without clearing every room.

S14/S15 must calculate an exact deterministic replay from content and
tick rules; the old hand-counted example omitted cast trace, cooldowns,
and movement rounding and must not be used as a numerical golden.

## Glossary

Glossary: merged into 07-glossary.md.
