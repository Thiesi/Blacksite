# The tram ride: travel, not teleport (proposal)

**Status:** the owner agreed to T1 to T4 on 2026-11-05 (§6). The technical
lead's and presentation lead's reviews are folded in. T5 is open.
Nothing here changes canon or code. Canon changes go top-down in their
own PRs.
**Author:** creative consultant (Claude Opus 5.5), 2026-11-04.
**Base:** `main` at dd489f9. The owner's note of 2026-11-01 says trams
"feel like teleporters", and the owner agreed to fix the ride rather
than the network.

Each claim below is labelled:

- **[canon]**: in the bible, the gazetteer, the cast or the design docs.
- **[built]**: works on `main` today.
- **[new]**: my proposal.

## 1. Why a ride feels like a teleport

What happens today [built]:

1. You stand on the platform tile and press E. A full-screen overlay replaces the
   view and reads "You wait on the platform. Departure in N s."
2. At departure you leave the zone. The overlay reads "The tram hums."
   and "Arrival follows departure."
3. Ten seconds later you are standing in the other zone.

The platform is never seen while you wait: the overlay covers it. You
never see who rides with you. Every line takes 10 s, wherever it goes.
Nobody speaks. Three more facts make it worse:

- **The hub's crowd is not on the platforms.** The Central Tram Hub's
  commuters, Kestrel staff and Wardens spawn along the top wall
  (rows 3 and 4). The two platforms are on row 14 [built]. Clinic Row's
  platform is at the south end (row 31), and its patients spawn on rows
  1 to 4 [built]. Block Street's residents already spawn beside its
  platform [built].
- **Only two of the six lines exist.** The Clinic and Terraces lines are
  built. Chapel, Rim, Market and Lamp are canon, and their zones are not
  built yet [canon, built].
- **The Dispatcher is silent.** The cast and the gazetteer have it on
  the tram public address [canon], the factions file says otherwise (T5),
  and its dialogue file is dormant [built].

None of this is a problem with the network. It's a problem with the
ride: there is no place, no people and no time.

## 2. What must not change

- **Hub and spoke, one terminus per line, no stops between.** "A line
  crosses ground where it does not stop, so a ride reveals nothing on the
  way." [canon, gazetteer] The network's gaps are political: Kestrel
  serves no line to Old Works, Sodium Row or the Spire, and the Neon
  Stair is walked [canon].
- **The schedule.** Departures every 90 s on a stable UTC schedule,
  holds of at most 30 s and then 120 s of immunity, and an in-flight
  ride always completes [canon, built].
- **Absent from both zones while riding.** Nobody can be attacked in a
  car [built].
- **The Dispatcher never speaks about itself.** It gives times, routes
  and warnings, and has never been recorded lying [canon]. Under the Cut
  outcome, Holt replaces the Dispatcher's barks [canon].

## 3. The proposal: six parts

**3.1 The platform is a place [new].** Waiting no longer covers the
view. You stand on the platform and see it. The countdown takes the
hint row while it runs ("Clinic line, 34 s"), and moving off the
platform still cancels boarding. The platform edge gets a ground look,
so you can see where to stand. Each hub platform gets a departure board:
a sign with a 22-wide face showing its line name and a coarse state
(NEXT 1 MIN, BOARDING or HELD), never a live count and never other
destinations. Only the two built platforms get a board and a crowd. The
hub's five commuters move to the platforms: two on each platform's edge
and one between them. The boarding tile stays free: it is outside their
spawn region and they don't wander onto it. The Kestrel staff
stand at the ticket office and the Wardens stand by the plaza exit. Clinic
Row's platform gets two patients waiting. Crowds at platforms stay
non-talkers, because a talker beside a platform tile takes E from a caller
standing on it until S39 ships. Commuters board with you and get off at
the other end, but only as text (3.2), so no NPC movement code changes.

**3.2 The shared car [new].** At departure, everyone on the same line's
same departure is in the same car. While riding, the map pane shows the
car, and the side panel's NEARBY becomes IN THE CAR:

> The Clinic line car. Riding with you: Second, a Kestrel clerk,
> two commuters.

