# Beyond the roguelike map: three playable paradigms (proposal)

**Status: exploration for the owner, issue #68.** Not canon. All three
prototypes run in the trial build beside the shipped map and the proposal
map (`spec.md`), on the same server, the same simulation and the same
combat. F7 cycles all five views on one game state.

**Direction (owner, 2026-10-25):** after first hands-on play, **auto
(prototype C) is the preferred player-experience direction**. It is a
direction to plan around, not acceptance: final acceptance and the
detailed interaction rules in section 5 remain open and are tuned by
play.

**Visual target (owner, 2026-10-25):** the Tin Halo mockup in section 10
is the bar for how the game should look: scenes that say where you are,
what kind of place it is and who holds it, without a line of text.

```
python scripts/playtest_68.py --geometry candidate --view street   # A: eye level
python scripts/playtest_68.py --geometry candidate --view scene    # B: places
python scripts/playtest_68.py --geometry candidate --view auto     # C: chosen by context
python scripts/playtest_68.py --geometry candidate --view auto --inspect  # C, showing why
```

## 1. The question

The proposal map (`spec.md`) makes Karst legible and lit, and it is
still a top-down grid of glyphs: a roguelike. That is not a failure of
polish. The top-down map is a paradigm with a fixed relationship
between the player and the world, and some of what the owner asks for
sits outside it.

What the top-down map does better than anything else:

- **Tactics.** Exact positions, lines of fire, cover, distances, who is
  behind you. Blacksite's combat is built on this and must keep it.
- **Honesty.** What you see is what the server says you see, cell for
  cell. Nothing is implied.
- **Speed.** One keypress, one tile, no ambiguity.

What it cannot do, however it is lit:

- **Presence.** You are a symbol looking down at other symbols. Nothing
  is ever *in front of* you, *above* you or *at the end of the street*.
  The gazetteer's Sodium Row is "orange lamps, wet pavement, music from
  six doorways"; on a map it is a coloured rectangle you stand on.
- **Scale and verticality.** Karst is towers, terraces, a Ring overhead.
  A plan view has no height and no sky.
- **Places as places.** The map knows tiles; people think in places: the
  stage, the alley behind the bars, the Halo's door. A map makes you
  navigate coordinates, not intentions.
- **Narrative framing.** RPG moments (arriving somewhere, being in a
  bar, choosing where to go next) have no shape of their own on a grid.

So the question is not "how do we make the map nicer?" but "what other
relationship between player and world can a terminal sustain, while the
spatial simulation and tactical combat stay exactly as they are?"

## 2. What stays fixed

All three prototypes are views over the unchanged server:

- the same zone grid, sight, memory, movement rules, cooldowns, combat,
  hazards, NPCs and Lattice;
- the same authorized view bodies (plus the additive presentation fields
  in `spec.md` 3.3);
- the tactical map as the screen of danger: in both prototypes any
  threat (a hazard, a target, a hostile, combat, heat) hands the screen
  to the proposal map, labelled TACTICAL, with absolute arrow keys. They
  are exploration and place paradigms, not combat paradigms.

Each needed exactly one new server affordance, both trial-only behind
`BLACKSITE_PRESENTATION_TRIAL`:

| Affordance | Used by | What it does | What it does not do |
|---|---|---|---|
| `view_shape` (deep camera) | A, B | the view covers as far north and south as east and west (up to the 4096-cell budget), so you can see down a street | it does not widen sight: unseen tiles stay unsent |
| `walk_to` | B | the server walks your body to a known tile, one ordinary `move` per movement cooldown | no speed-up, no teleport, no route through ground you do not know; any key, a hit, a fight or a blocked way stops it |

## 3. Prototype A: street view (eye level)

