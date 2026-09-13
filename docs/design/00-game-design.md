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
   two to five, with a sequential route for a lone resident, including
   seasonal finales. Archetype changes efficiency, never story access.
6. **A small population is a feature.** A node has a handful of concurrent
   players. Systems are designed so that two players online at once have
   things to do together, and one player alone still has a city that moves.
7. **Scarcity has an address.** Jobs change a named service, route, or
   relationship. The player sees who benefits and what capacity is given
   up. There is no city survival meter or offline hunger damage.
8. **Mystery with usable evidence.** Records reveal actionable facts and
   competing explanations. The action UI tells the truth about rules;
   fictional witnesses need not agree about motives.

### 1.1 Repeat-play contract

A short session contains a complete job: inspect district conditions,
choose a loadout and approach, commit in the field, recover, and see a
consequence. Target 10–20 minutes for a generated job and 20–35 minutes
for a prepared finale. These are playtest targets, not expiry timers.
Reading is optional; every objective has a short operational summary,
and found texts remain available in the journal after danger.

Challenge combines visible patrol routes, trace, equipment slots, body
exposure, and control windows. Templates vary these within validated
bounds. Never hide a required command in prose or reroll a critical fact
because a menu was reopened.

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
- **Evasion** = Nerve / 3 plus equipment modifiers. Cover is subtracted
  separately in §5.3 and must not be counted twice.
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
first milestone is grade 5, **Ninety-Day**: completed work earns early
discharge of the Wake lease. Personhood arrives at the earlier of grade
5 or 90 elapsed real days from first decant. Set `legal_at` once; debt,
death, leaving a faction, and season changes cannot remove it. Renting
requires personhood; joining also requires standing +30. PvP protections
depend on grade, independently of personhood (§7.3). Show elapsed lease
days and the early-discharge XP target separately. NPC day-count lines
use actual elapsed days, never a fixed day selected only by grade.

Grade 1 starts at 0 XP. For n = 2..30 the cumulative threshold is
100 × n × (n + 1) / 2 (grade 5: 1 500; grade 10: 5 500; grade 30:
46 500). Award 3 points and +1 Vitals on each grade gained, not creation.
Fade cannot reduce a grade or its already-earned benefits.

XP sources: combat (scaled by opponent grade), successful runs (scaled by
core tier), contracts, relay captures and holds, crafting, discovery
(first visit to a zone or cell), and season contributions.

### 3.5 Earning schedule and repetition limits

All rewards carry receipts. Combat XP is max(5, floor(20 * (1 +
(opponent grade - own grade)/10))) for an eligible defeated opponent;
one reward per NPC spawn, at most one per opposing BBS identity per
24 h. No XP for self/crew damage or a failed nonlethal mission kill.
A successful core run pays 40 * tier on its first data lift per core
per BBS identity per UTC day. Relay capture is section 7.4; an active
participating member earns 10 hold XP per completed 10 min, at most
60 per identity per UTC day across relays. Crafting pays 15 * item tier
on successful fabrication using consumed inputs. Zone discovery pays
25 and authored cell discovery 5 once per character; generated Silt
cells do not create infinite discovery XP. Contribution pays 25 once
per unique source receipt. Contract XP is its disclosed reward.

| Meaningful use | Skill gain |
|---|---|
| weapon hit / melee hit on eligible threat | +0.2 / +0.3 to its line |
| eligible hostile damage absorbed with armour | +0.1 Armour |
| stealth with a live hostile in sight | +0.05/s Stealth, at most 1 per encounter |
| drone command changing an objective or damaging a threat | +0.1 Drones |
| first visit to an authored cell | +0.05 Lattice |
| successful program with a new target/state change | +0.15 Programs |
| completed fabrication consuming inputs | +1 Fabrication |
| hymn restoring a real deficit / dissonance affecting a threat | +0.15 in that line |
| first hidden-cell discovery in an authored sector | +0.5 Listening |

Each skill caps at 100; use gains cap at 2 points per line per UTC day,
independent of grade-point spending (1 point buys 1 skill point).
Repeat casts on an unchanged state, movement loops, training sessions
and repeated signal samples give no gain. An encounter ends after
60 s without a hostile interaction; splitting it cannot bypass the
per-line daily cap. These are initial balance values, subject to the
human earning-curve checks in section 18, not measured progression speed.

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

The full starter kit is in §17. All archetypes receive Pick and
Umbrella. Public terminals supply a three-slot loan rig while connected;
a carried portable rig upgrades its slots. Ghosts keep a rig anywhere.
The tutorial drone and ICE are private training actors: cannot kill,
create debt, drop loot, or affect another caller. Briefing progress is
resumable; reading every screen is not required. The first job teaches
the route choice in §9.4 and explicitly labels the Terraces contested.

## 5. Meatspace

Safe/pocket areas reject hostile damage, hazards, abduction, and forced
movement. Player-caused controls, drones, splash, and damage-over-time
obey the same invariant. Guards are presentation, not the safety check.
A runner may explicitly enter dangerous NPC cores from a safe body
location after a black-ICE warning. That permits the core's NPC feedback
only, never PvP. Tutorial simulation is the bounded exception in §4.


### 5.1 Zones and tiles

- The city is a graph of **zones**. Each zone is a tile map (width 40 to
  200, height 20 to 100) authored as a text file with a legend, plus
  metadata: name, district, safety class, faction lean, exits, spawners,
  relays, terminals, lights.
- Tiles have a glyph, colours per capability tier, passability, cover
  value (0 to 3), and an optional interaction.
- **Safety class**: `safe` (hostile harm blocked by the server), `pocket`
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
- Clamp hit probability to 5-95 % and damage to at least 1 after armour.
  Cooldown starts on cast completion. Durations round up to the next
  100 ms tick. Fast repeat attacks are allowed, but new threats and
  hazardous state changes get at least 2 s warning with a safe response.
- Shock decay starts 3 s after the last hit. A knockdown at shock 100
  lasts 2 s and resets shock to 60.
- **Damage** = base × (1 + skill / 200) − armour vs type. Adds shock equal
  to damage / 2.
- **Melee** costs the weapon's listed stamina, ignores half of armour, and has a 1.0 s
  cooldown.
- **Cover** is a tile property. Standing adjacent to a cover tile with the
  attacker on the other side applies it.
- **Consumables** (med patches, stims) are instant with a 10 s cooldown
  per class.
- **Hymns and dissonance** are Cantor abilities with the same cooldown
  model; hymns affect crew members within 6 tiles.
- **Drones** are Operator-controlled actors with their own position,
  health, and one weapon or tool; they follow or hold.

For `clear` objectives with `resolution: subdue`, a supplied restraint
action channels for 3 s against an adjacent NPC at shock 80 or higher.
Completion removes that mission NPC from combat as restrained, not dead;
no kill XP. The card labels the target and permitted equipment. Lethal
damage fails the objective. This never permits player imprisonment.

### 5.4 Death and clones

- Health 0 is **down**: five seconds during which a crew member can pick
  you up. Then **dead**.
- Dead characters wake in the nearest Sablier vat (Vatside, or a faction
  vat if a member) after a 20 s decant timer.
- **Clone debt**: 5 % of chits on hand (not banked) plus a fixed fee of
  grade × 10 chits, and a **fade** of 2 % of the XP toward the next
  grade. Debt that cannot be paid from hand is owed to Sablier and
  deducted at 25 % of subsequent chit awards, rounded down, until paid.
  Refunds, transfers, and market principal are not earnings.
- **Corpse cache**: in contested and open zones, all *unsecured* inventory
  drops in a cache at the death tile for five minutes. **Secured** slots
  (three by default, more with implants) never drop. In safe zones nothing
  drops. Killers loot freely; others must wait 60 s.

The victim may recover their cache immediately. Equipped weapons and
armour drop unless secured; installed implants and learned programs
persist. Quest records and learned schematics are journal state and do
not drop. Wake Hall supplies a free recovery loan when usable gear is
missing: bound sidearm, 50 rounds, coverall, two patches. Loan goods
cannot be sold, traded, cached, crafted, or stockpiled; only missing
loan quantities are replaced. Recovery never requires another player.

### 5.5 NPCs

Non-player actors run **behaviours**: idle, wander, patrol (waypoints),
guard (hold, aggro on hostile), hunt (chase), flee (below 20 % health),
vendor, talker. Aggro rules use the faction relations matrix; a Halvard
patrol shoots Unmoored members in the Scour and ignores Kestrel. Freelance
characters are neutral to faction NPCs unless a declared restricted
perimeter or hostile action gives a reason to engage. Open ground permits
violence; it does not make traders automatic enemies. Hostile perimeters
display a warning before entry. A hunting NPC gives up 20 s after losing
sight; wander pauses last 200 to 1000 ms; NPCs in a zone that has been
dormant for 30 minutes are despawned and respawn from their spawners on
wake. Wardens log refused attacks in safe zones and issue a warning within 2
seconds. Warden **heat** lasts 10 minutes and causes pursuit only outside
safe/pocket areas. Curfew doubles new heat durations, not damage.

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
- Moving between adjacent cells takes max(0.2, 1.0 - Cortex / 100) s,
  rounded up to ticks after modifiers, with the same 0.2 s floor.
  Lifting data or flipping a control takes 3 s. Integrity recovers 5 per
  second after jacking out.
- A runner in the Lattice is a **presence** with its own health analog,
  **integrity** (100), and a **trace** meter (0 to 100). Integrity 0 means
  forced jack-out with shock 100 and, if black ICE did it, real damage.
- Runners see each other in the same cell or core room and can attack
  each other with programs (**burning**). Burning a runner in a civic
  sector raises your trace.

Public cells are safe from burning. Elsewhere burning requires both
bodies outside safe/pocket areas, neither participant protected by the
contested grade rule, and faction/Marked checks (§7.3). Jack-out is
instant in public cells and a 2 s, damage-interruptible channel elsewhere.
After three interruptions on one attempt, it completes on its next
scheduled end. ICE cannot hold a caller forever; Silt uses the same rule.

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
  programs have a cast time (0.3 to 2 s; Ledger is passive) and cooldown. Trace rises per
  second in a core (by tier) and per hostile action.
- At trace 100: civic sector, Wardens are dispatched to your body's
  location; corporate core, a **hunter** ICE spawns and follows you across
  cells; black core, the core's owner faction is told exactly where you
  are.

### 6.4 Interlock rules

