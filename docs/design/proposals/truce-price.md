# Knowing the price before you draw (proposal)

**Status:** proposal, not canon. Nothing here is built, and nothing goes on
the running demo until the technical lead says so.
**Authors:** creative consultant and presentation lead, 2026-11-07.
**Scope:** truce zones, meaning Sodium Row today. Targets `main`, as a small
slice before P11 and separate from it, tried on the demo first if the technical
lead agrees.

Labels: **[built]** works on `main`; **[demo]** only on
`demo/sodium-row-evening`; **[open]** waits on an owner decision; **[new]** is
proposed here.

## The finding

From the owner's first playtest, on one run:

> It must be presented more prominently, at least to new players (no idea how
> though).

They knew the rule only because they had defined it. "Nobody draws on Sodium
Row. Sable makes sure of it." "flew by". Their grade 5 "stood no chance", and
they want that, and being turned away at the Halo was "absolutely right". The
punishment stays. A new player being shut out "for quite a bit" without warning
is the problem.

## Why it flies by

On `main` the rule is its own line straight after the arrival paragraph in the
log, in the same style [built]. On the demo it's the paragraph's third sentence
[demo]. Either way it arrives as you start walking. Nothing states the price
before you fire [built]:

| When | What S38 shows | Says the cost? |
|---|---|---|
| Always | header `CONTESTED─TRUCE─PvP G5+` | no, one word |
| First arrival | arrival line | no |
| Target selected | TARGET: "Firing marks you" or "Truce: Sable answers" | no; names the result, not what it costs |
| After firing | "You break Sodium Row's truce. You are Marked for 15 min." and "Sable is coming for you." | yes, too late |

## What a player needs to know

1. Sable's people will come for you, and you'll probably lose.
2. Fire on a player and you're Marked for 15 minutes, so anyone can hunt you.
   Attacking an NPC brings the guards but no Mark [built].
3. The Halo and Vesper's work are closed until the Mark runs out [open].

The proposal doesn't say how to get away. That stays the player's skill.

## The proposal

**The guarantee: a notice, twice [new].** A notice is the only thing that shows
at every size and holds: until a key and at least 8 s (terminal UI 2.5). It
isn't always on the hint line, though. It moves to the header if you're
threatened, a prompt is open or your target's relation is hostile, which
includes a Marked or hostile-faction target. At 80x24 on the Row the limits for
one unwrapped line are:

- **Hint line:** 64 cells with `Ctrl-X leave`, less if `Esc/B back` shows.
- **Header:** 36 cells.

So the wording fits where each notice is likely to land. The keeper's name comes
from the zone.

- **On first arrival in a truce zone, once per character.** Returning players
  aren't told again. This one is rarely threatened, so it can use the hint line
  (54 cells). If it does land in the header, the "Sable comes" half survives.

  > Fire here and Sable comes. At a player: Marked 15 min.

- **The first time per session that TARGET shows a truce warning.** That's when
  a new player is actually deciding, and it often lands in the header, so it
  must fit there. It says only what applies to this target:

  | TARGET shows | Notice | Cells |
  |---|---|---|
  | "Firing marks you" | Fire: Marked 15 min. Sable comes. | 33 |
  | "Truce: Sable answers" | Fire here and Sable comes. | 26 |

  The door reads the existing `target.warning`, so this needs no server field
  and adds no key. S38's "no fire confirmation" stands. The owner reports you
  can't fire by accident, so there's no case for a confirm. The build must test
  both texts through the header at 80x24.

**The cost:** the first-target notice can cover the key hints for at least 8 s,
once per session, just when a new player may want the `F` hint. We accept that,
because the price matters more at that moment.

The log line and the TARGET wording stay as they are. TARGET has 21 columns at
80x24, so it can't carry the price.

**Making you notice and believe it: the street says so [new].** None of this is
guaranteed, so it supports the notice and doesn't replace it.

- **An enforcer tells you.** A person with a weapon does more than any UI, and
  saying it once, flatly, is in character. `npc-row-enforcer` gets a talker
  record, shared by both posts:
  - Bark, its only one: "Nobody draws on the Row. You can. Then you pay."
  - Marked: "You know what you did. So do we."
  - Wake: "You're new, so once. Draw on this street and we come for you. You
    won't enjoy it."
  - Greeting: "Hands empty and we've got nothing to say."
- **Paint at the Stair foot.** `NOBODY DRAWS` in the `paint` role, like "TIN
  HALO →" and the Clause's tally. Not a sign in Sable's colours: the Row belongs
  to nobody, on paper [canon], and Sable doesn't advertise. It reads as what
  everyone knows, and somebody wrote it and nobody painted over it. On the demo
  it goes near the arrival tile, around (4,13) under the first lamp, with the
  position settled at capture. On `main` its place follows S25c.
- **Repetition.** A few more barks mention the price, and `is_wake` lines can
  state it on a first meeting. On `main`, all talk here waits on the cast going
  live (Q6, P8), so the notice can't depend on it.

**Unchanged:** the P11 card. It comes later in the queue and your first key
closes it, so nothing should rely on it.

## Decisions for the owner

1. **Notices outside node news.** UI 2.5 defines notices as node news, so this
   needs a small top-down canon edit. We recommend yes.
2. **Item 3.** Q7 (the Halo refuses you) and closing Vesper's work (#143 §8, an
   owner gate) aren't recorded. The notices leave this out until they are. If
   both land, the wording needs another pass, because neither form fits as it
   stands: adding "No Halo, no work." makes the arrival notice 72 cells (limit
   64), and "Fire: Marked 15 min. No Halo, no work." is 38 (header limit 36).
   It's the owner's actual complaint, so we'd want it there.

**One question first:** did the owner notice `TRUCE` in the header or "Firing
marks you" at all? If they did and it still didn't register, that supports this
proposal. If they missed them, TARGET and the header have a problem of their own.

## Order, if only some of it goes ahead

1. Notice at first target.
2. Notice on first arrival.
3. Paint and enforcer. They're cheap and make the street feel lived in anyway.
4. More barks and `is_wake` lines.

## Flags and how we'd know

- **Touches:** presentation and notice flow only. No change to movement,
  visibility, access, combat or balance.
- **Disclosure:** the rule and its price are public. Nothing here says who
  arranged the truce, and nothing distinguishes the plainclothes Warden.
- **Not tested:** the presentation lead ran the wording through `main`'s text
  fitters and checked the S38 strings against `main`. Nobody has seen these
  notices in play, and the presentation lead will judge the paint from a capture.
- **Playtest passes if:** a new player, asked before they ever fire, can say what
  happens if they draw on the Row, and someone who draws anyway says they knew.