**What it is.** A first-person view of Karst at street level, drawn
from the tiles the server sent. Two pixels per terminal cell (`▀`), a
grid raycaster in the door. Buildings stand 2.4 tiles tall, with
rooflines against a night sky where the Ring hangs as a band of debris.
Facades take the district's colours from the looks layer; signs glow at
street height and their letters are written across the facade; upper
storeys have windows, some lit. The ground is cast from the same looks:
lamp pools, the card table's felt, puddles, cover, warned hazard tiles.
People and things stand where the server says, as figures and shapes,
with names over the near ones. Unknown space is darkness; remembered
space is drawn at half light, without people.

**Controls.** Up walks forward, Down steps back, Left and Right turn.
Turning is the door's; a step is translated into the ordinary absolute
move, so the server receives exactly what the map would send. A small
radar in the side panel, turned so that ahead is up, keeps the tactical
picture. The line under the view says which way you face, where you are,
and what is in front of you.

![Sodium Row, the stage ahead](paradigms/sodium-stage-street-132x50-truecolor.png)
![Sodium Row looking east](paradigms/sodium-street-east-street-132x50-truecolor.png)
![The alley behind, looking west](paradigms/sodium-alley-west-street-132x50-truecolor.png)
![Meridian Plaza at 80x24](paradigms/plaza-fountain-street-80x24-256.png)
![16 colours](paradigms/sodium-alley-west-street-80x24-16.png)

**What it gives.** Presence. For the first time Sodium Row is a street
you are standing in: buildings on either side, lit windows, the Ring
above, a Sable enforcer close enough to read. The alley behind the bars
is a dark canyon. This is the paradigm closest to Neocron and to the
owner's sense of "entering a different reality", and it costs no
content beyond the looks layer: any dressed zone works.

**What it costs.**

- **Tactical blindness.** You see a 66-degree cone. Someone behind you is
  only on the radar. That is why danger switches to the map; the switch
  itself is a context change at the worst moment, and needs playtesting.
- **Orientation.** Turning is a new skill. Grid-locked 90-degree turns
  keep it simple but make the world feel coarse; smooth turning would
  need the server to know about facing.
- **Resolution.** At 80x24 the view is 55x32 pixels. Shapes read; detail
  does not. Signs are legible near, not far. 132x50 is much better.
- **16 colours.** Whole-cell pixels in grey and a few hues: it reads as
  buildings and windows, and is clearly the weakest tier.
- **Cost.** Measured in the door process: 10 ms per frame at 80x24, 30 to
  39 ms at 132x50, against 5 and 13 to 15 ms for the map. A step redraws
  most cells, up to about 25 KiB at 132x50: fine locally and over SSH,
  heavy on a slow Telnet link.
- **Movement feel.** Walking forward one tile per step is honest to the
  simulation and slower to read than the map: the eye has to rebuild the
  picture each step.

## 4. Prototype B: scenes (places and intentions)

**What it is.** You are always somewhere with a name. The screen leads
with that place: a glimpse at eye level (prototype A's renderer, a
strip), the place's name, a line or two of its own text, who is here,
what is in reach (`E`), and a list of **ways**: other named places,
exits and things you know of, with distance and compass direction.
Choosing a way (comma and full stop) and pressing Space asks the server
to walk you there in real time, through the simulation, step by step; the screen updates as
you go ("Walking to The alley behind. Any key stops."). The place
changes under you as you cross into it. The arrows still step you tile
by tile and Enter still talks (A5 in section 5); the first version used
Up, Down and Enter for ways and was changed after play.

Places are content: `places` in the looks file, each a named rectangle
with a sentence and an anchor tile. The Plaza, Clinic Row and Sodium Row
(shipped and candidate) have them. A place is listed only when its
anchor is on ground you know, so the list of ways never maps unseen
space; on an uncharted contested street you start with very few ways.

![Sodium Row as a scene](paradigms/sodium-street-scene-132x50-256.png)
![Walking to the alley](paradigms/sodium-walking-scene-80x24-256.png)
![Arrived](paradigms/sodium-alley-scene-132x50-256.png)
![Plaza](paradigms/plaza-fountain-scene-80x24-256.png)