A car is one departure from one platform: the key is origin zone, exit
and departure time, so each direction of a line is its own car. It is
worked out from the riders when the view is drawn, with no new state.
Riders have left the world, so NEARBY's sight test can't run. IN THE CAR
shares NEARBY's entry builder (name, role, class, relation), so a disguise
holds, and these rules replace the sight test:

1. Only connected callers are real entries. NPC passengers are generic
   text ("two commuters", "a patient"), never actors, so no covered NPC
   can appear. Their mix comes from a seed derived from the car's key.
2. The private-visibility and training filters stay, so a mission-isolated
   caller never appears.
3. Stealth doesn't hide you. It shortens detection range, and a sealed car
   has no range. This is today's rule, and I don't propose a new one.
4. A Mark shows as it does in NEARBY. It is already public.
5. Entries are names only. They carry no target action, Tab doesn't select
   them, and no entry shows who anyone is hunting.
6. The arrival line ("You arrive at Clinic Row with Second.") follows the
   same rules.
7. The list starts at departure and reaches nobody outside the car.

Riders on one departure already land side by side, so arriving together
needs no code and no spread. What is new is knowing who is aboard 10 to
16 s sooner. That works both ways: a Marked caller also sees the hunter,
and both would see each other in NEARBY on arrival anyway.

**3.3 A view from each line, naming nothing [new].** Each line gets
three or four lines of text shown in the car's map pane during the ride
(not in the log), in order. The ride time is split evenly, and the
"Brakes." line always gets the last slice. Each line stays under about
70 characters and stays on screen until the ride ends. They describe what the window
shows, never a district name, a street name or a sign. The ride reveals
no map knowledge (no seen-zone update and no map reveal), which keeps
the canon in §2. A first draft for the Clinic line:

> The car lurches out of the shed into the dark.
> Steam rises off something large and warm to the right.
> Lit windows, close enough to see the shelves inside, then gone.
> Brakes. The smell of disinfectant comes in before the doors open.

And for the Terraces line:

> The car leaves the shed on a long, level run.
> Washing lines between blocks, at the height of the window.
> A school bell or an alarm, too short to tell which.
> Brakes. Somebody on the platform is already shouting a name.

The presentation lead owns how the view looks. The text itself is
shared between me and the presentation lead.

**3.4 Ride times by distance [new; numbers change, owner gate].** Today
every ride takes 10 s. The shortest line stays at 10 s, and the others
scale by straight-line distance on the gazetteer's city plan [canon],
measured from the hub to each terminus. The plan's wall is about twice as
wide as it is tall in characters, so one row counts as two columns.

| Line | Relative length | Ride |
|---|---|---|
| Chapel (not built) | 1.0 | 10 s |
| Terraces | 1.14 | 11 s |
| Market (not built) | 1.4 | 14 s |
| Clinic | 1.5 | 15 s |
| Rim (not built) | 1.5 | 15 s |
| Lamp (not built) | 1.61 | 16 s |

This replaces my first table, which came from the website's schematic and
wrongly had Clinic as the shortest line.

The value is an optional `ride_seconds` on the exit, defaulting to
`TRAM_RIDE_SECONDS`. The validator allows it on trams only, from 10 to 16,
and requires the return exit to match. The technical lead found this safe
for the demo: a hunter stays one interval behind, hub transfer windows
fall from 80 s to at worst 74 s, and holds and rides in flight are
unaffected. A search found no deadline tied to ride length, but that was
not an audit, so the demo watches for it (§4).

If it reaches `main`, a non-default value moves the mechanics fingerprint
of the hub and that district, which needs the owner's approval. Canon says
10 s in game design lines 535 and 1239-40 and gazetteer lines 454 and
2039, and `tests/world/test_exits.py` and `accept_s08_netbbs.py` assume it.

**3.5 The Dispatcher on the public address [new; in-game text
shared].** Short announcements, heard by callers boarding that line,
each at most once per departure, and only for events that already exist:

- **30 s before departure:** "Clinic line. Departure in thirty seconds."
- **A hold (S15):** "Clinic line held." A hold can be shorter than 30 s,
  and the Dispatcher doesn't lie, so this names no time.
- **Curfew, at the hub:** "Curfew in force. Outbound services run on
  schedule."