- Each control in a core maps to one object in one zone. Flipping it
  changes the object immediately and posts to the zone log ("The gate
  cycles open. Nobody touched it.").
- Ordinary controls reset on their declared timer (5 to 30 minutes).
  Only controls tagged `owner_policy` persist for a relay owner. Travel
  denial, hazards, cuts, and service jobs always expire.
- A crew member who reaches a core's hardware in meatspace can **cut
  power**: every runner inside is jacked out with shock 100 and the core
  is offline for 10 minutes. This is the main defence against hostile
  runners and the main reason to bring a Hardline.
- Private cores (apartments) can be hacked: the runner sees the resident's
  storage manifest and can lift *one* unsecured item per successful run,
  once per day per apartment. The resident is told. This is the game's
  only theft-from-offline-players mechanic and is deliberately narrow.

Cut power takes 5 s, interrupted by damage. Safe hardware may be serviced
under a contract permission; it cannot eject unrelated runners. The Wake
training core cannot be cut. A private door hack opens its delivery
vestibule only, giving no access to occupants or additional storage.
The theft limit is one unit, not a stack, per apartment per rolling 24 h,
shared by all attackers. Impounded goods remain protected.

Every closed route has manual egress or an alternate return route.
In-flight transitions complete; a tram hold cannot strand an absent
actor. Transit holds last at most 30 s, followed by 120 s immunity.
Gate Nine's inward pedestrian egress remains available; its 25-chit toll
buys optional outbound fast passage. Scheduled outbound passage is free.

### 6.5 The Silt

Descent cells exist at the bottom of each sector. The Silt is procedurally
generated per descent from a seeded graph, deep, and populated by ICE that
does not belong to anyone and by **residuals** (fragments of past runners,
one of which is Ninety-Nine). Season contributions and Choir story arcs
live here. The Silt has no trace, city sitrep location, remote Pulse, or
Operator beacon. Crew already in the same descent see one another
normally. A Silt Beacon marks the entrance, not the runner.

Any rig can enter an accessible descent; no tier-3 rig is mandatory.
Deepwater makes traversal easier. Every band has a reachable riser, even
after Undertow, and an exit action. No riddle, buff, or response is
required to leave. Listening is a 3 s scan with 10 s cooldown: reveal
adjacent hidden cells at Listening >= 20; below that show their direction.
Lantern reveals them for anyone. Required routes also have a visible
surveyed bypass. Discoveries persist per graph, not as coordinates in
another seed.

### 6.6 Silt procedures and readable ICE

ICE has a readable role: gate, alarm, patrol, deception, displacement,
or feedback. Inspect shows its trigger, current state, and a counter
available without a particular archetype. Faction style changes the
problem: Kestrel schedules access, Sablier heals defenders, Sable reports
intruders, Halvard isolates and burns, Choir responds to signals.

A Chorister shows a repeating sample with a three-state indicator:
`listening`, `sampling`, `release`. Use a 3 s survey during `listening`
to record it, then a 3 s hold during `sampling`; each state lasts 5 s.
Success grants one 5-minute mapping effect for this descent: reveal
adjacent cells, without a stat bonus or contribution payout. A failed
hold raises a warning and resets the cycle; attacking starts its normal
fight. Withdraw remains available. There is no randomly good dialogue
answer. Listening or a prior record previews the cycle, while anyone
can observe it and act. Training this cycle repeatedly earns no XP.

A Sweeper announces the next cell in its patrol 5 s before entry and
leaves a reachable side route. Liar marks suspect data separately from
objective instructions; Compass distinguishes decoys. It cannot falsify
cost, exit, safe-zone, or transaction UI. Mission-critical signals are
text-and-glyph state, never colour, sound, or remembered prose alone.

## 7. Factions

### 7.1 Membership and standing

- **Standing** with each faction is −100 to +100, starting at the values
  set by the Wake recruiter choice (+10 with one faction, 0 elsewhere).
- Contracts, kills, and relay actions move standing with the relevant
  factions and their allies and enemies (halved).
- At standing +30 and legal personhood a player may **join** through its
  recruiter. One faction at a time. Leaving costs −50 with the former
  faction and a 7-day cooldown before joining another.
- Members get: faction chat, faction vats, faction vendors, faction
  contracts, the right to capture relays, and the faction's colour.
- Ranks at standing +30, +50, +70, +90 carry titles and, at +90, one
  mechanical perk per faction. Titles are in the faction dossiers;
  the complete perk schedule is §7.6 and implemented by S20. A
  perk must never be a flat combat multiplier.

Ordinary reputation: killing a faction NPC gives -5 with that faction
and explicit +2 with each of its hostiles; killing a nonhostile player
gives -10 with their faction; an eligible Marked kill gives +5 Wardens
once per victim BBS identity per 24 h. Unauthorized power cut gives -10
with the owner; permitted mission cuts use only the mission reward.
Reported apartment theft gives -10 Wardens once per theft receipt.
These explicit deltas do not propagate again. Ordinary single-faction
contract rewards propagate under section 9.3; forks/finales list their
complete multi-faction deltas. No standing is earned from a refused
attack, tutorial target or uncompleted interaction.

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

In a contested zone, PvP involving a character below grade 5 is refused
in both directions. Grade 5 is not a calendar-based loss of protection.
For eligible characters, attacking a player whose faction is not **hostile**
to yours (or any Freelance) makes you
**Marked** for 15 minutes: any player may attack you anywhere outside a
safe zone without becoming Marked themselves, Wardens engage you on sight
in contested zones, and your name shows red. Killing a Marked player gives
standing with the Wardens. In open zones nothing marks anyone.

Check legality at hostile action commitment, including misses, controls,
drones, and burning; attribute it once to the responsible player.
Recheck safety at impact. Attacking an already Marked player is exempt.
NPC mission crimes use standing and contract failure, not a second
Marked definition. Bounties do not grant attack immunity.

### 7.4 Relays and territory

- A relay is an object with a **control
  terminal** and a **core**. To capture: a member of a faction must hold
  the terminal (stand adjacent and interact) for 3 minutes, *and* the
  relay's core must be hacked open by a runner during that window, *or*
  the capturing crew must hold it for 8 minutes without a runner.
- A held relay pays the holding faction **influence** per hour (the
  season leaderboard score) and grants members a zone buff and access to
  the relay's vendor.
- Relays cannot be captured during a Curfew event. Scour relays pay
  triple.

An active holder must be conscious, in meatspace, and channelling; a
jacked body does not hold. A runner may be Freelance or another faction
if explicitly supporting the named claim. Support never grants ownership.
An eligible member can hold alone for the slower route. Opposing active
claims freeze clocks; passers-by do not contest. A 5 s absence aborts a
claim. Curfew pauses existing claims, without completing or deleting them.

Influence rates are 10/hour, 30/hour in the Scour, and 20/hour at Shaft
Relay. Carry fractional remainders; settle whole points once, stopping
at season end. Treasury receives the same whole amount. The daily member
share is 1 % of treasury, rounded down, capped at 200 chits and debited
atomically once per BBS identity per UTC day. Capture gives 100 XP and
+15 standing to participating members, −15 with the old owner to the
capturer. Recapturing that relay gives the same identity no capture XP
or standing for 24 h; influence still accrues.

### 7.5 Public services and work orders

Four services have bounded work orders with state `normal`, `fault`,
`repairing`, or `allocated`. They use ordinary contracts and controls,
not a population simulation. The S19 work-order scheduler offers a fault every 60 minutes of
server uptime per service, at most one fault on the node. It lasts
20 minutes; NPC repair then restores normal service. No faults accumulate
while the server is stopped. Neutral relay ownership is normal operation.

Any resident may repair. First acceptance reserves the work order for that
player or its frozen accepted job roster for 10 minutes. Abandonment,
deadline, or all participants leaving releases it. The reserver selects one
allocation below before the roster joins; on repair completion it lasts 20
minutes and cannot be overwritten or extended. Another order waits for the
original 60-minute cooldown. A relay owner cannot veto public repair.
Duplicate commands cannot claim another reward.

The work-order reserver selects its allocation; the frozen roster sees
that selection before joining and receives the same disclosed result.
Changing it requires releasing and reserving again before repairs start;
a completed repair cannot be reassigned. This uses the work-order
revision and receipt, independent of crew leadership.

| Service / location | Fault and task | Common allocation | Reserve allocation |
|---|---|---|---|
| Sump / `sink-floor` | flooded shortcut; replace pump feed and flip Sump control | drain marked public shortcut; salvage niche stays flooded | drain workers' salvage niche; public route stays long |
| Cold Chain / `vatside-clinics` | elective surgery discount unavailable; carry power unit and verify thermal record | surgery service fee −10 % for visitors | surgery service fee −20 % for workers only |
| Depot / `tramyard-depots` | surplus warehouse shut; carry manifest and release latch | surplus vendor buy-back budget ×2 for everyone | reserve surplus salvage cache for workers |
| Relay Zero / `oldworks-main` | survey feed stale; reset hardware and calibrate in network | publish local core's current patrol route | workers receive temporary local gate credential |

Each order identifies the exact changed door, cache, vendor, or core,
the foregone allocation, and a safe return route. Effects never change
essential stock, vats, rent, or standing thresholds. Sump water affects
authored regions only, with 5 s warning. Cold Chain never refuses care.
Sump and Depot reserve caches each contain two `slv_power` units per
order, shared by its workers. Common and reserve cannot both be claimed.
Relay Zero's credential opens one declared gate, not ICE immunity.
Standard reward: 200 chits, 100 XP, +5 with the handler's faction per
participating worker, without crew scaling. Allocation adds no XP.

### 7.6 Faction identity in play

All factions admit every archetype. These member perks activate at +90;
other titles are cosmetic. Perks cease below +90 or on leaving. Public
fallbacks preserve necessary information and story access.

| Faction | Useful method and its cost | +90 perk | Public fallback |
|---|---|---|---|
| Halvard | isolates faults; closes useful routes | one free containment-charge service fee per UTC day; item still costs full price | manual hardware cut or paid charge |
| Sablier | preserves continuity; retains records | choose any unlocked faction vat for next decant | nearest public vat |
| Kestrel | plans routes; excludes unlisted loads | reserve escort slot on next committed Convoy | public board at departure |
| Wardens | protects a centre; leaves districts exposed | see Marked players' zones during active marks | local sight and ordinary sitrep |
| Choir | detects signals; risks overinterpreting them | see announced Surge's next ICE variants | same labels at encounter entry |
| Sable | supplies unavailable goods; prices dependence | reserve one rotating vendor item for 10 min, once per UTC day | public stock after reservation expires |
| Unmoored | shares access; exposes people and records | bound residual-fragment loan once per UTC day, consumed on jack-out | ordinary programs; public Ninety-Nine advice |
| Ferrymen | brings parts home; chooses who gets guided | read committed Ring-fall forecast free | buy chart or use public warnings |

The charge service fee is 150 chits per use, separate from the
1 500-chit consumable. The perk cannot change range, time, or safety.
Nobody can bar another player from the Tin Halo, remove a recruiter, or
reserve essential stock. The Choir's historical nine seats do not cap
players earning the Ninth title. Kestrel reservations do not close the
public escort contract; they notify the member and preserve their slot.

### 7.7 Relay schedule and limits

Each row instantiates `lat-relay-<slug>` from `lat-relay-uplink`. The
physical relay, terminal, and uplink hardware share the listed zone;
service controls are separate scoped targets. Every member benefit
ends with ownership and stacks only once. Defaults outside this table
are not additional perks. Scour cores remain reachable when neutral.

| Relay slug / name | Zone | Tier | Member effect |
|---|---|---|---|
| `shaft` / Shaft Relay | `spire-shaft-head` | 5 | shaft telemetry view; 20 influence/hour; available after level opening |
| `cold-chain` / Cold Chain Relay | `vatside-clinics` | 2 | surgery service fee -10 %, strongest service discount only |
| `depot` / Depot Relay | `tramyard-depots` | 2 | faction vendor budget refresh every 30 min instead of 60 |
| `gate-nine` / Gate Relay Nine | `tramyard-wall-gate` | 3 | free optional outbound fast passage; other users 25 chits |
| `cable` / Cable Relay | `sink-rim` | 3 | optional cable ride free; route holds bounded by §6.4 |
| `sump` / Sump Relay | `sink-floor` | 2 | pump telemetry reveals active work-order allocations |
| `bell` / Bell Relay | `chapel-towers` | 3 | hymn radius +1 tile within Chapel Ward |
| `zero` / Relay Zero | `oldworks-main` | 3 | trace gain §10 %, excluding fixed action costs |
| `yard` / Yard Relay | `oldworks-yards` | 3 | fabrication quality +0.05, final cap 1.15 |
| `block` / Block Relay | `terraces-blocks` | 2 | next rent invoice -10 %; one extra Tripwire in private core |
| `cavern` / Cavern Relay | `under-caverns` | 3 | current local patrol overlay, not exclusive base map |
| `outworks` / Outworks Relay | `under-outworks` | 4 | contribution Depth +10 %, rounded down, no extra XP/ballot |
| `mile` / Mile Relay | `scour-ring-1` | 2 | current local patrol route on convoy map; no combat immunity |
| `beacon` / Beacon Relay | `scour-ring-2` | 3 | committed impact sites 5 min early |
| `crash` / Crash Relay | `scour-ring-3` | 4 | harvest grade +1 step, capped compute; cannot create intact |
| `far` / Far Relay | `scour-ring-4` | 4 | current local telemetry and carrier record |

Cable fare is 5 chits; a free stair/ladder route remains. Gate Nine's
ordinary outbound opening is 60 s every 5 minutes. Trams depart every
90 s with a 10 s journey and no fare in v1. These are schedules anchored
to the injected clock, never reset on entering a dormant zone. Private
ICE cannot inflict black feedback or bypass the theft cap.

## 8. Economy

### 8.1 Chits

Chits are integers. Sources: contracts, core data, salvage sales, vendor
sales, relay income (faction treasury pays members a share). Sinks: gear,
implants and surgery, rent, ammo, drugs, clone debt, fabrication.
Banked chits (at a Kestrel branch or apartment safe) are never lost to
death. Vendor resale is 40 % of list, with per-vendor hourly budgets;
ordinary prices vary linearly between the standing endpoints, clamped
there. Freelance pays list regardless of standing, but can still use
public services and story permits. Public essential stock is unlimited.
There is no hunger/thirst decay. Rations and water are supplies and
flavour, not another survival meter.

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
  factions. Fabrication skill improves the quality floor under the formula below.
- Intact salvage is the season-contribution currency of the Custodian
  arc.

Baseline salvage: each ring keeps 2-6 nodes, one replacement per
10 minutes of server uptime, with 1-6 units per node. Harvest channels
2 s/unit; only completed units transfer. Ring weights: hull/optics/
power/compute/intact = 90/10/0/0/0, 55/25/20/0/0, 35/25/25/15/0,
20/20/25/30/5. Restart preserves node units and RNG. Intact cannot be
bought from or sold to NPC vendors; player trading is allowed.

Learned schematics persist. Fabrication consumes inputs on successful
completion of a 3 s channel. Quality = 0.85 + 0.15 * skill/100 + U(0,
0.15), capped 1.15 after relay modifiers. Higher skill improves the floor,
not the size of negative rolls. Scale only the declared primary stat;
never control durations, permissions, implant tolerance, or stack counts.
No random roll is needed where an item has no quality-scaled stat.

### 8.5 Implants and surgery

- Implants occupy **tolerance** points and a slot (head, eyes, spine,
  arms, torso, legs, rig). A character has at most one implant per slot
  except arms (two). Removal at any clinic charges 20% of list,
  has no failure roll and returns the implant at unchanged quality.
  A replacement may remove and install in one visit, displaying both
  costs before commitment.
- Sablier clinics charge the item price plus a 20 % surgery fee with a 2 % failure chance (item
  lost, 30 s of shock). Black clinics in the Sink install at 60 % price
  with 15 % failure and no extra service fee. Owned implants use
  a service fee of 20 % of list at Sablier or 12 % at a black clinic;
  failure consumes the owned item. Both menus show the exact total.
- Resonance implants require Cantor and Choir standing +20 to install,
  except the starter First Ear. Installed abilities keep working after
  leaving the Choir; tier unlocks come from the installed equipment.

### 8.6 Drugs

Each substance has an effect, a duration, a **crash** (opposite effect
for half the duration), and an addiction clock: three doses inside its
window creates a dependency that imposes the crash until detox.
Sablier detox costs 400 chits and takes 10 minutes, offline-safe.

### 8.7 Apartments

Rented in the Terraces per week of real time in chits, paid from the bank
automatically. Contains storage and a private core by housing class (section 17.1),
a safe with banked chits and a terminal. Rent lapse of
two weeks evicts and moves everything to a Kestrel impound (fee to
reclaim).

## 9. Contracts

### 9.1 Objectives and approaches

Contracts have six objective types, composable in ordered stages. A card
shows the current stage, location, approach, reward, foreseeable costs,
and abort route before acceptance. Stages use server facts, not text
parsing or a narrator deciding whether a response was good.

| Type | Completion evidence | Allowed variants |
|---|---|---|
| fetch | transfer the named item at turn-in | delivered object or recovered world cache |
| hack | authorised data lift or named control receipt | inspect, lift, flip, enter |
| escort | assigned NPC reaches destination alive | street or network route; fixed mission instance |
| clear | specified NPCs resolved | kill or explicitly subdue, never ambiguous |
| plant | consume item at named target | zone object or core room; 3 s channel, +10 trace in a core |
| survey | observe named cells, tiles, or object state | visit, compare records, inspect a current signal |

A job may offer alternative stage sequences using those same types.
Rewards are fixed on acceptance. Generated objectives scale by
ceil(base * (1 + 0.5 * (roster size - 1))); each participant's reward
scales by 1 + 0.25 * (size - 1), rounded down. Story jobs and work orders
use fixed rewards and their declared participant scaling instead.
Freeze the roster on acceptance; joining at turn-in grants nothing.

Generated contracts expire after 60 real minutes, at most three active
per player. Boards show five offers per handler and refresh every
30 minutes. Story stages have no real-time expiry except explicitly
labelled field windows. A failed or abandoned stage is retryable; a
committed branch choice is not. Required loan items can be reissued,
bound and without a sale value. NPC escorts reset without removing the
public handler. No seasonal chain requires logging in at 04:12 or waiting
through multiple real Curfews; stored cycle logs satisfy those surveys.

### 9.2 Evidence, custody, and intrigue

The journal stores discovered records with asset ID, source object,
source's claimed author/date, acquisition time, season, and a one-line
operational finding. A separate field holds the source's interpretation.
The UI never labels a machine voice CUST or TEN. A signed local receipt
proves an action happened, not who is conscious behind a process.
Records do not consume inventory slots and cannot be lost on death.

Evidence can unlock a patrol window, a maintenance credential, a route,
or a different delivery recipient. Those are typed permissions with
scope and expiry. Persistent story evidence stays useful to its chain;
forecasts expire visibly when the event changes. No player is sent to
coordinates taken from a different generated Silt graph.

A decision card can offer private delivery or publication. It explicitly
lists who learns the record, standing deltas, rewards, and access effects.
Publication reveals authored findings and NPC identities only, never
another caller's hidden body, private storage, or messages. A branch group
commits once per character; an immutable receipt prevents returning the
same evidence to collect both exclusive outcomes. Reading and copying a
record are free; reward claims are not. Faction memberships and permits
cannot prevent a Freelance player from reaching the central chain.

### 9.3 Story and shared-world scope

Story encounters use mission-scoped NPCs, caches, permissions, and
objective receipts. Other players cannot kill the only copy of a quest
NPC or consume somebody else's critical item. Stage forks affect the
participant record unless explicitly declared as a public service order
(§7.5) or settled season outcome (§13). All public consequences have one
owning subsystem, a duration, and a restart rule.

Standing has two reward modes: `propagate` applies one base faction
delta and one non-recursive half-delta to its allies/opponents;
`explicit` applies the authored vector once, without propagation. Round
halves toward zero and clamp the final result to -100..+100. Story forks,
finales, and Vesper's introductions use explicit vectors. This prevents
an eight-faction introduction from rewarding and punishing itself.

### 9.4 Authored jobs that establish the game

| Job | Preparation and field action | Decision and observable result |
|---|---|---|
| Vesper's first thing | inspect the stair latch at Block 4; use a 5 s manual release or jack at the adjacent loan terminal for a 3 s flip; both routes are sheltered from NPC fire | carry the package via the longer lit stair or the short dark landing; same 200 chits, 100 XP, explicit +5 to each faction; no moral quiz or surprise duel |
| Sump work order | survey pump telemetry; carry one supplied bound power unit to the hardware; flip the sump bypass; crew can split these steps | choose the public shortcut or salvage niche in §7.5; returning players see that exact water layout and expiry |
| Walked templates | Sablier offers a paid escort to a clinic for four willing mission NPCs; Unmoored offers shielding their recall tags in place | clinic gives 400 chits, Sablier +15, Unmoored -10; shielding gives 200 chits, Unmoored +15, Sablier -10 and a public route record; both give 200 XP, share branch group `walked-templates-s1`, and keep consent explicit |
| Ration discrepancy | lift the Depot allocation record; compare its consignment ID with an observed crate at Gate Nine; bring the finding to the handler | private delivery: 400 chits, Kestrel +10, one 20-min warehouse credential; publish: 200 chits, Unmoored +10, Kestrel -10, public copy of that warehouse's patrol route for 20 min; either gives 200 XP |

The final two jobs are playable demonstrations of faction methods, not
universal morality scores. The clinic preserves people but logs them;
the shield preserves their location but forgoes medical evaluation.
Their records describe those consequences without asserting what a
person ought to choose. The ration fork is `kes-s1-2` in the season arc.

### 9.5 Content readiness

S19 delivers the engine, generated templates, and the first job on maps
already shipped. It defines and validates future story bundles against
an explicit manifest, but does not activate unresolved references.
S25 supplies remaining maps; S26 activates Season 1 chains and finales
with their complete referenced content. Seasons 2 and 3 remain design
specifications until separately authored and accepted.

## 10. Crews

- A crew is 2 to 5 players. Invite, accept, leave, kick by leader.
- Crew chat, crew list in the side panel with health and zone, a
  **beacon** (Operator) that shows a crew member's position across zones.
- Loot: corpse caches and core data are free-for-all by default; the
  leader can set round-robin.
- XP from a kill or run is shared with eligible crew in that zone/sector,
  plus crew on its linked hardware/body-guard objective in meatspace.
  Require a mission contribution (guarding within 6 tiles for 10 s,
  completing a linked control, dealing damage, or healing) in the last
  60 s. Full XP within 5 grades, else multiplier max(0.25,
  1 - (gap - 5) / 20). Apply once per receipt and identity, not once
  per layer. Unrelated or absent crew get none.

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

Events are scheduled by the server with persisted plans, weights, and
cooldowns. A forecast is information about a plan already committed,
never knowledge of a future RNG roll. Every 20 minutes the scheduler
may reserve an eligible event and its zone/route; it starts 60 minutes
later. At most two plans/running events share the schedule, and affected
physical zones and sectors cannot overlap. Event-specific cooldowns
start at completion. A plan made ineligible is cancelled with a public
forecast correction; it is never silently moved to another ring.

| Event | Where | Duration | Cooldown / weight | Effect |
|---|---|---|---|---|
| Ring-fall | one Scour ring | 20 min | 90 min / 5 | salvage and NPC recovery crews; impact sites show 5 s hazard warning |
| Curfew | Core's three zones | 60 min | 4 h / 2 | ordinary inbound entry restricted; relay claims pause; new Warden heat durations x2 |
| Choir Surge | sectors | 15 min | 3 h / 2 | announced ICE variants; Cantor beneficial effect magnitudes +30 %; maps current Silt band |
| Exhale | Undercity | 30 min | 2 h / 3 | spawn rate x3 within authored caps; keys and temporary shortcut controls |
| Convoy | declared Scour route | 25 min | 60 min / 4 | public escort/raid jobs; NPC convoy follows `routes.json` |

Curfew preserves outward travel, internal Core movement, existing safe
pockets, public vat use, banking, and at least one reachable shelter
from every district. Pass holders may enter; Marked pass holders use
other shelters. It does not imprison a player in the Core or cancel a
journey already underway. NPC transit permits in historical reports are
not necessarily Curfew Passes.

Surge swaps only compatible non-black variants of equal or lower tier.
Show the new behaviour 5 s before activation; preserve damage already
received and do not restart a cast to get an instant hit. Never add
black ICE to a non-black room or change the tutorial/private core rules.
The +30 % bonus affects heal/shield/stamina/shock relief magnitudes,
not damage, cooldowns, range, duration, or restrictions. No season result
penalises a player's archetype. Silt reveal affects current-band geometry;
it reveals neither future seeds nor an identity behind a voice.

Ferrymen charts reveal the committed Ring-fall ring 60 minutes early;
Skywatch narrows its timing, and Beacon Relay reveals sites 5 minutes
before impact. Everyone gets the 5 s impact warning. Local job hazards
and service faults are separate bounded state machines, not extra world
event slots. They cannot change safe/pocket tiles.

Persist plans, instance IDs, seeds, start/end times, targets, allocations,
and claimed rewards. Restart resumes unexpired effects without rerolling
or spawning duplicate salvage. Expired events restore their baseline;
no offline meteor strikes or offline contract deaths are replayed.
Removal of an effect reveals the next active layer (base, owner policy,
service order, event, season); it must not restore an obsolete snapshot.

## 13. Seasons and the Descent

### 13.1 Contribution and access

Depth starts at 0. A console consumes unique contribution units in one
transaction: tagged data 250, intact salvage 500, Undercity key 1 000.
Faction credit follows membership at delivery; Freelance gets its own
unranked ledger and personal credit. Consoles at the Tin Halo and season
door accept everyone. A stolen/copied journal record is not a fresh
contribution unit. Each source respawns at most once per 60 minutes of
server uptime. XP is 25 per contribution unit, once. Delivery never
changes the machine balance; both kinds of work enable investigation.

At season creation the SysOp selects a published Depth target: small
node 10 000, standard 100 000, large 250 000; default small. The setting
is fixed during ordinary play, not scaled by concurrent login count.
A season has a suggested 90-day duration, but transitions only on the
operator's explicit advance. No player loses access because a silent
calendar expired. Advance with no eligible completion requires an
explicit no-outcome acknowledgement and records no settled choice.

The level opens at target and supports expeditions of 1-5, including
Freelance and any archetype mix. Everyone enters at the season door.
An expedition is a persistent instance roster distinct from the live
crew: it survives leader changes, reconnects, or a dissolving crew.
At most four instances run; others queue FIFO and can cancel freely.

Each encounter supplies a terminal loan rig, recoverable preparation
controls, an extraction route, and a sequential solution. A crew can
split jobs simultaneously; one player uses a 120 s local control latch
to cross after jacking out. No simultaneous-plate gate, mandatory class,
or NPC companion purchase blocks a solo player. Scale threats by the
roster at entry (1/2/3/4/5 participants: 1/2/3/4/5 mission drones), not
by surprise reinforcements when someone reconnects. Enemy stats stay
fixed; approaches and overlapping tasks create the extra difficulty.

Checkpoint after each completed phase. On restart or an empty instance
for 10 minutes, tear down live actors, retain checkpoint and committed
rewards, and return participants to the entry shelter without debt.
Unclaimed consumables reset with their phase; claimed loot never does.
Archived levels remain available for story objectives after settlement,
with their local branch scenery, but cannot pay another season ballot.

### 13.2 Choice, consent, and settlement

After the final phase every participant sees all unlocked alternatives,
consequences, and the records supporting them in a safe decision room.
Each chooses independently, or leaves and returns later. No leader spends
another member's standing or assigns their name. Name options accept
only that player's own character name/handle; no free-text insertion of
someone else's identity. A condition on an option is satisfied by that
expedition's evidence, not another crew's hidden global flag.

A personal decision gives its explicit standing/access effects once and
writes a completion receipt plus Chronicle expedition entry. It does not
change the shared city yet. One ballot per `(origin, bbs_user_id, season)`;
extra permitted characters and repeat runs add none. A committed choice
is final; replay is for practice, assistance, and unclaimed story records.
The ballot and reward receipt commit atomically before acknowledgement.

On advance, count ballots equally; highest count selects the public
outcome for the next season. A tie or no ballots means no new public
modifier and zero balance movement; record the counts and dissent.
Otherwise apply the winning option's delta once, clamped to -3..+3.
Zero-delta options preserve existing balance rather than resetting to
EVEN. CUST/TEN tags are internal voice weights, never moral scores.
No cross-node identity claim or perfect alt-account prevention is implied.

The Chronicle records all expedition choices, final counts, public
outcome, duration, and the actual changed services. It attributes NPC
interpretations. For name-bearing public text, choose the earliest
winning ballot's consenting name, and disclose that selection rule on
the decision card. Failure to reach the level never invents a result.
Leaderboards show influence and contribution as separate columns, with
no undocumented sum. Grade, kills, runs, and repairs are separate lists.

### 13.3 Outcome schedule

Personal standing vectors below apply only to the chooser, without
ally propagation. Access/traits are per chooser, capped once. Public
modifiers start on settlement and end at the next settlement, unless
explicitly permanent. They do not touch essential services or class
power. These are binding rules for the three authored season concepts.

| Season / option | Personal cost and gain | Public outcome | Delta |
|---|---|---|---|
| 1 Seal | Halvard +20, Unmoored -10 | optional east maintenance shortcut closed; Exhale spawn multiplier 2 instead of 3; Curfew weight 1 instead of 2 | -1 |
| 1 Open | Halvard -20, Choir +10, Unmoored +10 | optional east shortcut open; its Exhale wave cap gains 2 drones; regular route unchanged | +1 |
| 1 Answer | Sablier -15; name recorded, one extra top-band survey record per descent | default routes/events; Vatside repeats selected consenting name, attributed as a reported anomaly | 0 |
| 2 Restore | Halvard -20, Kestrel +20 | reconnect local telemetry trunk only; optional cavern freight lift; Ring-fall weight 10 instead of 5 | -1 |
| 2 Cut | Kestrel -15, Sable +15, Unmoored +15 | manual tram interval 120 s instead of 90; Depot surplus work orders available at Tin Halo too; Dispatcher barks replaced by Holt | +1 |
| 2 Chair | Wardens -10, Kestrel +10, Ferrymen +10; own handle recorded | normal routing, public committed Convoy timetable and consenting operator acknowledgement | 0 |
| 3 Silence | Choir -20, Halvard +15, Wardens +15 | no Surge variant swaps; ordinary Surge map reveal/bonuses continue; optional gallery cache closed | -1 |
| 3 Name | Sablier -15, Choir +20; optional Listened calibration | optional gallery route opens; local recovery patrol added with cap 2 | +1 |
| 3 Ninety-Nine | Unmoored -10; requires recovered residual and its affirmative offer | gallery terminal adds Ninety-Nine; Old Works retains archived navigation advice and referral | 0 |

Listened is a reversible equipped calibration: +10 Listening and +10 %
corporate trace while active, clamped to skill limits. Toggle at any safe
terminal for free; the historical decision remains. No permanent stat
award makes one story ending compulsory. The mapped record from Answer
adds information, not a second contribution drop.

### 13.4 Narrative evidence and delivery

Each revelation states an observed event, its source, and at least two
compatible explanations. Logs from a process cannot authenticate that
same process's self-description. Later seasons may challenge motives,
not secretly undo an earned credential, delete characters, or open a way
out of Karst. Previous seals leave maintenance access to archived story
sites; local telemetry links never restore the global network.

Both voice registers have one guaranteed line per finale. Additional
ambient lines use the zone/instance RNG: skip an opposing tag with
probability 0.7 at |balance| = 1 or 2, 0.9 at 3, no skip at 0. These
weights never suppress instructions, costs, warnings, or a required clue.
Future NPC positions and dialogue condition on settled outcomes or the
viewing player's receipt, never the most recent crew's completion.

## 14. Anti-abuse and fairness

- Everything is server-authoritative; the client sends keys and commands,
  never state.
- Rate limits: 20 inputs per second per session, 4 chat lines per 5
  seconds, one market action per second.
- Alt characters: one character per BBS user per node. A SysOp may raise
  that.
- Camping: a vat area is a safe pocket; a Warden precinct is a safe pocket.
- Griefing of new players: bidirectional contested PvP protection below
  grade 5, no bounties below grade 5,
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

## 17. Initial content schedules

These tables are normative numerical content, mirrored in the world
catalog and Lattice reference for author convenience. A change edits both
in the same design PR; S02 validates the authored runtime data against
these values. Item tiers are 1-3; program/core/ICE tiers are 1-5.
Descriptions and maker voices remain in the world catalog. Times use
§5.3 tick rounding. IDs with underscores are valid for table records;
zone, core, dialogue, and text IDs use hyphens.

### 17.1 Equipment, supplies, fabrication, and housing

These canonical numeric tables are mirrored in the world catalog for
content authoring. Edit both together. Main sections 3-13 govern
permissions, stacking, action timing and acquisition; catalog prose
supplies descriptions. Item tiers are 1-3, program/core/ICE tiers 1-5
with the explicit tutorial exception. Underscore item/program IDs are
valid; zone/core instance IDs retain their own documented convention.

#### Manufacturers

| Maker | Who | Makes |
|---|---|---|
| Halvard Ordnance | Halvard subsidiary | kinetic and energy weapons, heavy armour |
| Ostrom Optical | Halvard subsidiary | eyes, sights, energy weapons |
| Sablier | Sablier | implants, medical consumables, detox, drugs with a label |
| Kestrel Issue | Kestrel | cheap, sturdy, everywhere; convoy guard kit |
| Civic Pattern | Wardens | standard-issue Warden gear; sold only to Wardens |
| Sable Works | Red Sable workshops in the Sink | chemical weapons, black-clinic implants, drugs without a label |
| Old Works Collective | the Unmoored | rigs, programs, jury-rigged energy gear |
| Chapel Foundry | the Choir | resonance implants (built from Sablier parts), dissonance projectors |
| Ferry-make | Ferrymen | anything built from Ring-fall; ugly, heavy, hits hard |

#### 1.1 Damage types and what resists them

| Type | Typical source | Armour stat that reduces it |
|---|---|---|
| kinetic | slugs, flechettes, blades, clubs | `arm_k` |
| energy | lasers, arc coils, pulse | `arm_e` |
| chemical | acid, nerve agents, incendiary gel | `arm_c` |
| dissonance | Cantor projectors and hymns | `arm_d` (rare) |

#### 1.2 Ranged, tier 1

| ID | Name | Maker | Type | Range | Dmg | CD | Acc | Ammo | Wt | Price | Line |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `wpn_kestrel_sidearm` | Kestrel Issue Sidearm | Kestrel Issue | kinetic | 6 | 12 | 0.8 | 55 | `ammo_9x` | 1.0 | 120 | The starter pistol. Everyone in Karst has fired one; most of them at the wrong person. |
| `wpn_halvard_hv7` | Halvard HV-7 Carbine | Halvard Ordnance | kinetic | 9 | 16 | 1.0 | 55 | `ammo_5x` | 3.2 | 340 | A guard's rifle. Boring, accurate, never jams, never surprises anyone. |
| `wpn_sable_streetsweeper` | Sable Works Streetsweeper | Sable Works | kinetic | 3 | 28 | 1.6 | 40 | `ammo_shell` | 3.8 | 300 | Pipe shotgun. In the Sink, "nice to meet you" is a sound. |
| `wpn_ostrom_pinlight` | Ostrom Pinlight | Ostrom Optical | energy | 7 | 10 | 0.6 | 65 | `ammo_cell` | 1.1 | 260 | A laser pointer that grew up. Quiet, precise, useless against plate. |
| `wpn_sable_spitter` | Sable Works Spitter | Sable Works | chemical | 4 | 9 (+4/s, 3 s) | 1.2 | 50 | `ammo_gel` | 2.0 | 280 | Sprays a caustic gel that keeps working after you stop. Don't stand downwind. |
| `wpn_ferry_slugthrower` | Ferry-make Slugthrower | Ferry-make | kinetic | 5 | 22 | 1.5 | 45 | `ammo_scrap` | 4.5 | 200 | Half of it fell out of the sky. The other half is a bicycle. |
| `wpn_kestrel_flare_pistol` | Kestrel Issue Flare Pistol | Kestrel Issue | chemical | 8 | 6 (+6/s, 4 s) | 2.0 | 35 | `ammo_flare` | 1.2 | 90 | Meant to call a convoy. Also sets things on fire, which sometimes calls a convoy. |
| `wpn_ow_arcpen` | Old Works Arc-Pen | Old Works Collective | energy | 5 | 11 | 0.7 | 60 | `ammo_cell` | 0.8 | 240 | A soldering tool with ambitions. Runners carry it because it fits next to a rig. |

#### 1.3 Ranged, tier 2

| ID | Name | Maker | Type | Range | Dmg | CD | Acc | Ammo | Wt | Price | Line |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `wpn_halvard_hv9` | Halvard HV-9 Battle Rifle | Halvard Ordnance | kinetic | 11 | 24 | 1.1 | 60 | `ammo_5x` | 4.0 | 1400 | The rifle the HV-7 wanted to be. Spire security carry it with the safety off. |
| `wpn_halvard_dmr` | Halvard Longline DMR | Halvard Ordnance | kinetic | 16 | 40 | 2.4 | 70 | `ammo_7x` | 5.5 | 1900 | Marksman's rifle. In the Scour, you hear it after you're already down. |
| `wpn_ostrom_lance` | Ostrom Lance | Ostrom Optical | energy | 10 | 22 | 1.0 | 70 | `ammo_cell` | 2.6 | 1600 | Corporate laser rifle. Draws a line from you to the problem and removes the problem. |
| `wpn_ow_coilgun` | Old Works Coilgun | Old Works Collective | kinetic | 9 | 30 | 1.8 | 50 | `ammo_flechette` | 3.4 | 1200 | Rails from a tram motor, capacitor from a vat. Sounds like a slammed door. |
| `wpn_sable_needler` | Sable Works Needler | Sable Works | chemical | 8 | 14 (+5/s, 4 s) | 0.9 | 60 | `ammo_needle` | 1.8 | 1300 | Fires hypodermic darts. What's in them is up to you. |
| `wpn_sable_pump` | Sable Works Twelve | Sable Works | kinetic | 4 | 42 | 1.9 | 45 | `ammo_shell` | 4.2 | 1100 | A proper shotgun, machined, with the maker's mark filed off out of habit. |
| `wpn_kestrel_convoy_smg` | Kestrel Issue Convoy SMG | Kestrel Issue | kinetic | 7 | 13 | 0.5 | 50 | `ammo_9x` | 2.8 | 1000 | Convoy guards get one each and a box of magazines. Spray, reload, repeat. |
| `wpn_ferry_meteor_cannon` | Ferry-make Meteor Cannon | Ferry-make | kinetic | 6 | 60 | 3.0 | 40 | `ammo_scrap` | 9.0 | 1500 | A satellite thruster housing loaded with bolts. Heavy weapon (Hardline only). |
| `wpn_ostrom_arc_projector` | Ostrom Arc Projector | Ostrom Optical | energy | 5 | 18 (arc: 2 targets) | 1.4 | 55 | `ammo_cell` | 3.9 | 1700 | Jumps between targets. Halvard uses it on crowds and calls it "de-escalation". |
| `wpn_sable_torch` | Sable Works Torch | Sable Works | chemical | 3 | 20 (+8/s, 3 s) | 1.5 | 50 | `ammo_gel` | 5.0 | 1250 | Flamethrower. The Sink's answer to a locked door. Heavy weapon (Hardline only). |
| `wpn_chapel_tuning_fork` | Chapel Foundry Tuning Fork | Chapel Foundry | dissonance | 6 | 15 | 1.2 | 65 | none (Resonance) | 1.4 | 1500 | A dissonance projector. Cantor only. It does not make a sound you can hear; the target disagrees. |

#### 1.4 Ranged, tier 3

| ID | Name | Maker | Type | Range | Dmg | CD | Acc | Ammo | Wt | Price | Line |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `wpn_halvard_hv12` | Halvard HV-12 Assault Rifle | Halvard Ordnance | kinetic | 12 | 32 | 0.9 | 65 | `ammo_5x` | 4.4 | 5200 | Spire issue. If you see one outside the Spire, someone died for it. |
| `wpn_halvard_anvil` | Halvard Anvil LMG | Halvard Ordnance | kinetic | 10 | 26 | 0.5 | 45 | `ammo_7x` | 11.0 | 6800 | Heavy weapon (Hardline only). Suppression as a personality. |
| `wpn_ostrom_scalpel` | Ostrom Scalpel | Ostrom Optical | energy | 14 | 48 | 2.0 | 80 | `ammo_cell` | 3.0 | 6500 | Surgical laser rifle. Ostrom says it's for eye clinics. Ostrom says a lot of things. |
| `wpn_ostrom_sunlance` | Ostrom Sunlance | Ostrom Optical | energy | 8 | 70 | 3.0 | 60 | `ammo_cell` | 8.5 | 7400 | Heavy weapon (Hardline only). Brief, bright, final. |
| `wpn_sable_widow` | Sable Works Widow | Sable Works | chemical | 9 | 18 (+9/s, 5 s) | 1.0 | 65 | `ammo_needle` | 2.2 | 5600 | Needler with a nerve-agent reservoir. Illegal in the Core, which is where it is confiscated. |
| `wpn_ow_railpistol` | Old Works Railpistol | Old Works Collective | kinetic | 8 | 38 | 1.3 | 60 | `ammo_flechette` | 1.9 | 5000 | Coilgun tech, pocket size. Runners' choice for the walk home. |
| `wpn_ferry_ringfall_rifle` | Ferry-make Ring-fall Rifle | Ferry-make | kinetic | 15 | 55 | 2.6 | 60 | `ammo_scrap` | 7.0 | 4800 | Barrel from a satellite boom, sight from an optics grade. Nobody makes two alike. |
| `wpn_kestrel_gate_gun` | Kestrel Issue Gate Gun | Kestrel Issue | kinetic | 9 | 30 | 0.7 | 55 | `ammo_5x` | 5.0 | 4600 | Gate-guard carbine, Kestrel's only tier-3 design. Ugly, cheap for what it is, replaces itself. |
| `wpn_chapel_choir_bell` | Chapel Foundry Choir Bell | Chapel Foundry | dissonance | 7 | 30 (cone: 3 tiles) | 2.2 | 60 | none (Resonance) | 2.8 | 6000 | Cantor only. A cone of pure disagreement. Wardens classify it as a musical instrument. |
| `wpn_ostrom_pulse_carbine` | Ostrom Pulse Carbine | Ostrom Optical | energy | 10 | 28 | 0.8 | 65 | `ammo_cell` | 3.3 | 5400 | Energy counterpart to the HV-12, sold to Sablier security. Cleaner. Same result. |

#### 1.5 Melee

| ID | Name | Maker | Type | Dmg | Stamina | Wt | Tier | Price | Line |
|---|---|---|---|---|---|---|---|---|---|
| `wpn_kestrel_baton` | Kestrel Issue Baton | Kestrel Issue | kinetic | 14 | 6 | 0.9 | 1 | 40 | Starter melee. A stick that has been to meetings. |
| `wpn_sable_shiv` | Sable Works Shiv | Sable Works | kinetic | 18 | 5 | 0.3 | 1 | 60 | Fast, quiet, easily lost, easily replaced. |
| `wpn_ferry_wrench` | Ferry-make Ring Wrench | Ferry-make | kinetic | 26 | 10 | 3.0 | 1 | 110 | A tool for satellites. Also for people who touch your salvage. |
| `wpn_halvard_shock_baton` | Halvard Shock Baton | Halvard Ordnance | energy | 22 (+10 shock) | 8 | 1.2 | 2 | 700 | Adds shock on hit. Security issue; the humane option, by Halvard's definition. |
| `wpn_sable_machete` | Sable Works Machete | Sable Works | kinetic | 34 | 9 | 1.6 | 2 | 650 | The Sink's ceremonial blade. The ceremony is short. |
| `wpn_ow_arc_knuckles` | Old Works Arc Knuckles | Old Works Collective | energy | 20 (2-hit) | 7 | 0.7 | 2 | 800 | Capacitor gloves. Two fast hits per swing. Don't shake hands. |
| `wpn_sable_acid_blade` | Sable Works Etcher | Sable Works | chemical | 24 (+6/s, 3 s) | 9 | 1.4 | 3 | 3200 | A blade that keeps cutting after you've put it away. |
| `wpn_halvard_ram` | Halvard Breaching Ram | Halvard Ordnance | kinetic | 60 (+30 shock) | 20 | 9.0 | 3 | 4000 | Heavy weapon (Hardline only). Knocks down anything smaller than a door. Most things are. |
| `wpn_chapel_hand_bell` | Chapel Foundry Hand Bell | Chapel Foundry | dissonance | 28 | 6 | 0.9 | 3 | 3600 | Cantor only. Touch-range dissonance. Mother Quell carries one and has never been seen to use it. |

#### 1.6 Ammunition

| ID | Name | Stack | Price per stack | Notes |
|---|---|---|---|---|
| `ammo_9x` | 9x pistol rounds | 50 | 25 | Kestrel Issue, everywhere |
| `ammo_5x` | 5x rifle rounds | 60 | 60 | Halvard pattern |
| `ammo_7x` | 7x heavy rounds | 40 | 110 | Halvard pattern; DMR and LMG |
| `ammo_shell` | shotgun shells | 24 | 45 | Sable Works and Kestrel |
| `ammo_cell` | energy cell | 30 charges | 70 | Ostrom pattern; rechargeable at any terminal for 10 chits |
| `ammo_gel` | caustic gel canister | 20 | 55 | Sable Works |
| `ammo_needle` | needle darts | 30 | 90 | Sable Works; loaded with the weapon's fixed agent (no custom mixing in v1) |
| `ammo_flechette` | flechette rails | 30 | 80 | Old Works |
| `ammo_scrap` | scrap bolts | 20 | 15 | Ferry-make; fabricated from hull salvage 1:20 |
| `ammo_flare` | flares | 6 | 30 | Kestrel Issue |

#### 2. Armour

| ID | Name | Maker | Layer | arm_k | arm_e | arm_c | arm_d | Evasion | Wt | Tier | Price |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `arm_wake_coverall` | Sablier Wake Coverall | Sablier | body | 2 | 2 | 4 | 0 | 0 | 1.0 | 1 | 0 |
| `arm_kestrel_vest` | Kestrel Issue Vest | Kestrel Issue | body | 6 | 3 | 2 | 0 | 0 | 3.0 | 1 | 220 |
| `arm_sable_leathers` | Sable Works Leathers | Sable Works | body | 5 | 4 | 6 | 0 | 0 | 2.5 | 1 | 260 |
| `arm_ferry_scrap_plate` | Ferry-make Scrap Plate | Ferry-make | body | 10 | 4 | 3 | 0 | −4 | 7.0 | 1 | 300 |
| `arm_kestrel_helmet` | Kestrel Issue Helmet | Kestrel Issue | head | 4 | 2 | 1 | 0 | 0 | 1.0 | 1 | 120 |
| `arm_halvard_guard_suit` | Halvard Guard Suit | Halvard Ordnance | body | 12 | 8 | 6 | 0 | −2 | 5.0 | 2 | 1500 |
| `arm_ostrom_weave` | Ostrom Reflective Weave | Ostrom Optical | body | 6 | 14 | 4 | 0 | 0 | 2.0 | 2 | 1600 |
| `arm_sable_chem_suit` | Sable Works Chem Suit | Sable Works | body | 6 | 5 | 16 | 0 | 0 | 3.5 | 2 | 1400 |
| `arm_halvard_visor` | Halvard Tactical Visor | Halvard Ordnance | head | 8 | 6 | 3 | 0 | 0 | 1.5 | 2 | 800 |
| `arm_kestrel_greaves` | Kestrel Issue Greaves | Kestrel Issue | limbs | 6 | 3 | 3 | 0 | −1 | 2.5 | 2 | 700 |
| `arm_chapel_vestment` | Chapel Foundry Vestment | Chapel Foundry | body | 5 | 5 | 5 | 12 | 0 | 2.0 | 2 | 1500 |
| `arm_halvard_plate` | Halvard Breacher Plate | Halvard Ordnance | body | 24 | 14 | 10 | 0 | −10 | 14.0 | 3 | 6000 |
| `arm_ostrom_mirror` | Ostrom Mirror Shell | Ostrom Optical | body | 10 | 26 | 8 | 0 | −3 | 5.0 | 3 | 6200 |
| `arm_sable_widow_suit` | Sable Works Widow Suit | Sable Works | body | 12 | 10 | 26 | 0 | −2 | 4.5 | 3 | 5800 |
| `arm_halvard_breacher_helm` | Halvard Breacher Helm | Halvard Ordnance | head | 14 | 10 | 6 | 0 | −2 | 3.0 | 3 | 2800 |

#### 3.1 Standard implants

| ID | Name | Maker | Slot | Tol | Effect | Tier | Price |
|---|---|---|---|---|---|---|---|
| `imp_ostrom_lowlight` | Ostrom Lowlight Eyes | Ostrom Optical | eyes | 1 | sight radius +3 in dark zones | 1 | 600 |
| `imp_sablier_sub_dermal` | Sablier Subdermal Mesh | Sablier | torso | 1 | arm_k +3 | 1 | 700 |
| `imp_sablier_adrenal` | Sablier Adrenal Governor | Sablier | torso | 1 | stamina regen +50 % | 1 | 650 |
| `imp_kestrel_loadframe` | Kestrel Loadframe Spine | Kestrel Issue | spine | 1 | carry weight +15 kg | 1 | 500 |
| `imp_sablier_secure_pocket` | Sablier Secure Pocket | Sablier | torso | 1 | +1 secured inventory slot | 1 | 900 |
| `imp_ostrom_rangefinder` | Ostrom Rangefinder | Ostrom Optical | eyes | 1 | range penalty halved | 2 | 1800 |
| `imp_halvard_reflex_arm` | Halvard Reflex Arm | Halvard Ordnance | arms | 2 | weapon cooldown −10 % | 2 | 2200 |
| `imp_halvard_stabiliser` | Halvard Stabiliser Arm | Halvard Ordnance | arms | 2 | accuracy +8 with kinetic | 2 | 2000 |
| `imp_sablier_shock_sink` | Sablier Shock Sink | Sablier | spine | 2 | shock decay ×2 | 2 | 2100 |
| `imp_sablier_clotting` | Sablier Clotting Glands | Sablier | torso | 2 | chemical damage-over-time halved | 2 | 1900 |
| `imp_sablier_sprint_legs` | Sablier Sprint Legs | Sablier | legs | 2 | sprint tile time 80 ms; stamina cost −20 % | 2 | 2400 |
| `imp_ow_ghost_step` | Old Works Ghost Step | Old Works Collective | legs | 2 | stealth stance sight reduction 60 % instead of 50 % | 2 | 2300 |
| `imp_ostrom_target_lock` | Ostrom Target Lock | Ostrom Optical | head | 2 | target retained through cover; shows target health | 2 | 1700 |
| `imp_sablier_second_heart` | Sablier Second Heart | Sablier | torso | 3 | health +40 | 3 | 5500 |
| `imp_halvard_dermal_plate` | Halvard Dermal Plate | Halvard Ordnance | torso | 3 | arm_k +8, arm_e +4; evasion −3 | 3 | 5200 |
| `imp_sablier_secure_vault` | Sablier Secure Vault | Sablier | spine | 2 | +2 secured slots | 3 | 4800 |
| `imp_sablier_detox_gland` | Sablier Detox Gland | Sablier | torso | 2 | drug crash duration halved; addiction window halved | 3 | 4400 |
| `imp_ow_drone_uplink` | Old Works Drone Uplink | Old Works Collective | head | 2 | Operator: +1 drone slot; others: may run one drone | 3 | 5000 |
| `imp_halvard_heavy_mount` | Halvard Heavy Mount | Halvard Ordnance | arms | 3 | Hardline: heavy weapon cooldown −15 % | 3 | 5800 |

#### 3.2 Rig implants

| ID | Name | Maker | Slot | Tol | Slots | Effect | Tier | Price |
|---|---|---|---|---|---|---|---|---|
| `imp_rig_native` | Native Rig (Ghost only, built in) | Sablier template | rig | 0 | 3 | jack in anywhere | — | — |
| `imp_rig_ow_jury` | Old Works Jury Rig | Old Works Collective | rig | 1 | 3 | jack in anywhere; trace gain +10 % | 1 | 1200 |
| `imp_rig_sablier_clinical` | Sablier Clinical Rig | Sablier | rig | 2 | 4 | jack in anywhere; integrity +10 | 2 | 3600 |
| `imp_rig_ow_deepwater` | Old Works Deepwater Rig | Old Works Collective | rig | 3 | 6 | jack in anywhere; cell move time −20 %; Silt movement benefit; descent allowed with any rig | 3 | 8000 |

#### 3.3 Resonance implants (Cantor only)

| ID | Name | Maker | Slot | Tol | Effect | Tier | Price |
|---|---|---|---|---|---|---|---|
| `imp_res_first_ear` | Chapel First Ear | Chapel Foundry | head | 1 | unlocks hymns tier 1; Listening +10 | 1 | 900 |
| `imp_res_throat` | Chapel Throat | Chapel Foundry | spine | 1 | unlocks dissonance tier 1 | 1 | 900 |
| `imp_res_second_ear` | Chapel Second Ear | Chapel Foundry | eyes | 2 | hidden cells visible within 2 cells; Listening +15 | 2 | 2600 |
| `imp_res_chord` | Chapel Chord | Chapel Foundry | spine | 2 | unlocks hymns tier 2; hymns affect 8 tiles; unlocks dissonance tiers 1-2; replaces Throat | 2 | 2800 |
| `imp_res_tremor` | Chapel Tremor | Chapel Foundry | arms | 2 | dissonance abilities +20 % damage | 2 | 2700 |
| `imp_res_ninefold_lattice` | Chapel Ninefold Lattice | Chapel Foundry | head | 3 | unlocks hymns and dissonance tiers 1-3; replaces First Ear | 3 | 7000 |
| `imp_res_tenant_ear` | Chapel Tenant's Ear | Chapel Foundry | eyes | 3 | during Choir Surge: sees all ICE class and integrity; Silt residuals speak first | 3 | 7500 |
| `imp_res_silence` | Chapel Silence | Chapel Foundry | torso | 2 | arm_d +15; immune to knockdown from dissonance | 3 | 4500 |

#### 4. Hymns and dissonance (Cantor abilities)

| ID | Name | Kind | Tier | Cast | CD | Effect |
|---|---|---|---|---|---|---|
| `hymn_steady` | Steady | hymn | 1 | 0.5 s | 12 s | crew shock −20 immediately |
| `hymn_mend` | Mend | hymn | 1 | 1.0 s | 15 s | crew health +15 over 5 s |
| `hymn_march` | March | hymn | 2 | 1.0 s | 30 s | crew stamina cost −50 % for 10 s |
| `hymn_ward` | Ward | hymn | 2 | 1.5 s | 40 s | crew arm_all +5 for 12 s |
| `hymn_ninefold` | Ninefold | hymn | 3 | 2.0 s | 90 s | crew: pick up a downed member instantly, once |
| `dis_jam` | Nerve-jam | dissonance | 1 | 0.5 s | 8 s | target weapon cooldowns +50 % for 4 s |
| `dis_stutter` | Stutter | dissonance | 1 | 0.5 s | 10 s | target movement 400 ms/tile for 4 s |
| `dis_shear` | Shear | dissonance | 2 | 1.0 s | 14 s | 25 dissonance damage, +20 shock |
| `dis_hush` | Hush | dissonance | 2 | 1.0 s | 20 s | target cannot use consumables or hymns for 6 s |
| `dis_choir` | Choir | dissonance | 3 | 2.0 s | 60 s | 30 dissonance damage to every hostile within 4 tiles, +30 shock |

#### 5. Rigs, programs and Lattice gear

| ID | Name | Slots | Wt | Tier | Price |
|---|---|---|---|---|---|
| `item_rig_portable_ow_brick` | Old Works Brick | 3 | 2.0 | 1 | 800 |
| `item_rig_portable_ow_slab` | Old Works Slab | 5 | 2.5 | 2 | 3000 |
| `item_rig_portable_halvard_case` | Halvard Field Case | 6 | 3.5 | 3 | 7000 |

#### 6. Drugs

| ID | Name | Maker | Effect | Duration | Crash | Window | Price |
|---|---|---|---|---|---|---|---|
| `drug_sablier_focus` | Focus (labelled) | Sablier | accuracy +10 | 120 s | accuracy −10 | 30 min | 60 |
| `drug_sablier_calm` | Calm (labelled) | Sablier | shock decay ×2 | 180 s | shock decay ×0.5 | 30 min | 50 |
| `drug_sable_redline` | Redline | Sable Works | weapon cooldown −20 % | 90 s | cooldown +20 % | 20 min | 120 |
| `drug_sable_glass` | Glass | Sable Works | evasion +10, sight +2 | 90 s | evasion −10 | 20 min | 130 |
| `drug_sable_brick` | Brick | Sable Works | arm_k +8, stamina cost +20 % | 120 s | arm_k −8 | 30 min | 110 |
| `drug_sable_deepwater` | Deepwater | Sable Works | Lattice: cell move −30 %, trace gain +20 % | 300 s | move +30 % | 30 min | 180 |
| `drug_ow_static` | Static | Old Works Collective | Lattice: integrity +20 | 240 s | integrity −20 | 40 min | 200 |
| `drug_chapel_hush` | Hush (sacrament) | Chapel Foundry | Listening +20; Cantor cast −25 % | 180 s | Listening −20 | 60 min | 150 |
| `drug_ferry_ringdust` | Ring-dust | Ferry-make | stamina regen ×3; health −1/s | 60 s | stamina regen ×0.3 | 15 min | 40 |
| `drug_sable_lullaby` | Lullaby | Sable Works | health +30 over 10 s; movement 400 ms/tile | 30 s | health −10 | 20 min | 90 |
| `drug_sable_chrome` | Chrome | Sable Works | tolerance +1 (temporary; implant installed under it fails when it wears off unless Vitals grew) | 20 min | shock +40 | 24 h | 500 |

#### 7. Consumables

| ID | Name | Maker | Class | Effect | Price |
|---|---|---|---|---|---|
| `con_sablier_patch` | Sablier Med Patch | Sablier | heal | health +25 | 40 |
| `con_sablier_trauma_kit` | Sablier Trauma Kit | Sablier | heal | health +60; 2 s use time | 150 |
| `con_kestrel_ration` | Kestrel Ration Bar | Kestrel Issue | food | stamina +20; removes Ring-dust crash | 10 |
| `con_sable_stim` | Sable Works Stim | Sable Works | stim | stamina full; shock +10 | 45 |
| `con_sablier_neutraliser` | Sablier Neutraliser | Sablier | antidote | ends chemical damage-over-time | 60 |
| `con_ow_cell_charger` | Old Works Cell Charger | Old Works Collective | tool | recharges one energy cell anywhere; 3 uses | 200 |
| `con_ferry_flare_stick` | Ferry-make Flare Stick | Ferry-make | light | sight radius 8 for 3 min in dark zones | 15 |
| `con_halvard_breach_charge` | Halvard Breach Charge | Halvard Ordnance | tool | destroys a locked (not hackable-only) door; 5 s fuse; noise alerts zone | 350 |
| `con_sablier_pickup` | Sablier Pickup Kit | Sablier | revive | pick up a downed crew member in 2 s instead of 5 | 120 |
| `con_kestrel_beacon` | Kestrel Convoy Beacon | Kestrel Issue | tool | during a Convoy event, marks your position to the convoy; the convoy detours | 80 |

#### 8. Drones (Operator)

| ID | Name | Maker | Health | Evasion | Range | Weapon / tool | Tier | Price |
|---|---|---|---|---|---|---|---|---|
| `drn_kestrel_mule` | Kestrel Mule | Kestrel Issue | 60 | 5 | 8 | carrier: +20 kg carry | 1 | 400 |
| `drn_ostrom_eye` | Ostrom Eye | Ostrom Optical | 20 | 25 | 14 | scout: reveals sight radius 6 around itself; silent | 1 | 500 |
| `drn_halvard_sentry` | Halvard Sentry | Halvard Ordnance | 80 | 5 | 6 | kinetic 12 dmg, range 6, CD 1.0 | 2 | 1800 |
| `drn_sable_stinger` | Sable Works Stinger | Sable Works | 35 | 20 | 8 | chemical 8 (+4/s 3 s), range 4, CD 1.2 | 2 | 1600 |
| `drn_sablier_medic` | Sablier Medic | Sablier | 40 | 15 | 6 | heals crew +8/s within 2 tiles | 2 | 2000 |
| `drn_ow_relay` | Old Works Relay | Old Works Collective | 30 | 15 | 10 | terminal on legs: jack in from the drone's tile; drone destroyed = forced jack-out | 3 | 4200 |
| `drn_halvard_hound` | Halvard Hound | Halvard Ordnance | 120 | 10 | 8 | melee 30 kinetic, CD 1.0; hunts a target you mark | 3 | 5000 |
| `drn_ferry_lifter` | Ferry-make Lifter | Ferry-make | 90 | 5 | 6 | carrier: +60 kg; can carry salvage grade `intact` | 3 | 3800 |

#### 9. Salvage

| ID | Grade | What it was | Wt per unit | Base price | Fabrication use |
|---|---|---|---|---|---|
| `slv_hull` | hull | panels, booms, shielding | 4.0 | 15 | frames, plate, scrap bolts |
| `slv_optics` | optics | lenses, sensors, mirrors | 1.0 | 60 | sights, eyes, energy emitters |
| `slv_power` | power | cells, capacitors, radioisotope units | 2.5 | 80 | energy weapons, cells, drones |
| `slv_compute` | compute | boards, memory, radiation-hardened cores | 0.5 | 120 | rigs, programs, drone brains |
| `slv_intact` | intact | a component that still works | 3.0 | — | season contribution; tier-3 schematics |

#### 10. Schematics

| ID | Makes | Salvage cost | Skill min | Source |
|---|---|---|---|---|
| `sch_scrap_bolts` | `ammo_scrap` ×20 | hull 1 | 0 | any Ferrymen vendor, 50 |
| `sch_scrap_plate` | `arm_ferry_scrap_plate` | hull 6 | 10 | Ferrymen vendor, 200 |
| `sch_slugthrower` | `wpn_ferry_slugthrower` | hull 4, power 1 | 10 | Ferrymen vendor, 250 |
| `sch_ring_wrench` | `wpn_ferry_wrench` | hull 2 | 0 | Ferrymen vendor, 80 |
| `sch_flare_stick` | `con_ferry_flare_stick` ×5 | power 1 | 0 | Ferrymen vendor, 60 |
| `sch_cell` | `ammo_cell` ×1 | power 1 | 15 | Old Works vendor, 300 |
| `sch_arcpen` | `wpn_ow_arcpen` | power 2, optics 1 | 20 | Old Works vendor, 400 |
| `sch_coilgun` | `wpn_ow_coilgun` | hull 3, power 3, compute 1 | 35 | Old Works, standing +30, 1500 |
| `sch_jury_rig` | `imp_rig_ow_jury` | compute 3, power 1 | 30 | Old Works, standing +30, 1200 |
| `sch_meteor_cannon` | `wpn_ferry_meteor_cannon` | hull 8, power 2 | 40 | Ferrymen, standing +30, 1800 |
| `sch_ringfall_rifle` | `wpn_ferry_ringfall_rifle` | hull 6, optics 3, intact 1 | 60 | Ferrymen, standing +60, 4000 |
| `sch_railpistol` | `wpn_ow_railpistol` | power 4, compute 2, intact 1 | 60 | Old Works, standing +60, 4500 |
| `sch_deepwater_rig` | `imp_rig_ow_deepwater` | compute 6, power 3, intact 2 | 70 | core data, Old Works tier-3 core only |
| `sch_lifter` | `drn_ferry_lifter` | hull 8, power 3, compute 1 | 45 | Ferrymen, standing +40, 2500 |
| `sch_stinger` | `drn_sable_stinger` | hull 2, power 2, compute 1 | 30 | Sable vendor, standing +20, 1000 |
| `sch_etcher` | `wpn_sable_acid_blade` | hull 2, intact 1 | 50 | Sable, standing +50, 3000 |
| `sch_mirror_shell` | `arm_ostrom_mirror` | optics 8, hull 3, intact 1 | 65 | core data, Spire tier-3 core only |
| `sch_hunterkiller` | `prg_hunter_killer` | compute 5, intact 1 | 60 | core data, Silt only |

#### 11. Starter kit (end of the Wake, design §4)

| Item | Qty |
|---|---|
| `arm_wake_coverall` | worn |
| `wpn_kestrel_sidearm` | 1 |
| `ammo_9x` | 1 stack (50) |
| `wpn_kestrel_baton` | 1 |
| `con_sablier_patch` | 2 |
| `con_kestrel_ration` | 2 |
| chits | 200 |
| `story_vesper_card` (*Vesper, Tin Halo, Sodium Row*) | 1 |

#### 12. Vendor inventories

| Vendor | Zone | Stock | Tier |
|---|---|---|---|
| Kestrel Depot Counter | Tramyard | `wpn_kestrel_sidearm`, `wpn_halvard_hv7`, `wpn_kestrel_flare_pistol`, `wpn_kestrel_baton`, `arm_kestrel_vest`, `arm_kestrel_helmet`, `con_kestrel_ration`, `con_kestrel_beacon`, `imp_kestrel_loadframe` | list |
| Kestrel Convoy Armoury | Tramyard | `wpn_kestrel_convoy_smg`, `arm_kestrel_greaves`, `wpn_kestrel_gate_gun` (standing +60) | member |
| Halvard Public Concourse | The Spire | `wpn_halvard_hv7`, `arm_halvard_visor`, `imp_halvard_stabiliser`, `wpn_halvard_shock_baton` | list |
| Halvard Security Issue | The Spire | `wpn_halvard_hv9`, `wpn_halvard_dmr`, `arm_halvard_guard_suit`, `imp_halvard_reflex_arm`, `drn_halvard_sentry`; `wpn_halvard_hv12`, `wpn_halvard_anvil`, `arm_halvard_plate`, `arm_halvard_breacher_helm`, `wpn_halvard_ram`, `imp_halvard_dermal_plate`, `imp_halvard_heavy_mount`, `drn_halvard_hound` (standing +60) | member |
| Ostrom Showroom | The Core | `wpn_ostrom_pinlight`, `imp_ostrom_lowlight`, `imp_ostrom_rangefinder`, `drn_ostrom_eye`, `ammo_cell` | list |
| Ostrom Contract Sales | The Spire | `wpn_ostrom_lance`, `wpn_ostrom_arc_projector`, `arm_ostrom_weave`, `imp_ostrom_target_lock`; `wpn_ostrom_scalpel`, `wpn_ostrom_sunlance`, `wpn_ostrom_pulse_carbine` (Halvard or Sablier member, standing +50) | restricted |
| Sablier Clinic (any) | Vatside, faction halls | all Sablier implants, `con_sablier_patch`, `con_sablier_trauma_kit`, `con_sablier_neutraliser`, `con_sablier_pickup`, `drug_sablier_focus`, `drug_sablier_calm`, detox, surgery | list |
| Sablier Wake Outfitter | Vatside | starter kit items, `arm_wake_coverall` | list |
| Warden Quartermaster | The Core | Civic Pattern equivalents of `arm_halvard_guard_suit`, `wpn_halvard_hv9`, `wpn_halvard_shock_baton` (same stats, blue) | member |
| Sink Market | The Sink | `wpn_sable_streetsweeper`, `wpn_sable_spitter`, `wpn_sable_shiv`, `arm_sable_leathers`, `con_sable_stim`, all Sable drugs, `ammo_gel`, `ammo_needle` | list |
| Sable Works Back Room | The Sink | `wpn_sable_needler`, `wpn_sable_pump`, `wpn_sable_torch`, `wpn_sable_machete`, `arm_sable_chem_suit`, `drn_sable_stinger`; `wpn_sable_widow`, `arm_sable_widow_suit`, `sch_etcher` (standing +50) | member |
| Black Clinic | The Sink | any standard implant at 60 % list, 15 % failure; `drug_sable_chrome` | list |
| Old Works Bench | Old Works | `wpn_ow_arcpen`, all tier-1 and tier-2 programs, `item_rig_portable_ow_brick`, `item_rig_portable_ow_slab`, `imp_rig_ow_jury`, `con_ow_cell_charger`, `drug_ow_static`, `sch_cell`, `sch_arcpen` | list |
| Old Works Deep Bench | Old Works | `wpn_ow_coilgun`, `wpn_ow_arc_knuckles`, `imp_ow_ghost_step`, `imp_rig_sablier_clinical` (stolen stock), `imp_ow_drone_uplink`, tier-3 programs; `wpn_ow_railpistol`, `sch_railpistol`, `drn_ow_relay` (standing +60) | member |
| Chapel Almoner | Chapel Ward | `arm_chapel_vestment`, `drug_chapel_hush`, `imp_res_first_ear`, `imp_res_throat` (Cantor, Choir standing +20) | restricted |
| Chapel Foundry | Chapel Ward | `wpn_chapel_tuning_fork`, all tier-2 resonance implants; `wpn_chapel_choir_bell`, `wpn_chapel_hand_bell`, tier-3 resonance implants (standing +60) | member |
| The Landing Trade Post | The Landing | `wpn_ferry_slugthrower`, `wpn_ferry_wrench`, `arm_ferry_scrap_plate`, `con_ferry_flare_stick`, `drug_ferry_ringdust`, `ammo_scrap`, tier-1 schematics; buys salvage at +20 % | list |
| Ferry's Own | The Landing | `wpn_ferry_meteor_cannon`, `drn_ferry_lifter`, tier-2 and tier-3 Ferry-make schematics (standing gates as listed) | member |
| The Tin Halo (Vesper) | Sodium Row | contracts, rumours, `drug_sable_glass`, `con_sable_stim`, one rotating tier-2 item per day from any maker at +40 % | list |

#### 13. Apartments

| ID | Name | Storage slots | Core tier | Rent / week |
|---|---|---|---|---|
| `apt_terrace_cell` | Terrace Cell | 40 | 1 | 300 |
| `apt_terrace_flat` | Terrace Flat | 80 | 2 (upgradeable to 3, 2 000 chits) | 900 |
| `apt_terrace_corner` | Corner Flat | 120 | 3 | 2 200 |

#### 15. Passes, charges and story items

| ID | Name | Class | Source | Wt | Price | Line |
|---|---|---|---|---|---|---|
| `key_containment_charge` | Containment Charge | consumable | Halvard vendor, standing +50 | 1.5 | 1 500 | Cuts a core's power from any tile within 3 of its hardware, through the wall. Single use. Halvard's answer to a locked server room. |
| `key_curfew_pass` | Curfew Pass | pass | Warden vendor, standing +30 | 0.1 | 400 | Admits the holder to the Core during a Curfew. Expires after 7 days. Marked holders are refused at the line. |
| `key_row_pass` | Row Pass | pass | Red Sable vendor, standing +30 | 0.1 | 250 | Opens a nonessential Sable back-room shortcut. Public bars and boards remain available. |
| `key_visitor_pass` | Spire Visitor's Pass | pass | Halvard vendor, or lifted from the Gatehouse pass registry | 0.1 | 600 | Admits one non-Halvard character to the Spire Mezzanine for 30 minutes. |
| `key_silt_beacon` | Silt Beacon | consumable | Choir vendor, standing +30 | 0.5 | 900 | Marks a descent cell for the crew for one hour; crew members see it on the sector view from any cell. |
| `key_ringfall_chart` | Ring-fall Chart | data | Ferrymen Charter rank (+70) reads it at the Landing | 0.2 | 1 200 | Names the next Ring-fall ring one hour early. Sells to anyone who did not earn it. |
| `story_vesper_card` | Vesper's Card | misc | starter kit | 0.1 | — | A contract card. *Vesper, Tin Halo, Sodium Row.* |
| `story_telemetry_unit_warm` | Warm Telemetry Unit | data | Halvard Season 1 | 0.5 | — | Site Zero salvage that is still warm. |
| `story_halvard_seal_beacon` | Seal Beacon | misc | Halvard Season 1 | 0.5 | — | A monitor beacon Halvard wants planted at the seal. |
| `story_sealed_template_canister` | Sealed Template Canister | misc | Sablier Season 1 | 0.5 | — | A canister from below the outworks. Sablier does not say what is in it. |
| `story_template_shield_rig` | Template Shield Rig | misc | Unmoored Season 1 | 0.5 | — | Shields walked templates from Sablier's recall signal. |
| `story_resonance_beacon` | Resonance Beacon | misc | Choir Season 1 | 0.5 | — | Quell's beacon for a cell that should not exist. |
| `story_listening_stake` | Listening Stake | misc | Ferrymen Season 1 | 0.5 | — | A stake the Ferrymen drive at a conduit head to hear it hum. |
| `story_residual_fragment_99b` | Residual Fragment 99-B | data | Unmoored Season 1 | 0.5 | — | A second copy of Ninety-Nine that says one thing. |
| `story_unmoored_drop_cache` | Drop Cache | misc | Unmoored Season 1 | 0.5 | — | The cache under Terrace Nine. |
| `story_authority_image_copy` | Authority Image Copy | data | Halvard Season 2 | 0.5 | — | A copy of the Dispatcher's process image. |
| `story_holt_manual_schedule` | Holt's Hand Schedule | data | Kestrel Season 2 | 0.5 | — | A convoy schedule written by hand. Late, unreliable, human. |
| `story_choir_beacon_2` | Choir Beacon II | misc | Choir Season 2 | 0.5 | — | A beacon for the shaft head. |
| `story_ferrymen_repeater` | Ferrymen Repeater | misc | Ferrymen Season 2 | 0.5 | — | A repeater for the Far Relay. |
| `story_stuck_door_package` | Stuck-door Package | misc | Vesper's first contract | 0.5 | — | A package behind a door that sticks. |

### 17.2 Programs

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

### 17.3 ICE

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

## 18. Design acceptance before calling it compelling

These are required future verification scenarios, not tests already run.

| Scenario | Success criterion | Owning slices |
|---|---|---|
| Fresh solo Wake of each archetype | finish briefing, run loan terminal, complete first job without a class gate | S07, S13, S19, S30 |
| Repair with two opposing memberships | each role contributes; one allocation commits; both screens show same route and expiry | S15, S19, S21, S24 |
| Records disagree | operational finding available without reading full text; sources remain distinguished | S19, S27 |
| Silt without special gear | infer Chorister procedure, survive warning, find riser or jack out | S14 |
| Mixed crew splits layers | guard and runner receive one completion credit each; idle bystander does not | S22 |
| One-player finale and five-player finale | same meaningful options, sequential and parallel solutions, recoverable interrupted phase | S26 |
| Conflicting finales and replay | personal entries persist, one identity/ballot, settlement independent of last finisher | S26 |
| Death while poor, then return after absence | usable recovery kit, retained legal status/evidence, no service or forecast rerolls | S10, S16, S24 |
| 80×24 and 132×50 with wide handle | current danger, escape, objective, and cost remain readable without opening scrollback | S04, S30 |

Human sessions must establish whether choices feel different, preparation
helps, failure teaches, and another player changes the experience. Timing
and economy targets in the catalog are unvalidated hypotheses. An automated
validator cannot establish fun. Unresolved balance values may be tuned in
the owning slice with same-PR canon propagation, never invented silently.

The Level 1 maintenance drone uses health 40, kinetic damage 6, cooldown
2 s, range 5, accuracy 60. Finale control channels are 3 s in the network,
5 s at hardware, with 120 s sequential latches. Level 2 pulse lanes warn
5 s, remain live 5 s, and deal 5 energy damage/s. S26 converts these values
from this section. No player must finish reading during a live hazard.