**What it gives.** The RPG frame. Sodium Row stops being a rectangle and
becomes a set of places with names and purposes: the Live Room, the card
court, the alley behind, Tin Halo square. You move by intention ("go to
the card court"), not by counting tiles, and you arrive *somewhere*. It
suits safe hubs and social streets, where most time is spent choosing
where to go and whom to see. It gives writers a natural home (a place's
text, later its people and rumours), and it reads well at 16 colours
because it is mostly words.

**What it costs.**

- **Content.** Every zone needs authored places with names and text.
  Without them the paradigm has nothing to show. That is S25 and S27 work
  at roughly ten places per zone.
- **Distance from the body.** Walking by menu removes the skill and
  pleasure of moving. In contested space that matters: positioning is
  half of play. Scenes there must hand over to the map early, or the
  paradigm becomes a liability.
- **Menu drift.** If places are thin, a scene becomes a menu of
  destinations, which is a worse MUD, not a better RPG. The text, the
  glimpse and the people have to carry it.
- **A new mechanic.** `walk_to` is automation. It is honest (ordinary
  steps, known ground only, stops on anything), but it changes how a
  player can act and needs a decision (S1 below).
- **Ambiguity.** "Here: Sodium regular x3" hides who is where. That is
  fine at a bar and wrong in a fight, which is again why threat hands
  over to the map.

## 5. Prototype C: auto (the view follows the moment)

**What it is.** The door picks the view from context instead of a key.

**Principles** (owner and presentation lead, 2026-10-25). These are the
proposed contract for the decider; the rules below implement them.

- **A1 Danger first.** A threat shows the tactical map on the same frame.
  Nothing delays it: no look, no animation, no preference, no pin.
- **A2 No oscillation.** Escalation is immediate; calming is slow. A view
  only becomes calmer automatically when the danger hold ends.
- **A3 Intent, not geography.** How you move says what you are doing.
  Ground only sets where a zone starts.
- **A4 An escape hatch that never fights you.** Your own keys choose the
  view, and the choice holds until you leave the zone. F7 leaves auto.
- **A5 Keys keep one meaning.** Every key does the same in every view, so
  a view change never changes what your fingers do. Arrows always step,
  Enter always talks, and ways have keys of their own.
- **A6 Inspectable.** During development every decision carries its rule
  and a reason, shown live and written to a trace, so tuning can tell a
  wrong decider from wrong surroundings (geometry, content, safety data).

**Rules**, in order; the first that applies decides
(`door/present/context.py`):

1. **danger:** anything threatening (a hazard, a target, a hostile,
   combat, heat) shows the tactical map at once.
2. **hold:** the tactical map stays 5 seconds after the last threat, so a
   fight does not flicker in and out of view.
3. **look:** entering a zone, reaching the end of a walk, or F5 shows a
   short look at eye level: street view for 3 to 4 seconds. It faces
   across the most open known ground to a facade at least 6 m away, so it
   frames the place rather than the wall behind you. It is only a look:
   any key closes it and acts in the view underneath.
4. **intent:** how you last moved in this zone decides. Stepping with the
   arrows means the **map**; choosing a way (comma, full stop, Space) or
   being walked means the **scene**. On the map, the first way key brings
   the scene up rather than acting blind.
5. **ground:** until you move, safe and pocket ground with named places
   is a scene, and everywhere else is the map. Ground with no places is
   always the map.

Because ground only decides where a zone starts, walking along a
safe/contested boundary cannot flip the view; there is nothing to damp.
Way keys do nothing during danger: a walk never starts in a fight.

**Keys under auto and scenes.**

| Key | Map | Scene | Look | Tactical |
|---|---|---|---|---|
| Arrows | step | step (and choose the map) | close the look, step | step |
| Enter | talk | talk | close the look, talk | talk |
| `,` `.` | bring up the scene | previous / next way | close, then as underneath | nothing |
| Space | bring up the scene | walk to the way | close, then as underneath | nothing |
| F5 | look | look | end the look | nothing |
| F10 | inspector | inspector | inspector | inspector |

The manual street view (prototype A) keeps its own turning arrows; it is
a separate prototype, not part of auto.

**The inspector.** F10 (or `--inspect`) draws the current decision over
the bottom of the viewport: its tag, the rule that fired, the reason in
plain words ("you are moving tile by tile", "held 3.0 s more after
hostile Rook", "safe ground with 6 named places"), the inputs it read
(safety, places, how you moved, threat age, look time left), and the last
changes with how long ago each happened. It never covers the side panel,
so DANGER and vitals stay readable. With `BLACKSITE_AUTO_TRACE` set (the
playtest sets it to `.test-tmp/playtest-68-*/auto-trace.jsonl`), each
change is one JSON line: time, from, to, rule, reason, zone, position and
inputs. Reading it after a session shows whether a surprising switch was
the decider (a rule to change) or its surroundings (a safety boundary,
missing places, a threat the server reported).

A tag in the header always names the current view (LOOK, SCENE, MAP,
TACTICAL), and TACTICAL is drawn in the danger colour. The server is
unchanged from A and B: ordinary moves, trial walks, the deep camera.

![One journey under auto, 80x24](paradigms/auto-journey-80x24-256.png)

The journey above is one continuous run of the real door, with no keys
pressed to change views:

1. arriving in the Plaza: a look;
2. settling into the Plaza's scene;
3. walking to the south promenade;
4. arriving there: a look;
5. arriving in Sodium Row: a look;
6. the map on contested ground;
7. Tab targets an enforcer: TACTICAL.

At 132x50 and in truecolor: `paradigms/auto-*-132x50-truecolor.png`.

**What it gives.** Each prototype where it is strongest, without asking
the player to manage views. Arrivals get an establishing shot for free,
the way a film cuts to the street before the scene. Hubs read as places,
and the street is tactical when it should be. It is the closest any of
these come to an RPG that moves between exploration, social space and
danger.

**What it costs.**

- **Scenes lose their arrow cursor.** Ways moved to comma, full stop and
  Space so the arrows can always step (A5). It is less discoverable; the
  hint line names the keys.
- **A step in a scene leaves it.** Under A3 one arrow step means you are
  moving tile by tile, so the map comes up; a way key brings the scene
  back. Whether that reads as responsive or fussy needs play.
- **Contested ground can stay a scene.** If you chose a way, crossing
  onto contested ground keeps the scene until something threatens you
  (A1 still applies at once). That is A3 by design; the danger rule is
  the safety net.
- **Durations are guesses.** The 5-second hold and the 3 to 4 second look
  need play to tune; the trace is there to tune them from.
- **The decider reads threats the door infers.** It treats a nearby
  hostile relation as danger, so a view switch would disclose any NPC the
  server marks hostile. A server-declared threat field is the honest
  input (planned as P4 in the technical lead's integration plan).
- **Big open spaces look empty.** The Plaza is wider than eye level can
  see at this depth, so its look is mostly sky and paving. Looks are at
  their best in streets, alleys and interiors.
- **Bandwidth spikes.** Every look is a full street-view frame.

## 6. Side by side

| | Proposal map (`spec.md`) | A: street view | B: scenes | C: auto |
|---|---|---|---|---|
| Feels like | a lit tactical map | being in the street | being somewhere, choosing where next | a game that frames each moment |
| Best at | tactics, honesty, speed | presence, scale, atmosphere | RPG framing, hubs, social play, writing | arrivals, hubs and danger each in their best view |
| Worst at | presence, places | awareness behind you, 16 colours | moment-to-moment movement, contested space | keys that change meaning at boundaries |
| Content needed | looks per zone | looks per zone (same) | looks plus places with text per zone | as B |
| Server change | additive fields | deep camera | deep camera, `walk_to` | as B |
| Door CPU, 132x50 | 13-15 ms/frame | 30-39 ms/frame | 15-17 ms/frame | as the view it shows; looks cost as A |
| Bandwidth per step | small diff | most of the screen | small diff while walking | small, with a spike per look |
| 16 colours | good | crude | good | good, except looks |
| Danger | native | hands over to the map | hands over to the map | the map, held 5 s past the threat |

## 7. What I think it means

Neither prototype should replace the map. They answer different
moments, and the most promising direction is to stop treating "the
view" as one thing:

- **Arriving and looking** belong to the street view: the place card
  (spec 5.6) could become a street-view establishing shot of where you
  stand, the thing S33's vignettes were meant to be, but live.
- **Being in a hub** belongs to scenes: the Plaza, the Tin Halo, Clinic
  Row's interiors, Vesper's bar, the Lattice terminals' surroundings.
- **Danger and contested ground** belong to the tactical map, which every
  prototype already falls back to.

Prototype C is that idea, built. In captures it does what it should: one
journey moves through a look, a scene, a walk, a look, the map and
TACTICAL without a key pressed to change views. Whether that reads as a
game framing its moments or as a screen that will not sit still is
exactly what play has to show. The key-meaning switch at boundaries is
the part I trust least.

## 8. Decisions these raise

| ID | Decision | Why it needs you |
|---|---|---|
| S1 | Is `walk_to` (server-walked travel over known ground) acceptable as a mechanic, and where (safe hubs only, everywhere)? | it changes how players act and what a bot could script |
| S2 | Is the deep camera acceptable (larger views, more bandwidth)? | changes the view budget and the camera rule in UI 2 |
| S3 | Which paradigm, if any, becomes a supported view, and for which contexts? | product direction; affects S25, S27, S30, S33 scopes |
| S4 | Should facing become server state the view can set (smooth turning, facing-aware rules later)? | today facing is persisted but unused; making it meaningful is a rule change |
| S5 | Places as content: who writes them, and are they canon (gazetteer) or presentation (looks)? | names of places become world text |
| S6 | If the view follows context, may the arrow keys change meaning with it, or must movement keys always move the body? | answered for auto by A5 (one meaning per key); the manual street view still turns with them |

## 9. Honest limits

- First played by the owner on 2026-10-25 (auto preferred). The A1-A6
  rules above came out of that session and have not been played yet.
- Only three zones have places, and only the Sodium Row candidate has
  enough architecture for street view to show what it can do. On the
  shipped Sodium Row (an open rectangle) street view shows mostly open
  ground and distant walls: geometry matters more at eye level than on
  a map.
- The street view has no animation (no flicker, no rain, no moving
  crowds between server updates). It could; each would cost CPU and
  bandwidth and would need its own rule about never imitating a threat.
- The Lattice keeps its own linework view in every prototype; going down
  is already a change of medium.
- Menus, text views and dialogue are unchanged.

## 10. Visual target: the Tin Halo

![The Tin Halo as an auto scene, 132x50 truecolor](target/tin-halo-scene-132x50-truecolor.png)

**Status: adopted by the owner as the visual target, 2026-10-25.** This is
the level of detail Blacksite's scenes should reach. Under ideal
conditions (truecolor, 132x50, a terminal that draws the full Unicode
block set), every place should read like this: a room you could walk
into, not a description of one. The owner's words: a game that conveys
what matters through scenery and scenes, not only through text, so the
atmosphere is set before anything is explained.

It is a target, not a capture. It was composed by hand
(`scripts/presentation_mockups/target_tin_halo.py`) on the door's real
132x50 layout and palette roles, and nothing in the game draws it yet.
Full-size glimpse: [`target/tin-halo-glimpse.png`](target/tin-halo-glimpse.png).

**What the frame does without words.** The cans overhead say where you
are before the title does. The bouncer at your shoulder, with Sable's red
at his arm, says whose pocket this is. The booths and lamps say people
stay here; the lit back-bar says this is a bar that is looked after.
Three cyan screens at the counter say Vesper is working. The red door at
the back says there is a back room and it is not for everyone. The sign
inside reads TIN HALO in full while the one outside reads TIN HAL: the
place is kept, the street is not.

**How it is built.** Three choices make the difference to today's
street view:

- **Sextants, not half-blocks.** The glimpse is 214x57 sub-pixels in
  107x19 cells (Unicode 13 block sextants, 2x3 per cell) against 107x38
  with half-blocks. The cost is two colours per cell; with lighting that
  changes smoothly that is rarely visible.
- **Light as content.** Lamps, screens, the back room's spill and the
  halo itself are light sources with colour, reach and strength; walls,
  floor and people take their colour from them, with haze in depth and
  reflections on the floor. Today's renderer shades by distance only.
- **Dressing as content.** Booths, shelves of bottles, the counter,
  stools, boards and the hanging cans are set pieces placed in the room,
  not tiles. People are silhouettes with rim light from the nearest
  source, standing or seated.

**What it takes to reach it** (each a proposal for the plan, not a
commitment):

1. **A glyph tier beyond CP437, by opt-in only.** Canon (UI 1) limits
   every glyph to characters that exist in CP437, because NetBBS
   transcodes UTF-8 to CP437 for SyncTERM-class callers. Sextants do not
   survive that, and the door cannot detect support: NetBBS sends only
   the boolean `unicode_style`. The workable shape (technical lead,
   plan section 13): a per-player setting, chosen against a test
   pattern, half-blocks by default, for eye-level art only. Maps, chrome
   and text stay CP437. This needs a UI 1 amendment (D-T9).
2. **Lighting data in looks.** Per place: light sources (position,
   height, colour, reach), ambient level, haze colour. Decoration only:
   no rule reads it (spec R4, R6).
3. **Set pieces in looks.** A small library of dressing (counter, booth,
   shelf, stool, lamp, board, hanging cans, pipes) placed by zone,
   rendered at eye level. On the map a set piece shows only where its
   tile already says the same thing (a counter on a blocking tile), so
   the map never draws an obstacle that is not there; the validator
   checks it.
4. **A lit renderer.** The street raycaster gains lights, set pieces,
   seated and standing figures, fog and reflections. Static parts of a
   place can be painted once per position and heading and cached; only
   people and lights that change are redrawn.
5. **Figures from the server's actors only.** Everyone drawn is someone
   the server disclosed, where it put them, and a property test checks
   every figure against the view body. Silhouettes carry behaviour
   colour (D10); a faction mark like the bouncer's Sable red must come
   from a disclosed field, never a hidden allegiance. A threat is never hidden by
   dark, haze or a set piece: danger still hands the screen to the
   tactical map (A1).
6. **Budgets.** A full sextant glimpse in truecolor is about 2,000 cells,
   roughly 60 to 80 KiB when every cell changes: four to five times
   today's 16 KiB per-delta ceiling. A still room sends almost nothing,
   but a turn of the head is a full redraw. Looks need their own budget
   class (rate-limited full redraws, falling back to half-blocks or the
   map on slow links) and a CPU budget, measured over real NetBBS SSH
   and web paths.
**First step (proposed, D-T10):** a live spike, V0, that renders the
Tin Halo from look data (lights, set pieces, places) in the real door
behind the trial flag. The owner compares a live capture with this
target before any authoring at scale; the spike's look schema becomes
the draft content format.

7. **Authoring at scale.** The real cost. Every place worth standing in
   needs its light, dressing and figures authored to this standard. That
   is world-building work as much as engineering, and it should follow
   the gazetteer, place by place.

**Outside canon in the mockup.** Besides the sextants, the chrome uses
glyphs CP437 lacks: diagonal arrows in the ways list, eighth-blocks in
the vitals bars, `◆` and `×`. The CP437 build uses `↑↓←→` with the
compass letters, whole-cell bars, `♦` and `x`. Those are small losses;
the glimpse is the one that matters.

**Invented for the mockup.** The place "Under the halo", the selected
way's text about Vesper, the detail box, and several log lines are
illustrative and not canon. The Tin Halo's lore line, its NPCs, objects,
Sable and the Ferrymen are real content.
