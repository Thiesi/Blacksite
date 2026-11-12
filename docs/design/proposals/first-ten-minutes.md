# The first ten minutes (proposal)

**Status:** proposal for S48 part 2 ("the opening as a scene"), revised
on 2026-11-12 to fold in the creative lead's reviews (#220, comments
6818289355 and 6818712685), the presentation lead's (6818330068 and
6818720000) and the technical lead's rulings (6818687523). **This file
is the single source S48 builds
the opening from.** It changes no canon and no code. Where it and canon
differ, canon wins; canon PR #219 records the owner's decisions of
2026-11-12, and section 8 says which canon text S48's implementation PR
edits first.
**Author:** outside reviewer (Claude Fable 5.2), 2026-11-12.
**Base:** `main` at a959921. Slice: `S48-first-evening.md` (PR #218).
**Scope:** from opening your eyes in the Wake Hall to standing on Sodium
Row knowing what to do next. Vesper, the first job and the rest of the
evening are S48 part 1.

H1 and the S25 layout approval are not granted by this document.

Each claim is labelled:

- **[built]**: works on `main` today. I ran it through the production
  `Core` and the real door renderer at 80x24 and 132x50.
- **[decided]**: an owner decision of 2026-11-12, or a lead's ruling
  recorded in section 8.
- **[new]**: proposed here.

The mocks are wider than this file's 76-column wrap on purpose: they are
screens.

## 1. What the opening has to do

A person who has never seen the game, playing alone, should be able to
say five things when they reach the Row:

1. I am a clone on a ninety-day lease, and the days count.
2. Arrow keys walk, `E` uses the thing beside me, and the HERE box tells
   me what that thing is.
3. `Tab` then `F` is a fight. `J` at a terminal is the other world.
4. A voice in the log is someone talking to me, and I can read it back.
5. I have a card for someone called Vesper at the Tin Halo, at the far
   end of this street.

Nothing else is required of the first ten minutes. Factions, grades,
implants, the market and the Blacksite can all wait.

Three rules shape every beat:

- **Nothing stops the walk.** No full-screen text before the first step.
  Vantongeren talks in the log while the player moves. The one screen
  that takes over, the decant record, opens only on a key the player
  pressed (AGENTS.md §4, "menus never gate on questions").
- **The floor shows the way.** Clinics paint lines on the floor. The
  Wake Hall gets one, from the gurney to the street door.
- **One new thing per beat.** Each beat teaches one key, and the hint
  line names only that key.

## 2. What is there today

From my run on `main` [built]:

- The first screen is the menu "THE WAKE - Choose your archetype". Then
  a name prompt, six pages of briefing, eight recruiter cards, and only
  then the hall.
- The hall has no place record, so no walls are drawn. It is a field of
  dots with four `Θ` and two `$`.
- HERE already names what is in reach: `Θ Decant vat`, `$ Recruiter
  cards`, `+ Corridor door`, `§ Tutorial terminal`, `» Clinic Row`. The
  hint line already carries `E use Corridor door` and `J jack in at
  Tutorial terminal`. This is the best teaching tool the game has, and
  this proposal leans on it.
- The lesson hint is a toast, "The corridor teaches targeting. Tab
  selects; F fires; B skips training.", shown from the first second and
  cut off at 80 columns.
- The orderlies answer "Not yet." The outfitter's name is cut to
  `$ Sablier ...utfitter` in HERE.
- The drone lesson works: it wakes at two tiles, `Tab` and `F` work, and
  `B` skips it.
- The terminal lesson works but takes four screens: `J` puts you on the
  whole Vatside sector grid, `E` opens a ROOM menu whose second row is
  "Enter with NPC risk  BLACK ICE may injure body", Enter starts the
  encounter, and after the Tripwire is down `E` and Enter lift the
  record. The record's text is never shown.
- Outside, Clinic Row's `MERIDIAN PLAZA` sign is 60 tiles from the door,
  and Meridian Plaza's `SODIUM ROW` paint is about 35 tiles from where
  you arrive. Nothing tells you which way the card points.

The geometry [built], which this proposal does not change:

```
########################################     # wall      . floor
#...................#..................#     V decant vat (Θ)
#...................#..................#     D Vantongeren's desk ($)
#..V.V.V.V..........#..................#     C recruiter cards ($)
#...................#   sealed room,   #     @ where you wake (6,5)
#.....@.....D.......#   no door, never #     + corridor door (20,14)
#...................#   seen           #       and street door (38,16)
#...................#..................#     d the drone wakes here (23,14)
#...................#..................#     O outfitter ($)  T terminal (§)
#...................#..................#
#.......C...........#..................#
#...................####################
#...................#..................#
#...................#..................#
#...................+..d...............#
#...................#.............OT...#
#...................#.................+#
#...................#..................#
#...................#..................#
########################################
```

## 3. The room [new]

"One obvious way on" [decided] is met without moving a wall, a door or
an object. Five content changes do it:

1. **A place record,** `looks/vatside-wake-hall.json`, so the hall has
   walls, like the three places P6b shipped.
2. **A painted line** (the paint role) from the tile beside the gurney,
   down past the cards, through the corridor door, past the terminal,
   and ending at the street door:
   - `│` from (7,6) to (7,13), corner `└` at (7,14);
   - `─` from (8,14) to (19,14), and from (21,14) to (36,14);
   - corner `┐` at (37,14), `│` at (37,15), and a last `└` at (37,16),
     the tile beside the street door, so the line visibly ends there.
   The corners are one-character paint words, since a line mark takes
   one glyph. On the floor these shapes can't be taken for a wall:
   walls are `█` at 16 colours and blank facade cells otherwise. People
   and objects draw over the line.
   Every interactable on the way is one step from the line, so HERE
   names each one as the player passes it.
3. **Signs and paint words:** ` DECANT ` on the wall above the vats,
   ` RANGE ` and ` ISSUE ` on the wall above the east room, `CARDS`
   painted by the table, `CLINIC ROW →` painted before the street door.
   A Sablier clinic is kept up: every sign whole, no worn letters, no
   flicker. Arrows are CP437's four (`← → ↑ ↓`) and never diagonal,
   here and in the street paint of 4.10.
4. **The hall is charted** (terminal UI 2.3), with the two rooms on the
   way as its public region. The player sees the room, the line and the
   door before taking a step. The sealed north-east room stays out of
   the region and is never drawn.
5. **The street door is drawn `»`** [decided, item 16]: `»` marks a way
   out of a place, `+` a door inside one. The corridor door stays `+`.
   The tile now agrees with HERE, which already says `» Clinic Row`.

In the mocks, wall faces are drawn as `█`, which is how 16 colours draws
them. At 256 colours and truecolor they are blank cells on the facade
colour (terminal UI 2.2).

## 4. The script

Conventions:

- **Screen** says what changes on screen. **Can do** lists what the
  beat teaches; everything else already works and is never blocked.
- **Next** is the trigger for the next beat. Position triggers are
  tiles in `vatside-wake-hall`.
- Speech is a log line of kind `speech` (gutter `"`). Every spoken line
  below fits two log rows at 80x24 with its speaker's name.
- **Every scripted line goes to the caller alone** [decided]: the
  briefing, the lessons, Okafor's read-out of the record and the voice
  layer. A veteran decanting after a death, or a second Wake on the
  next gurney, never hears someone else's opening or learns their
  template.
- **Nobody moves for the opening** [decided]. Vantongeren stays at her
  desk, the orderlies by the vats, Okafor by the street door, the
  outfitter at the counter. Anything else would be seen by everyone in
  the hall.
- **Vantongeren's lines reach the caller anywhere in the hall's public
  region** [decided, item 9]. They are scripted and caller-only; there
  is no general rule for speech out of sight. In the fiction it is the
  hall channel, and one line of Okafor's names it. A hall-channel line
  looks like any spoken line: the ordinary speech gutter and her name,
  with no tag [decided, item 23].
- Lines marked **(kept)** are the existing text, word for word. Lines
  marked **(new)** or **(changed)** are not. Section 4.12 lists every
  change to existing text. The creative lead has adopted every line
  below; where a line is the creative lead's own wording it says
  **(creative lead)**.
- **Pacing** [new]: at least four seconds between two spoken lines. A
  beat's lines wait for that gap. The beats are only a few steps apart,
  so a player who keeps walking will trigger the next beat while lines
  are still waiting. Then:
  - a line marked **†** is an anchor. It is never dropped while the
    player is in the hall. There are six: 1.1, 2.1, 3.1, 3.3, 6.2 and
    10.1. Together they say what you are, how long the lease is, what
    death costs and where to go;
  - every other waiting line from an earlier beat is dropped.

  **Order.** The current beat's lines always go first, in their own
  order. An older anchor is spoken only when no current line is
  waiting, oldest first. So a lesson line is never held up by the
  briefing.

  **Quiet times.** No briefing line is spoken while a target is set,
  while an ICE is warned, in a menu or text page, or while jacked in.
  The lines that belong to a fight are the exception: 6.2 and 6.5 are
  spoken during the drone fight, at the first hit, because that is
  the moment they are about. At 80x24 line 6.2 takes two of the three
  log rows and the newest danger line keeps the third, so no danger
  line leaves the log inside ten seconds (terminal UI 2.5).

  **What a runner misses.** An anchor still unspoken when the player
  leaves the hall is dropped. A player who skips both lessons and
  never pauses can reach the street in about a minute having heard
  four or five lines. That is their choice. The lease is still on the
  side panel, and every line stays readable at Vantongeren's desk
  (4.11).

  Worked example, from the tile distances. Walking is one tile per
  200 ms, diagonals included (game design 5.2). The gurney is at
  (6,5), the line starts at (7,6), and the drone wakes when the player
  is within two tiles of (23,14): 23 steps, a little under five
  seconds without a pause. That player hears 1.1 at once and 2.1 four
  seconds later, and then the drone wakes. 6.1 is a danger line and
  comes at once. 6.2 and 6.5 come at the first hit. After the fight
  6.6 comes at once; then, on the walk to the terminal, 7.1 and 7.2
  when their tiles are reached, and 3.1 and 3.3 in the gaps between
  them. If the player jacks in before those two are spoken, they wait,
  and follow 9.8 and 9.9 after the record. Lines 1.2, 1.3, 2.2, 2.3,
  3.2 and all of beats 4 and 5 were dropped. A player who stands
  still for the first half minute hears beats 1 to 3 in full, in
  order.
- **Hints** are the bottom row. A lesson hint shows until its key has
  been used once, then never again for that character. It takes the
  objective slot of the row [decided, item 10]. **While a lesson hint
  shows, the row holds only that hint, any `E`/`J` context and
  `? help`** [decided]: none of the other key-help groups. On zone
  screens `? help` ends the row; on menu and text pages the built row
  leads with it. Key names come from the caller's keymap; the text
  below is the arrows keymap.

### 4.1 Beat 1: eyes open

- **Screen.** The hall, in the new frame: double lines, `POCKET`. You
  are `@` beside the vats. Vantongeren stands at her desk, two orderlies
  near the vats. The line runs from your feet to the door. The side
  panel shows your gurney number, `No. 0431`, where your name will be
  [decided, item 3], an empty grade slot until the record is read
  [decided, item 24], `day 1/90` [decided, item 13], and full bars.
- **Can do.** Walk. Nothing else is needed.
- **Hint.** `Arrow keys walk. Follow the line on the floor.  ? help`
- **Next.** Beat 2 on your third step, or after 12 seconds.

| # | Speaker | Line |
|---|---|---|
| 1.0 | place | You wake on a gurney under a number. **(kept, first sentence)** |
| 1.1 † | Vantongeren | Open your eyes slowly. The light's cheap and it stays on. **(kept)** |
| 1.2 | Vantongeren | I'm Vantongeren. I run this hall. I was decanted here too, a long time ago, from a template like yours. **(kept)** |
| 1.3 | Vantongeren | I'm telling you that first because it's the only thing I can say that you'll believe. **(kept)** |

The place line is cut to its first sentence. The rest ("White light,
warm plastic, a floor drain. Past the cards, a corridor. Past the
corridor, a terminal.") is now what the screen shows, and at 80x24 the
full paragraph would fill two of the three log rows before she speaks.
The full text stays as the zone's lore.

A second Wake in the hall shows in NEARBY as `☻ No. 0388 ~`. It is the
first other person a new player sees, and it needs no explaining.

```text
╔═VATSIDE═Wake Hall═POCKET══════════════════════════════╤════════════00:00═════╗
║       ██ DECANT ███████████                           │─ TARGET ─────────────║
║       █···················█                           │ none   Tab picks     ║
║       █···················█                           │─ NEARBY ─────────────║
║       █··Θ·Θ·Θ·Θ·☻········█                           │ ☻ Dr. Vantongeren ~  ║
║       █········☻··········█                           │ ☻ Sablier orderly ~  ║
║       █·····@·····$☻······█                           │ ☻ Sablier orderly ~  ║
║       █······│············█                           │                      ║
║       █······│············█                           │                      ║
║       █······│············█                           │                      ║
║       █······│············█                           │                      ║
║       █······│$···········█                           │                      ║
║       █······│·CARDS······██ RANGE ██ ISSUE ██        │──────────────────────║
║       █······│············█··················█        │ No. 0431             ║
║       █······│············█··················█        │ HP  ██████████ 90    ║
║       █······└────────────+────────────────┐·█        │ STA ██████████ 55    ║
║       █···················█·············$§·│·█        │ SHK ░░░░░░░░░░ 0     ║
║       █···················█················└»█        │ 0 ch     day 1/90    ║
╟───────────────────────────────────────────────────────┴──────────────────────╢
║» You wake on a gurney under a number.                                        ║
║" Vantongeren: Open your eyes slowly. The light's cheap and it stays on.      ║
║                                                                              ║
║Arrow keys walk. Follow the line on the floor.  ? help                        ║
╚══════════════════════════════════════════════════════════════════════════════
```

```text
╔═VATSIDE═Wake Hall═POCKET══════════════════════════════════════════════════════════════════════════════════╤════════════00:00═════╗
║                                                                                                           │─ TARGET ─────────────║
║                                                                                                           │ none   Tab picks     ║
║                                                                                                           │─ NEARBY ─────────────║
║                                                                                                           │ ☻ Dr. Vantongeren ~  ║
║                                                                                                           │ ☻ Sablier orderly ~  ║
║                                                                                                           │ ☻ Sablier orderly ~  ║
║                                                                                                           │                      ║
║                                                                                                           │                      ║
║                                                                                                           │                      ║
║                                 ██ DECANT ███████████                                                     │                      ║
║                                 █···················█                                                     │                      ║
║                                 █···················█                                                     │                      ║
║                                 █··Θ·Θ·Θ·Θ·☻········█                                                     │                      ║
║                                 █········☻··········█                                                     │                      ║
║                                 █·····@·····$☻······█                                                     │                      ║
║                                 █······│············█                                                     │                      ║
║                                 █······│············█                                                     │                      ║
║                                 █······│············█                                                     │                      ║
║                                 █······│············█                                                     │                      ║
║                                 █······│$···········█                                                     │                      ║
║                                 █······│·CARDS······██ RANGE ██ ISSUE ██                                  │                      ║
║                                 █······│············█··················█                                  │                      ║
║                                 █······│············█··················█                                  │                      ║
║                                 █······└────────────+────────────────┐·█                                  │                      ║
║                                 █···················█·············$§·│·█                                  │                      ║
║                                 █···················█················└»█                                  │                      ║
║                                 █···················█···CLINIC ROW →···█                                  │                      ║
║                                 █···················█··················█                                  │                      ║
║                                 ████████████████████████████████████████                                  │                      ║
║                                                                                                           │                      ║
║                                                                                                           │                      ║
║                                                                                                           │                      ║
║                                                                                                           │──────────────────────║
║                                                                                                           │ No. 0431             ║
║                                                                                                           │ HP  ██████████ 90    ║
║                                                                                                           │ STA ██████████ 55    ║
║                                                                                                           │ SHK ░░░░░░░░░░ 0     ║
║                                                                                                           │ 0 ch     day 1/90    ║
╟───────────────────────────────────────────────────────────────────────────────────────────────────────────┴──────────────────────╢
║» You wake on a gurney under a number.                                                                                            ║
║" Vantongeren: Open your eyes slowly. The light's cheap and it stays on.                                                          ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║Arrow keys walk. Follow the line on the floor.  ? help                                                                            ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
```

### 4.2 Beat 2: the shape

- **Screen.** Unchanged. You are on the line.
- **Next.** Beat 3 when you reach row 8.

| # | Speaker | Line |
|---|---|---|
| 2.1 † | Vantongeren | You're a Wake. You came out of a vat this morning from a Sablier template that's older than the wall. **(kept)** |
| 2.2 | Vantongeren | You don't remember anything because there's nothing to remember; the template doesn't carry memories, only a shape. **(kept)** |
| 2.3 | Vantongeren | The shape is yours now. What you put in it is your business. **(kept)** |

### 4.3 Beat 3: the lease

- **Next.** Beat 4 when you are one step from the cards table (rows 9
  to 11 on the line).

| # | Speaker | Line |
|---|---|---|
| 3.1 † | Vantongeren | Here's the part they make me say and the part I'd say anyway. For ninety days you're Sablier property under lease. **(kept)** |
| 3.2 | Vantongeren | You'll find that means less than it sounds like: you can go where you want, work for who you want, and nobody can sell you. **(kept)** |
| 3.3 † | Vantongeren | After ninety days you're a person, with a name on the civic roll. Nothing gets you there sooner. The days count without you. **(changed, creative lead)** |

"Nothing gets you there sooner" is canon PR #219's sentence. "They
count without you" is repeated in her talk line (4.12) on purpose.

### 4.4 Beat 4: the cards

- **Screen.** HERE shows `$ Recruiter cards`. The floor says `CARDS`.
- **Can do.** `E`. This is where `E` is learned: on something harmless,
  named on screen, that can be put down again.
- **Hint.** The context the door already builds: `E look at Recruiter
  cards  ? help`. No lesson hint is added.
- **`E`** opens the existing card menu (the eight pitches, "Take no
  card"), with its action bar `enter take this card  Esc/B put them
  down`. A taken card logs `√ You take the <faction> card.` and the
  table then reads as the existing recruitment contact. A card counts
  when it is taken here. Leaving without one is not final: the table
  stays open in the Wake Hall afterwards [decided, item 4].
- **Next.** Beat 5 when you reach column 12 or beyond on row 12 or
  below. The cards are never required.

| # | Speaker | Line |
|---|---|---|
| 4.1 | Vantongeren | The city's run by eight groups who'd each like you to think they're the only one that matters. **(kept)** |
| 4.2 | Vantongeren | Every one of them has left a card on my desk. I hand them out without preference. **(kept)** |
| 4.3 | Vantongeren | They all resent that and none of them can prove it. Take one, or don't. It's an introduction, not a contract. **(kept)** |
| 4.4 | Vantongeren | Work registers your signature sooner: a flat in your own name, and a side, if one will have you. It isn't personhood. It's a pen. **(new, creative lead)** |

She never says "Signatory". The panel shows the grade's name when it
arrives.

```text
╔═VATSIDE═Wake Hall═POCKET══════════════════════════════╤════════════00:00═════╗
║       ██ DECANT ███████████                           │─ HERE ───────────────║
║       █···················█                           │ $ Recruiter cards    ║
║       █···················█                           │─ TARGET ─────────────║
║       █··Θ·Θ·Θ·Θ·☻········█                           │ none   Tab picks     ║
║       █········☻··········█                           │─ NEARBY ─────────────║
║       █···········$☻······█                           │ ☻ Dr. Vantongeren ~  ║
║       █······│············█                           │ ☻ Sablier orderly ~  ║
║       █······│············█                           │ ☻ Sablier orderly ~  ║
║       █······│············█                           │                      ║
║       █······│············█                           │                      ║
║       █······@$···········█                           │                      ║
║       █······│·CARDS······██ RANGE ██ ISSUE ██        │──────────────────────║
║       █······│············█··················█        │ No. 0431             ║
║       █······│············█··················█        │ HP  ██████████ 90    ║
║       █······└────────────+────────────────┐·█        │ STA ██████████ 55    ║
║       █···················█·············$§·│·█        │ SHK ░░░░░░░░░░ 0     ║
║       █···················█················└»█        │ 0 ch     day 1/90    ║
╟───────────────────────────────────────────────────────┴──────────────────────╢
║" Vantongeren: The city's run by eight groups who'd each like you to think    ║
║  they're the only one that matters.                                          ║
║                                                                              ║
║E look at Recruiter cards  ? help                                             ║
╚══════════════════════════════════════════════════════════════════════════════
```

### 4.5 Beat 5: the corridor door

- **Screen.** HERE shows `+ Corridor door`. The door stands open
  [built]; walking through it works.
- **Next.** Beat 6 when you are within two tiles of (23,14), which is
  today's wake-up distance for the drone.

| # | Speaker | Line |
|---|---|---|
| 5.1 | Vantongeren | When you're ready, walk to the door. There's a drone in the corridor that's been malfunctioning since Tuesday. **(kept)** |
| 5.2 | Vantongeren | Deal with it; consider it the first thing you've ever done. **(kept)** |
| 5.3 | Vantongeren | Then there's a terminal. Nurse Okafor will show you how to jack in. The door past it opens from the other side. **(kept)** |

### 4.6 Beat 6: the drone

- **The weapon** [decided]. The lesson is fought with a **hall training
  pistol**, issued for the lesson only. It hangs on a cable by the
  corridor door; nothing new has to be drawn for it. It is in the
  player's hand when the drone wakes, it is bound, it never leaves the
  Wake Hall, and it
  is removed when the lesson ends (drone down or skipped) or the player
  leaves. The Kestrel sidearm comes with the starter kit, after the
  record (9.10). So TARGET reads `with Training pistol` here.
- **Screen.** A `τ` on the line ahead. NEARBY lists what is in sight in
  this room, hostile first: `τ Training drone !`, then Okafor and the
  outfitter. Vantongeren and the orderlies are behind the wall and are
  neither drawn nor listed. After `Tab`, TARGET fills in: name, health
  bar, range, `hostile`, your weapon.
- **Can do.** `Tab`, then `F`. `B` walks past the lesson [built].
- **Hints,** one at a time:
  - `Tab picks the drone.  B walks past it  ? help`
  - after `Tab`: `F fires. Keep firing.  B walks past it  ? help`
- **Next.** Beat 7 when the drone is down or skipped.

| # | When | Speaker | Line |
|---|---|---|---|
| 6.0 | the drone wakes | system | A pistol on a cable by the door. Your hand takes it before you decide. **(creative lead)** |
| 6.1 | the drone wakes | danger | A drone turns in the corridor. It has seen you. Its shots can't kill. **(changed)** |
| 6.2 † | its first hit on you, or see below | Vantongeren | If you die, you'll wake up here, or somewhere like here, with a bill. Sablier keeps a copy. **(kept)** |
| 6.3 | four seconds later | Vantongeren | It's not free and it's not perfect and you'll lose a little of yourself each time. But it's a copy. **(kept)** |
| 6.4 | four seconds later | Vantongeren | It's more than the city outside the wall gets. **(kept)** |
| 6.5 | after 6.2, once | Okafor | That's her on the hall channel. She watches every first one. **(new, creative lead)** |
| 6.6 | the drone is down | combat | The drone stops. It had been trying since Tuesday. **(changed)** |
| 6.7 | the drone is skipped | system | You walk past it. It keeps trying. **(new)** |
| 6.8 | the lesson ends, or you leave the hall | system | The cable reels the pistol back to the wall. **(creative lead)** |

**Order.** When the drone wakes: 6.0, then 6.1, both at once. At the
end: 6.6 or 6.7, then 6.8, then 6.2 if it is still owed. A disconnect
shows no line. 6.0 and 6.8 are the creative lead's (#220, comment
6818712685). The cable carries the rule, so nobody has to say the
pistol stays in the hall; and the hand that moves first is the
template's, two beats before the record says so.

**6.2 always gets said.** A player who skips the drone with `B`, or
downs it before it lands a hit, never fires "its first hit". Then 6.2
is spoken when the lesson ends, after 6.6 or 6.7 and 6.8, and ahead of
any older anchor, and 6.5 follows it as usual. The next thing this
player does is take a job, so they hear what dying costs first.

Combat lines (`* Miss: Training drone.`, `‼ Training drone hits you for
3.`) are unchanged [built]. 6.2 and 6.5 are spoken during the fight
(see Pacing). 6.3 and 6.4 are ordinary lines: they follow 6.2 at the
gap, and are dropped if the fight has ended and the player has reached
the next beat.

Vantongeren is in the other room for 6.2 to 6.4, and for any anchor
line still queued when the player went through the door. That is the
hall channel (conventions), and 6.5 is the one line that names it.

```text
╔═VATSIDE═Wake Hall═POCKET══════════════════════════════╤════════════00:00═════╗
║       █···················█                           │─ HERE ───────────────║
║       █··Θ·Θ·Θ·Θ··········█                           │ + Corridor door      ║
║       █···················█                           │─ TARGET ─────────────║
║       █···········$·······█                           │ Training drone       ║
║       █······│············█                           │ HP  ██████░░░░ 60%   ║
║       █······│············█                           │ 3 m  open  hostile   ║
║       █······│············█                           │ with Training pistol ║
║       █······│············█                           │─ NEARBY ─────────────║
║       █······│$···········█                           │ τ Training drone !   ║
║       █······│·CARDS······██ RANGE ██ ISSUE ██        │ ☻ Nurse Okafor ~     ║
║       █······│············█··················█        │ ☻ Wake Outfitter ~   ║
║       █······│············█··················█        │──────────────────────║
║       █······└────────────+@──τ────────────┐·█        │ No. 0431             ║
║       █···················█·············$§·│·█        │ HP  ████████▌░ 78    ║
║       █···················█············☻··☻└»█        │ STA ██████████ 55    ║
║       █···················█···CLINIC ROW →···█        │ SHK ▌░░░░░░░░░ 2     ║
║       █···················█··················█        │ 0 ch     day 1/90    ║
╟───────────────────────────────────────────────────────┴──────────────────────╢
║‼ Training drone hits you for 3. (x4)                                         ║
║" Vantongeren: If you die, you'll wake up here, or somewhere like here, with a║
║  bill. Sablier keeps a copy.                                                 ║
║F fires. Keep firing.  B walks past it  ? help                                ║
╚══════════════════════════════════════════════════════════════════════════════
```

```text
╔═VATSIDE═Wake Hall═POCKET══════════════════════════════════════════════════════════════════════════════════╤════════════00:00═════╗
║                                                                                                           │─ HERE ───────────────║
║                                                                                                           │ + Corridor door      ║
║                                                                                                           │─ TARGET ─────────────║
║                                                                                                           │ Training drone       ║
║                                                                                                           │ HP  ██████░░░░ 60%   ║
║                                                                                                           │ 3 m  open  hostile   ║
║                                                                                                           │ with Training pistol ║
║                                                                                                           │─ NEARBY ─────────────║
║                                                                                                           │ τ Training drone !   ║
║                                 ██ DECANT ███████████                                                     │ ☻ Nurse Okafor ~     ║
║                                 █···················█                                                     │ ☻ Wake Outfitter ~   ║
║                                 █···················█                                                     │                      ║
║                                 █··Θ·Θ·Θ·Θ··········█                                                     │                      ║
║                                 █···················█                                                     │                      ║
║                                 █···········$·······█                                                     │                      ║
║                                 █······│············█                                                     │                      ║
║                                 █······│············█                                                     │                      ║
║                                 █······│············█                                                     │                      ║
║                                 █······│············█                                                     │                      ║
║                                 █······│$···········█                                                     │                      ║
║                                 █······│·CARDS······██ RANGE ██ ISSUE ██                                  │                      ║
║                                 █······│············█··················█                                  │                      ║
║                                 █······│············█··················█                                  │                      ║
║                                 █······└────────────+@──τ────────────┐·█                                  │                      ║
║                                 █···················█·············$§·│·█                                  │                      ║
║                                 █···················█············☻··☻└»█                                  │                      ║
║                                 █···················█···CLINIC ROW →···█                                  │                      ║
║                                 █···················█··················█                                  │                      ║
║                                 ████████████████████████████████████████                                  │                      ║
║                                                                                                           │                      ║
║                                                                                                           │                      ║
║                                                                                                           │                      ║
║                                                                                                           │──────────────────────║
║                                                                                                           │ No. 0431             ║
║                                                                                                           │ HP  ████████▌░ 78    ║
║                                                                                                           │ STA ██████████ 55    ║
║                                                                                                           │ SHK ▌░░░░░░░░░ 2     ║
║                                                                                                           │ 0 ch     day 1/90    ║
╟───────────────────────────────────────────────────────────────────────────────────────────────────────────┴──────────────────────╢
║‼ Training drone hits you for 3. (x4)                                                                                             ║
║" Vantongeren: If you die, you'll wake up here, or somewhere like here, with a bill. Sablier keeps a copy.                        ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║F fires. Keep firing.  B walks past it  ? help                                                                                    ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
```

### 4.7 Beat 7: the terminal

- **Screen.** HERE shows `§ Hall terminal` and `$ Wake Outfitter`
  (renamed so both fit the panel). Okafor stands by the street door.
- **Can do.** `J`.
- **Hint.** The context the door already builds: `J jack in at Hall
  terminal  E open Wake Outfitter  ? help`. Nothing else takes the row
  in this beat.
- **Next.** Beat 8 on `J`. Beat 9 directly if the player presses `E` on
  the outfitter, Okafor or the street door instead: the terminal is a
  lesson, and lessons can be skipped [decided].

| # | When | Speaker | Line |
|---|---|---|---|
| 7.1 | you pass (27,14) | Okafor | Up you get. Vantongeren does the speech; I do the walking. **(kept)** |
| 7.2 | within two tiles of the terminal | Okafor | Stand close and jack in. Your body stays up here with me. **(new, creative lead)** |

No key name is spoken by a person. The hint row says `J`.

```text
╔═VATSIDE═Wake Hall═POCKET══════════════════════════════╤════════════00:00═════╗
║       █···················█                           │─ HERE ───────────────║
║       █··Θ·Θ·Θ·Θ··········█                           │ § Hall terminal      ║
║       █···················█                           │ $ Wake Outfitter     ║
║       █···········$·······█                           │─ TARGET ─────────────║
║       █······│············█                           │ none   Tab picks     ║
║       █······│············█                           │─ NEARBY ─────────────║
║       █······│············█                           │ ☻ Nurse Okafor ~     ║
║       █······│············█                           │ ☻ Wake Outfitter ~   ║
║       █······│$···········█                           │                      ║
║       █······│·CARDS······██ RANGE ██ ISSUE ██        │                      ║
║       █······│············█··················█        │                      ║
║       █······│············█··················█        │──────────────────────║
║       █······└────────────+──────────────@─┐·█        │ No. 0431             ║
║       █···················█·············$§·│·█        │ HP  ██████████ 90    ║
║       █···················█············☻··☻└»█        │ STA ██████████ 55    ║
║       █···················█···CLINIC ROW →···█        │ SHK ░░░░░░░░░░ 0     ║
║       █···················█··················█        │ 0 ch     day 1/90    ║
╟───────────────────────────────────────────────────────┴──────────────────────╢
║* The drone stops. It had been trying since Tuesday.                          ║
║" Okafor: Stand close and jack in. Your body stays up here with me.           ║
║                                                                              ║
║J jack in at Hall terminal  E open Wake Outfitter  ? help                     ║
╚══════════════════════════════════════════════════════════════════════════════
```

### 4.8 Beat 8: down and back

- **Screen.** The Lattice view of the training core: one room, one
  Tripwire. **The training terminal enters its own core directly**
  [decided, item 6], so the player never sees the district grid or the
  BLACK ICE row in the first five minutes. The grid first appears on
  the player's first real jack-in.
- **Can do.** `Tab`, `1`, `E`, `J`.
- **Hints,** one at a time:
  - `Tab picks the Tripwire.  J leaves  ? help`
  - `1 casts Pick. Let it land.  J leaves  ? help`
  - Tripwire down: `E opens the room.  J leaves  ? help`
  - in the room menu the action bar is the hint [built]; the only row
    is `Your decant record  text  ready`
  - record lifted: `J brings you back.  ? help`
- **Next.** Beat 9 when you are back in your body.

| # | When | Kind | Line |
|---|---|---|---|
| 8.1 | on jack-in | system | The city goes quiet. Cells resolve under your feet. **(kept)** |
| 8.2 | | system | Your body stays upstairs. Okafor has it. **(changed)** |
| 8.3 | the Tripwire warns | danger | Training Tripwire: alarm, 2s warning. Pick; J leaves the lesson. **(kept)** |
| 8.4 | Tripwire down | combat | Pick hits Training Tripwire: 10. Integrity 0. **(kept)** |
| 8.5 | lift starts | system | Lifting Your decant record: 3s, 0 trace on start. **(kept)** |
| 8.6 | lift done | system | Transfer committed: Your decant record. **(kept)** |
| 8.7 | on jack-out | system | You jack out. Your body is here. **(kept)** |

Today 8.2 is "Your body stays upstairs. Its shelter still matters.",
followed by "Arrows follow links. J brings you back from a public
cell." Neither is true of this one-room lesson, so the training
terminal uses 8.2 and drops the second line. Every other terminal keeps
both.

One fault to fix on the way [built]: a Pick cast that the Tripwire
interrupts logs `‼ Your program cast is interrupted.` and nothing says
to cast again. The hint `1 casts Pick. Let it land.` stays up until a
cast lands.

```text
╔═WAKE HALL / CORE═POCKET═══════════════════════════════╤════════No. 0431══════╗
║ (01)                                                  │INTEGRITY 100/100     ║
║                                                       │TRACE 0               ║
║                                                       │BODY POCKET           ║
║                                                       │HP 90/90              ║
║                                                       │RIG                   ║
║                                                       │1 Pick                ║
║                                                       │2 Umbrella            ║
║                                                       │3 Empty               ║
║                                                       │ROOM                  ║
║                                                       │Training terminal     ║
║                                                       │                      ║
║                                                       │                      ║
║ ROOM / Training terminal                              │                      ║
║ > Training Tripwire 10/10 [warning 1.4s]              │                      ║
║ alarm / entry / 5 integrity, 0 body damage            │                      ║
║ Pick; J leaves the lesson                             │                      ║
║                                                       │                      ║
╟───────────────────────────────────────────────────────┴──────────────────────╢
║+ The city goes quiet. Cells resolve under your feet.                         ║
║‼ Training Tripwire: alarm, 2s warning. Pick; J leaves the lesson.            ║
║                                                                              ║
║1 casts Pick. Let it land.  J leaves  ? help                                  ║
╚══════════════════════════════════════════════════════════════════════════════
```

### 4.9 Beat 9: the record

This is the archetype choice [decided: after both lessons]. In the
fiction nothing is chosen: the template was fixed in the vat (bible
8.1), and the player is reading their own record aloud. The creative
lead has adopted that framing.

- **Opens when** the player comes back from the terminal with the
  record, or presses `E` on the outfitter, on Okafor, or on the street
  door without a template. It never opens by itself anywhere else.
  `Esc` puts it down and returns to the hall; the street door asks
  again.
- **Screen.** The built menu geometry [built, P12], with a new title,
  `DECANT RECORD - No. <digits> - Template`, and four rows:
  - at 80x24 the detail is the fixed box of 66 columns by 4 rows at
    y=12, above the action bar;
  - at 132x50 the list is on the left and the detail is the right-hand
    column, 53 wide.
  The detail is the existing archetype paragraph and one new last line
  that points back at what the player just did, **with no blank line
  between them**, so all four fit 66x4 (Cantor exactly). The selected
  row is shown by the menu's highlight, which plain text can't show:
  the 80x24 mock has Cantor selected and the 132x50 mock Ghost.
- **Action bar:** `enter read this line  Esc/B put the record down`.
  **Hint row:** `? help  Enter read this line  Esc/B put the record
  down`, the same verbs.
- **Then** the existing name prompt: `Name for the roll (Enter keeps
  Stan):`. The handle is the default; the gurney number is never a
  name, and names of the form `No. <digits>` are reserved [decided,
  item 3].
- **Then** the kit is issued and the side panel changes: the name
  replaces the number, the grade appears, and the bars move to the
  template's real numbers. A Hardline sees HP go from 90 to 130. That
  change is the lesson in what a template is.

| # | When | Speaker | Line |
|---|---|---|---|
| 9.1 | the record opens after the terminal | Okafor | Read me the template line. I have to hear you say it. **(new)** |
| 9.2 | it opens without the terminal lesson | Okafor | No record in hand? I keep a copy. Read me the template line. **(new)** |
| 9.3 | Hardline read | Okafor | Hardline. Thought so. You took that hit like furniture. **(new)** |
| 9.4 | Ghost read | Okafor | Ghost. You didn't make a sound on my floor. I mind that. **(new)** |
| 9.5 | Cantor read | Okafor | Cantor. Don't hum in here. The vats pick it up. **(new)** |
| 9.6 | Operator read | Okafor | Operator. You've been counting my staff since you came in. **(new)** |
| 9.7 | before the name prompt | Okafor | And a name. The roll wants one. **(new)** |
| 9.8 | name entered | Vantongeren | Many names vanish from the lease rolls. Some leave the work; some disappear. The roll does not tell me which. **(kept)** |
| 9.9 | four seconds later | Vantongeren | Keep your own record. **(kept)** |
| 9.10 | kit issued | reward | Issued: sidearm, 50 rounds, baton, two patches, two rations. **(new)** |
| 9.11 | kit issued | reward | 200 chits. A card, on top: Vesper, the Tin Halo, Sodium Row. **(new)** |

9.3 to 9.6 are caller-only like everything else: nobody else in the
hall learns the template from Okafor. They never claim something that
didn't happen. 9.3's second sentence needs the drone to have hit the
player: if the drone was skipped, or went down before it landed a hit,
9.3 is "Hardline. Thought so." alone. The script's "first hit" trigger
already records that. 9.4 is the same kind of claim: its second and
third sentences need the player never to have fired in the hall;
otherwise it is "Ghost. Thought so." alone. 9.5 is an instruction and
9.6 is Okafor's opinion of you, so neither depends on what happened.
The guard on 9.4 is mine, added after the creative lead adopted the
line; the wording of the short forms is theirs.

Detail text per row (the existing paragraph, then the new line):

| Row | Existing paragraph | New last line |
|---|---|---|
| Hardline | You hold the heavy end. You can use heavy weapons and armour. Your frame takes the load. Your body takes two more implants than most. **(last sentence changed)** | That drone would have hurt you less. |
| Ghost | You carry a native rig. You can jack in anywhere. You move quietly and use stealth. Your nerve and cortex do the work. **(kept)** | You wouldn't have needed the terminal. You carry your own. |
| Cantor | You hear the signal. You can use resonance implants, hymns and dissonance. Your First Ear starts with Steady. **(kept)** | The hum under the floor is louder for you. Some people will want to know what you hear. **(creative lead)** |
| Operator | You direct the work. You can control two drones. Your Mule carries the load. You watch the costs and keep your crew together. **(kept)** | You'd have sent something else down that corridor first. |

The same care applies to the new last lines. Each is shown only when
what it points at happened: Hardline's when the drone hit the player,
Ghost's when the player jacked in at the terminal, Operator's when the
drone woke. Cantor's is always shown. Without its last line a detail
is the existing paragraph alone.

These facts (was hit, fired, jacked in, the drone woke) are lesson
progress. They are kept in the stored wake record with the rest of it
(ruling on item 2), so a caller who drops and returns sees the record
they earned.

The validator should check each of these four details, with and
without its last line, against 4 rows at 66 columns, as it checks other
menu details, and the build should
capture all four at both sizes.

```text
╔═DECANT RECORD═POCKET═══════════════════════════════════════════No. 0431══════╗
║    ┌─ DECANT RECORD - No. 0431 - Template ──────────────────────────────┐    ║
║    │ Choice                                                             │    ║
║    │ Hardline                                                           │    ║
║    │ Ghost                                                              │    ║
║    │ Cantor                                                             │    ║
║    │ Operator                                                           │    ║
║    │                                                                    │    ║
║    │                                                                    │    ║
║    │                                                                    │    ║
║    │                                                                    │    ║
║    │                                                                    │    ║
║    │ You hear the signal. You can use resonance implants, hymns and     │    ║
║    │ dissonance. Your First Ear starts with Steady.                     │    ║
║    │ The hum under the floor is louder for you. Some people will want   │    ║
║    │ to know what you hear.                                             │    ║
║    │ enter read this line  Esc/B put the record down                    │    ║
║    └────────────────────────────────────────────────────────────────────┘    ║
╟──────────────────────────────────────────────────────────────────────────────╢
║+ Transfer committed: Your decant record.                                     ║
║" Okafor: Read me the template line. I have to hear you say it.               ║
║                                                                              ║
║? help  Enter read this line  Esc/B put the record down                       ║
╚══════════════════════════════════════════════════════════════════════════════
```

```text
╔═DECANT RECORD═POCKET═══════════════════════════════════════════════════════════════════════════════════════════════No. 0431══════╗
║          ┌─ DECANT RECORD - No. 0431 - Template ──────────────────────────────────────────────────────────────────────┐          ║
║          │ Choice                                               You carry a native rig. You can jack in anywhere. You │          ║
║          │ Hardline                                             move quietly and use stealth. Your nerve and cortex   │          ║
║          │ Ghost                                                do the work.                                          │          ║
║          │ Cantor                                               You wouldn't have needed the terminal. You carry your │          ║
║          │ Operator                                             own.                                                  │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │                                                                                                            │          ║
║          │ enter read this line  Esc/B put the record down                                                            │          ║
║          └────────────────────────────────────────────────────────────────────────────────────────────────────────────┘          ║
╟──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╢
║+ You jack out. Your body is here.                                                                                                ║
║+ Transfer committed: Your decant record.                                                                                         ║
║" Okafor: Read me the template line. I have to hear you say it.                                                                   ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║                                                                                                                                  ║
║? help  Enter read this line  Esc/B put the record down                                                                           ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
```

### 4.10 Beat 10: the door, the street, the Row

- **Screen.** HERE shows `» Clinic Row`; the door tile is `»`; the line
  ends beside it; the floor says `CLINIC ROW →`.
- **Hint.** `E go to Clinic Row  ? help` [built].

| # | When | Speaker | Line |
|---|---|---|---|
| 10.1 † | within two tiles of the street door, kit issued | Vantongeren | Vesper, at the Tin Halo on Sodium Row, pays on time. Her card's the one I put on top. **(kept)** |
| 10.2 | at the door | Okafor | Past the step it's Clinic Row. Our name's on it, not our protection. Walk like you know that. **(new, creative lead)** |

```text
╔═VATSIDE═Wake Hall═POCKET══════════════════════════════╤════════════00:00═════╗
║       █··Θ·Θ·Θ·Θ··········█                           │─ HERE ───────────────║
║       █···················█                           │ » Clinic Row         ║
║       █···········$·······█                           │─ TARGET ─────────────║
║       █······│············█                           │ none   Tab picks     ║
║       █······│············█                           │─ NEARBY ─────────────║
║       █······│············█                           │ ☻ Nurse Okafor ~     ║
║       █······│············█                           │ ☻ Wake Outfitter ~   ║
║       █······│$···········█                           │                      ║
║       █······│·CARDS······██ RANGE ██ ISSUE ██        │                      ║
║       █······│············█··················█        │                      ║
║       █······│············█··················█        │                      ║
║       █······└────────────+────────────────┐·█        │──────────────────────║
║       █···················█·············$§·│·█        │ Stan             G1  ║
║       █···················█············☻··☻@»█        │ HP  ██████████ 130   ║
║       █···················█···CLINIC ROW →···█        │ STA ██████████ 70    ║
║       █···················█··················█        │ SHK ░░░░░░░░░░ 0     ║
║       ████████████████████████████████████████        │ 200 ch   day 1/90    ║
╟───────────────────────────────────────────────────────┴──────────────────────╢
║√ 200 chits. A card, on top: Vesper, the Tin Halo, Sodium Row.                ║
║" Vantongeren: Vesper, at the Tin Halo on Sodium Row, pays on time. Her card's║
║  the one I put on top.                                                       ║
║E go to Clinic Row  ? help                                                    ║
╚══════════════════════════════════════════════════════════════════════════════
```

From here a single **errand line** [decided, items 10 and 12] holds
the objective slot of the hint row. It is an errand, not a contract: a
card is "an introduction, not a contract", and the first contract is
Vesper's to offer. It names the card and the next signed thing to
follow, nothing else. **It clears when Vesper's talk page first
opens**, not when the player reaches the Row, and it never nags.

Each errand line has a declared short form, used at 80x24 before the
`E`/`J` context is dropped, because for a new player the `E` label is
the more useful of the two:

| Where | Full form | Short form |
|---|---|---|
| Clinic Row | `Card: Sodium Row. Follow MERIDIAN PLAZA, east.` | `Card: Sodium Row` |
| Meridian Plaza | `Card: Sodium Row. Take the NEON STAIR.  M map` | `Card: Sodium Row` |
| Sodium Row and the Tin Halo, until Vesper's page opens | `Card: Vesper, at the Tin Halo. Far end of the street.` | `Card: Tin Halo` |

The validator should check that every short form, plus the longest
`E` label on the path, plus `? help`, fits 78 columns.

Two more one-time rows on this walk:

| When | Hint row |
|---|---|
| Clinic Row, after 12 tiles walked | `Shift with an arrow runs.  ? help` (eight seconds) |
| Sodium Row, on first arrival | S44's price notice, if S44 has landed |

**`Ctrl-P`** is taught where it is needed [decided]: the first time a
spoken line is cut or pushed out of view in the hall, the row shows
`Ctrl-P reads back what you missed.  ? help` once (P12 already marks a
cut newest entry `... Ctrl-P`). If that never happens in the hall, it
shows once on Clinic Row, after the shift hint.

Three paint marks make the signs true from where the player stands
[new]:

- Clinic Row: `MERIDIAN PLAZA →` on the pavement at (5,3), in sight of
  the Wake Hall door. The wall sign of the same name is 60 tiles east.
- Meridian Plaza: `← NEON STAIR` at (72,4), in sight of the Clinic Row
  arrival, and `NEON STAIR ↓` at (56,8), where the walk turns south.
  The existing `SODIUM ROW` paint at (58,36) and ` NEON STAIR ` sign at
  (55,39) finish the route.
- Sodium Row needs none: `← NEON STAIR` and the far `TIN HALO →` exist.

The frame teaches safety on this walk without a word: double teal
lines in the hall, single amber `CONTESTED` on Clinic Row, double `SAFE`
on the plaza, single amber again on the Row. Okafor's 10.2 is the only
line that points at it.

The opening ends when the Row's place line arrives. The player has a
card, a name on it, a street, and a direction.

The Row mocks are real captures from `main` with this section's log and
hint rows. The 80x24 one shows the price notice, the 132x50 one the
errand line in full. The header's `SODIUM ROW─Sodium Row` is the built
header; the presentation lead carries that separately.

```text
┌─SODIUM ROW─Sodium Row─CONTESTED─TRUCE─PvP G5+─────────┬────────────00:00─────┐
│    DRINKS     LIVE MUSIC  STAGE              DRINKS   │─ HERE ───────────────│
│ ···,·······,·······,·······,·······,·······,·······,··│ » Meridian Plaza     │
│ ,@← NEON STAIR· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·│─ TARGET ─────────────│
│ ·    , ··    , ··    , ··    , ··    , ··    , ··    ,│ none   Tab picks     │
│ · ,··     ,··     ,··     ,··     ,··     ,··     ,·· │                      │
│ ·    ···     ··, ∙   ··,     ∙·,     ··,     ··,     ·│                      │
│ ··· ·   ∙∙· , · ·∙∙·     ·∙··  ∙ ·· ,    ·· , ∙∙··    │                      │
│ ·, ·∙∙ $··∙ · ∙∙  ··∙    ∙∙·  ∙∙·  ··    , ·· ·∙∙  ·∙∙│                      │
│ ·   ·∙·∙·∙  · ∙·∙···∙ ,··  ·∙∙∙·      ,··     ∙ · ·∙∙ │                      │
│ ···,    ·   ∙··∙· ·,     ··,       ·· ·· ··,     ··,  │                      │
│ ,    ··· ∙··∙∙ ··∙   ·· ,    ··· · ·∙· ··∙   ·· ,    ·│                      │
│ ·    ,·∙▒▒▒▒ · ∙· ·  , ··    ,∙ ·∙ ···▒▒▒▒   , ··    ,│──────────────────────│
│ · ,··  ∙▒▒▒▒∙·····,··     ,··    ∙∙∙∙ ▒▒▒▒,··     ,·· │ Stan             G1  │
│ ·    ··,  ∙  ∙∙·∙    ··,     ··,··∙·· ·      ··,     ·│ HP  ██████████ 130   │
│ ··· ,    ·· ·    ·· ,    ·· ,    ··      ·· ,    ·· , │ STA ██████████ 70    │
│ ·, ··    , ··    , ··    , ··    , ··    , ··    , ·· │ SHK ░░░░░░░░░░ 0     │
│ ·     ,··     ,··     ,··     ,··     ,··     ,··     │ 200 ch   day 1/90    │
├───────────────────────────────────────────────────────┴──────────────────────┤
│» You walk under orange lamps on wet pavement. You hear music from six        │
│  doorways. At the street's end, you see the Tin Halo's sign, lit whole.      │
│                                                                              │
│Fire: Sable comes, no Halo. At a player: Marked 15m, no work.                 │
└──────────────────────────────────────────────────────────────────────────────
```

```text
┌─SODIUM ROW─Sodium Row─CONTESTED─TRUCE─PvP G5+─────────────────────────────────────────────────────────────┬────────────00:00─────┐
│                                                                                                           │─ HERE ───────────────│
│                                                                                                           │ » Meridian Plaza     │
│                                                                                                           │─ TARGET ─────────────│
│                                                                                                           │ none   Tab picks     │
│       DRINKS     LIVE MUSIC  STAGE              DRINKS       TICKETS      OPEN LATE                       │                      │
│    ···,·······,·······,·······,·······,·······,·······,·······,·······,·······,·······,·······,······     │                      │
│    ,@← NEON STAIR· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,·     │                      │
│    ·    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ···     │                      │
│    · ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··    ·     │                      │
│    ·    ···     ··, ∙   ··,     ∙·,     ··,     ··,     ··,     ··,     ··,  ∙  ··,     ··,     ··, ·     │                      │
│    ··· ·   ∙∙· , · ·∙∙·     ·∙··  ∙ ·· ,    ·· , ∙∙··       ·· ∙∙ ∙ ∙· ,  ∙· ·  ·   ·· ,    ·· ,    ·     │                      │
│    ·, ·∙∙ $··∙ · ∙∙  ··∙    ∙∙·  ∙∙·  ··    , ·· ·∙∙  ·∙∙   ,∙∙· ∙∙ ·∙·· ·∙∙ ∙·∙∙   , ··    , ··    ,     │                      │
│    ·   ·∙·∙·∙  · ∙·∙···∙ ,··  ·∙∙∙·      ,··     ∙ · ·∙∙ ,··  · ·∙∙∙     ,∙ · ·  ,··   · ,··     ,···     │                      │
│    ···,    ·   ∙··∙· ·,     ··,       ·· ·· ··,     ··,      ·∙  · ···,     ··,    ···∙∙∙· ∙··,     ·     │                      │
│    ,    ··· ∙··∙∙ ··∙   ·· ,    ··· · ·∙· ··∙   ·· ,    ··  · ·   · ·   ·· ,    ·· ∙ ·∙ ·  ·    ·· ,·     │                      │
│    ·    ,·∙▒▒▒▒ · ∙· ·  , ··    ,∙ ·∙ ···▒▒▒▒   , ··    ,∙ ·  ∙ · ·  ·  ▒▒▒▒    ,∙ ·  ·· · · ·  , ···     │                      │
│    · ,··  ∙▒▒▒▒∙·····,··     ,··    ∙∙∙∙ ▒▒▒▒,··     ,··     ·· ·····,··▒▒▒▒ ,··  ·∙∙ ∙∙·∙·∙ ,··    ·     │                      │
│    ·    ··,  ∙  ∙∙·∙    ··,     ··,··∙·· ·      ··,     ··,·  ∙ ∙∙·     ··,     ··,∙·∙······    ··, ·     │                      │
│    ··· ,    ·· ·    ·· ,    ·· ,    ··      ·· ,    ·· ,    ·· ·    ·· ,    ·· ,    ·· ·    ·· ,    ·     │                      │
│    ·, ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    ,     │                      │
│    ·     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,···     │                      │
│    ···,     ··,     ··,     ··,     ··,     ··,     ··,     ··,     ··,     ··,     ··,     ··,     ·     │                      │
│    ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,    ·· ,·     │                      │
│    ·    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ··    , ···     │                      │
│    · ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··     ,··    ·     │                      │
│    ·    ··,     ··,     ··,     ··,     ··,     ··,     ··,     ··,     ··,     ··,     ··,     ··, ·     │                      │
│    ··· ,    ·· ,    ·· ··  ∙·· ·    ·· ,    ··   ······∙    ·· ,    ··  · ·  ···    ·· ,    ·· ,    ·     │                      │
│    ·, ··    , ··    , ·  ∙ ∙·· ··   , ··    , · · ··· ∙     , ··    , ∙ ·∙··   ·    , ··    , ··    ,     │                      │
│    ·     ,··     ,··   ·· ·   ∙ ∙ ··     ,··  ∙   ·· ∙  ∙ ··     ,·· ∙ · ·   · · ···     ,··     ,···     │                      │
│    ···,     ··,     ···∙  · ··∙     ··,     ··  ∙ · ··∙ ∙   ··,     ···∙∙ · ··· ·   ··,     ··,     ·     │                      │
│    ,    ·· ,    ·· ,   · ··· ·  ·· ,    ·· ,     ·∙· · ··· ,    ·· ,      ∙·∙ · ·· ,    ·· ,    ·· ,·     │                      │
│    ·    , ··    , ··    , ·∙    , ··    , ··    , ·     , ··    , ··    , ··    , ··TIN HALO →  , ···     │──────────────────────│
│    ··,·······,·······,·······,·······,·······,·······,·······,·······,·······,·······,·······,·······     │ Stan             G1  │
│                                                                                          TIN HALO         │ HP  ██████████ 130   │
│                                                                                                           │ STA ██████████ 70    │
│                                                                                                           │ SHK ░░░░░░░░░░ 0     │
│                                                                                                           │ 200 ch   day 1/90    │
│                                                                                                           │                      │
├───────────────────────────────────────────────────────────────────────────────────────────────────────────┴──────────────────────┤
│» You walk under orange lamps on wet pavement. You hear music from six doorways. At the street's end, you see the Tin Halo's sign,│
│  lit whole.                                                                                                                      │
│                                                                                                                                  │
│                                                                                                                                  │
│                                                                                                                                  │
│                                                                                                                                  │
│                                                                                                                                  │
│                                                                                                                                  │
│Card: Vesper, at the Tin Halo. Far end of the street.  E go to Meridian Plaza  ? help                                             │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
```

### 4.11 The people in the hall

**Vantongeren at her desk.** `E` beside her opens her talk page (S42,
P12). Her greeting while you are still unread is 1.1. One new offer,
`h  Hear it again`, opens the three briefing texts as text pages, with
the edits of 4.12, a blank line between paragraphs and the full frame
width (76 columns at 80x24). #216's empty page goes when the wrap stops
appending a blank row after the last paragraph.

**The orderlies** (`npc-sablier-orderly`, two of them). A talk page
with one line and no offers, picked in order, one per visit [new]:

| # | Line |
|---|---|
| O1 | Line's on the floor. It only goes one way. |
| O2 | She'll talk whether you stand there or not. Walk. |
| O3 | Gurney's yours till the next one. That's about an hour. |

One bark for P8's emitter, at the default interval [new]:
"Four today. Vat three's slow again."

**The Wake Outfitter.** Before the record: "Record first. Then I know
what size." [new]. After it, the existing counter opens.

**Okafor after the record.** Her existing lines stand; her "situation"
line ("Your day count's on the record. Keep an eye on it.") is already
right for the calendar lease.

### 4.12 Every change to existing text

The lease and Signatory wording is the creative lead's final text, and
canon PR #219 takes it where the two differ, so there is one text.

| Where | Today | Now | Why |
|---|---|---|---|
| `wake-briefing-2.md` | "After ninety days you're a person, with a name on the civic roll and the right to rent a flat and join whoever will have you. Grade five earns an early discharge. It counts completed work, not time spent waiting." | "After ninety days you're a person, with a name on the civic roll. Nothing gets you there sooner. The days count without you." | The shortcut is gone [decided]. Day 90 grants everything a Signatory has (#219, §3.4), so the line can stay silent on renting and joining. |
| `wake-briefing-3.md` | "Take one, or don't. It's an introduction, not a contract. No recruiter owns your choice. Sablier holds the lease until it is discharged." | "Take one, or don't. It's an introduction, not a contract." then line 4.4 | The last two sentences are rulings, and line 3.1 already says who holds the lease. The cut stands in the briefing text too. |
| `wake-archetype-hardline.md` | "Your implant tolerance gains two points." | "Your body takes two more implants than most." | A stat line in a voice file. |
| `zone-vatside-wake-hall.md` | three sentences as the arrival line | first sentence as the arrival line; all three stay as lore | Log room at 80x24. |
| `vantongeren.json`, line `wake` | "Your lease still runs. You'll find the elapsed days on your record. Grade five earns an early discharge. Time does not earn a grade." | "Your lease still runs. You'll find the days on your record. They count without you." | Contradicts the calendar lease. |
| drone wake line (`npcs/engine.py:423`) | "Your training drone wakes. Tab targets; F fires; B skips. Its shots cannot kill." | line 6.1; the keys move to the hint row | Keys in prose. |
| drone down line (`combat/engine.py:519`) | "The training drone falls silent. The tutorial terminal is ahead." | line 6.6 | "Tutorial" is not a word anyone in Karst says. |
| object names in `vatside-wake-hall.json` | "Tutorial terminal", "Sablier Wake Outfitter" | "Hall terminal", "Wake Outfitter" | The second is cut in HERE today. |

Everything else Vantongeren says is her existing text, in its existing
order, cut into lines.

**Order of merging.** The "Today" column is `main`, where canon still
says grade five earns an early discharge. Lines 3.3 and 4.4 agree with
#219, not with `main`. S48 already waits for the canon PR
(`S48-first-evening.md`, "doesn't start before it merges"); the build
should also test that the briefing content equals the fixed script in
`docs/world/05-story-arcs.md` as merged, so that the one line that is
never dropped can't say the opposite of the rules. The login lines
that contradicted the lease are fixed in #219.

## 5. The voice in the walls: Wake Hall portion

S48 part 5 [decided]: unattributed, rare, optional, one switch. This is
the Wake Hall half of about thirty lines; the Row half is the creative
lead's. The creative lead has adopted the lines below, with T3, T7 and
T8 in their own wording.

**How it shows** [decided, items 9 and 11].

- T1 to T13 are `ambient` log lines: gutter `·`, dim, no speaker. A
  place's own voice is what ambient lines already are (terminal UI
  2.5), so the layer hides in plain sight.
- C1 is a `system`-kind line in the world log. **Neither is ever the
  `notice` kind.** That kind is the node operator's channel: it takes
  the hint row and is kept in help. An in-fiction "Notice:" there would
  make players doubt real maintenance notices. No line of this layer
  appears on the hint row or in help. No line outside the operator's channel starts with "Notice:"; S48 adds a validator test for it.
- Nothing on screen ever names the voice (game design 9.2).
- Every line goes to the caller alone.

**Rules**

- Each line fires at most once per character, ever.
- At most **two** in the Wake Hall on a character's first visit, and at
  least 45 seconds apart. P8's per-caller budget applies on top.
- Never while a target or a warned ICE is active, and never inside six
  seconds of a spoken line. A trigger that lands in those windows is
  lost, not delayed.
- Never in a menu or a text page.
- The other voice answers **at most once per character**, and only
  directly after the character's second line from this layer.
- One content switch turns the whole layer off.

**Triggers and lines**

| # | Trigger | Line |
|---|---|---|
| T1 | 20 seconds on the gurney tile without moving | You can stay. The light stays on anyway. |
| T2 | three bumps into a wall inside ten seconds | The line goes to the door. I didn't paint it. I watched. |
| T3 | five seconds beside a vat | One of these was yours. They don't say which. That one's still warm. **(creative lead)** |
| T4 | standing in the south-west corner, 12 tiles off the line | Nothing over there. I checked. I check a lot. |
| T5 | the card menu closed with no card taken | Eight cards. Nobody left one for me. |
| T6 | "Hear it again" read to its last page | She says that to all of you. She means it each time. I counted. |
| T7 | the drone skipped with `B` | You left it running. I'll keep it company. **(creative lead)** |
| T8 | the drone down | It wanted to be finished, I think. **(creative lead)** |
| T9 | the first jack-in, after the Tripwire is down | You came down. Most of them stop at the door. |
| T10 | ten seconds in the training room after the lift | It's quiet now. I like it when you stay a minute. |
| T11 | a name entered that differs from the handle | <name>. I'll try to say it right. |
| T12 | eight seconds at the street door, kit issued, not leaving | I can't hear you as well out there. Go anyway. |
| T13 | the first decant after a death, in this hall | Again. You look the same. You always look the same to them. |

**The answer,** once, four seconds after the second line:

| # | Line |
|---|---|
| C1 | Hall channel: unscheduled output. Source: none on record. Disregard. |

Settled by the creative lead:

- "Was it hard?" is saved for the Level 1 finale. A player who reaches
  the door should hear that question for the first time there.
- T11 stays, and says the name correctly. The third listener's "It
  said it back wrong" only works if, earlier, it got the name right.
- T13 stays in this layer.
- C1's "hall channel" is the same channel Vantongeren uses. The thing
  in the walls uses her channel, and Sablier's notice gives that away
  without explaining it.
- No line claims to be a person, a machine, or either name. T13 says
  "to them", not "to me".

## 6. Discoverability

**Keys.** Each is learned by using it on something named, never from a
list.

| Key | Learned at | What tells the player |
|---|---|---|
| arrows | beat 1 | the hint row; the painted line gives a reason to move |
| `E` | beat 4, the cards | HERE names the table; the hint row says `E look at Recruiter cards` |
| `Esc` / `B` back | beat 4 | the card menu's action bar |
| `Tab` | beat 6 | the hint row; TARGET filling in is the reward |
| `F` | beat 6 | the hint row, after `Tab` |
| `B` skip | beat 6 | the hint row |
| `J` | beat 7 | the hint row's `J jack in at Hall terminal`; Okafor's 7.2 says what, the row says which key |
| `1` | beat 8 | the hint row; the RIG list shows `1 Pick` |
| Enter in menus | beats 4, 8, 9 | each menu's action bar |
| `Ctrl-P` | when a spoken line is first cut or pushed out of view | the hint row, once; P12's `... Ctrl-P` mark on the cut entry |
| shift-arrows | Clinic Row | the hint row, once, on a long straight walk |
| `M` | Meridian Plaza | the errand line's full form |
| `?` | every beat | the last words of every zone hint row |

**The log** is learned in beat 1: the first thing that happens is a
person speaking in it, by name, with a `"` gutter. By beat 6 the player
has seen four gutters (`»` place, `"` speech, `‼` danger, `*` combat)
doing four different jobs, and never needs them explained.

**Help** [decided, item 14]. `?` in a zone opens today with eight
pages, the first a key table. Page 1 becomes "This screen": the keys
above and a legend of the shapes in view. The conditions:

- the legend is built only from drawn cells, under the names HERE and
  NEARBY use. A hidden exit, a covered NPC's true name, or anything out
  of sight never appears in it;
- every entry gives glyph and word, never colour alone;
- the page fits one 80x24 screen, and keys come from the caller's
  keymap;
- the existing pages follow unchanged.

**Symbols.** Every shape on the path, and what names it:

| Shape | What | Named by |
|---|---|---|
| `@` | you | reverse video; your number, then your name, pinned in the panel; it moves when you press a key |
| `☻` | a person | NEARBY: `☻ Dr. Vantongeren ~`; HERE when beside them |
| `Θ` | decant vat | the ` DECANT ` sign; HERE: `Θ Decant vat` [built] |
| `$` | a desk, table or counter | HERE: `$ Recruiter cards`, `$ Wake Outfitter` [built]; `CARDS` and ` ISSUE ` |
| `│ ─ └ ┐` on the floor | the painted line | the hint row in beat 1; orderly line O1 |
| blank or `█` | wall | you can't walk into it; floor beside a wall always has grain (terminal UI 2.2) |
| `+` | a door inside a place | HERE: `+ Corridor door` [built] |
| `»` | a way out | HERE: `» Clinic Row` [built]; `CLINIC ROW →` on the floor; the line ends at it |
| `τ` | drone | NEARBY: `τ Training drone !`; TARGET after `Tab`; line 6.1 |
| `§` | terminal | HERE: `§ Hall terminal` [built, renamed]; Okafor's 7.2 |
| `(01)` | a Lattice cell | the ROOM block beside it: `Training terminal` [built] |
| `!` and `~` after a name | hostile, neutral | the drone is the first `!`; everyone else in the hall is `~` |
| the frame | how safe you are | the header word; it changes four times on the walk to the Row |

Two shapes are **not** explained in the first ten minutes, on purpose:
cover (`░ ▒ ▓`) and the vendor counter's stock. Both belong to the
first job.

## 7. New against reused

### Reused as built

- The Wake Hall map, every object tile and both doors.
- HERE, TARGET and NEARBY, and the hint row's `E`/`J` context (P3, P5).
- The drone lesson's rules: wake distance, private drone, can't kill,
  `B` skips (`server/npcs/engine.py:405`, `server/combat/engine.py:514`
  and `:925`).
- The training core `cores/lat-wake-hall.json`: one room, the training
  Tripwire, the decant record.
- The card menu and name prompt bodies (`server/wake.py`).
- The menu geometry: the 66x4 detail box at 80x24 and the 53-wide
  detail column at 132x50 (`layout.py`, P12).
- The briefing and archetype texts, less the edits in 4.12.
- Okafor's "first" and "situation" lines; Vantongeren's talk file.
- The place layer: signs, marks and charted ground (P6).
- Talk pages and their fit (S42, P12); the emitter (P8).
- The loan rig at public terminals (game design §4).

### New content

| File | What |
|---|---|
| `content/looks/vatside-wake-hall.json` | theme, three signs, the line to (37,16), two paint words (section 3) |
| `content/zones/vatside-wake-hall.json` | `charted` with its public region; two object names |
| `content/items.json` | the hall training pistol: bound, no sale value, not usable outside the Wake Hall |
| `content/text/wake-briefing-2.md`, `-3.md`, `wake-archetype-*.md`, `zone-vatside-wake-hall.md` | the edits in 4.12; one new last line per archetype |
| the opening's script, as data (see below) | beats, triggers, lines, anchors and hints of section 4; the errand lines with their short forms |
| `content/dialogue/okafor.json`, `vantongeren.json` | the new lines, the changed `wake` line, the "Hear it again" offer |
| a talker file for `npc-sablier-orderly`, bound the way `row-street-regular` is bound to the Sodium regulars | O1 to O3 and the bark |
| the voice layer's file, with its switch | T1 to T13 and C1 |
| `content/looks/vatside-clinics.json`, `core-plaza.json` | three paint marks (4.10) |
| `content/bundles/s27-cast.json` | Vantongeren and Okafor placed and active, at fixed posts; S48 part 4 already asks for this |

### Layout

Nothing new is drawn. What changes:

- the panel's pinned name row reads `No. <digits>` until a name is
  entered. The grade slot stays empty until the record is read, and
  `G1` appears with the record, as the bars change [decided, item 24];
- the pinned lease row reads `day 1/90`, counting from 1 on the day of
  decant, then `on the roll`, or `signatory` once signed. With chits:
  `200 ch   day 1/90`. The 132x50 row `discharge 0/1500` goes
  [decided, item 13];
- the street door's tile is `»` [decided, item 16];
- lesson hints and errand lines take the objective slot of the hint
  row; while a lesson hint shows, the other key-help groups are left
  out [decided, item 10];
- the briefing pages wrap to the frame's width with paragraph breaks
  (`layout.py`: `briefing`, `wake_detail_width`);
- the decant record is the built menu with a new title.

### Code seams

| Seam | Where | Change |
|---|---|---|
| A body before a template | `server/characters.py:284-330` (creation), `server/wake.py` (stages), `server/rules/character.py` | Today the character is created after archetype, name and card. The scene needs a body in the hall first. The body is provisional and held in memory; the character row is created when the record is read [decided, item 2]. The per-user cap is checked before the caller is put in the hall, and `create` reports a refusal: today its cap check (`characters.py:284-285`) returns with no message and no stage change. **A redial takes the Wake over:** the stored wake record is per user (`identities[user]["wake"]`), and `Sessions.connect` (`sessions.py:186-191`) already replaces an older session for the same user with `bye: replaced`. The new session inherits the stored wake record (gurney number, lesson progress) and resumes where the caller was. The old session's provisional body is discarded, with the training pistol removed first, as for a disconnect. No refusal line. |
| Writes that assume a stored character | `server/lattice/engine.py:301` (`queue("save", ..., immediate=True)` on jack-in) and `:339` (on jack-out); `server/combat/engine.py:518` and `:926` (`player.progress["wake_combat"]`, then `remember`); the card's standing (`server/characters.py:296-298`, where `create` sets it today); zone discovery (`server/progression_engine.py:43`, `record_discovery`) | Every one of these is reachable from the hall before the record is read. The body is provisional [decided, item 2], so each must be held in the stored wake record and applied at creation, or suppressed; none may queue a save for an id `create` has not committed. The two saves come first; the skip path through `:926` counts as much as the win path through `:518`. The stored wake record holds the lesson progress, so a caller who drops mid-scene resumes where they were. The build lists each writer and says which it does. |
| The stage machine | `server/wake.py` | From `archetype → name → briefing → card → saving` to: in the hall from the first frame; `record → name → saving` on a key; cards at the table. |
| The number and the reserved name | `server/rules/character.py` (naming rule), `server/characters.py` (`serial`, the stored wake record in `identities[user]["wake"]`), the panel and NEARBY name paths | The gurney number is shown until a name is entered; `No. <digits>` is refused as a name. Source [decided, item 2]: the number is the player serial, taken when the caller is first put in the hall and kept in the stored wake record, which already survives a disconnect. It is then unique across callers and restarts, and a caller who drops and returns has the same number. A Wake that is never finished uses up a serial. |
| The scripted beats | new, beside `server/dialogue_runtime.py` | A small runner for an ordered list of beats with a closed set of triggers (entered a region, a step count, seconds, target set, first hit, drone down or skipped, jacked in, ICE down, data lifted, jacked out, template read, name entered, zone entered, a talk page opened). It emits `speech` lines through the one emit entry point (P4), **to the caller's session only**, anywhere in the hall's public region, and sets the view's `hint`. It holds the queue, the anchors and the quiet times of section 4. Lines and triggers are content, not code. It replaces the toast at `characters.py:330`. |
| The training pistol | `server/npcs/engine.py:405-423` (`training`), `server/combat/engine.py:514-520` and `:925-928`, the travel path out of the hall, the character save and load paths | Issued and equipped when the drone wakes; removed when the drone is down or skipped, on leaving the hall, and on disconnect. It never reaches a save. Three things make that true: on both the win path and the skip path the removal runs **before** `remember`; every character save leaves the training pistol out, so a save that fires mid-lesson can't store it; and a character loaded with one has it dropped, which covers a crash between the wake and the removal. |
| Lesson strings out of the engines | `server/npcs/engine.py:423`, `server/combat/engine.py:519` | The two drone lines move to the script. |
| Cards at the table | `server/faction_engine.py:265-285` and `:428` | `E` on the table opens the card menu for a character who has not taken a card, on the first visit or any later one; the card counts when it is taken [decided, item 4]. For a character who has one, the table is the recruitment contact, as today. |
| Training terminal entry | `server/lattice/engine.py:290-302` | A terminal with `training_core` enters that core's entry room, with lines 8.1 and 8.2 [decided, item 6]. |
| The record's conditional lines | `server/wake.py` (`body`, which already builds the menu detail per caller), the stored wake record | The detail's last line and the second sentences of 9.3 and 9.4 depend on four facts held as lesson progress: was hit, fired, jacked in, the drone woke. The detail is chosen when the menu body is built; nothing changes in the door. |
| The record on jack-out | `server/lattice/engine.py` `leave`, `server/wake.py` | Leaving the training core with the record lifted opens the record menu. |
| Hint row | `hints.py`, `door/present/chrome.py`, `server/views/zone_view.py` | A lesson hint or errand line in the objective slot; the errand's short form before `E`/`J` is dropped; no other key help beside a lesson hint; key names from the caller's keymap. |
| The errand | the script runner, `server/dialogue_runtime.py` | Set when the kit is issued; cleared when Vesper's talk page first opens. No contract record. |
| The street door's glyph | `door/present/zone.py`, the object-to-glyph path in `server/views` | A door that is a zone exit draws `»`. |
| The panel's pinned rows | `door/present/chrome.py`, `me` in the zone view | Number or name; an empty grade slot, then the grade; `day n/90`, `on the roll`, `signatory`. |
| Help page 1 | the help text view | "This screen", from drawn cells only. |
| Voice triggers | P8's emitter | A third source beside barks and zone ambience: triggered lines, caller-only, each with a once-per-character mark; C1 as a `system` line. |
| Content kinds | `content/schema.py`, `validate.py`, `loader.py` | The script and the voice file. The validator checks every spoken line against two rows at 80x24 with its speaker, every hint against 76 columns, each record detail against 4 rows at 66, and each errand short form with the longest `E` label and `? help` against 78. |
| Tests | `tests/character_helpers.py:create`, `tests/door/test_wake_render.py`, the `wake_*` goldens | `create()` walks the old menu order and most of the suite calls it. Keep a direct creation path for tests and give the scene its own walk test (S48's headless walk). Add a two-caller test: the second caller receives none of the first's scripted lines. Add a takeover test: a second connect for the same user mid-Wake replaces the first (`replaced`), and the new session keeps the gurney number and lesson progress, with no training pistol left on the discarded body. |

## 8. Rulings and open items

The numbers are the first draft's, so earlier comments on #220 still
point at the right item.

**Canon note.** The presentation lead's rulings on items 10, 13, 14 and
16 change canon text (terminal UI 2.2, 2.4, 10 and 11). S48's
implementation PR edits that text first, in the same PR, under
AGENTS.md §2. The lease and Signatory wording, the Wake's step order,
the reserved name form and the login lines are canon PR #219's.

### Settled

| # | Item | Ruling | By |
|---|---|---|---|
| 1 | Choosing a template after the vat | The record framing is adopted: the player reads their own record. Game design §4's step list is #219's. | creative lead |
| 2 | The body before the record | A provisional body held in memory. The stored wake record holds the gurney serial and the lesson progress, so a caller who drops mid-scene resumes where they were. The character row is created when the record is read, so storage only ever loads characters with an archetype. The serial is the source of the gurney number. The unread body's numbers are the engineer's to propose in S48: flat, and below every template. | technical lead |
| 3 | The name before the record | The gurney number shows until a name is entered. Names of the form `No. <digits>` are reserved; this goes into #219. | technical lead |
| 4 | When a recruiter card counts | When it is taken at the table. Leaving without one is not final: the table stays open in the Wake Hall afterwards. | technical lead |
| 5 | Charting the Wake Hall | Approved. S48 declares the fingerprint move and re-pins it in the same PR. | technical lead |
| 6 | The training terminal | Approved: it enters its own core directly. The sector grid first appears on the player's first real jack-in. | technical lead |
| 7 | Whether day 90 alone grants renting and joining | It does: day 90 grants everything a Signatory has (#219, §3.4). Lines 3.3 and 4.4 are final and #219 takes them. | creative lead, #219 |
| 8 | Renaming two objects | Allowed. S48 declares any change to P3's frozen labels and re-pins the digest with a reason. | technical lead |
| 9 | Vantongeren heard from the next room | Her opening lines are scripted, caller-only and deliverable anywhere in the Wake Hall's public region. There is no general speech-range rule. In the fiction it is the hall channel. | technical lead; creative lead for the fiction |
| 10 | Where a lesson hint sits | Lesson hints take the objective slot. Each errand line has a declared short form, used before `E`/`J` is dropped. While a lesson hint shows, the row holds only the hint, the `E`/`J` context and `? help`. | presentation lead |
| 11 | The voice layer | `ambient` with no speaker for T1 to T13; C1 a `system` line; never `notice`. "Was it hard?" is saved for the finale. T11 and T13 stay. | creative lead (lines), presentation lead (kinds), confirmed by the technical lead |
| 12 | The errand line | It stays an errand, with no contract behind it, and clears when Vesper's talk page first opens. | creative lead |
| 13 | The lease rows | `day 1/90`, then `on the roll` or `signatory`. `discharge 0/1500` is dropped. | presentation lead |
| 14 | Help's first page | A legend of drawn cells only, with the conditions in section 6. | presentation lead |
| 15 | Login lines 2 and 18 | Fixed in #219. | creative lead, #219 |
| 16 | The street door's glyph | `»` marks a way out of a place, `+` a door inside one. | presentation lead |
| 19 | The record is required before the street | Going into #219: game design §4 states that the record is the one required step before the street. | technical lead |
| 20 | The weapon in the drone lesson | A hall training pistol, issued for the lesson only, bound, kept in the Wake Hall, removed when the lesson ends or the player leaves. The Kestrel sidearm is still issued with the starter kit after the record. | technical lead |
| 21 | A shared hall | Every scripted line is caller-only, Okafor's read-out included. NPC positions are fixed for the whole opening. | creative lead |
| 22 (lines) | Lines 6.0 and 6.8 | The creative lead's wording (6818712685): the pistol is on a cable. A disconnect shows no line. | creative lead |
| 23 | How a hall-channel line looks | The ordinary speech gutter and name, with no tag. | presentation lead |
| 24 | The grade slot before the record | Empty until the record is read. The name row shows only `No. <digits>`, and `G1` appears with the record. | presentation lead |

### Open

17. **"Eight groups"** stays as written until the Lamp Compact is built
    (#90).
18. **The five-minute target.** Read at walking pace with both lessons,
    I estimate three and a half to four and a half minutes. It is
    settled by a timed walk on the S48 build, with someone who hasn't
    read this.
22. **The numbers S48 has to propose.** Two sets, both for game design
    §17 in the implementation PR:
    - the unread body's attributes, flat and below every template
      (ruling on item 2). The mocks show HP 90 and STA 55, the lowest
      template values, as a placeholder; the real numbers will be
      lower;
    - the training pistol's damage, range and cooldown, and whether a
      second Wake sees it drawn. I'd give it the Kestrel sidearm's
      numbers, so the lesson teaches the real weapon.
25. **The Row header's `SODIUM ROW─Sodium Row`** is the built header.
    The presentation lead carries it; the mocks leave it as built.

Two notes the presentation lead carries, neither blocking: the built
menu's `Choice` label above the record's four rows is redundant under
this title and will go with the vendor pages' follow-up; and a mark
for the cable mount by the corridor door is optional.

## 9. What to watch in the H1 session

Not acceptance criteria; things worth writing down while someone plays.

- Does the player move before Vantongeren's second line?
- Do they press `E` at the cards without being told to?
- How many seconds between the drone appearing and the first `Tab`?
- Does anyone read HERE, or only the hint row?
- After a cast is interrupted, do they cast again?
- At the record, do they read all four rows or take the first?
- On Clinic Row, do they turn east?
- If a line from the walls appears, do they say anything out loud?
