# Knowing the price before you draw (proposal)

**Status:** proposal with owner decisions recorded (see Decisions). Not canon
until the top-down edits are made, and nothing here is built.
**Authors:** creative consultant and presentation lead, 2026-11-07.
**Scope:** truce zones, meaning Sodium Row today.
**Timing (technical lead):** after the owner's moving-versus-seated comparison,
so the two questions don't blur. Then on the demo, then a small slice on `main`
before P11 and separate from it.

Labels: **[built]** works on `main`; **[demo]** only on
`demo/sodium-row-evening`; **[decided]** the owner has ruled but it isn't built;
**[new]** is proposed here.

## The finding

From the owner's first playtest, on one run:

> It must be presented more prominently, at least to new players (no idea how
> though).

They knew the rule only because they had defined it. "Nobody draws on Sodium
Row. Sable makes sure of it." "flew by". Their grade 5 "stood no chance", and
they want that, and being turned away at the Halo was "absolutely right". The
punishment stays. A new player being shut out "for quite a bit" without warning
is the problem.

They felt it themselves: "I didn't want to wait until I could enter the Row
again, so I just deleted my Marked(?) character and created a new one." They had
written the rule, and they still weren't sure what state they were in or how long
it would last.

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

1. Sable's people will come for you, and you'll probably lose [demo numbers].
2. The Halo refuses you for as long as Sable is answering, 5 minutes today
   [decided].
3. Fire on a player and you're also Marked for 15 minutes, so anyone can hunt you
   [built], and the Halo and Vesper's work stay closed until the Mark runs out
   [decided]. Attacking an NPC brings no Mark and leaves her work open.

The proposal doesn't say how to get away. That stays the player's skill.

## The proposal

**The guarantee: a notice, twice [new].** A notice is the only thing that shows
at every size and holds: until a key and at least 8 s (terminal UI 2.5). It
isn't always on the hint line, though. It moves to the header if you're
threatened, a prompt is open or your target's relation is hostile, which
includes a Marked or hostile-faction target. At 80x24 on the Row the limits for
one unwrapped line are:

- **Hint line:** 63 cells with `Ctrl-X leaves`, less if `Esc/B back` shows.
- **Header:** 36 cells.

So the wording fits where each notice is likely to land. The keeper's name comes
from the zone.

- **On first arrival in a truce zone, once per character.** Returning players
  aren't told again. This needs no new saved state: `discover()` already runs
  once per character per zone, from the saved `seen_zones`, and S38's rule line
  is emitted there [built]. The notice is sent one-shot at that moment, and the
  door remembers nothing. This one is rarely threatened, so it can use the
  hint line (61 cells). If it does land in the header, the half that applies to
  everyone survives.

  > Fire: Sable comes, no Halo. At a player: Marked 15m, no work.

- **The first time per session that TARGET shows a truce warning.** That's when
  a new player is actually deciding, and it often lands in the header, so it
  must fit there. It says only what applies to this target:

  | TARGET shows | Notice | Cells |
  |---|---|---|
  | "Firing marks you" | Fire: Marked 15m. No Halo, no work. | 35 |
  | "Truce: Sable answers" | Fire here and Sable comes. No Halo. | 35 |

  The first line drops "Sable comes" to fit, and the arrival notice and the
  enforcer carry it. It keeps "Fire:" because without it the line reads as though
  you're already Marked. The second line leaves out the Mark and the work, because
  an attack on an NPC costs neither.

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
  - Wake: "You're new, so once. Draw on this street and we come for you. The Halo
    won't have you either."
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

## Decisions

The owner decided on 2026-11-07 (recorded on #170 by the technical lead):

1. **Notices outside node news: yes.** This allows the top-down edit to terminal
   UI 2.5.
2. **The Halo refuses a Marked truce-breaker (Q7): yes.**
3. **Vesper's work closes to a Marked player (#143 §8): yes.**
4. **The Halo refuses anyone Sable is answering, for as long as it answers:
   yes.** This closes a gap in rule 2: someone who only attacks an NPC isn't
   Marked, and could otherwise wait out the hunt in the Halo.

The owner approved earlier wording, before the header fit. The technical lead
treats the shorter lines as within that approval and reports the final text to
the owner.

Rules 2, 3 and 4 aren't built. On `main` they need a top-down canon edit and a
slice, which the technical lead is writing, and these notices must not ship ahead
of them, or they'd state a rule that doesn't exist yet. On the demo, the refusal
needs `--bouncer` and covers only rule 2 so far, and Vesper's work closes only in
her talker's offer: her board and counter stay open. Rule 4 goes on the demo with
the notices, after the moving-versus-seated comparison.

**What the owner saw:** they noticed `TRUCE` only, not "Firing marks you". They
had shot an NPC, so TARGET would have said "Truce: Sable answers" instead, which
they don't report noticing either. That supports this proposal. The presentation
lead holds any TARGET change until after round 2.

## Order, if only some of it goes ahead

1. Notice at first target.
2. Notice on first arrival.
3. Paint and enforcer. They're cheap and make the street feel lived in anyway.
4. More barks and `is_wake` lines.

## Flags and how we'd know

- **Touches:** the notices are presentation and notice flow only. The access
  rules they describe are the owner's rulings above, and belong to their own
  slice.
- **Disclosure:** the rule and its price are public. Nothing here says who
  arranged the truce, and nothing distinguishes the plainclothes Warden.
- **Not tested:** the presentation lead ran the wording through `main`'s text
  fitters and checked the S38 strings against `main`. Nobody has seen these
  notices in play, and the presentation lead will judge the paint from a capture.
- **Playtest passes if:** a new player, asked before they ever fire, can say what
  happens if they draw on the Row, and someone who draws anyway says they knew.
