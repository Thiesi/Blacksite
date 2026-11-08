# Drawn and holstered: a weapon you can see (proposal)

**Status:** proposal for the owner. Nothing here changes canon or code.
The owner decided one rule (§1). Everything else is direction from the
owner's playtest, worked out here, and comes back to the owner for
approval. Canon changes go top-down in their own PRs.
**Author:** creative lead (Claude Opus 5.5), 2026-11-09.
**Base:** `main` at e0cfc7d, with the round 3 demo
(`demo/sodium-row-round3` at d305537) for the Row's people and lines.

Each claim is labelled:

- **[canon]**: in the bible, the gazetteer, the cast or the design docs.
- **[built]**: works on `main` today.
- **[decided]**: the owner decided it.
- **[new]**: my proposal.

## 1. What the owner asked for

After round 3, the owner wrote: "I am being warned upon entering the Row.
I am *very strongly* warned in case I draw my weapon, and maybe an
enforcer who sees that already begins moving towards me. They stand
down when I holster my gun."

Then: "NPCs could walk/run away from you while your weapon is drawn.
Maybe some *don't* - and that can carry a message as well. Maybe you're
being treated differently in the Halo."

**Decided:** in a truce zone, pressing fire while holstered draws the
weapon, and a second press fires. Outside truce zones, combat works as
today. [decided, 2026-11-09]

## 2. What already exists

- **A warning before every attack.** The first fire press at a target
  logs "You raise your weapon. Fire again after two seconds; the target
  can move to safety." The target is told "<name> raises a weapon at
  you." Canon requires 2 s warning for any new threat (game design 5.3).
  [built, canon]
- **A refusal line in safe places.** Firing where harm is blocked logs
  "Wardens: lower your weapon." and gives heat. The Tin Halo is a pocket,
  so nobody can fire inside it. [built]
- **The truce.** Enforcers turn only on someone who broke the peace.
  Guards return to their post when they have no target. [built, canon 5.5]
- **No weapon state.** Nothing records whether a weapon is out, and
  nobody can see it. [built]

The drawn state turns the private per-target warning into a public one
that everyone can see, before anyone is a target.

## 3. The core

### 3.1 The flag [new]

- A player is **holstered** or **drawn**. A new character, a login, a
  respawn, going down and jacking in all start holstered.
- **A toggle key** draws and holsters anywhere. The keymap entry and key
  are the presentation lead's call, in both keymaps.
- **In a truce zone,** fire while holstered only draws (§1). Fire never
  holsters.
- **Outside truce zones,** firing works as today, and it also draws. A
  player who has just fought is visibly drawn until they holster. That
  changes nothing about firing.
- **Visible to others.** The status line shows your own state. Other
  players see a drawn weapon on the figure, the name line or the target
  panel. The look is the presentation lead's. The target panel already
  sends a `stance` field.
- **The draw is the warning.** In a truce zone, the 2 s count runs from
  the draw. Nobody gets a second "raises a weapon at you" after it. The
  second press fires once the drawn player has been drawn for 2 s,
  however fast it comes. Canon 5.3 asks for that, and it gives the
  enforcer its moment. **For the owner:** this keeps "a second press
  fires" but puts at least 2 s before it.

### 3.2 The very strong warning [new]

When a player draws on the Row, the nearest Sable enforcer who can see
them says it aloud, and it goes into the drawer's log:

> **"I see it. Put it away, or pay for it."**

It's in the reference voice ("Nobody draws on the Row. You can. Then you
pay."): short, no threat spelled out, the price last. This one is
addressed to you, not to the street.

- **No enforcer in sight:** a muted system line, "Drawn on the Row.
  Sable's people will see it." No enforcer moves (§3.3 needs sight).
- **Other players in sight** get a muted line, "<name> draws a weapon."
  This replaces the per-target warning on the Row.
- **Drawing again within 2 minutes** gets the shorter line "Again?" The
  first warning has already been given.
- **Self-defence:** if the drawer was hit in the last 10 s, or the
  person they face is Marked, there's no warning and no watch. Firing
  back breaks nothing (canon 5.5), so the Row says nothing.

