# Sodium Row: experience design (proposal)

**Status:** owner decisions of 2026-10-31 recorded in §10 (Q1 to Q6).
This file stays a design record. Canon changes still go top-down in
their own PRs (Q4: gazetteer), and geometry stays behind S25c and H3.
**Author:** creative consultant (Claude Opus 5.5), 2026-10-31.
**Scope:** `sodium-row` and `sodium-tin-halo`. Base: `main` at 6f1eac4,
the truce decision in #141 (S38), and the place layer in #126 (P6b).

Each claim below is labelled:

- **[canon]**: already in the bible, gazetteer, cast or design docs.
- **[built]**: works on `main` today.
- **[dormant]**: built but switched off (an authoring bundle).
- **[new]**: my proposal.

## 1. What the Row is for

Karst has three places where people go to spend money after work, and
the Row has to stand apart from the other two:

| Place | What it sells | Who owns it |
|---|---|---|
| Warmwater | comfort: baths, rooms, being looked at | the Lamp Compact, with relays [canon] |
| Tramyard Market | goods, loudly, by day | Kestrel [canon] |
| **Sodium Row** | **the truce: a place to meet anyone** | **nobody, on paper** [canon] |

The Row's product is neutral ground. It is the only street where a
Halvard guard and an Unmoored runner drink fifty metres apart and nothing
happens, and the only one where every faction's people can be seen at
once. Vesper arranged that and sells access to it [canon]. Everything on
the Row should serve three pillars:

1. **The truce you can feel.** Nobody is attacked for their colours.
   Drawing is possible from grade 5, and it is never free (§5).
2. **The whole city on one street.** Each bar has its crowd by custom,
   not by ownership, so walking the Row means reading the city's
   politics from who drinks where.
3. **Information has a price ladder.** Street talk is free and unreliable.
   Vesper's word costs chits and is true. The Halo's core can be robbed,
   and Vesper notices [canon]. The House Lights ledger records who
   came to the Row and when [canon]. The Row remembers.