- **Curfew, at a district platform:** "Curfew in force at the Core. Entry
  by Curfew Pass. Marked holders are refused." The pass rule is canon
  (`key_curfew_pass` in the game design).
- **Under the Cut outcome:** Holt takes these lines over, and the
  interval reads 120 s [canon].

During Curfew, the Curfew line replaces the 30 s call. The Dispatcher
announces; it never chats, never says "I" and never uses a handle, so its
rare personal address keeps its weight. In the demo these are log lines
from a tick-time check that calls `schedule()` and remembers each platform
and departure in memory. Speech is dormant on `main` until the Q6 slice.

**3.6 Multi-stop: not now [new].** The canon says one terminus per line
(§2), and I recommend keeping it. A stop is only worth adding if it is a
real place with a reason to get off, and none of the planned zones needs
one today. If one ever does, it's a canon change, decided on its own.

## 4. How to test it

A demo branch, never merged, like the Sodium Row demo, and kept separate
from it. Because platform crowds are non-talkers (3.1), it doesn't wait
for S39.

- **Dressed:** the Clinic line gets all of §3, because a new Wake is
  most likely to ride it first.
- **Plain:** the Terraces line keeps today's ride. Only the hub's
  crowd placement (3.1) is shared by both lines.

On the city plan the dressed line is also the longer one, so one run
can't separate dressing from time. Run it twice, changing only the data:

- **Run 1, flat:** both lines at 10 s. This tests the dressing alone.
- **Run 2, by distance:** Clinic at 15 s and Terraces at 11 s. Compared
  with run 1, this tests T1.

Questions for the tester to answer, before reading the success criteria:

1. Which line felt longer? Which district felt farther from the Core?
2. Who was on the platform, and who rode with you?
3. Did either ride feel like going somewhere? Where did it break?
4. In run 2, did the extra Clinic time feel like distance or like waiting?

The test succeeds if, in run 1, the tester calls the Clinic line farther
at equal time, names at least one fellow passenger and describes the ride
as travel. T1 holds if, in run 2, the extra time reads as distance. One
tester playing both runs is thin evidence, and the second run knows the
first, so a weak result reopens the question rather than settling it.

The demo also exercises what the search couldn't rule out: a Marked
escape, a disconnect and reconnect during a ride, a contract timer, and a
hub transfer at the 74 s window.

## 5. Who does what

| Part | Owner |
|---|---|
| Platform population and placement, NPC passengers, line view text, Dispatcher lines | consultant (text shared with the presentation lead) |
| Waiting without the overlay, status-line countdown, departure board, car overlay | presentation lead |
| The car's passenger list, arriving together, per-line ride times, the 30 s announcement | technical lead |
| Ride times, the passenger list's information | owner (T1, T2) |

## 6. Questions for the owner

- **T1. Ride times by distance**, 10 s to about 16 s (§3.4)? I recommend
  yes, in the demo first, after the technical lead's movement checks.
- **T2. The passenger list** names the callers in your car (§3.2)? I
  recommend yes: it's what makes the car shared, and it never leaves the
  car.
- **T3. Keep one terminus per line**, with no multi-stop (§3.6)? I
  recommend yes.
- **T4. A demo branch** with one dressed line and one plain line (§4)?
  I recommend yes, after the Sodium Row playtest.
- **T5. Does the Dispatcher speak on the tram public address?** Open. The
  cast file and the gazetteer say yes, and `02-factions.md:341` says "only
  on convoy channels and, occasionally, to a player". The bible doesn't
  decide it. I recommend amending the factions line to match the cast file,
  in the canon PR that follows the demo. The demo can run without an answer.

**Owner decisions, 2026-11-05:** T1 to T4 agreed, as recommended.

- **T1:** ride times scale with distance, in the demo first, after the
  technical lead's movement checks.
- **T2:** the car shows who rides with you, through IN THE CAR.
- **T3:** each line keeps one terminus.
- **T4:** a never-merged demo branch, with the Clinic line dressed and
  the Terraces line plain, after the Sodium Row playtest.

After the owner agreed, checking the city plan changed the per-line
numbers within T1's 10 to 16 s (§3.4), and the two-run test replaced a
single comparison within T4's dressed and plain lines (§4).

Canon is unchanged. The ride times go to canon only after the demo.
