# Extras: a full street where few people move (proposal)

**Status:** proposal for the owner. Nothing here changes canon or code.
The counts depend on a measurement the technical lead has commissioned
(§6). Canon changes go top-down in their own PRs.
**Author:** creative lead (Claude Opus 5.5), 2026-11-09.
**Base:** `main` at e0cfc7d, with the round 3 demo
(`demo/sodium-row-round3` at d305537) for the Row's map, people and
lines. Coordinates are the demo's.

Labels: **[canon]**, **[built]**, **[decided]**, **[new]**, as in the
other proposals.

## 1. What the owner asked for

After the round 3 seated walk, the owner wrote: "The street doesn't feel
particularly alive. I think it needs a good bunch more NPCs. And I think
it's totally reasonable if most of them are stationary most of the time.
Think of movies or TV series: they usually stuff the background with
extras way beyond what IRL locations like the ones in the scenes look
like... if stationary NPCs cost us (next to) nothing, we should have
plenty of them, with only very few moving at any given time."

The owner also agreed to "seated, with errands" in the bars: drinkers
who now and then get up, staggered so one or two per bar are moving.
[decided, 2026-11-09]

**One model for both:** everyone has a few places they belong. They
stand or sit at one most of the time. Now and then one of them walks to
another, and only a few are walking at any moment. The street and the
bars run the same rule.

## 2. The rule: posts and a moving budget [new]

- **Posts.** Each crowd has a list of authored tiles: seats, a spot at
  the counter, a place in a doorway, a stretch of wall. Each person has
  a **home post** (their seat or their usual spot). They spawn there,
  and the walk home brings them back there.
- **Holding.** At a post the person stands or sits still: no steps and
  no random draws. Holding is the normal state, and it's what makes a
  person cheap.
- **Moving.** When the hold time ends, the person picks another free post
  from their own crowd's list, walks there and holds again. From an
  errand post they always go back home next.
- **The moving budget.** The person moves only if their crowd is under
  its cap of people walking (1 per bar, 2 for the Halo and for each
  street crowd), and the zone is under its budget (§6). Otherwise they
  hold a little longer. That bounds how many move at once, whatever the
  head count.
- **Reach (S42).** Nobody starts a move while a player who can talk is
  beside them. A walk already under way pauses while a player stands
  beside them, so you can talk to anyone you walk up to.
- **Custom (gazetteer).** Posts belong to a crowd, so a Kestrel driver
  only walks between Kestrel places. Only the street regulars, who are
  nobody's crowd, use posts along the whole street.
- **Flight and the walk home.** A shot person flees as today. Afterwards
  A9's walk home takes them back to their home post, so a fled drinker
  has somewhere to go: their seat.

This replaces `wander` for the crowds. Guards, patrols and hunts don't
change.

## 3. Who stands where: the street [new]

Each entry is the crowd, where it stands, how many at full density (and
lean), and why it's there. All are civilians, apart from the Sable
people. Looks are the presentation lead's.

| Place | Who | Full (lean) | What it shows |
|---|---|---:|---|
| Upstairs door, foot of the Stair | Halvard staff, Sablier staff | 2 (1) | a smoke before the walk back up; the respectable end |
| The Long Shift door | Kestrel crew | 3 (2) | the shift-change knot, loud, half in and half out |
| The Quarter Tone door | Choir listeners | 2 (1) | stepped out, not talking, facing the door |
| The Clause door, at the chalk tally | Clause regulars | 3 (2) | counting days on the sign |
| Spare Parts door and its public terminal | Unmoored runners | 3 (2) | one at the terminal, two keeping watch |
| Card court | 2 card players (seated), Mira Solenne, watchers (street regulars) | 3 + 4 (3 + 2) | the Row's centre; Sable at the table, everyone else standing round it |
| The stage | street regulars | 4 (2) | a knot facing the stage, whether anyone's on it or not |
| South wall, between doorways | street regulars | 6 (3) | leaning, waiting, smoking; a line of shapes along the wall |
| Foot of the Stair | street regulars | 2 (1) | waiting for someone who's coming down |
| Alley mouths | Kestrel driver, Unmoored runner | 2 (1) | smokers in the dark between doorways |
| Halo end | doorstep pair, street regulars | 2 + 2 (2 + 1) | "Past Spare Parts, then the street gives up." |
| Two other public terminals | Clause stray, Kestrel crew | 2 (1) | someone always checking something |

That's **about 40 on the street at full density** and about 24 lean,
against 8 on `main` today. The two enforcers stay at their posts
[built]. Every crowd except the street regulars and the card watchers
reuses a set that's already proven in round 3, with its own lines.

**The street regulars are split into three crowds by stretch** (west:
stage, Stair foot, wall; middle: card court watchers, wall; east: wall,
Halo end). Each is its own spawner group with its own posts. There are
two reasons. A shot scatters the stretch around it, not all 40 people,
which is more believable and caps the burst of movement. And it gives
the Warden a crowd of the right size (§5).