Not the Row's job: sex work and pleasure houses (Warmwater's, since #91),
faction territory (no relays, by agreement [canon]), and a black market
(the Sink's).

## 2. What a player experiences today

From the content on `main`, the P6b captures (#126) and the
inventory of live systems:

- **A parking lot.** The map is one open 98 × 28 floor. Bars are counters
  standing in the open, named "Row bar 1" to "Row bar 5" [built]. The
  gazetteer's alcoves, doorways and alleys don't exist.
- **Counters that do nothing.** Only Vesper sells. The five bars, the
  drug dealer, the ticket tout, the Halo bar and the Ferrymen liaison
  answer "That counter is not open" [built].
- **Nobody speaks.** All 44 dialogue files, including Vesper's, Dolf's and
  Mira Solenne's, are dormant. Talkers answer "Not yet." [dormant]
- **One crowd.** All five "Sodium regulars" and four "Halo regulars" are
  Sable members [built]. "Every faction's off-duty members" [canon] is
  not expressed.
- **The rule was inverted.** Enforcers shot four factions on sight. The
  owner has since approved the truce (S38, #141).
- **Nothing happens here.** Every Vesper job sends you elsewhere. The Row
  is a corridor to the Halo's door.
- **The Halo is a bowling alley.** 44 × 22 with sight 8, so Vesper is not
  the centre of the room (owner verdict, V0).

What already works well and should be kept: the arrival paragraph, the
first-contract chain (Vantongeren's card, then Vesper, then the Terraces),
Vesper's daily rotating stock [built], her referral bypass for hostile
handlers [built], the stage blackout and back-room door controls in the
Lattice [built], and the plainclothes Warden's disguise [built].

## 3. The places

Map sketch below is a proportion guide for S25c, about 1 character per
2 to 3 tiles. The geometry stays frozen behind S25's layout gate; this
is the intent the gate judges, not an authored map.

```
######################################################################
#    |UPSTAIRS |LONG SHIFT|QUARTER TONE|THE CLAUSE |SPARE PARTS|  >  #  > Old Works
#    |   $  ..  |  $  ...  |   $  ..    |  $  ...   |  $  ..  T |     #    (later)
# S  ####+#######+##########+############+###########+#######  ##### #
# T  :E .........................................................   #
# A  :............................ the Strip ......................H #  H Halo door:
# I  :E......#####.......%%..T.....%%.......T..........E..... ##+## #    end of the view
# R  :.......#STAGE#..pit......#####[card court]#####.......  #   # #
# >  #####...#####..#########..#####....$$....######..#####.. #   # #
#          .|alley  $Solenne.......%%....[house lights]......+back #
######################################################################
 E  Sable enforcer post    : the Stair landing    $ counter / anchor
 T  public terminal        %  cover               H  the Tin Halo
```

### 3.1 The Neon Stair foot (arrival)

- **Purpose:** the threshold where Warden law ends and Sable's truce
  begins. It's also the only way back to the safe Core [built].
- **Distinct because:** you arrive above the street, on the landing.
  The Strip runs away from you to the Tin Halo's half-burnt sign, which
  closes the far end of the view.
- **You perceive:** the Halo sign straight ahead, enforcers posted at the
  bottom of the steps, the header `CONTESTED─TRUCE─PvP G5+` (S38).
- **You do:** arrive, leave, wait for someone. During Curfew the Stair
  gate is shut [built: entry restriction]. The Row fills with people who
  can't get home, which the Warden curfew log already describes [canon].
- **Systems:** exit; guard spawner posts; `event:curfew` spawner for the
  crowd at the gate [built].
- **Extra work:** geometry (landing, sightline), S25c.
- **Presentation:** presentation lead's. At 132 × 50 the view down the
  street ends on the Halo sign. At 80 × 24 the arrival and the Halo door
  share one axis, the Halo carries a sign band facing down the Strip,
  and a painted "TIN HALO →" street sign stands at the landing. Painted
  signs count as in-world cues in playtest 1; frame labels don't.
- **Playtest passes if:** on first arrival the player walks toward the
  Halo without consulting the map label.

### 3.2 The Strip and its five bars

- **Purpose:** the city's meeting ground, read from left to right.
- **Distinct because:** each bar is a doorway into a shallow alcove with
  its own crowd by custom. Each alcove has a street wall face at least
  14 tiles wide, with its doorway on that face, to carry its sign. Order runs from respectable to rough with
  distance from the Stair, so the walk itself tells you something.

| Bar [new name] | Crowd by custom | Why there |
|---|---|---|
| **Upstairs** | Halvard and Sablier staff | nearest the Stair; the shortest walk back to safety |
| **The Long Shift** | Kestrel drivers and depot crews | loud, cheap, full at every shift change |
| **The Quarter Tone** | Choir and Cantors | music kept low; Solenne's best customers [canon] |
| **The Clause** | Wakes, strays, Ferrymen in town | drinks to day ninety; "stray" is no insult here [canon] |
| **Spare Parts** | Unmoored runners | Old Works end; a public terminal inside [canon: most bars have one] |

No bar for Wardens or Sable, deliberately. Wardens drink on the Row only
in plain clothes, and Sable keeps no bar: it plays cards at the court,
sells at the alley mouth and watches. That is the politics, in
geography. Canon's "music from six doorways" is the five bars and the
Halo.

- **You perceive:** whose colours sit in which doorway, which crowd goes
  quiet when you walk in, which bar's prices are kinder to you.
- **You do:** buy drinks; prices move with your standing with that bar's
  faction [built: reputation pricing]. Your own faction's bar is cheaper
  and an enemy's bar costs more. Meet people. Jack in at Spare Parts.
- **Systems:** vendors with faction and stock [built]; spawners per
  alcove with faction NPC templates [built]; presented faction colour
  [built]; talker lines by `member_of` / `enemy_of_me` [dormant].
- **Extra work:** drink items. The canon "small shock reduction" doesn't
  exist as an item; it's a catalog entry and a game design number.
  New NPC templates per crowd (content). Bar names into the gazetteer
  and glossary once approved.
- **Presentation:** each bar's sign and light carries its crowd, e.g.
  Kestrel orange at the Long Shift, without colour being the only cue.
  The presentation lead owns how.
- **Playtest passes if:** after one walk the player can say which bar
  belongs to which crowd, and gives directions like "past the stage, the
  Choir bar".

### 3.3 The stage and the pit

- **Purpose:** the Row's focus, and the target of its favourite mischief.
- **Distinct because:** the street widens in front of it into a standing
  pit, the one place crowds bunch.
- **You do:** watch, gather, emote [built: zone emotes]. A runner in the
  House Lights core can black out the stage lights: sight drops to 5 for
  30 seconds around it [built]. The Lattice canon calls it "stealth for
  everyone"; the build caps sight. Hunters see less rather than losing
  you outright, and the playtests use the built effect. That's the Row's sanctioned chaos, and
  it isn't an attack under the truce (S38).
- **Extra work, later:** the sign-grid message, a runner's 20-column text
  on every sign for 60 seconds [canon, not built]. The best multiplayer
  prank in the design, but new engineering and moderation; see §8.
- **Playtest passes if:** a two-player test uses the blackout for
  something the designers didn't script.

### 3.4 The card court

- **Purpose:** Sable's corner of the street, and its free rumour exchange.
- **Distinct because:** a half-enclosed square off the Strip, tables as
  cover, Sable regulars playing.
- **You do:** listen. Card players' talk comes from the city's live state
  (`event_active`, `service_state` conditions [dormant]). It's sometimes
  stale, the free bottom rung of the ladder.
- **Not proposed:** a card game. New system, no core value (§8).

### 3.5 The back alley

- **Purpose:** "Deals made in the doorways and unmade in the alleys
  behind" [canon]. The getaway route, and the hardware behind the Row's
  lights.
- **Distinct because:** narrow, dark, two passages in, out of the Strip's
  sightline. Mira Solenne, Sable's franchisee [canon cast], works its
west mouth [new placement]. The House
  Lights sign-grid room is here [canon], so a crew cutting the Row's
  lights by hand stands in the alley.
- **Truce:** it applies here too, so the alley is not lawless. It is
  where pursuit is slow and witnesses are few.
- **Dark is mood, not rule.** Sight stays the zone's. The alley is
  dangerous because of its shape: out of the Strip's line of sight, two
  ways in, cover. The stage blackout is the only rule that darkens the
  Row.
- **Systems:** geometry, a hardware object [built], Solenne as a vendor
  (stock to author).
- **Playtest passes if:** a player who draws on the Strip thinks of the
  alley as a way out without being told.

### 3.6 The Tin Halo

- **Purpose:** where work and people meet. The one room on the Row where
  nobody can be touched (pocket [built]), and so the safest public chair
  to jack in from in the south of the city.
- **Distinct because:** small. The room is about 28 × 12 instead of
  44 × 22. The map stays at least 40 × 20 (game design §5.1's zone floor),
  with the room built inside it and the rest solid, so no rule changes.
  The whole room is visible (V0-3 lit pockets) and Vesper, at the end of the
  bar, faces the door [canon]: you see her the moment you enter, and she
  saw you first. Dolf behind the bar [canon, unplaced]. Booths for crews.
  The back room behind the bar.
- **You do:** take work and turn in any job [built]; buy Vesper's daily
  rotating item [built]: "what has Vesper got today" is a real reason to
  come back. Meet your crew. Jack in safely.
- **[new] The back room's alley door.** The back room gets a second door
  into the alley. The Halo core's `back-door` control already opens the
  back room for 300 seconds [built]. With an alley door, that control
  becomes a way out. This is a route change, so it's under the layout
  gate (§10, Q2, approved). It isn't free: the runner must get through
  the Halo core's ICE and Vesper notices [canon], and the alley door is
  in plain sight from the alley, so a hunter's crew that covers both
  doors wins. That balance is a playtest question.
- **Playtest passes if:** the owner calls the room intimate, and names
  Vesper as its centre without reading the label.

## 4. Who is there, and why

| Who | Where | Behaviour | Status |
|---|---|---|---|
| Sable enforcers ×2 | Stair foot, mid-Strip; always in view | guard; keep the truce | built, posts [new] |
| Off-duty crowds, 2 per bar | inside their alcove | wander in alcove | [new] templates |
| Sable card players ×2 | card court | idle talkers | [new] |
| Plainclothes Warden ×1 | moves between bars | talker, disguised | built |
| Mira Solenne | alley west mouth | vendor, talker | cast [canon], unplaced |
| Vesper, Dolf, bouncer, 3 regulars | the Halo | as canon | Dolf unplaced |
| Curfew crowd | at the Stair gate | `event:curfew` | [new] |

This is 16 NPCs on the Row against 8 today. The Row already misses the
132 × 50 CPU budget at 8 (P6b). The technical lead has added an 8/11/16
sweep to A8's evidence, so main gets no increase until it's measured.
The demo branch may run 16. Fallback: one per bar, keeping the card players (11).

Halo regulars become a mix of factions, not four Sable members.

## 5. The price and the getaway

The owner, 2026-10-31, in session with the creative consultant:

> In my vision, Sable makes indeed sure "nobody draws on Sodium Row".
> That should be interpreted as "Sable makes you pay for drawing --
> unless you are very skilled, in which case you might escape your
> punishment."

S38 as approved (#141) defines breaking the peace. It is an attack
whose target is on the Row and that is either an attack on a player
that Marks the attacker, or an attack on an NPC that wasn't already
hostile to the attacker. The truce follows the target's body, wherever
the shot, drone or burn comes from. The keeper (Sable) answers, and the
log says "Sable is coming for you." (presentation lead).

That definition suits the chase. Fighting your way out through
enforcers who are already after you doesn't break the peace again, and
your victim may fire back freely. The first shot is the crime; what
follows is the getaway. Three more things make it a price and not a
fine:

1. **Strong enough to lose to.** Today's enforcers are grade 1 with a
   Kestrel sidearm; a grade-5 veteran kills both. Two steps:
   - **Grade and kit (content).** Row enforcers get a template of their
     own, tuned so a solo grade-5+ player who stands and fights loses.
     The numbers go in game design with a test (§10, Q3).
   - **Reinforcements (new engine behaviour).** Responders summoned near
     the victim go beyond §5.5's local alert. The technical lead files
     it as a separate slice with its own approval, only if the tuned
     posts prove too easy in the demo.
2. **It follows you.** The Mark already does: 15 minutes in which anyone
   may hunt you and Wardens engage [built]. Add: Vesper's contract offer
   carries `not_marked` [dormant condition], so drawing on the Row costs
   you the Row's work until the Mark expires.
3. **Escape takes skill.** That's geometry: the sanctuary is up the
   Neon Stair into the safe Core, and enforcers post at its foot. The
   Halo next door is a pocket; whether it may shelter a truce-breaker is
   open (§10, Q7). During Curfew the Stair is shut, so on Curfew nights
   there is no sanctuary: the Row's most dangerous night, and it should
   say so. Two
   alley passages give a choice. Hunters give up 20 seconds after losing
   sight [built]. A crewmate can black out the lights for 30 seconds from
   the Lattice [built]. Those are the stories people tell.

## 6. Coming back: one player, five visits

No scripted quest. Every change below comes from state the game already
keeps (standing, grade, contracts, Mark, legal status, events), shown
through talker conditions that exist but are dormant.

1. **Day 3, Wake.** You come down the Stair with Vantongeren's card.
   The Clause is full of other Wakes. Vesper: "You've got the card. Sit."
   [canon]
2. **First thing done.** Every faction's standing is +5 [built], so every
   bar is a little cheaper. Dolf: "Good. You came back. Most don't the
   first week." [new line]
3. **Joined Kestrel.** The Long Shift is cheaper and its crowd talks to
   you (`member_of kestrel`); Upstairs is fine; at Spare Parts the
   runners go quiet (`enemy_of_me`). The street turns into a map of who
   you are.
4. **Grade 5.** The header's `PvP G5+` now means you. Dolf: "You can be
   shot on the Row now. Notice how nobody does." [new line] The truce
   is now something you rely on.
5. **Discharged.** `legal` holds. At the Clause: "Day zero. Nobody here
   owns your lease." [new line] Curfew night, the Stair shut, you sit
   in the Halo with a crew while the Row fills up outside.

Nothing here tells the player the Row has changed. It just treats them
differently.

## 7. Multiplayer situations the Row creates

None of these is scripted; each falls out of systems that exist:

- **The standoff.** A bounty target sits in the Halo (pocket, safe). The
  hunter waits on the Strip. A crewmate jacks in, flips the back-room
  door from the Halo core, and the target leaves by the alley. Needs Q2.
- **Enemies at neighbouring bars.** A Kestrel crew at the Long Shift, an
  Unmoored pair at Spare Parts. Nothing happens, and that's the point.
  When something does, it's a chase.
- **Blackout.** Somebody kills the stage lights. For 30 seconds, sight
  is 5 for everyone near it: a handoff, an escape, a joke.
- **Curfew night.** The Stair is shut and the Row is crowded with
  callers who can't get home.

## 8. Feasibility

| Item | Kind | Owner | Gate |
|---|---|---|---|
| Truce, Marking, provocation on players | rule (approved) | Codex, S38 | owner done |
| Enforcer posts, crowds, placement | content | me, after #126 | technical review |
| Bar vendors and stock | content | me | technical review |
| Drink items with shock reduction | content + numbers | me, game design edit | owner |
| Bar names, crowd custom | canon (gazetteer) | me | owner |
| `event:curfew` crowd | content | me | technical review |
| Vesper `not_marked` offer, crowd and Dolf lines | content, dormant system | me | needs speech live |
| Activating speech and barks | engineering, S27 and P8 | technical lead | plan order |
| Geometry: Stair landing, alcoves, alley, small Halo | layout | S25c | H3 |
| Halo back room to alley door | route change | S25c | owner, H3 |
| Enforcer grade and kit | content + numbers | me, game design edit | owner |
| Summoned reinforcements | new engine behaviour | separate slice, if needed | owner |
| Lattice cell names mirroring the Row | content | Sonnet batch | review |
| Sign-grid message | new engineering + moderation | later | owner |
| Card game, gambling | new system | not proposed | — |

**The single largest gap is speech.** Without live dialogue the Row's
people stay silent, and half of §6 can't be felt. The technical lead
says a narrow slice could deliver the cast as plain log lines after
#126 and S38. On main that changes the adopted sequence (cast delivery
waits for P8 and S25c), so it's an owner decision (§10, Q6). On the demo
branch it's allowed now.

## 9. Demonstration: one evening on Sodium Row

The smallest thing that lets the owner judge this design in play.

- **Form:** a demo branch, never merged, like the V0 spike. It runs
  through the existing local play path, behind a switch. Production maps
  and gates stay untouched.
- **Contents:**
  1. Candidate geometry for the Row and the Halo per §3, built from the
     presentation lead's #69 candidate.
  2. The population of §4, within a CPU count the technical lead sets.
  3. Speech switched on for Vesper, Dolf, Solenne and the crowds, about
     30 new lines, in plain log form.
  4. Bar vendors with drinks, and S38's truce if it has landed. If it
     hasn't, a demo-only stand-in.
  5. P6b's dressing extended to the new geometry by the presentation
     lead.
- **Three playtests, about 20 minutes each:**
  1. Arrive as a new Wake. Can you find the Halo without labels? Can you
     name the bars' crowds after one walk? Can you say the Row's rule?
  2. Return as a grade 5 faction member, with prepared state. Does the
     Row treat you differently? Do you want a drink in your own bar?
  3. Two callers on an ordinary night. One draws; does Sable make them
     pay, and does the getaway feel earned? Curfew night is a separate,
     optional run, because the Stair is shut and there is no sanctuary.
- **Split:** Codex's queue is full, so the creative consultant and the
  presentation lead build it from shipped systems: I do content, layout
  and speech, and the presentation lead does dressing and the switch.
  The technical lead reviews it for safety and disclosure only. Scope is
  agreed by all three before any code.

## 10. Decisions

Decided by the owner on 2026-10-31 (Q1 in #141; Q2 to Q6 recorded on
#143 by the technical lead):

| Q | Decision | What follows |
|---|---|---|
| Q1 | The truce: yes | S38 (#141) |
| Q2 | The Halo's back room gets an alley door: yes | production behind S25c and H3, with C1's Halo door (#92); allowed on the demo now |
| Q3 | The price: yes in direction, numbers first | concrete enforcer grade and kit to the owner before any PR; the fingerprint moves in that PR |
| Q4 | Five bars with crowds by custom: yes | gazetteer and glossary PR; map placement behind S25c; crowd sizes after A8's NPC sweep |
| Q5 | The demo: yes | branch never merged, outside the S25c gate; built by the creative consultant and the presentation lead; the technical lead reviews safety and disclosure |
| Q6 | Speech before P8 as plain log lines on `main`: yes | a narrow slice after #126 and S38, filed by the technical lead |

Open, raised in review after the decisions (to settle before playtest 3):

- **Q7. May the Halo shelter a truce-breaker?** The Halo is a pocket, so
  a Marked attacker can step in and wait out the Mark, which undercuts
  the price when the fight is near its door. Recommendation: the Halo
  refuses entry to a player Marked for breaking the Row's truce until the
  Mark ends. The refusal is a rule on entering the Halo zone by any
  entrance (the front door, or the alley door of Q2 however it was
  opened), voiced by the bouncer at the front. A crewmate who opens the
  back door from the Halo core opens it for everyone else, not for the
  truce-breaker. Players Marked elsewhere still get Vesper's "Sit at the
  back." This is a new rule (door refusal by Mark cause). The demo can
  try it before the owner decides; game design §7.6's "nobody can bar
  another player" is about players, not this.

## 11. Ideas recorded for later

Not part of this proposal; recorded so they don't widen it:

- The sign-grid message (canon, unbuilt), with chat-grade filtering.
- The Ferrymen liaison present in the Halo only during a Convoy
  (`event:convoy`, dormant event).
- An S37 dead drop in the back alley; S36 tags on the Strip, never in
  the Halo (a pocket).
- Night texture: `sight_radius_night` per zone exists [built]; the Row
  could be brighter at night than by day, which is true to a sodium
  street.
