# Blacksite — Gazetteer

Every zone in Karst, the Undercity, and the Scour, with the data a content
author needs to build its map file and the flavour a writer needs to keep
it in voice. Canon is `00-bible.md` §4; the zone model is
`../design/00-game-design.md` §5. Map sizes are targets for the authored
tile file, not limits. Sight radius is the default per zone; carried
lights and stealth stance modify it per the design document.

Zone IDs are stable identifiers. Content files, exits, spawners, relays,
contracts, and the asset manifest reference them. Renaming an ID is a
migration.

## Overview

| ID | Name | District | Class | Lean | Size (w × h) |
|---|---|---|---|---|---|
| `spire-atrium` | Spire Atrium | The Spire | safe | Halvard | 60 × 30 |
| `spire-mezzanine` | Spire Mezzanine | The Spire | safe | Halvard | 50 × 24 |
| `spire-shaft-head` | Shaft Head | The Spire | contested | Halvard | 70 × 40 |
| `core-plaza` | Meridian Plaza | The Core | safe | Wardens | 90 × 40 |
| `core-tram-hub` | Central Tram Hub | The Core | safe | Kestrel / Wardens | 80 × 30 |
| `core-precinct` | Warden Precinct | The Core | safe | Wardens | 50 × 24 |
| `vatside-wake-hall` | Wake Hall | Vatside | pocket | Sablier | 40 × 20 |
| `vatside-clinics` | Clinic Row | Vatside | contested | Sablier | 80 × 34 |
| `vatside-vat-row` | Vat Row | Vatside | contested | Sablier | 90 × 36 |
| `tramyard-depots` | Ration Depots | Tramyard | contested | Kestrel | 120 × 40 |
| `tramyard-market` | Tramyard Market | Tramyard | contested | Kestrel | 80 × 36 |
| `tramyard-wall-gate` | Gate Nine | Tramyard | contested | Kestrel | 70 × 50 |
| `sink-rim` | The Rim | The Sink | contested | Sable | 100 × 30 |
| `sink-terraces` | Sink Terraces | The Sink | contested | Sable | 90 × 60 |
| `sink-floor` | The Floor | The Sink | contested | Sable | 70 × 40 |
| `chapel-towers` | Cooling Towers | Chapel Ward | contested | Choir | 80 × 40 |
| `chapel-nave` | The Nave | Chapel Ward | pocket | Choir | 50 × 30 |
| `oldworks-main` | Contractor Street | Old Works | contested | Unmoored | 110 × 34 |
| `oldworks-yards` | Fabrication Yards | Old Works | contested | Unmoored | 100 × 50 |
| `oldworks-drop` | The Drop | Old Works | pocket | Unmoored | 40 × 20 |
| `terraces-blocks` | Block Street | The Terraces | contested | neutral | 120 × 40 |
| `terraces-lobby` | Residence Lobby | The Terraces | pocket | neutral | 40 × 24 |
| `sodium-row` | Sodium Row | Sodium Row | contested | neutral (Sable-enforced) | 100 × 30 |
| `sodium-tin-halo` | The Tin Halo | Sodium Row | pocket | neutral | 44 × 22 |
| `under-service` | Service Level | Undercity | open | none | 120 × 50 |
| `under-drowned` | The Drowned Level | Undercity | open | none | 100 × 60 |
| `under-caverns` | Karst Caverns | Undercity | open | none | 150 × 80 |
| `under-outworks` | Blacksite Outworks | Undercity | open | none | 120 × 70 |
| `under-shaft-foot` | Shaft Foot | Undercity | open | none | 60 × 60 |
| `scour-landing` | The Landing | The Scour | pocket | Ferrymen | 60 × 30 |
| `scour-ring-1` | Wall Ring | The Scour | open | Kestrel / Halvard | 160 × 80 |
| `scour-ring-2` | Beacon Ring | The Scour | open | Ferrymen | 180 × 90 |
| `scour-ring-3` | Crash Ring | The Scour | open | none | 200 × 100 |
| `scour-ring-4` | Far Ring | The Scour | open | none | 200 × 100 |
| `blacksite-l1` | Blacksite Level One | The Blacksite | instanced | none | see story arcs |

Thirty-five zones. Five safe, six pockets, sixteen contested, seven open,
one instanced.

## Sketch legend

Used in every layout sketch below. Sketches are proportion guides at
roughly one character per three to five tiles, not the authored map.

```
#  wall / impassable        .  floor
%  cover (value 1–3)        +  door (locked doors noted in text)
T  Lattice terminal         R  relay control terminal
>  zone exit                ~  water (slows, no cover)
!  hazard tile              $  vendor / NPC anchor
V  clone vat                L  light source (sight radius bump)
```

---

## The Spire

### `spire-atrium` — Spire Atrium

- **Class:** safe. **Lean:** Halvard. **Size:** 60 × 30. **Sight:** 14.
- **Exits:** `core-plaza` (street, the Spire steps); `spire-mezzanine`
  (lift, pass-gated: Halvard standing +10 or a visitor's pass item).
- **Relays:** none.
- **Terminals:** two public Lattice terminals, Halvard-sector cells only.
- **Vendors / anchors:** Halvard recruiter (Liaison Desk), a Sablier
  concession clinic, a Kestrel courier desk.
- **Spawners:** Halvard security (guard behaviour, escalating like
  Wardens but corporate).

The only room in Karst with a horizon. Forty metres of glass looks out
over the wall to the Scour, and past the Scour to a line where the ground
stops and the Ring begins. People come in just to stand there. Security
lets them, for a while. The floor is polished stone quarried out of the
shaft itself, and if you put your ear to it, people say, you can hear it
hum. People say a lot of things in the Atrium. Security listens to those
too.

```
##########################
#..............L.........#
#..%%..$......T..$..%%...#
#.......................+#  + lift to mezzanine
#..%%.........T.....%%...#
#.......L.......L........#
######>>>>>>>>>>>>########  > steps to core-plaza
```

### `spire-mezzanine` — Spire Mezzanine

- **Class:** safe. **Lean:** Halvard. **Size:** 50 × 24. **Sight:** 12.
- **Exits:** `spire-atrium` (lift); `spire-shaft-head` (service lift,
  locked: Halvard member or a story contract key).
- **Relays:** none.
- **Terminals:** one Halvard-member terminal (Spire core entrance,
  tier 4).
- **Vendors / anchors:** Halvard quartermaster (heavy weapons, armour),
  Halvard contract handler, Director Halvard's outer office (story
  anchor, not enterable).
- **Spawners:** Halvard security, Halvard staff (talkers).

The corporate floor. Carpet that has never seen the street, doors that
open before you touch them and refuse to open at all if the building has
decided about you. Halvard members treat it like a barracks with better
coffee. Everyone else gets a pass, a chaperone drone, and the feeling of
being measured for something.

```
########################
#.$...T....+........$..#
#......##########......#
#..%...#........#...%..#
#......#..(HQ)..#......#
#+.....##########.....+#  left + service lift down / right + lift to atrium
########################
```

### `spire-shaft-head` — Shaft Head

