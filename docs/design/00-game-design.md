# Blacksite — Game Design

This document defines the rules of the game: the systems, their numbers,
and how they connect. It is written for the people who will build the
slices in `docs/plan/slices/`, and every slice references the section it
implements. Numbers here are **initial values**; the balance slice tunes
them, but a slice must not change a number silently. Change it here, note
the change in the slice's PR, and keep the tests that validate it.

The setting is fixed in `docs/world/00-bible.md`. The technical entity
model that mirrors these rules is `docs/design/01-entities.md`.

---

## 1. Pillars

1. **Two layers, one world.** Meatspace (zones, streets, combat) and the
   Lattice (sectors, cores, ICE) are equally deep and constantly touch.
   Every core has a physical location; every important door has a core.
2. **Real time, readable.** The server ticks at 10 Hz. Nothing a player
   must react to happens faster than about a second, and everything that
   matters is announced in the log a beat before it lands. Terminal latency
   over Telnet or SSH is part of the design, not an obstacle to it.
3. **Zoned risk.** Where you stand tells you what can happen to you. Safe
   zones are safe. Contested districts are policed by faction relations
   and the Marked rule. Open zones are open.
4. **Persistence without permadeath.** Death costs time, chits, and
   unsecured inventory. It never costs the character.
5. **The crew is the unit.** Solo play is always possible; everything from
   hacking cover to relay capture to the Blacksite is tuned for crews of
   two to five.
6. **A small population is a feature.** A node has a handful of concurrent
   players. Systems are designed so that two players online at once have
   things to do together, and one player alone still has a city that moves.

## 2. Session shape

- A player enters the door from NetBBS, and the client connects to the
  node's running game service. If the character exists, they appear where
  they logged out (safe zones only; a character who logs out in a
  contested or open zone stays in the world as a **sleeper** for 60
  seconds, then is moved to the nearest safe zone with a clone-debt
  penalty if they were in combat).
- New players go through the Wake (section 4) in under five minutes.
- The NetBBS door session has a wall-time cap (currently one hour). The
  client warns at five minutes and one minute, exits cleanly about 5 s
  before the cap so the platform watchdog never kills it mid-frame, and
  re-entering the door resumes instantly because all state is on the
  server. See
  `docs/upstream/` for the request to lift the cap.
- Logging out from a safe zone is instant. From elsewhere it is the
  sleeper rule above.

## 3. Characters

### 3.1 Attributes

Five attributes, each 1 to 100. Starting values depend on archetype.
Attributes raise through **skill lines**, not directly.

| Attribute | Governs |
|---|---|
| Frame | melee and kinetic weapon handling, carry weight, armour use |
| Nerve | reflexes, evasion, stealth, drone control, energy weapons |
| Cortex | Lattice speed, program strength, trace resistance, crafting |
| Resonance | resonance implants (Cantor abilities), Tenant contact, ICE empathy |
| Vitals | health pool, shock resistance, implant tolerance, drug tolerance |

Derived values:

- **Health** = 50 + 2 × Vitals.
- **Stamina** = 30 + Nerve + Frame / 2. Sprinting drains 2 per sprint
  tile; melee costs 10 per swing; stamina regenerates 1 per tick (10 per
  second) when not sprinting.
- **Shock** = a 0 to 100 meter. Damage adds shock; shock above 80 slows
  actions; shock 100 is a knockdown. Decays 5 per second out of combat.
- **Tolerance** = Vitals / 10 implant points (round down, min 4). A
  Ghost's native rig occupies the rig slot at 0 tolerance.
