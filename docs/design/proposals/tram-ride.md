# The tram ride: travel, not teleport (proposal)

**Status:** proposal for the owner, with questions T1 to T4 in §6.
Nothing here changes canon or code. Canon changes go top-down in their
own PRs.
**Author:** creative consultant (Claude Opus 5.5), 2026-11-04.
**Base:** `main` at db54b24. The owner's note of 2026-11-01 says trams
"feel like teleporters", and the owner agreed to fix the ride rather
than the network.

Each claim below is labelled:

- **[canon]**: in the bible, the gazetteer, the cast or the design docs.
- **[built]**: works on `main` today.
- **[new]**: my proposal.

## 1. Why a ride feels like a teleport

What happens today [built]:

1. You step on the platform tile. A full-screen overlay replaces the
   view and reads "You wait on the platform. Departure in N s."
2. At departure you leave the zone. The overlay reads "The tram hums."
   and "Arrival follows departure."
3. Ten seconds later you are standing in the other zone.

The platform is never seen while you wait: the overlay covers it. You
never see who rides with you. Every line takes 10 s, wherever it goes.
Nobody speaks. Three more facts make it worse:

- **The hub's crowd is not on the platforms.** The Central Tram Hub's
  commuters, Kestrel staff and Wardens spawn along the top wall
  (rows 3 and 4). The platforms are on rows 14 and 27 [built]. Clinic Row
  and Block Street also spawn their crowds far from their platforms
  [built].
- **Only two of the six lines exist.** The Clinic and Terraces lines are
  built. Chapel, Rim, Market and Lamp are canon, and their zones are not
  built yet [canon, built].
- **The Dispatcher is silent.** The canon says it speaks on the tram
  public address [canon], and its dialogue file is dormant [built].

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
destinations. (Presentation lead, #157 review.) The hub's commuters move to the platforms: two or three on
each platform's edge, and the rest between platforms. The Kestrel staff
stand at the ticket office and the Wardens stand by the plaza exit. The
district platforms get one or two of the local crowd waiting:
patients at Clinic Row, residents at Block Street. Commuters board with
you and get off at the other end, but only as text (3.2), so no NPC
movement code changes.

**3.2 The shared car [new].** At departure, everyone on the same line's
same departure is in the same car. While riding, the map pane shows the
car, and the side panel's NEARBY becomes IN THE CAR:

> The Clinic line car. Riding with you: Second, a Kestrel clerk,
> two commuters.

IN THE CAR is the NEARBY panel's own code, so a disguise or a cover holds in the car too. NPC passengers are
generic ("two commuters", "a patient"), never named, and are drawn from
the crowds at both ends of the line. On arrival, the car's callers step
out together on neighbouring tiles. Arrival already works that way; the
log line becomes "You arrive at Clinic Row with Second."

The list goes only to the people in the car, never to the destination
zone. Seeing who rode with you is information, so this needs the
technical lead's review and the owner's yes (T2).

**3.3 A view from each line, naming nothing [new].** Each line gets
three or four lines of text shown in the car's map pane during the ride
(not in the log), in order. The ride time is split evenly, and the
"Brakes." line always gets the last slice. Each line stays under about
70 characters. They describe what the window
shows, never a district name, a street name or a sign. The ride reveals
no map knowledge (no seen-zone update and no map reveal), which keeps
the canon in §2. A first draft for the Clinic line:

> The car lurches out of the shed into the dark.
> Pipes run alongside the line, then drop away below it.
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
every ride takes 10 s. I propose 10 s for the shortest line, scaled by
distance on the city plan, so the longest line takes about 16 s. From
the website's transit diagram (a mockup, not canon), the lines are,
relative to the Clinic line:

| Line | Relative length | Ride |
|---|---|---|
| Clinic | 1.0 | 10 s |
| Chapel | 1.1 | 11 s |
| Terraces | 1.4 | 14 s |
| Rim, Market | 1.5 | 15 s |
| Lamp | 1.55 | 16 s |

The lengths need checking against the city plan, which owns them. The
change is small, but it touches movement: a Marked caller's escape time,
courier and contract timing, and the pacing set beside Gate Nine's
schedule (game design §5.6, §7.7). It goes to the technical lead for those checks before the
owner decides (T1).

**3.5 The Dispatcher on the public address [new; in-game text
shared].** Short announcements, heard by everyone on the hub's
platforms and in the car, each at most once per departure, and only for
events that already exist:

- **30 s before departure:** "Clinic line. Departure in thirty seconds."
- **A hold (S15):** "Clinic line held. Departure in thirty seconds."
- **Curfew:** "Curfew in force. Outbound services run on schedule.
  Inbound passengers present a pass at the line." The pass rule is canon
  (`key_curfew_pass` in the game design).
- **Under the Cut outcome:** Holt takes these lines over, and the
  interval reads 120 s [canon].

The Dispatcher announces; it never chats, and it never says "I". The
lines go through the same speech rule as the Sodium Row barks (log lines,
spaced out, never during a fight), so there's nothing new to build for
delivery.

**3.6 Multi-stop: not now [new].** The canon says one terminus per line
(§2), and I recommend keeping it. A stop is only worth adding if it is a
real place with a reason to get off, and none of the planned zones needs
one today. If one ever does, it's a canon change, decided on its own.

## 4. How to test it

A demo branch, never merged, like the Sodium Row demo:

- **Dressed:** the Clinic line gets all of §3, because a new Wake is
  most likely to ride it first.
- **Plain:** the Terraces line keeps today's ride. Only the hub's
  crowd placement (3.1) is shared by both lines.

Questions for the tester to answer, before reading the success criteria:

1. Which line felt longer? Which district felt farther from the Core?
2. Who was on the platform, and who rode with you?
3. Did either ride feel like going somewhere? Where did it break?

The test succeeds if the tester calls the Clinic line farther (even
though it's the shorter line), names at least one fellow passenger, and
describes the Clinic ride as travel.

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