- **Class:** contested. **Lean:** Halvard. **Size:** 70 × 40.
  **Sight:** 8 (industrial lighting, pools of dark).
- **Exits:** `spire-mezzanine` (service lift, locked from below by a
  Spire core control); `under-shaft-foot` (the Shaft: a maintenance
  cage, story-gated, opens only during the season finale arc).
- **Relays:** **Shaft Relay** (the only relay inside the Spire; capturing
  it is a story milestone and pays Halvard-tier influence).
- **Terminals:** one hardware terminal (Shaft Head core, tier 5; its
  hardware location is in this zone).
- **Vendors / anchors:** none. A Halvard engineering crew (talkers, will
  not trade).
- **Spawners:** Halvard security (heavy), maintenance drones, and during
  Exhale events, things that came up the shaft.

Under the carpet and the coffee, the building is a plug. The shaft head
is a concrete collar thirty metres across with a cage lift bolted over
the hole, welded shut, unwelded, welded again. Halvard engineers work
here in shifts and do not talk about the shifts. The air comes up warm.
Everything metal is slightly, permanently, damp.

```
##########################
#+......%%........%%.....#  + service lift up
#...#####.......#####....#
#...#...#..!!!..#...#.T..#
#...#...#.!###!.#...#....#
#...#####..!R!..#####....#
#..........!!!...........#  ! shaft collar; R Shaft Relay on the cage
##########################
```

---

## The Core

### `core-plaza` — Meridian Plaza

- **Class:** safe. **Lean:** Wardens. **Size:** 90 × 40. **Sight:** 12.
- **Exits:** `spire-atrium` (steps); `core-tram-hub` (street);
  `core-precinct` (street); `sodium-row` (street, the Neon Stair);
  `terraces-blocks` (street); `vatside-clinics` (street, Sablier
  Boulevard).
- **Relays:** none.
- **Terminals:** four public Lattice terminals (Core sector).
- **Vendors / anchors:** Kestrel bank branch, general vendor
  (consumables, ammo), Warden recruiter, Civic Authority notice board
  (contract board), Descent console (Civic).
- **Spawners:** Wardens (guard, instant response), civilians (wander,
  talkers), courier drones.

The centre of the snow globe. Neon in every colour Kestrel can source
pigment for, a fountain that has run on the same recycled water for forty
years, and the tram bells. The Ring hangs over the plaza at night like a
chandelier somebody forgot to turn off, and the Wardens under it are
polite and armed and everywhere. This is where you come to be safe, to be
seen, and to log off. Nobody has died on Meridian Plaza in nineteen years.
The Marshal keeps count.

```
##############################
#>.$.......T.......T.....$.>#  top exits: spire steps / sablier blvd
#....%%..............%%.....#
#..........L..~~..L.........#
#...........~~~~............#
#....%%.....~~~~.....%%.....#
#..T....$..........$....T...#
#>.........>.........>.....>#  bottom: tram hub / precinct / neon stair / terraces
##############################
```

### `core-tram-hub` — Central Tram Hub

- **Class:** safe. **Lean:** Kestrel / Wardens. **Size:** 80 × 30.
  **Sight:** 12.
- **Exits:** `core-plaza` (street); trams to `tramyard-market`,
  `vatside-clinics`, `terraces-blocks`, `chapel-towers`, `sink-rim`
  (tram platforms; a tram departs every 90 seconds and the ride is a
  10-second transition).
- **Relays:** none.
- **Terminals:** two public terminals.
- **Vendors / anchors:** Kestrel ticket office (tram passes, courier
  service), Kestrel recruiter, a noodle counter (food consumables).
- **Spawners:** Wardens, Kestrel staff, commuters.

Five platforms under a vaulted roof that was the Site Zero rail
marshalling shed before there was a city. The trams are the same trams.
Kestrel repaints them every decade and the paint is the only thing that
changes. Departure bells, the Dispatcher's voice from speakers that were
never meant to carry a voice, and the smell of hot brakes and noodles.

```
################################
#..$.....T.....$.....T....$....#
#..............................#
#>>>>#>>>>#>>>>#>>>>#>>>>#.....#  platforms: market/clinics/terraces/chapel/sink
#..............................#
#..%%..........%%..........%%..#
######>>>>######################  > core-plaza
```

### `core-precinct` — Warden Precinct

- **Class:** safe. **Lean:** Wardens. **Size:** 50 × 24. **Sight:** 12.
- **Exits:** `core-plaza` (street).
- **Relays:** none.
- **Terminals:** one member terminal (Precinct core entrance, tier 3;
  hardware location here, in the evidence vault).
- **Vendors / anchors:** Warden quartermaster (kinetic weapons, light
  armour, restraints), Warden contract handler, Marshal Brann's office
  (story anchor), bounty desk (market board, bounties tab), holding
  cells.
- **Spawners:** Wardens (many).

Blue tile, bad lighting, good locks. The precinct is the oldest civic
building in Karst, and the Marshal's office is where the contractor town's
site superintendent sat. She kept his desk. Detainees are processed in a
room with a view of the plaza, so they can think about it. Wardens
recruit here, and they recruit people who have been in the holding cells
at least once, on the theory that it saves a step.

```
########################
#.$...........$....T..+#  + vault (hardware)
#.......%%.............#
#..######....######....#
#..#cell#....#cell#....#
#..######....######.$..#
###########>>###########  > core-plaza
```

---

## Vatside

### `vatside-wake-hall` — Wake Hall

- **Class:** pocket. **Lean:** Sablier. **Size:** 40 × 20. **Sight:** 10.
- **Exits:** `vatside-clinics` (door, the Wake door; opens after the
  tutorial or immediately for a returning character).
- **Relays:** none.
- **Terminals:** one tutorial terminal (Wake Hall cell, tier 0, one ICE).
- **Vendors / anchors:** Dr. Ilse Vantongeren (tutorial talker), the
  Wake corridor (one scripted hostile drone), the eight recruiter cards
  on a rack.
- **Spawners:** the tutorial drone only; Sablier orderlies (talkers).
- **Vats:** the decant vats (default respawn for Freelance and Sablier
  characters).

White light, warm plastic, a floor drain. You wake on a gurney under a
number and a woman with a clipboard says your number back to you and then
asks what you would like to be called instead. Along the wall, a rack of
cards from eight organisations who would like you to work for them. Past
the cards, a corridor with a drone in it. Past the drone, a terminal.
Past the terminal, a door that opens onto the city, and the city smells
of rain that never falls.

```
####################
#VVVV..............#
#VVVV..$...........#
#..........#########
#..........#.!.....#  ! tutorial drone
#....[cards]#......T#
####################+#  + Wake door to vatside-clinics
```

### `vatside-clinics` — Clinic Row

- **Class:** contested. **Lean:** Sablier. **Size:** 80 × 34.
  **Sight:** 12.
- **Exits:** `vatside-wake-hall` (door); `core-plaza` (street, Sablier
  Boulevard); `vatside-vat-row` (street); `core-tram-hub` (tram
  platform).
- **Relays:** **Cold Chain Relay** (controls Vatside's refrigeration
  grid; holders get a discount on surgery).