- **Evasion** = Nerve / 3 plus cover. (Nerve / 2 made tier-1 fights last
  about 17 s against the 6–10 s pillar; see the catalog's balance notes.)
- **Carry** = Frame / 2 kg before movement slows; items carry weights in
  the catalog.

### 3.2 Archetypes

Starting attributes (Frame / Nerve / Cortex / Resonance / Vitals) and the
one thing each archetype can do that others cannot:

| Archetype | Start | Unique |
|---|---|---|
| Hardline | 40 / 20 / 15 / 5 / 40 | Heavy weapons and heavy armour; +2 tolerance |
| Ghost | 15 / 40 / 35 / 10 / 20 | Native rig (jack in anywhere); stealth stance |
| Cantor | 10 / 20 / 25 / 45 / 25 | Resonance implants; hymns (crew buffs), dissonance (nerve-jam attacks) |
| Operator | 20 / 30 / 30 / 5 / 30 | Two drone slots; contract and vendor price bonuses; crew beacon |

### 3.3 Skill lines

Skills are 0 to 100 and raise through use (Neocron-style: doing the thing
earns skill XP in that line) plus explicit spending of **grade points**
earned per character grade. Twelve lines:

Frame: *Kinetic*, *Melee*, *Armour*.
Nerve: *Energy*, *Stealth*, *Drones*.
Cortex: *Lattice*, *Programs*, *Fabrication*.
Resonance: *Hymns*, *Dissonance*, *Listening*.

Every 10 points across a line's attribute group raises the attribute by
1 (so a character who spreads across Kinetic, Melee, Armour raises Frame
fastest). Vitals raises only through **grade** (below) and implants.

### 3.4 Grades and personhood

Character **grade** is the level analog: 1 to 30, from cumulative XP.
Each grade grants 3 grade points and +1 Vitals. Grade names are flavour
(Wake, Ninety-Day, Resident, Citizen, Notable, Name, and beyond) and the
first real milestone is grade 5, **Ninety-Day**, when the character is
legally a person: they may rent an apartment, join a faction formally,
and are eligible for the Marked rule instead of being simply shot.

XP sources: combat (scaled by opponent grade), successful runs (scaled by
core tier), contracts, relay captures and holds, crafting, discovery
(first visit to a zone or cell), and season contributions.

## 4. The Wake (onboarding)

The Wake is the tutorial and takes place in the Wake Hall, a safe pocket
in Vatside. It must be completable in five minutes and skippable by a
returning player who deletes a character.

1. Open your eyes. Choose archetype (four cards with one paragraph each).
2. Choose a name (the BBS handle is the default and always shown).
   Names are 2 to 24 display columns of letters, digits, spaces,
   hyphens, underscores, and apostrophes, unique per node
   (case-insensitive). One character per BBS user per node by default;
   the cap is a world setting the SysOp can raise.
3. Dr. Vantongeren's briefing: three screens, one choice (which faction's
   recruiter's card to take, or none). The choice sets initial standing,
   not membership.
4. Walk to the door: movement keys, look, interact.
5. The corridor: one hostile drone. Targeting, fire, cooldown, the log.
6. The terminal: jack in, one cell, one weak ICE, jack out. The door opens.
7. Out into Vatside with 200 chits, a starter weapon, a med patch, and a
   contract card for Vesper at the Tin Halo.

## 5. Meatspace

### 5.1 Zones and tiles

- The city is a graph of **zones**. Each zone is a tile map (width 40 to
  200, height 20 to 100) authored as a text file with a legend, plus
  metadata: name, district, safety class, faction lean, exits, spawners,
  relays, terminals, lights.
- Tiles have a glyph, colours per capability tier, passability, cover
  value (0 to 3), and an optional interaction.
- **Safety class**: `safe` (no player attacks; Wardens instant), `pocket`
  (safe area inside a contested zone), `contested` (faction rules and
  Marked), `open` (anything).
- Zones are loaded from content files at server start and hot-reloadable
  by the admin CLI (empty zones only).

### 5.2 Movement and sight

- One tile per 200 ms walking, 100 ms sprinting (stamina). Diagonals cost
  the same. Movement is server-authoritative; the client predicts nothing.
- Sight is line of sight with a radius per zone lighting (Core: 12 tiles;
  Undercity: 5 unless you carry a light). Stealth stance halves the range
  at which others see you.
- Players in the same zone see each other's glyph, name (on target or
  hover), and faction colour.

### 5.3 Combat

Real time, cooldown-based, server-resolved.

- **Target** the nearest hostile or cycle. Fire with one key. A weapon has
  range, base damage, cooldown (0.5 to 3.0 s), accuracy, ammo type, and
  damage type (kinetic, energy, chemical, dissonance).