**Optional, needs new lines:** the gazetteer's ticket tout (convoy
passage, Scour rides) [canon, unplaced], with a haggler beside them,
near the Old Works end. It's a new speaker, so it's the owner's to
approve.

## 4. The bars and the Halo: errands [new]

The same rule indoors. Every drinker's home post is their seat.

| Errand post | Weight | Hold there | What it shows |
|---|---:|---|---|
| The counter | 50 | 5–10 s | buying a round |
| The bar's street doorway | 30 | 10–20 s | a drinker looking out; from the street the doorways come alive |
| Beside another seated drinker | 20 | 10–20 s | a word at another table |

- **The rhythm:** each drinker holds their seat for 60–180 s (uniform,
  drawn per hold). At most **1 per bar and 2 in the Halo** are up at
  once. With 2 to 4 drinkers per bar, someone gets up roughly every
  minute per bar, so walking the Row you nearly always see one person
  on their feet somewhere.
- **Leaving and arriving without spawning.** The bars are alcoves in the
  street's map, the same zone as the street, so a drinker can walk out.
  A **swap** is the leave-and-arrive: a drinker walks out to their
  crowd's doorway post on the street, and the person standing there
  walks in and takes the seat. Nobody spawns in sight, so canon 5.5's
  spawn rule stands.
- **Real arrivals** down the Stair, and departures up it, would need
  people to spawn and despawn at an exit in view. That's a change to
  canon 5.5's spawn rule, so it's later and the owner's call (§8).
- **The Halo** is its own zone. Its errands are the bar (Dolf), the
  tables, and standing near Vesper without crowding her. The Halo
  copies of the Kestrel crew, Clause regular and runner keep their
  street-free lines (S42 talk audit).

## 5. The plainclothes Warden is never the odd one out [new]

The S42 rule extends to posts. The Warden's spawner names its crowd with
`poses_as`, and the validator also checks:

- **The same behaviour and the same numbers:** posts, the same post
  list, the same hold range and the same weights as its counterpart.
- **The same cap:** the Warden counts in its crowd's moving cap, so it
  moves exactly as often as anyone in that crowd.
- **The same area:** its posts are its crowd's posts. This also fixes the
  tell I noted on #183. Today the Warden's spawn region is a smaller
  patch than the regulars' whole street, so a long watch could pick it
  out.

On the Row the Warden poses as a **middle-stretch street regular**. That
crowd stands round the card court, along the middle wall and at the
Clause and Quarter Tone doors. It's where canon's "moves between bars"
[canon] and its future pickpocket work [canon, unbuilt] belong. It has
6 to 8 real regulars beside it, enough company that NEARBY never shows
one regular alone.

## 6. Cost: what's measured, and the budget [new]

What exists: A8's sweep on #144 measured 8, 11 and 16 Row NPCs, all
wandering, at 132x50. That's 73.7, 79.5 and 140.5 CPU s/h against a
108 target (`docs/ops/captures/p6-a8-cpu/README.md`). It didn't
separate still people from moving ones. The technical lead has
commissioned a new grid on the Row: stationary extras at 0/20/40/80,
moving at 4/8/12, with 1 and 4 callers in view. **The design scales to
whatever that measurement allows:**

- **Head count** goes from lean (about 24) to full (about 40). The
  places stay the same and only the numbers per place change.
- **The zone's moving budget** is a number per zone in content, set from
  the measurement. My starting guess for the Row is 6 people walking at
  once, plus the enforcers when they watch or hunt. The bars add their
  1 each.
- **A scatter case belongs in the grid:** a shot on the middle stretch
  makes that crowd flee all at once. That's the worst burst.
- **Barks don't scale with head count.** The scheduler limits what each
  caller hears, so 40 speakers aren't 40 times the talk, just more
  sources nearby. Repetition depends on set size, and that's still an
  open playtest question.

## 7. Where it goes

| Piece | Kind | When |
|---|---|---|
| The engineer's measurement | measurement only | now (the technical lead) |
| Posts behaviour, crowd caps, zone moving budget, the pause for reach, the validator links to `poses_as` | engine, one slice | after the measurement; demo first |
| The street's extras, the bar errands, the swaps, the regulars split in three | content, my population PR | after that slice, with the counts from the measurement |
| Ticket tout and haggler | content plus new lines | with the population PR, if the owner approves |
| Arrivals and departures at the Stair | canon 5.5 plus engine | later, the owner's call |

**Nothing goes in the Row rules slice.** None of this touches the truce
rules, and the Row rules slice ships as scoped.

**Demo first:** a round 4 demo branch with posts, the extras at full
density, the bar errands and the drawn-weapon core (the other proposal).
That way the owner walks one street with all of it. The `--seated` and
moving switches stay for comparison.

## 8. Questions for the owner

1. **Posts and a moving budget** as the one rule for the street and the
   bars (§2)?
2. **The street list** in §3: anyone missing, or anyone who shouldn't be
   there?
3. **The ticket tout** as a new speaker (§3)?
4. **Swaps** for leaving and arriving now, with real arrivals at the
   Stair later as a canon change (§4)?
5. **Demo first,** on round 4 (§7)?