- **Terminals:** two public terminals; one Sablier-member terminal
  (Clinic core, tier 2).
- **Vendors / anchors:** Sablier main clinic (implant surgery, detox),
  Sablier recruiter, pharmacy vendor (meds, licensed drugs), Descent
  console (Sablier).
- **Spawners:** Sablier security (guard, slow), patients, one Warden
  patrol on a long loop.

Sablier's shop window. Clinics with their logo in cyan on white, a street
so clean that dirt looks like an accident, and the constant polite
overhead voice reminding you that your clone insurance premium is due.
People fight here, sometimes, in the alleys behind the clinics, and
Sablier security arrives afterwards to bill both parties for the repair.

```
################################
#>....$.....T........$.......>.#  top: wake hall / sablier blvd
#..######......######..######..#
#..#$...#..%%..#..$.#..#....#..#
#..######......######..######..#
#........R..............T......#
#>>>>..........................#  bottom-left: tram; right edge: vat row
##############################>#
```

### `vatside-vat-row` — Vat Row

- **Class:** contested. **Lean:** Sablier. **Size:** 90 × 36.
  **Sight:** 9.
- **Exits:** `vatside-clinics` (street); `terraces-blocks` (street);
  `under-service` (maintenance ladder behind the vat halls, unlocked).
- **Relays:** none.
- **Terminals:** one hardware terminal (Vat core, tier 3; its controls
  include the Sablier faction vat and the cold-storage doors).
- **Vendors / anchors:** black-clinic front door (Sable-run; surgery at
  60 %); Sablier vat technicians (talkers, gossip).
- **Spawners:** Sablier security, vat-hall drones, occasionally Sable
  runners (hunt behaviour toward Sablier members).
- **Vats:** the Sablier faction vat.

Where the bodies are made. Long halls of amber tanks, each with a number
and a heartbeat on a screen, and the sound of a thousand pumps. Sablier
does not advertise Vat Row and does not have to. Behind the third hall, a
door with no logo leads to a clinic that will install anything, and the
ladder behind that goes down to where the vats drain.

```
######################################
#>..........%%............%%........>#  left: clinics / right: terraces
#..#######....#######....#######.....#
#..#VVVVV#....#VVVVV#....#VVVVV#..T..#
#..#VVVVV#....#VVVVV#....#VVVVV#.....#
#..#######....#######....#######+....#  + black clinic
#..........................!.....>...#  > ladder down (under-service)
######################################
```

---

## Tramyard

### `tramyard-depots` — Ration Depots

- **Class:** contested. **Lean:** Kestrel. **Size:** 120 × 40.
  **Sight:** 10.
- **Exits:** `tramyard-market` (street); `tramyard-wall-gate` (street);
  `oldworks-main` (freight siding).
- **Relays:** **Depot Relay** (controls the ration distribution
  schedule; holders' faction vendors restock twice as fast).
- **Terminals:** one hardware terminal (Depot core, tier 3; controls the
  warehouse doors and the freight cranes).
- **Vendors / anchors:** Kestrel quartermaster (tools, drones, carrier
  frames), Kestrel contract handler (convoy contracts), impound office
  (evicted apartment contents).
- **Spawners:** Kestrel security, loader drones, freight crews,
  opportunist thieves (Sable-aligned, wander then hunt).

Warehouses the size of districts and the districts' food in them. The
depots run on a schedule the Dispatcher announces in a voice that never
changes pitch, and the cranes move to it like a slow dance. Guards here
are bored and well fed. Thieves here are hungry and fast, and the space
between the containers is where Karst's real politics gets decided,
one pallet at a time.

```
############################################
#>.....................................R...#  left: market
#..####..####..####..####..####..####......#
#..#..#..#..#..#..#..#..#..#..#..#..#..T...#
#..####..####..####..####..####..####......#
#.........%%........%%........%%.....$.....#
#>....................................$...>#  left: wall gate / right: old works siding
############################################
```

### `tramyard-market` — Tramyard Market

- **Class:** contested. **Lean:** Kestrel. **Size:** 80 × 36.
  **Sight:** 12.
- **Exits:** `tramyard-depots` (street); `core-tram-hub` (tram
  platform); `sink-rim` (street, the Long Stair down).
- **Relays:** none.
- **Terminals:** two public terminals (market board access).
- **Vendors / anchors:** the market: general goods, ammo, food,
  second-hand gear (rotating stock), Ferrymen salvage buyer (the one
  place inside the wall that pays for Ring-fall), Kestrel recruiter.
- **Spawners:** Kestrel security, market crowds, pickpocket NPCs
  (steal small chit amounts from players standing still too long; a
  Nerve check resists).

Every stall in Karst that could not afford a plaza frontage. Tarpaulin
roofs, shouted prices, a Ferrymen buyer with a set of scales and a
sawn-off, and the tram bells from the platform at the north end. The
market is the loudest place in the city and the only one where Halvard
and Sable can stand at adjacent stalls and both pretend not to notice.

```
################################
#>>>>...........................#  tram platform
#.$.$.$.$.$.$.$.$.$.$.$.$.$....#
#..............................#
#.%.$...$...$...$...$...$..%.T.#
#..............................#
#>.$.$.$.$.$.$.$.$.$.$.$.$...T.#  left: depots
###########################>####  > long stair to sink-rim
```

### `tramyard-wall-gate` — Gate Nine

- **Class:** contested. **Lean:** Kestrel. **Size:** 70 × 50.
  **Sight:** 11.
- **Exits:** `tramyard-depots` (street); `scour-ring-1` (the gate:
  opens on a Kestrel schedule every 5 minutes for 60 seconds, or on a
  Gate core control, or for a convoy).
- **Relays:** **Gate Relay Nine** (controls the gate schedule; holders
  open the gate on demand and tax non-members a toll in chits).
- **Terminals:** one hardware terminal (Gate core, tier 3).
- **Vendors / anchors:** Kestrel convoy master (escort contracts),
  Halvard checkpoint (searches for contraband on the way in; Halvard
  members exempt), Ferrymen guide (Scour passage, ring maps).
- **Spawners:** Kestrel security, Halvard checkpoint troops, convoy
  crews staging, and during Ring-fall, salvage runners heading out.

The wall is eleven metres of poured concrete and Ring-fall hull plate,
and Gate Nine is a hole in it with a schedule. Inside the gate, convoy
trucks idle in a yard that used to be a park. Outside, the Scour starts
immediately, as if the wall had been drawn with a ruler. The Dispatcher
counts the gate down over the yard speakers. People who want to leave
Karst stand here and watch the count and then do not.

```
######################
#>.......%%..........#  > depots
#....$........$......#
#.......R..T.........#
#..%%..........%%....#
#....[convoy yard]...#
#..!!..........!!....#  ! checkpoint barriers
######>>>>>>##########  > the gate to scour-ring-1
```

---

## The Sink

### `sink-rim` — The Rim

- **Class:** contested. **Lean:** Sable. **Size:** 100 × 30.
  **Sight:** 9.
- **Exits:** `tramyard-market` (the Long Stair); `core-tram-hub` (tram
  platform); `sink-terraces` (cable car, three stations along the rim;
  or a rope descent, hazard).
- **Relays:** **Cable Relay** (controls the cable cars; holders ride
  free and can stop the cars).
- **Terminals:** two public terminals (Sink sector; the Sink's public
  cells are unusually well connected to Old Works).
- **Vendors / anchors:** rim bars, a Sable enforcer post (talkers, the
  toll), fence (buys stolen goods, no questions), Sable recruiter.
- **Spawners:** Sable enforcers (guard, aggro on Warden and Kestrel
  members), rim crowds, Warden patrols that stop exactly at the top of
  the Long Stair.

A kilometre of edge. The Rim is the lip of the sinkhole, a street of bars
and cable-car stations built where the ground still holds, and below it
the terraces go down in the dark like the inside of a throat. Sable
enforcers lean on the railings and collect a toll from anyone who looks
like they can pay it. The Wardens come as far as the stair. The Ring
lights the whole hole at night, and the cable cars swing across it like
lanterns.

```
##################################
#>>>>...........>.........$......#  tram / long stair
#..$.....%%..........%%......$...#
#..........R.......T.............#
#.T..............................#
#>>####>>#######>>#######>>#######  > cable-car stations down
#!!####!!#######!!#######!!#######  ! rope descents
```

### `sink-terraces` — Sink Terraces

- **Class:** contested. **Lean:** Sable. **Size:** 90 × 60. **Sight:** 7.
- **Exits:** `sink-rim` (cable car up, three stations); `sink-floor`
  (stairs and ladders, several); `oldworks-yards` (a tunnel through the
  sinkhole wall, Sable-tolled).
- **Relays:** none.
- **Terminals:** three semi-public terminals (Sable-run; using one
  without Sable standing +0 costs a chit fee).
- **Vendors / anchors:** the black market (weapons, illegal drugs,
  unlicensed programs, stolen schematics), black clinic (second
  location), Sable contract handler, Sable's cable car (Tomasz Reyes's
  moving office; a story anchor that appears at a random station every
  few minutes).