- **To hit** = accuracy + skill / 2 − target evasion − cover × 10 − range
  penalty (5 per tile beyond half the weapon's range). Rolled per shot;
  the roll and the reasons are visible in the combat log on request.
- Shock decay starts 3 s after the last hit. A knockdown at shock 100
  lasts 2 s and resets shock to 60.
- **Damage** = base × (1 + skill / 200) − armour vs type. Adds shock equal
  to damage / 2.
- **Melee** costs stamina, ignores half of armour, and has a 1.0 s
  cooldown.
- **Cover** is a tile property. Standing adjacent to a cover tile with the
  attacker on the other side applies it.
- **Consumables** (med patches, stims) are instant with a 10 s cooldown
  per class.
- **Hymns and dissonance** are Cantor abilities with the same cooldown
  model; hymns affect crew members within 6 tiles.
- **Drones** are Operator-controlled actors with their own position,
  health, and one weapon or tool; they follow or hold.

### 5.4 Death and clones

- Health 0 is **down**: five seconds during which a crew member can pick
  you up. Then **dead**.
- Dead characters wake in the nearest Sablier vat (Vatside, or a faction
  vat if a member) after a 20 s decant timer.
- **Clone debt**: 5 % of chits on hand (not banked) plus a fixed fee of
  grade × 10 chits, and a **fade** of 2 % of the XP toward the next
  grade. Debt that cannot be paid from hand is owed to Sablier and
  deducted from the next chits earned.
- **Corpse cache**: in contested and open zones, all *unsecured* inventory
  drops in a cache at the death tile for five minutes. **Secured** slots
  (three by default, more with implants) never drop. In safe zones nothing
  drops. Killers loot freely; others must wait 60 s.

### 5.5 NPCs

Non-player actors run **behaviours**: idle, wander, patrol (waypoints),
guard (hold, aggro on hostile), hunt (chase), flee (below 20 % health),
vendor, talker. Aggro rules use the faction relations matrix; a Halvard
patrol shoots Unmoored members in the Scour and ignores Kestrel.
Freelance characters are treated as neutral by every NPC in contested
zones and as hostile by every faction NPC in open zones with no faction
lean. A hunting NPC gives up 20 s after losing sight; wander pauses last
200 to 1000 ms; NPCs in a zone that has been dormant for 30 minutes are
despawned and respawn from their spawners on wake. Wardens in safe zones
respond to any attack within 2 seconds with escalating force and a
Warden **heat** on the attacker that persists for 10 minutes.

### 5.6 Interactions

The interact key on an adjacent object: doors (open, locked, hackable),
terminals (jack in), vendors, vats, relays, caches, tram stops, apartment
doors, ladders and lifts (zone exits), lights. Zone transitions take
time during which the actor is absent from both zones: street exits are
instant, ladders and lifts 1 s, cable cars 3 s, trams 10 s (hub and
spoke: every district platform goes to the Core tram hub only).

## 6. The Lattice

### 6.1 Sectors and cells

- A **sector** is a graph of **cells** rendered as a grid (see the terminal
  UI document). Cells have a type: public, gated (needs a key or a program),
  hidden (found by a Listening check or a program), core entrance, and
  Silt descent.
- Moving between adjacent cells takes 1.0 s minus Cortex / 100 s.
  Lifting data or flipping a control takes 3 s. Integrity recovers 5 per
  second after jacking out.
- A runner in the Lattice is a **presence** with its own health analog,
  **integrity** (100), and a **trace** meter (0 to 100). Integrity 0 means
  forced jack-out with shock 100 and, if black ICE did it, real damage.
- Runners see each other in the same cell or core room and can attack
  each other with programs (**burning**). Burning a runner in a civic
  sector raises your trace.

### 6.2 Cores

A core is a small graph of **rooms** (3 to 12) behind an entrance cell.
Rooms hold **data** (loot: chits, salvage data, contract objectives, season
contributions), **controls** (mapped to meatspace objects), and **ICE**.
Cores have a **tier** 1 to 5. Every core has a physical **hardware
location** in a zone.

### 6.3 ICE and programs

- The runner's **rig** has slots (3 to 7) for **programs**: attack
  (damage ICE integrity), shield (absorb), decoy (reduce trace gain),
  loader (speed), key (open gated cells), stealth (delay ICE activation),
  and utility (map, lift data).
- ICE has integrity, an attack, a trigger (on entry, on data touch, on
  trace threshold), and a class. Classes and the full bestiary are in
  `docs/world/03-lattice.md`. Black ICE deals meatspace damage on each
  hit.
- Encounters are real time with the same cooldown model as meatspace:
  programs have a cast time (0.5 to 2 s) and cooldown. Trace rises per
  second in a core (by tier) and per hostile action.
- At trace 100: civic sector, Wardens are dispatched to your body's
  location; corporate core, a **hunter** ICE spawns and follows you across
  cells; black core, the core's owner faction is told exactly where you
  are.

### 6.4 Interlock rules

- Each control in a core maps to one object in one zone. Flipping it
  changes the object immediately and posts to the zone log ("The gate
  cycles open. Nobody touched it.").
- Controls reset on a per-core timer (5 to 30 minutes) unless the core is
  **owned** by a faction that holds the relay above it.
- A crew member who reaches a core's hardware in meatspace can **cut
  power**: every runner inside is jacked out with shock 100 and the core
  is offline for 10 minutes. This is the main defence against hostile
  runners and the main reason to bring a Hardline.
- Private cores (apartments) can be hacked: the runner sees the resident's
  storage manifest and can lift *one* unsecured item per successful run,
  once per day per apartment. The resident is told. This is the game's
  only theft-from-offline-players mechanic and is deliberately narrow.

### 6.5 The Silt

Descent cells exist at the bottom of each sector. The Silt is procedurally
generated per descent from a seeded graph, deep, and populated by ICE that
does not belong to anyone and by **residuals** (fragments of past runners,
one of which is Ninety-Nine). Season contributions and Choir story arcs
live here. A runner in the Silt cannot be traced but cannot be found by a
crew either.

## 7. Factions

### 7.1 Membership and standing

- **Standing** with each faction is −100 to +100, starting at the values
  set by the Wake recruiter choice (+10 with one faction, 0 elsewhere).
- Contracts, kills, and relay actions move standing with the relevant
  factions and their allies and enemies (halved).
- At standing +30 and grade 5 a player may **join** a faction through its
  recruiter. One faction at a time. Leaving costs −50 with the former
  faction and a 7-day cooldown before joining another.
- Members get: faction chat, faction vats, faction vendors, faction
  contracts, the right to capture relays, and the faction's colour.
- Ranks at standing +30, +50, +70, +90 carry titles and, at +90, one
  mechanical perk per faction. Titles and perks are defined in
  `docs/world/02-factions.md` and implemented by the factions slice; a
  perk must never be a flat combat multiplier.

### 7.2 Relations matrix

`H` hostile, `N` neutral, `A` allied. Rows are the acting faction.

|  | Halvard | Sablier | Kestrel | Wardens | Choir | Sable | Unmoored | Ferrymen |
|---|---|---|---|---|---|---|---|---|
| Halvard | — | A | A | N | H | H | H | H |
| Sablier | A | — | N | N | N | N | H | N |
| Kestrel | A | N | — | A | N | H | N | H |
| Wardens | N | N | A | — | N | H | H | N |
| Choir | H | N | N | N | — | N | A | A |
| Sable | H | N | H | H | N | — | H | N |
| Unmoored | H | H | N | H | A | H | — | N |
| Ferrymen | H | N | H | N | A | N | N | — |

The matrix is symmetric by construction except where the story wants a
one-sided grudge; the data file is the truth and a test asserts the
intended asymmetries. A season definition may carry a **relations
override** (a list of pairs with a replacement value) that applies while
that season is active; the story arcs use this to let the world's
alliances shift with the plot without editing the base matrix.

### 7.3 Marked

In a contested zone, attacking a player whose faction is not **hostile**
to yours (or any Freelance, or any character below grade 5) makes you
**Marked** for 15 minutes: any player may attack you anywhere outside a
safe zone without becoming Marked themselves, Wardens engage you on sight
in contested zones, and your name shows red. Killing a Marked player gives
standing with the Wardens. In open zones nothing marks anyone.

### 7.4 Relays and territory

- A relay is an object in a contested or open zone with a **control
  terminal** and a **core**. To capture: a member of a faction must hold
  the terminal (stand adjacent and interact) for 3 minutes, *and* the
  relay's core must be hacked open by a runner during that window, *or*
  the capturing crew must hold it for 8 minutes without a runner.
- A held relay pays the holding faction **influence** per hour (the
  season leaderboard score) and grants members a zone buff and access to
  the relay's vendor.
- Relays cannot be captured during a Curfew event. Scour relays pay
  triple.

## 8. Economy

### 8.1 Chits

Chits are integers. Sources: contracts, core data, salvage sales, vendor
sales, relay income (faction treasury pays members a share). Sinks: gear,
implants and surgery, rent, ammo, drugs, clone debt, fabrication.
Banked chits (at a Kestrel branch or an apartment safe) are never lost to
death.

### 8.2 Vendors

Every faction hall and district has vendors with fixed inventories,
prices modified by standing (−20 % at +80, +30 % at −50), and a limited
buy-back budget that refills hourly (so selling 40 rifles to one vendor
does not work).

### 8.3 Market board

A player-to-player asynchronous market (listing, bid, buyout) with a 5 %
Kestrel fee, browsable from any terminal. Listings run 24 hours, 72
hours, or 7 days; bids are escrowed from the bidder's bank; a bought
item is delivered to the buyer's Kestrel impound (free to collect at any
Kestrel branch). Also hosts **bounties**: a player posts at least 100
chits on a name; whoever kills the target in a contested or open zone
collects. Bounties on players below grade 5 are refused.

### 8.4 Salvage and fabrication

- Ring-fall spawns **salvage** nodes in the Scour. Salvage has a grade
  (hull, optics, power, compute, intact) and a weight.
- **Fabrication** at a workshop turns salvage plus a **schematic** into an
  item. Schematics are found in cores, bought from Ferrymen, or granted by
  factions. Fabrication skill sets quality (a ±15 % stat roll).
- Intact salvage is the season-contribution currency of the Custodian
  arc.

### 8.5 Implants and surgery

- Implants occupy **tolerance** points and a slot (head, eyes, spine,
  arms, torso, legs, rig). A character has at most one implant per slot
  except arms (two).
- Sablier clinics install at list price with a 2 % failure chance (item
  lost, 30 s of shock). Black clinics in the Sink install at 60 % price
  with 15 % failure and no questions.
- Resonance implants require Cantor archetype and a Choir standing of
  +20.

### 8.6 Drugs

Each substance has an effect, a duration, a **crash** (opposite effect
for half the duration), and an addiction clock: three doses inside its
window creates a dependency that imposes the crash permanently until a
Sablier detox (chits and 10 minutes offline-safe).

### 8.7 Apartments

Rented in the Terraces per week of real time in chits, paid from the bank
automatically. Contains storage (40 slots), a safe (banked chits), a
terminal, and a private core (tier 1, upgradeable to 3). Rent lapse of
two weeks evicts and moves everything to a Kestrel impound (fee to
reclaim).

## 9. Contracts

- **NPC contracts** come from faction handlers and from Vesper. Types:
  fetch (bring item from zone), hack (lift data from core), escort (walk
  an NPC between zones), clear (kill N of type in zone), plant (place item
  in a core's room), survey (visit cells or tiles). Rewards: chits,
  standing, items, XP.
- Contracts are generated from templates with parameters, so the content
  slice ships templates and a handful of hand-written **story contracts**
  per faction that advance the season arc.
- **Crew contracts** scale objectives and rewards with crew size.
- A contract board exists at every faction hall and at the Tin Halo.

## 10. Crews

- A crew is 2 to 5 players. Invite, accept, leave, kick by leader.
- Crew chat, crew list in the side panel with health and zone, a
  **beacon** (Operator) that shows a crew member's position across zones.
- Loot: corpse caches and core data are free-for-all by default; the
  leader can set round-robin.
- XP from a kill or a run is shared across crew members in the zone or
  sector (full XP each if within 5 grades of each other; scaled otherwise).

## 11. Social layer

- **Say** (zone, 20-tile radius), **shout** (zone), **whisper** (player,
  anywhere), **faction**, **crew**, and **system** channels, colour coded.
- Emotes: `/me <text>` free-form in the zone channel, plus a fixed list
  with optional targets: wave, nod, shrug, salute, point, laugh, sigh,
  bow, glare, spit. Emotes are rate-limited with chat.
- The client keeps a 500-line log ring; on reconnect the server replays
  the last 50 lines the session could see.
- **Sitrep**: who is online, where (zone only, not tile), in which
  faction, and whether jacked in. Players can hide their zone at the cost
  of not seeing others' zones.
- **Ignore** and **report**, the latter written to the admin log.
- The BBS handle is always visible next to the character name in sitrep
  and whisper; the character name is what the world uses.

## 12. World events

Events are scheduled by the server's event engine with weights and
cooldowns, and can be forced by the admin CLI.

| Event | Where | Duration | Cooldown / weight | Effect |
|---|---|---|---|---|
| Ring-fall | one Scour ring | 20 min | 90 min / 5 | salvage nodes spawn, Ferrymen and Halvard NPC crews converge, meteor tiles are hazards |
| Curfew | the Core | 60 min | 4 h / 2 | Core sealed; relays uncapturable; Warden heat doubles outside |
| Choir Surge | all sectors | 15 min | 3 h / 2 | ICE mutates (random class swap), Cantor abilities +30 %, Silt map revealed |
| Exhale | Undercity | 30 min | 2 h / 3 | spawn rate ×3, new Undercity keys drop, Blacksite door cells appear |
| Convoy | Scour route | 25 min | 60 min / 4 | escort/raid contract auto-posted to all factions; the convoy is an NPC crew following a route from `routes.json` |

At most two events run at once and never two in the same zone. The
engine picks by weight among events off cooldown, at a base rate of one
attempt per 20 minutes.

## 13. Seasons and the Descent

- **Depth meter** 0 to 100 000 per season, fed by contributions delivered
  to any faction hall's **Descent console**: core data tagged as
  contribution (250 each), intact salvage (500), Undercity keys (1 000).
  The weights are per-season data and may differ by season.
- The contributor's faction is credited. The **season leaderboard** ranks
  factions by influence (relays) and depth (contributions), and players
  by grade, kills, runs, and contributions.
- At 100 000 the season's **Blacksite level** opens: an instanced zone
  plus an instanced sector for crews of 3 to 5, with a hand-authored
  layout, a scripted encounter, and a **choice** at the end that is
  recorded in the Chronicle. The level stays open until the season ends.
  At most 4 instances run at once; an empty instance is torn down after
  10 minutes. A finale choice may set **season flags** (named booleans
  in world meta) that other subsystems read, and may unlock a zone
  defined in that season's content (the gazetteer lists only the
  permanent city).
- The Chronicle is a read-only in-game document appended by the server
  with the season's outcome and a template paragraph per choice.
- Season end: leaderboards freeze and are kept; relays reset to neutral;
  standing, grade, gear, apartments persist; the Custodian/Tenant balance
  moves one step in the direction of the finale choice.

## 14. Anti-abuse and fairness

- Everything is server-authoritative; the client sends keys and commands,
  never state.
- Rate limits: 20 inputs per second per session, 4 chat lines per 5
  seconds, one market action per second.
- Alt characters: one character per BBS user per node. A SysOp may raise
  that.
- Camping: a vat area is a safe pocket; a Warden precinct is a safe pocket.
- Griefing of new players: the grade-5 rule, no bounties below grade 5,
  and Wake Hall as a safe pocket.
- The admin CLI can mute, kick, ban (by BBS user id), teleport, and
  refund.

## 15. Accessibility and terminal tiers

- Minimum: ANSI colour and cursor addressing at 80 × 24, UTF-8.
- Tiers: truecolor, 256 colour, 16 colour. Every colour in the palette has
  a value per tier. A colour-blind palette variant exists for the two most
  common deficiencies (swaps faction hue assignments; no information is
  colour-only, every state also has a glyph or a label).
- Larger terminals get a larger viewport and more log lines; the layout
  is computed, not hard-coded.
- No plain mode. The door refuses to start with a clear message if the
  terminal is smaller than 80 × 24.

## 16. What is deliberately out of scope for v1

- Cross-node play (designed for, not built; see the architecture
  document).
- Player-run factions or guilds beyond crews.
- Vehicles as driveable objects (trams are zone exits; convoys are NPCs).
- Voice, images, or sound.
- A web client of its own (NetBBS's web door mode carries the terminal).