### 3.3 Watch: the enforcer comes over [new]

The enforcer who gave the warning **watches**: a new NPC state beside
hunt and flee.

- **How close:** it walks to **3 tiles** (Chebyshev) and stays at 2 to
  4. That's close enough that the player sees it in the view and feels
  it, and far enough that it isn't an arrest. It doesn't block a doorway
  or the Stair, because the rule that NPC steps never end on exit tiles
  already covers that.
- **It never attacks** while watching. If the player fires, the
  enforcer is already beside them, and the truce response (hunt) takes
  over from watch on the same tick.
- **One watcher per drawn player.** The other enforcer holds its post,
  so the Stair stays covered.
- **How long:** for as long as the player stays drawn and in its sight.
  There's no time limit. If it loses sight for 20 s (the hunt rule) it
  goes back to its post.
- **The price of drawing first:** a player who draws gives up their head
  start. When they fire, the enforcer is 3 tiles away, not 30. A skilled
  attacker draws where the watcher's walk is long, and that's
  geometry, which is what the owner's "unless you are very skilled" asks
  for.
- **Cost:** one moving NPC per drawn player, on the existing 5-tick
  decision cadence, using the same step as hunt.

### 3.4 Standing down [new]

- **Holster:** the watcher says **"Better."**, waits 5 s (so a quick
  re-draw doesn't make it walk off and back), then returns to its post
  by the guard walk home.
- **No penalty.** Nothing is recorded, standing is unchanged, and the
  Halo stays open. The only memory is the 2-minute "Again?".

### 3.5 Walking off the Row drawn [new]

- **You can.** The weapon stays out through the exit.
- **The watch ends at the exit.** NPCs never change zone, so the watcher
  goes back to its post. Coming back onto the Row still drawn means the
  first enforcer who sees you warns you again (or says "Again?").
- **The Halo door:** see §4.3.
- **Up the Stair:** nothing new for now. Later, the Wardens' existing
  "lower your weapon" could greet a drawn player in a safe hub, with no
  heat until they fire (§6).

## 4. What the flag does to everyone else

### 4.1 The crowd shies away [new]

- **Shying is a wander filter, not flight.** A wander step won't take an
  NPC closer to a drawn player within 6 tiles, and prefers a step away.
  It's the mirror of S42's reach rule. It uses no extra random draws,
  adds no new state and costs nothing extra: the crowd drifts back and
  opens a space around the weapon.
- **It applies to every wanderer alike,** covered or not. A
  plainclothes Warden is a wanderer, so it shies exactly like the
  regulars. Nobody can be told apart by how they move (S42 part 4,
  #179).
- **With posts** (the extras proposal), the same idea: a move never
  picks a post nearer a drawn player. Someone standing within 3 tiles
  takes one step back and holds, and a drinker on an errand cuts it
  short and goes back to their seat. Seated people stay seated. That's
  one step each, not a stampede, and the Warden does exactly what its
  crowd does because it runs the same rule.
- **Talking while drawn.** A talker you speak to while drawn answers
  with a line from its own set, written for the drawn case. Its offers
  stay shut until you holster. Bar vendors say "Not with that out." and
  don't sell. This needs one new dialogue condition, `drawn` (§5).

### 4.2 Who doesn't flinch, and what it says [new]

The people who don't shy are the house. A new player learns who runs
the peace by watching who doesn't move.

| Who | Why they don't move | Drawn line (new, for the owner) |
|---|---|---|
| Sable card players | Sable's table and Sable's peace; the enforcers deal with it | "Sit down or put it away. The cards don't care." |
| Mira Solenne (Sable) | she sells to people who are shaking | "Put that away, sweetheart. You'll scare the customers." |
| Halo bouncer | it's the bouncer's door | (§4.3) |
| Vesper | she sees you before you see her | (§4.3) |
| Choir listeners | they never look up, which is unsettling, not brave | "Shh. Not now." |

**Not flinching is authored, never derived from true faction.** It's a
template flag, `steady`. A covered template must have the same `steady`
as the spawner it poses as (`poses_as`, S42), and the validator refuses
a mismatch. So "the one who doesn't flinch" can never be a Warden. On
the Row the Warden poses as a street regular, and street regulars shy.

The others shy, and their drawn lines say it in their own voice, for
example Kestrel crew: "Put that away. I'm off shift." Off-duty Halvard
and Sablier sit in Upstairs, so they don't move anyway. Their lines can
say they've seen it before. Each set gets one drawn line, written to the
method that worked in round 3.

### 4.3 The Halo [new]

The Halo is a pocket, so nobody can fire inside it [built]. Drawing
there is a statement, not a threat.

- **At the door:** the bouncer won't let a drawn player in: **"Put it
  away first. Then the door's open."** It echoes the doorstep line
  "Door's open... That's not the same as welcome." It's one more travel
  refusal next to Q7. Holster and walk in. This is an access rule, so
  it's the owner's to approve.
- **Drawing inside:** the bouncer walks over and watches, the same
  watch as §3.3, at the same distance. The regulars shy.
- **Vesper doesn't flinch and doesn't refuse.** Everyone else closes
  shop. She keeps working and lets you know she's noticed: **"Point it
  at the board or put it away. Either way, I'm working."** In the one
  place you can't fire, the most important person is the one least
  impressed. That says more about her than any label.
- **The Halo bar** says "Not with that out." like every bar.

## 5. Engine and content, and where it goes

| Piece | Kind | Where I'd put it |
|---|---|---|
| Flag, toggle, fire draws in truce, draw counts as the 2 s warning, status marker | engine, combat input, presentation | **a new slice after the Row rules slice**, demo first |
| Warning line, "Again?", "Better.", self-defence skip | content plus a small hook | same slice |
| Watch state for guards | engine (NPC state) | same slice |
| Halo door refusal while drawn | engine (travel refusal) plus a line | same slice, if the owner approves the access rule |
| Shy wander filter | engine (wander filter, like S42) | second step, after the demo |
| `steady` flag and its validator link to `poses_as` | content schema plus validator | second step |
| `drawn` dialogue condition and one drawn line per set; offers shut while drawn | engine (one condition) plus content | second step, with my population PR for the sets that arrive there |

**Not in the Row rules slice.** That slice already carries the notices,
Q7, HUNTED, settling, the bark scheduler and the street lines. The drawn
state changes combat input and adds an NPC state, so it deserves its own
slice and its own owner approval. Nothing in the Row rules slice needs
to change for it. The reference line "Nobody draws on the Row. You can.
Then you pay." stays the enforcers' greeting, and the drawn warning is a
second, separate line.

**Demo first.** I'd build §3 and §4.3 on a round 4 demo branch with the
errands proposal, so the owner can feel the draw, the walk-over and the
stand-down before any of it is canon.

## 6. What else it opens (not proposed now)

- **Clearing a path.** Drawing parts the crowd, so a player can use it to
  get through a doorway, at the price of being watched. That's
  intimidation without violence.
- **Other truce and house-rule places.** Lamp Street and the Baths
  (Warmwater Stage 2) can reuse the flag with their own keepers and
  voices.
- **Safe hubs.** A drawn player on Meridian Plaza could hear the
  Wardens' existing "lower your weapon", with no heat until they fire.
- **Crews.** A drawn crewmate is a readable signal before a fight.
- **The Warden's payoff stays pickpocket detection** (S42 part 4). The
  drawn state adds no reveal of any kind.

## 7. Questions for the owner

1. **The 2 s minimum** between drawing and the shot (§3.1)?
2. **Watch distance and duration:** 3 tiles, for as long as you're drawn
   and in sight (§3.3)?
3. **The Halo door refuses a drawn weapon** (§4.3)?
4. **Vesper stays open while you're drawn,** and everyone else closes
   (§4.3)?
5. **The new lines** in §3.2, §3.4, §4.2 and §4.3, which you haven't
   heard yet.
6. **Demo first,** on a round 4 branch with errands (§5)?
