# The Halo's back way: how anyone finds it (proposal)

**Status:** proposal. Nothing here changes canon or code. The presentation
lead owns any hint text and its fit. Which door the core's control opens
in the real game is still with the owner (the technical lead's
housekeeping, 2026-11-07).
**Author:** creative lead (Claude Opus 5.5), 2026-11-09.
**Base:** round 3 (`demo/sodium-row-round3` at d305537).

## 1. The result

Playtest 3 asked the owner to open the Halo's back door from its core.
The owner didn't try: "I have no idea how to actually do that." The
notes said to jack in. Nothing in the game said where, or that the
door's control lives in a core. **That is the finding: the back way
can't be discovered in play.** The only way to learn it was the playtest
notes.

## 2. What a player has to know, and what tells them today

| Step | What's true | What tells the player today |
|---|---|---|
| The back door exists | the Halo's back room has a door to the alley [built] | the alley side reads "The Halo's back door", "No handle this side." [round 3] |
| It's locked from inside too | `locked: true` [round 3 only] | "The door is locked. Its core controls the latch." |
| Which core | the Tin Halo core, `lat-tin-halo`, owned by Vesper, tier 2; its hardware is the cabinet beside the bar at (25, 8) [built] | nothing; the cabinet's name is "Tin Halo hardware" |
| How to get in | jack in at a terminal, or anywhere with a rig, then go to the Tin Halo core in the Row's sector [canon 6.2] | nothing in the Halo |
| Where the control is | a room in the core holds the `back-door` control [built] | its label, "back door", once you're inside |

The chain breaks between the second and the fourth step. The door says
"its core" but not which one, and nothing says how to reach it.

## 3. The fix: three small things [new]

**1. The door names its core.** The locked line names the place, not the
mechanism:

> "Locked. The latch runs off the Halo's own system."

The cabinet beside the bar is already "Tin Halo hardware". With this
line, a player who has seen a core and a hardware object can connect the
two. The wording is the presentation lead's.

**2. Somebody in the Halo says it, sideways.** In round 3 people
learned the Row from its talk, and they can learn this the same way. One
bark goes to the Halo's Unmoored runner, whose crowd jacks in for a
living, and one line to Dolf:

> Runner (bark, Halo copy only): "Back room's on Vesper's system. Jack in
> from the board if you want out the quiet way."

> Dolf (line, when the player is hunted or Marked): "Back door's on the
> house system. I don't know anything about it. Ask the board."

"The board" is the Halo's contract board terminal at (9, 6), the nearest
jack-in point. Both lines are new, so they're the owner's to approve.
They tell anyone in the room. That's right for a door canon puts in
plain sight, and the gazetteer has the back room as a known place. This
hides nothing, because the hard part is the ICE, not the knowledge.

**3. The control is findable once you're in.** The `back-door` control
keeps its label, and the core's room with the control is called "Back
room" rather than a numbered service room. Its first-time Lattice view
says what the control does: "back door: unlatch for 5 min".

## 4. What it changes in play

- **The getaway gets a route you can learn.** A hunted player in the
  Halo has heard the runner, knows the board is the jack-in point and
  knows the price is the ICE. That's skill, which is what the owner
  wants the escape to reward.
- **Crews get a role.** One player jacks in at the board while another
  waits at the back-room door. That's the two-player situation playtest
  3 meant to test.
- **No new disclosure.** No secret is revealed. Vesper's core, its owner
  and its controls are already shown to anyone who enters it.

## 5. Where it goes

- The locked line and the room label: the Row rules slice, if the back
  door's target is settled by then. Otherwise with it.
- The runner bark: my population PR (the Halo copy of the runner set).
- Dolf's line: my population PR (Dolf arrives there).
- For round 4: all three on the demo, so the owner can try the back way
  without the notes.