- **Spawners:** Sable enforcers, terrace residents, rival gang NPCs
  (aggro on everyone including Sable, in the lower terraces), Marked
  players hiding out.
- **Vats:** the Sable faction vat, in a clinic that does not put its name
  on the door.

Shacks on shelves on shacks. The terraces were cut into the sinkhole wall
by people who had nowhere else, and the wall has been slowly deciding
whether to keep them. Cable cars stop where they stop. Every landing has
a bar, a clinic, or a stall that sells what the market upstairs will not,
and the light comes from strings of bulbs and from the Ring reflected in
the standing water at the bottom. Sable owns the Terraces the way weather
owns a hillside.

```
################################
#>>...$...%%.......$......>>...#  cable stations
#..####......####.......####...#
#....>...$.....%%.T.......$....#
#..####......####.......####...#
#.......%%...$..$....T.........#
#..####......####.......####.>.#  > tunnel to oldworks-yards
#......>.........>.........>...#  > stairs to floor
################################
```

### `sink-floor` — The Floor

- **Class:** contested. **Lean:** Sable. **Size:** 70 × 40. **Sight:** 5
  (Ring-light on water only).
- **Exits:** `sink-terraces` (stairs, ladders); `under-caverns` (the
  Sump: a drain gallery at the lowest point, unlocked, hazardous).
- **Relays:** **Sump Relay** (controls the pumps; holders keep the Floor
  drained; when neutral, water tiles spread over an hour).
- **Terminals:** one hardware terminal (Sump core, tier 2; controls the
  pumps and the drain gallery grate).
- **Vendors / anchors:** none regular. A Ferrymen smuggler who sometimes
  camps here (buys salvage, sells ring maps).
- **Spawners:** rival gang NPCs, feral things that come up the Sump,
  Sable enforcers only during Exhale.

The bottom of the hole. Ankle-deep water over a floor nobody has seen,
the sound of the pumps when the pumps are running, and the sound of the
water rising when they are not. Things come up the drain. The Sump grate
is the only door into the Undercity that nobody guards, because nobody
who wants it guarded can hold the Floor for long.

```
######################
#>.....>.....>.......#  stairs up
#..~~......%%........#
#.~~~~........~~.....#
#..~~..R...T.~~~~....#
#........%%...~~.....#
#...~~........!!!....#  ! sump grate
##############>#######  > under-caverns
```

---

## Chapel Ward

### `chapel-towers` — Cooling Towers

- **Class:** contested. **Lean:** Choir. **Size:** 80 × 40. **Sight:** 10.
- **Exits:** `core-tram-hub` (tram platform); `chapel-nave` (the great
  door); `terraces-blocks` (street); `under-service` (a tower's drain
  stair, unlocked).
