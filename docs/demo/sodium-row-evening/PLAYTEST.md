# One evening on Sodium Row: playtest scripts

Demo only, on `demo/sodium-row-evening` (never merged). The design is
`docs/design/proposals/sodium-row-experience.md` (#143). These scripts
test whether the Row is a place, not whether the code works; the tests
in `tests/demo` cover the rules.

**Rule for every run:** play first, read later. Don't read the design,
the map files or this file's answers section before a run. Say aloud,
or note, what you think as you go. About 20 minutes each.

## Setup

- **Server:** `BLACKSITE_DEMO=sodium-row-evening`. Optional:
  `BLACKSITE_DEMO_BOUNCER=1` (the Halo turns away a truce-breaker, Q7),
  `BLACKSITE_DEMO_SIGNS=charted`, and `BLACKSITE_DEMO_BARK_GAP` (default
  12 s between ambient lines per caller).
- **Door:** `DOOR_BLACKSITE_PRESENTATION=1`, and
  `DOOR_BLACKSITE_DEMO_SIGNS=charted` with the server's sign toggle.
- **Launch recipe and prepared characters:** from the technical lead
  (pending). Playtests 2 and 3 need characters at grade 5, one a faction
  member. No admin command sets grade or faction today.
- Play at 132 × 50 truecolor first. Repeat playtest 1 at 80 × 24 if time
  allows.

## Playtest 1: arriving as a Wake

A new character, straight from the Wake Hall with Vantongeren's card,
signs dark (default). Then repeat with signs charted.

1. Walk from Meridian Plaza down the Neon Stair onto the Row.
2. Find the Tin Halo. Don't use the map's labels or the side panel to
   find it, only what you see on the street.
3. On the way, look into each bar's doorway. Talk to whoever is inside.
   Buy a drink somewhere.
4. In the Halo, talk to the bartender and to Vesper. Take her first job
   if you like; you needn't finish it.
5. Walk back out and up the Stair.

Afterwards, without looking anything up:

- Who drinks in which bar? Name as many as you can.
- How would you tell a friend to get to the card court? To the Halo?
- What is the Row's one rule, and who keeps it?
- Who is the most important person in the Halo, and how did you know?
- Did the street or the bar feel like a place or a set? Where did it
  break?
- Dark signs or charted signs: which did you navigate by?

## Playtest 2: coming back

A prepared character at grade 5 who is a member of one faction (Kestrel
suggested), with the first Vesper job completed.

1. Walk the same route as in playtest 1.
2. Stop in your own faction's bar, then in a rival's.
3. Talk to the bartender in the Halo again.

Afterwards:

- Did the Row treat you differently from your first visit? Where?
- Did your own bar feel like yours? Did the rival's feel unfriendly?
- Do you now notice that you could be shot here, and that nobody does?
- Would you come back here, and what for?

## Playtest 3: the price and the getaway

Two callers, both grade 5 or more, from factions that are hostile to each
other (for example Kestrel and Sable). An ordinary night, not Curfew. Run
it twice: once with `BLACKSITE_DEMO_BOUNCER=1`, once without.

1. Both meet in the card court, and nothing happens for a minute.
2. One draws on the other.
3. The attacker tries to get away: up the Stair, through the alley
   passages, or into the Halo. The victim may fire back or call for help.
4. Repeat with the attacker standing and fighting the enforcers instead
   of running.

Afterwards:

- Did drawing feel like a decision with a cost before you made it?
- Standing and fighting: did you lose, and did it feel fair?
- Running: did you get away? Was it skill or luck?
- With the bouncer on: did being turned away from the Halo feel right?
- Would you ever draw on the Row again? When?

Optional fourth run, on Curfew (an operator starts the event with
`blacksite.admin event force`). The Stair is shut, so there is no
sanctuary. There is no curfew crowd or visible gate yet.

## What would count as success

From the design (#143 §3 and §9):

- Playtest 1: the player finds the Halo without labels, names at least
  three bars' crowds after one walk, and can state the rule.
- Playtest 2: the player names at least one way the Row treated them
  differently, and gives a reason to come back.
- Playtest 3: standing and fighting loses; at least one getaway succeeds
  by skill; the attacker says the cost was clear before firing.

## What the consultant will do with your notes

Each answer goes back to the place it came from: geometry to the layout
intent, crowds and lines to the population, and rule feelings
(enforcer numbers, Q7) to their owner decisions. A failure is evidence,
not a verdict on the direction.