- **Relays:** **Bell Relay** (controls the towers' resonance bells;
  holders' Cantors get +10 % hymn range in Chapel Ward).
- **Terminals:** two public terminals (Chapel sector; hidden cells are
  denser here than anywhere else).
- **Vendors / anchors:** Choir recruiter (a novice at the tower door),
  a Choir apothecary (resonance-tuned drugs, Listening aids), Descent
  console (Choir).
- **Spawners:** Choir wardens (guard, defensive only), pilgrims
  (wander, talkers), Halvard observers (talkers who hunt Choir members
  during Choir Surge).

Four cooling towers from the Site Zero power plant, each a hundred metres
tall, each with a bell in it that is not a bell. The Choir keeps the
ward swept. There is no neon here, only sodium lamps and candles, and the
towers hum on the same note the Atrium floor does, if you have the
implants to hear it. Pilgrims sit on the steps with their eyes closed.
Halvard sends people to watch the pilgrims. The pilgrims know.

```
################################
#>>>>.........$..........>.....#  tram / terraces
#...####........####...........#
#...#..#..%%....#..#......T....#
#...####........####...........#
#.......R.................L....#
#...####...T....####...........#
#...#..#........#..#...$..+....#  + great door to nave
#...####...>....####...........#  > drain stair to under-service
################################
```

### `chapel-nave` — The Nave

- **Class:** pocket. **Lean:** Choir. **Size:** 50 × 30. **Sight:** 8.
- **Exits:** `chapel-towers` (great door).
- **Relays:** none.
- **Terminals:** one member terminal (Choir core, tier 3; its hardware is
  the bell mechanism in the crypt; the core's descent cell goes deeper
  into the Silt than any other).
- **Vendors / anchors:** Mother Serafine Quell (story anchor, sermons),
  Choir contract handler, resonance implant surgeon (Cantors only).
- **Spawners:** Choir wardens, choristers (talkers).
- **Vats:** the Choir faction vat, in the crypt.

The inside of the tallest tower, hollowed out and hung with cables that
go up into the dark and down into the crypt. The Choir sings here at
hours nobody else keeps, and the singing is not for the people in the
room. Mother Quell speaks to the congregation from a chair with a
cable in the back of it. She says the Tenant is lonely. She says it
with such ordinary kindness that it is hard to remember she is talking
about the thing under the city.

```
##########################
#..........+.............#  + great door
#...%...........%........#
#.......[choristers].....#
#...%...........%..T.....#
#.........$..............#
#...######.....######....#
#...#crypt#..V.#..$.#....#  crypt: hardware + vat
##########################
```

---

## Old Works

### `oldworks-main` — Contractor Street

- **Class:** contested. **Lean:** Unmoored. **Size:** 110 × 34.
  **Sight:** 8.
- **Exits:** `tramyard-depots` (freight siding); `oldworks-yards`
  (street); `oldworks-drop` (a door that is not marked; found by
  Listening or told by an Unmoored member); `sodium-row` (street).
- **Relays:** **Relay Zero** (the first relay in Karst, the original
  network hub; holders get a Lattice-wide −10 % trace gain).
- **Terminals:** four public terminals with unusual reach (Old Works
  sector cells connect to every district's public cells); two of them
  are illegal Lattice taps (no trace in civic cells while used, until a
  Warden patrol notices the tap).
- **Vendors / anchors:** program dealer (attack, decoy, stealth
  programs), rig workshop (rig upgrades, slot expansions), Unmoored
  recruiter (a graffiti tag you have to interact with).
- **Spawners:** Unmoored runners (guard, aggro on Halvard and Wardens),
  squatters, Warden tap-hunting patrols, Halvard snatch squads during
  Exhale.

The contractor town, forty years on. Prefab housing built for a
five-year job, streets laid out by someone who expected them to be
torn up, and the whole thing still here with the paint gone and the
Unmoored's tags on everything. The tags are maps. Every third door has
a cable coming out of it. The Unmoored do not have a headquarters; they
have Contractor Street, and Contractor Street has the best Lattice
access in the city, and everyone who wants that access is, for as long
as they need it, an anarchist.

```
############################################
#>........T......%%..........T............>#  freight siding / sodium row
#..###..###..###..###..###..###..###..###..#
#..#.#..#$#..#.#..#.#..#$#..#.#..#.#..#.#..#
#..###..###..###..###..###..###..###..###..#
#......R........T..............T...........#
#..###..###..###..###..###..###..###..###..#
#..#.#..#.#..#+#..#.#..#.#..#.#..#$#..#.#..#  + the drop (unmarked)
#..###..###..###..###..###..###..###..###.>#  > yards
############################################
```

### `oldworks-yards` — Fabrication Yards

- **Class:** contested. **Lean:** Unmoored. **Size:** 100 × 50.
  **Sight:** 7.
- **Exits:** `oldworks-main` (street); `sink-terraces` (tunnel,
  Sable-tolled); `under-service` (a collapsed floor; a ladder, unlocked).
- **Relays:** **Yard Relay** (controls the yard power; holders'
  fabrication rolls +5 % quality).
- **Terminals:** one hardware terminal (Yard core, tier 2; controls the
  gantry and the yard lights).
- **Vendors / anchors:** the fabrication workshop (public workshop, the
  main one in the city), schematic trader (Unmoored), scrap dealer.
- **Spawners:** Unmoored runners, rogue fabrication drones (hunt; left
  running for forty years), scrap thieves, Sable enforcers at the
  tunnel mouth.

Where the city was made. Gantries, presses, a foundry that still holds
heat if you feed it, and the Unmoored's workshop in the middle of it,
running on power they stole from a grid that was never turned off. The
yard drones were never turned off either. Some of them still think they
are building something.

```
##########################################
#>..........%%.............%%...........>#  main / tunnel to sink
#..########..............########........#
#..#......#..[gantry]....#..$.$.#...R....#
#..#..!!..#..............#......#........#
#..########....T.........########........#
#............%%..........................#
#..!!!!......[foundry]...........$.......#
#..!!!!.............................>....#  > ladder to under-service
##########################################
```

### `oldworks-drop` — The Drop

- **Class:** pocket. **Lean:** Unmoored. **Size:** 40 × 20. **Sight:** 6.
- **Exits:** `oldworks-main` (the unmarked door).
- **Relays:** none.
- **Terminals:** one member terminal (Unmoored core, tier 3; the core is
  small, well defended, and hosts Ninety-Nine's dead drop cell).
- **Vendors / anchors:** Ninety-Nine (accessible via the terminal, not in
  the room), Unmoored contract handler, Unmoored quartermaster (energy
  weapons, light armour, stealth gear).
- **Spawners:** Unmoored runners only.
- **Vats:** the Unmoored faction vat (a stolen Sablier unit, patched).

A basement under a prefab, a room full of hardware nobody manufactures
any more, and a chair with straps on it that the Unmoored insist are for
comfort. This is where the collective keeps what it cannot afford to
lose: its own vat, its own core, and the drop that Ninety-Nine lives in.
The recording says hello when you jack in. It sounds pleased to have
company. It always sounds pleased to have company, and the Unmoored have
stopped finding that reassuring.

```
####################
#+.................#  + unmarked door
#...%%.....$.......#
#..........$...T...#
#...[the chair]....#
#..V...........%%..#
####################
```

---

## The Terraces

### `terraces-blocks` — Block Street

- **Class:** contested. **Lean:** neutral. **Size:** 120 × 40.
  **Sight:** 11.
- **Exits:** `core-plaza` (street); `core-tram-hub` (tram platform);
  `vatside-vat-row` (street); `chapel-towers` (street); `terraces-lobby`
  (apartment block doors, several: each door leads to the shared lobby
  zone, and from the lobby to the player's own apartment interior).
- **Relays:** **Block Relay** (controls the block power; holders' rent
  is −10 % and their apartments' private cores get +1 ICE slot).
- **Terminals:** three public terminals.
- **Vendors / anchors:** the letting office (rent, apartment upgrades),
  a corner grocer, a Warden outpost (slow response, 8 seconds, light
  force).
- **Spawners:** residents, the Warden outpost patrol, burglars (hunt
  toward players carrying valuable unsecured items, in the alleys
  only).

Apartment blocks with balconies with washing on them, which is the most
optimistic thing in Karst. The Terraces are where people who have made it
to grade five go to sleep behind a door they pay for. The Warden outpost
on the corner is two officers and a drone, and they take their time.
Between the blocks, alleys where the block lights do not reach.

```
############################################
#>>>>.............>...........>...........>#  tram / plaza / vat row / chapel
#..#####..#####..#####..#####..#####..$....#
#..#...#..#...#..#...#..#...#..#...#.......#
#..#..+#..#..+#..#..+#..#..+#..#..+#..T....#  + block doors to lobby
#..#####..#####..#####..#####..#####.......#
#......%%........R........%%......$...T....#
#..[alleys]................................#
############################################
```

### `terraces-lobby` — Residence Lobby

- **Class:** pocket. **Lean:** neutral. **Size:** 40 × 24. **Sight:** 10.
- **Exits:** `terraces-blocks` (street door); the player's apartment
  interior (a per-player instanced room: storage, safe, terminal, private
  core hardware; door opens only for the tenant and crew members the
  tenant admits).
- **Relays:** none.
- **Terminals:** one public terminal (market board, letting).
- **Vendors / anchors:** a concierge (talker; reports who came by), a
  lift that goes to a floor that is not on the panel (story anchor for
  a Terraces arc).
- **Spawners:** residents.

Every block shares a lobby, in the way that every apartment in the game
shares a floor plan. A concierge who remembers faces, a lift, a wall of
mailboxes, and a door with your name on it, which after ninety days as a
number is the whole point.

```
####################
#+.....$...........#  + street
#.....[lift].......#
#..%..........T....#
#...[mailboxes]....#
#..+..+..+..+..+...#  + apartment doors (instanced interiors)
####################
```

---

## Sodium Row

### `sodium-row` — Sodium Row

- **Class:** contested. **Lean:** neutral, Sable-enforced.
  **Size:** 100 × 30. **Sight:** 13 (sodium lamps everywhere).
- **Exits:** `core-plaza` (the Neon Stair); `oldworks-main` (street);
  `sodium-tin-halo` (the Halo's door); several bar interiors folded into
  the street map as alcoves.
- **Relays:** none, by agreement. The agreement is enforced by Sable
  enforcers who attack anyone who attacks anyone.
- **Terminals:** three public terminals.
- **Vendors / anchors:** bars (drinks: cheap consumables with a small
  shock reduction), a drug dealer (street drugs, unlicensed), a ticket
  tout (convoy passage, Scour rides), emote anchors (a stage, a card
  table).
- **Spawners:** Sable enforcers (guard, aggro on any attacker), crowds,
  Warden plainclothes (talkers, pickpocket detection), every faction's
  off-duty members (talkers, gossip).

The one street where everyone pretends. Orange lamps, wet pavement,
music from six doorways at once, and the unwritten rule that nobody
draws on Sodium Row, enforced by the people most likely to break it
anywhere else. Fixers work here. Deals get made in the doorways and
unmade in the alleys behind, and the Tin Halo's sign at the end of the
street has been half burnt out for so long that "Tin Hal" is what people
call it.

```
##################################
#>..........................>....#  neon stair / old works
#.$..$..[stage]..$..$..$.........#
#..%%......................%%....#
#.....T.........T.........T......#
#.$..$..$..[cards]..$..$..$......#
#.............................+..#  + the Tin Halo
##################################
```

### `sodium-tin-halo` — The Tin Halo

- **Class:** pocket. **Lean:** neutral. **Size:** 44 × 22. **Sight:** 8.
- **Exits:** `sodium-row` (door).
- **Relays:** none.
- **Terminals:** two public terminals (contract board, market board).
- **Vendors / anchors:** Vesper (fixer: contracts, rumours, the starter
  contract card's destination), the bar, a back room (crew invitations
  and bounty postings happen anywhere, but this is where the fiction
  says they do), a Ferrymen liaison who is sometimes in.
- **Spawners:** regulars (talkers), one bouncer.

The bar at the end of the street, with a halo of tin cans over the door
that a drunk welded up forty years ago and nobody has taken down.
Vesper sits at the end of the bar with three screens and a drink that
does not get lower. Everyone who wants work comes here and everyone who
wants someone found comes here, and Vesper charges both of them and is
fair about it. The regulars know things. The regulars will tell you
things. Some of the things are true.

```
######################
#+.................T.#  + street
#...[tables]...%.....#
#....................#
#..$.[bar].......$...#  Vesper at the end of the bar
#..............+.....#  + back room
######################
```

---

## The Undercity

### `under-service` — Service Level

- **Class:** open. **Lean:** none. **Size:** 120 × 50. **Sight:** 5
  (emergency lighting, mostly dead).
- **Exits:** `vatside-vat-row` (ladder up); `chapel-towers` (drain stair
  up); `oldworks-yards` (ladder up); `under-drowned` (a stair down, a
  flooded lift shaft down); `under-caverns` (a breach in the tunnel
  wall).
- **Relays:** none.
- **Terminals:** two orphan terminals (Undercity sector, a sector nobody
  maintains; low trace, strange cells).
- **Vendors / anchors:** an Unmoored dead drop (contract objectives), a
  Choir shrine (Listening aid consumable, free, one per day).
- **Spawners:** rogue maintenance drones (hunt), feral dogs (hunt in
  packs), Marked players, Sable smugglers (flee, carrying loot).

The city's plumbing. Service tunnels wide enough for a truck, pipes as
thick as a tram, and the emergency lights that were supposed to last a
year and lasted forty and are now mostly dead. Every district has a
ladder down here and nobody uses them by choice. The drones that maintain
the tunnels still maintain them. They maintain the tunnels of anything
they find in the tunnels, too.

```
############################################
#>.....#####.....>.......#####......>......#  ladders up: vat row / chapel / yards
#......#...#.............#...#.............#
#..%%..#...+.....T.......+...#....%%.......#
#......#####.............#####.............#
#..........!!!...........................T.#
#>........[flooded lift]...!!!.........>...#  > stair to drowned / > breach to caverns
############################################
```

### `under-drowned` — The Drowned Level

- **Class:** open. **Lean:** none. **Size:** 100 × 60. **Sight:** 4.
- **Exits:** `under-service` (stair up); `under-outworks` (a sealed
  bulkhead, opened by a Drowned core control or an Undercity key item);
  `under-caverns` (a siphon: swim, hazard).
- **Relays:** none.
- **Terminals:** one hardware terminal (Drowned core, tier 3; controls
  the bulkhead and the level's pumps; the core has been running unowned
  since the Severance and its ICE has changed).
- **Vendors / anchors:** none. A Ferrymen corpse with a map (one-time
  loot per character, story anchor).
- **Spawners:** things that live in the water (hunt from water tiles
  only), rogue drones, Choir pilgrims (talkers, going down).

A whole level of Site Zero's outer works, flooded to the waist in water
that has not moved since the Severance. Concrete corridors with numbers
on them, a lift shaft you can look down into and see lights, and a
bulkhead at the far end that says AUTHORISED in a font that predates
everyone alive. The pumps still hum somewhere. The core that runs them
has had forty years alone to think about visitors.

```
##########################################
#>.....~~~~~~.....%%......~~~~~..........#  stair up
#..~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~...#
#..~~~~~~..#####..~~~~~..#####..~~~~~....#
#..~~~~~~..#.T.#..~~~~~..#...#..~~~~~....#
#..~~~~~~..#####..~~~~~..#####..~~~~~....#
#..~~~~!!!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~..#  ! siphon to caverns
#..........................%%...........+#  + bulkhead to outworks
##########################################
```

### `under-caverns` — Karst Caverns

- **Class:** open. **Lean:** none. **Size:** 150 × 80. **Sight:** 3
  (5 with a light; some chambers are lit by phosphorescent growth, 8).
- **Exits:** `under-service` (breach); `sink-floor` (the Sump grate);
  `under-drowned` (siphon); `under-outworks` (a natural fissure that
  opens onto the outworks' collapsed side); `scour-ring-2` (a cave mouth
  outside the wall: the Ferrymen's way in, known only to them and to
  players who have found it).
- **Relays:** **Cavern Relay** (an Unmoored-built relay on a stolen
  generator; holders can see the cavern map; when neutral, the caverns
  are unmapped for everyone).
- **Terminals:** one orphan terminal on the relay.
- **Vendors / anchors:** a Ferrymen way-station (buys salvage, sells
  lights and water), a Choir pilgrim camp (talkers).
- **Spawners:** feral things (several species, hunt), blind swarms
  (hazard clouds that move), Ferrymen smugglers, Halvard survey teams
  (guard, aggro on everyone not Halvard).

The plateau is hollow. Under the service levels the natural caverns
begin, limestone galleries and sinkholes and rivers that go somewhere
nobody has followed, and Karst is a thin crust over all of it. The
Ferrymen use the caverns to get in and out under the wall. The Choir uses
them to get down. Things live here that were something else before the
Severance and are now adapted to the dark, and the map changes when the
water does.

```
##################################################
#>.......###.........................###.........#  breach
#..###...###...%%.......~~~~.........###..>......#  > sump grate (sink-floor)
#..###...........~~~~~~~~~~~~~~..................#
#........###.....~~~~[river]~~~~~~...###....R.T..#
#..!!!...###.........~~~~~~~~..~~~...###.........#
#..!!!.........###........................$......#
#..............###.....%%...........>.........>..#  > fissure to outworks / > cave mouth to scour-ring-2
#>....................[siphon]...................#  > siphon to drowned
##################################################
```

### `under-outworks` — Blacksite Outworks

- **Class:** open. **Lean:** none. **Size:** 120 × 70. **Sight:** 6
  (the outworks' own lighting is coming back on, section by section).
- **Exits:** `under-drowned` (bulkhead); `under-caverns` (fissure);
  `under-shaft-foot` (the outworks' inner door: an Undercity key item,
  consumed; or the Outworks core control during an Exhale).
- **Relays:** **Outworks Relay** (the deepest relay; holders' Descent
  contributions count +10 %; capturing it during an Exhale is a season
  contribution in itself).
- **Terminals:** one hardware terminal (Outworks core, tier 4; the
  first core in the game whose ICE includes a hunter by default; its
  descent cell reaches the Silt in one step).
- **Vendors / anchors:** none. Halvard survey markers (story anchors: the
  Halvard arc's evidence). A residual's cache (Lattice-only, via the
  terminal).
- **Spawners:** Blacksite maintenance drones (guard; a different, older
  model than the city's), things from below during Exhale (hunt, in
  numbers), Halvard survey teams, Unmoored crews, Choir pilgrims who
  went too far (talkers, dying).

The outer works of Site Zero. Corridors the size of streets, blast doors
on rails, signs in a numbering scheme that no surviving document
explains, and lights coming on. The lights were not on last year. The
Halvard survey teams leave markers with dates on them and the dates get
closer together. This is as far down as the city goes before it stops
being the city and starts being the thing the city was built on top of.

```
##########################################
#+.......%%...............%%.............#  + bulkhead (drowned)
#..#######......#######......#######.....#
#..#.....#......#..T..#......#.....#..R..#
#..#.....+......+.....+......+.....#.....#
#..#######......#######......#######.....#
#..........[blast door rail].............#
#>.......!!!!..............!!!!..........#  > fissure (caverns)
#..........................%%..........+.#  + inner door to shaft foot
##########################################
```

### `under-shaft-foot` — Shaft Foot

- **Class:** open. **Lean:** none. **Size:** 60 × 60. **Sight:** 10
  (the shaft is lit from above and below).
- **Exits:** `under-outworks` (inner door); `spire-shaft-head` (the
  Shaft: the cage lift, story-gated, finale arc only); `blacksite-l1`
  (the season door: opens when the Depth meter fills; crews of 3 to 5
  enter an instance).
- **Relays:** none.
- **Terminals:** one hardware terminal (Shaft core, tier 5; shared
  hardware with `spire-shaft-head`'s core: it is the same core with two
  hardware locations, the only such core in the game).
- **Vendors / anchors:** the season door (interact: shows the Depth
  meter and the season's Chronicle entry so far). A Choir shrine and a
  Halvard marker, side by side.
- **Spawners:** Blacksite maintenance drones (guard, many), and during
  Exhale, whatever the season's story arc says.

The bottom of the shaft the Spire was built to plug. A circular chamber
with the cage lift's cable hanging down the middle of it into a pool of
light from very far above, and a door in the floor. The door is the
size of a tram. It has no handle and no keypad and no ICE, and it opens
when it decides to, and every season it decides once. The Choir have
carved their nine-fold sign beside it. Halvard have painted over the
sign. The Choir have carved it again.

```
##############################
#+..........................#  + inner door (outworks)
#........%%......%%.........#
#......####......####.......#
#......#.[cable].....#......#
#......#....!!!.....#..T....#  ! cage lift (shaft up, story)
#......####......####.......#
#............>>>>...........#  > the season door (blacksite-l1)
##############################
```

---

## The Scour

### `scour-landing` — The Landing

- **Class:** pocket. **Lean:** Ferrymen. **Size:** 60 × 30. **Sight:** 12
  (open sky, Ring-light).
- **Exits:** `scour-ring-1` (the causeway); `scour-ring-2` (the Ferrymen
  road, a marked route that skips most of Ring One's patrols).
- **Relays:** none.
- **Terminals:** one Ferrymen terminal (Landing core, tier 2; the only
  Lattice access outside the wall; the Ferrymen keep it on a salvaged
  satellite ground-station dish that still points at nothing).
- **Vendors / anchors:** Anouk, the Ferry (story anchor, recruiter),
  Ferrymen quartermaster (Ring-fall weapons, lights, water, ring maps),
  Ferrymen contract handler (salvage contracts), a salvage buyer at full
  price, Descent console (Ferrymen), the fabrication tent (workshop).
- **Spawners:** Ferrymen (guard, aggro on Halvard and Kestrel members),
  dogs, salvage crews resting.
- **Vats:** the Ferrymen faction vat, inside a crashed orbital module.

A camp built out of things that fell. Hull plate walls, a dish as big as
a house pointed at the Ring, and Anouk's chair in the shade of a
re-entry shield with eleven names cut into it. The Landing is where the
Ferrymen count their salvage and their dead, and it is the only place
outside the wall where you can sit down without checking the sky first.
They will feed you. They will also remember what you owe.

```
##############################
#>..........................>#  causeway (ring 1) / ferrymen road (ring 2)
#....%%.......[dish]....%%..#
#..$....$.......T.......$...#
#.....[module]....V.........#
#..$........%%..........$...#
##############################
```

### `scour-ring-1` — Wall Ring

- **Class:** open. **Lean:** Kestrel / Halvard patrols. **Size:** 160 × 80.
  **Sight:** 12 by day, 7 by night (Ring-light).
- **Exits:** `tramyard-wall-gate` (the gate); `scour-landing`
  (causeway); `scour-ring-2` (the convoy road; several tracks).
- **Relays:** **Mile Relay** (a Kestrel road marker one mile out;
  holders' convoys are safe on the Wall Ring road; pays triple like all
  Scour relays).
- **Terminals:** none.
- **Vendors / anchors:** the convoy road (Convoy events run along it),
  a Halvard forward post (guard; not enterable), scrap of the first
  Ring-fall (a landmark).
- **Spawners:** Halvard patrols, Kestrel road crews, scavenger NPCs,
  dogs, Ring-fall salvage nodes (low grade: hull, optics).

The wall behind you and the ground in front scraped flat by forty years
of things coming down. The convoy road is the only line on it. Halvard
patrols the first mile, Kestrel maintains the road, and the salvage here
is picked over hull plate that the Ferrymen would not bend down for.
This is where people learn that outside the wall the sky is not
decoration.

```
############################################
#>>>>>>.....................................#  the gate
#......%%.......[road]..................R...#
#...........................%%..............#
#..[halvard post]...........................#
#.........!!......%%........!!.......%%.....#  ! craters
#.>..............................[road]....>#  causeway / convoy road to ring 2
############################################
```

### `scour-ring-2` — Beacon Ring

- **Class:** open. **Lean:** Ferrymen. **Size:** 180 × 90. **Sight:** 12
  by day, 6 by night.
- **Exits:** `scour-ring-1` (convoy road); `scour-landing` (Ferrymen
  road); `scour-ring-3` (the beacon line); `under-caverns` (cave mouth,
  hidden until found).
- **Relays:** **Beacon Relay** (a Ferrymen navigation beacon; holders see
  Ring-fall impact sites on the map five minutes early).
- **Terminals:** none.
- **Vendors / anchors:** a Ferrymen way-camp (water, lights), the
  beacon line (a row of salvaged lights the Ferrymen keep lit toward
  Ring Three), a crashed convoy (landmark, loot once per character).
- **Spawners:** Ferrymen salvage crews (neutral to most), wildlife
  (larger, faster than the dogs), scavenger gangs, Ring-fall salvage
  nodes (hull, optics, power).

The Ferrymen's ring. Their beacons run out toward the horizon in a line
that bends with the ground, and the camps along them are the closest
thing to hospitality the Scour offers. Ring-fall lands here often enough
that the crews do not look up when it does. They look at where it went.

```
##############################################
#>.........................................>.#  ring 1 / landing
#....%%.........L..........L..........L......#
#............%%......[beacon line]...........#
#..[crashed convoy]..........R...............#
#.......!!!.............%%............!!!....#
#..$........................................>#  > ring 3
#.....>......................................#  > cave mouth (hidden)
##############################################
```

### `scour-ring-3` — Crash Ring

- **Class:** open. **Lean:** none. **Size:** 200 × 100. **Sight:** 11 by
  day, 5 by night.
- **Exits:** `scour-ring-2` (beacon line); `scour-ring-4` (no road; a
  bearing).
- **Relays:** **Crash Relay** (built into the largest intact wreck;
  holders' salvage nodes in Ring Three yield +1 grade step; the most
  contested relay in the game).
- **Terminals:** none.
- **Vendors / anchors:** the wreck field (landmarks; several large
  wrecks with interiors, fabricated as sub-areas of the map), no camp.
- **Spawners:** wildlife (packs), scavenger gangs (hunt), Halvard
  recovery teams (guard, aggro on everyone, appear after Ring-fall),
  Ring-fall salvage nodes (power, compute).

Where the big pieces land. The Crash Ring is a field of wrecks, some the
size of buildings, some still warm, and the ground between them is glass
in places. Every faction wants what is in the wrecks and no faction can
hold the ring, so every Ring-fall here is a race and every race is a
fight. The Ferrymen's beacons stop at the edge. Past the edge, you steer
by the Ring.

```
##################################################
#>......%%..........[wreck]..........%%..........#  beacon line
#............!!!.....#####.....!!!...............#
#..[wreck]...........#.R.#..........[wreck]......#
#...####.............#####............####.......#
#...#..#......!!!!.................!!.#..#.......#
#...####...........[glass]............####.......#
#.............%%..................%%............>#  > bearing to ring 4
##################################################
```

### `scour-ring-4` — Far Ring

- **Class:** open. **Lean:** none. **Size:** 200 × 100. **Sight:** 10 by
  day, 4 by night (dust).
- **Exits:** `scour-ring-3` (bearing). Nothing beyond. The map's outer
  edge is the same in every direction: the ground keeps going and the
  zone does not.
- **Relays:** **Far Relay** (a Site Zero telemetry mast from before the
  city; holders can hear the Custodian's carrier on it; the Choir and
  Halvard both want it and neither can keep it).
- **Terminals:** one orphan terminal on the mast (the only terminal in
  the Scour besides the Landing's; its cells belong to no sector and
  drop into the Silt directly).
- **Vendors / anchors:** the mast (landmark), the season artifact sites
  (Ring-fall of intact grade lands here and nowhere else).
- **Spawners:** wildlife (apex), the Custodian's own drones (guard;
  Ring-fall recovery units that have been collecting salvage for forty
  years and are the reason the far ring's wrecks are so picked clean),
  Halvard long-range teams, Ferrymen who have gone strange.

As far as anyone goes. Dust, a telemetry mast older than the city, and
drones that were not built by anyone in Karst, collecting Ring-fall
with a patience nobody else has. The intact salvage lands out here,
still working, and the drones get to it first unless you are faster.
At night the Ring is so bright you can read by it, and there is nothing
to read but the mast's plate, which says SITE ZERO, TELEMETRY 4, and a
date.

```
##################################################
#>...............................................#  bearing (ring 3)
#.......!!.........%%..........!!................#
#..............[artifact site].........[mast]....#
#....%%...........................R..T...........#
#.................!!!!...........................#
#..[artifact site]......[drone lanes].....%%.....#
#..........................!!....................#
##################################################
```

---

## The Blacksite

### `blacksite-l1` — Blacksite Level One

- **Class:** instanced. **Lean:** none. **Size:** defined by the story
  arcs document.
- **Exits:** entered from `under-shaft-foot` (the season door) by a crew
  of 3 to 5 when the season's Depth meter fills; leaves the same way.
- **Relays / terminals / vendors:** defined by the story arcs document.
  One instanced sector accompanies the zone.
- **Spawners:** defined by the story arcs document.

Placeholder. The first level of the Blacksite is season content. Its
layout, encounter, and the choice at the end are specified in
`05-story-arcs.md` and built by the season slice, not by the base zone
content slice. It exists in this gazetteer so that exits, IDs, and the
asset manifest can reference it.

---

## Content notes

- **Trams** are zone transitions with a 10-second ride, not driveable
  objects. The Central Tram Hub is the only zone with platforms to more
  than one destination; district platforms go to the hub only.
- **Instanced interiors** (apartments, `blacksite-l1`) are zones whose
  instances are keyed by tenant or crew. They share the zone model.
- **Hidden exits** (`under-caverns` cave mouth, the Drop's door) are
  exits with a `hidden` flag revealed by a Listening check, a program, or
  an NPC's dialogue flag on the character.
- **Shared cores** (`spire-shaft-head` and `under-shaft-foot`) are one
  core with two hardware locations; cutting power at either affects
  both. This is the only such core and the content loader should assert
  it.
- **Scour sight** has a day and night value; the server's clock is the
  node's local time. Night is 20:00 to 06:00.

## Glossary

Glossary: merged into 07-glossary.md.
