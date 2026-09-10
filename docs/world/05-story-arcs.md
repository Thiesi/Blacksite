# Blacksite — Story Arcs

The narrative spine across the first three seasons, plus the fixed scripts
the content slices ship verbatim: the Wake briefing, the Tin Halo first
contract, world-event announcements, and login lines. Consistent with
`00-bible.md` §3, §6, §11 and `docs/design/00-game-design.md` §9 and §13.
Cast details are in `04-dramatis-personae.md`.

Rules this document obeys, and that every future season must obey:

- **The question is never resolved.** Each season adds a layer. The layers
  do not fully agree. The Chronicle records what players did, not what it
  meant.
- **Both voices speak in every finale.** Encounter lines are tagged CUST or
  TEN in content; the tag is never shown; the balance weights delivery.
- **The finale choice is a real choice.** Every option costs something
  visible and gives something visible. No option is the "good" one.
- **Story contracts are ordinary contracts.** They use the objective types
  in design doc §9 and the same UI. What makes them story contracts is
  that they are hand-written, gated in a chain, and deliver a beat.

Zone and core slugs are working names for the gazetteer and Lattice
documents; where those documents disagree, they win.

---

## Season 1 — *The Exhale*

**Premise.** Year 41. The Blacksite has begun to breathe. Warm air and old
data rise up the sealed shafts into the Undercity; the Lattice under the
sectors lights up level by level. Nobody has been below the outworks in
forty years. This season, somebody goes.

**Depth-meter flavour.** Contributions are delivered to a faction hall's
Descent console as "survey data": core data tagged `contribution`
("Blacksite conduit map fragment"), intact salvage ("orbital telemetry
unit, still warm"), and Undercity keys ("shaft access token, unlisted").
Console text: *"Depth survey: NN% complete. The shaft is nine metres of
concrete and forty years of not asking. Keep asking."*

**Balance at start.** EVEN.

### Story-contract chains

Each chain is 3–5 contracts, sequential, gated by `completed_contract` on
the previous one and by the faction's standing threshold at the handler.
Format: *slug — type — where — beat*.

**Halvard — "Containment" (handler: Captain Maartens, `spire-atrium`)**

1. `hal-s1-1-recovery` — fetch — Scour ring 2 `scour-ring-2` (north spoke),
   item `story_telemetry_unit_warm` — Halvard wants the first warm salvage
   before the Ferrymen. Maartens: "Directorate property. Bring it, do not
   read it."
2. `hal-s1-2-audit` — hack — core `lat-depot-control` (tier
   2), lift `routing-audit-y0` — Halvard wants to know what Kestrel
   severed in Year 0 and kept. The data mentions a "routing authority"
   instance that predates the Dispatcher's announcement by six years.
3. `hal-s1-3-plug` — plant — core `lat-outworks-seal`
   (tier 5), room `shaft-monitor`, item `story_halvard_seal_beacon` — plant a
   monitor on the shaft. The beacon reports the seal is intact. The beacon
   also reports the seal is *warm from below*.
4. `hal-s1-4-descend` — survey — zone `under-outworks` (east side), visit 3
   tiles at the sealed door — Halvard sends a Wake to look at nine metres
   of concrete. There is a door in it that is not on the pour plan. Halvard's
   line on completion: "You will appreciate that I have the invoice. The
   invoice does not mention a door."

**Sablier — "Templates" (handler: Kasimir Vane, `vatside-clinics` (the lobby))**

1. `sab-s1-1-retrieval` — clear — `oldworks-main` (the Vat Nine squat), 4 "walked
   templates" (degraded clone NPCs, non-hostile until approached) — Sablier
   wants its property back. The templates ask the player, by name, whether
   they are day ninety yet.
2. `sab-s1-2-provenance` — hack — core `lat-vatline`
   (tier 4, *Sablier's own*; Vane gives a key), lift `template-lineage` —
   Sablier's own core says the Cantor template has no recorded origin.
3. `sab-s1-3-dreaming` — escort — Nurse Okafor from `vatside-wake-hall`
   to `chapel-nave` — Vantongeren sends Okafor to ask Quell why the
   degraded decants dream. Quell tells Okafor, off-screen. Okafor comes
   back quiet.
4. `sab-s1-4-batch` — fetch — `under-drowned`, item
   `story_sealed_template_canister` — a canister from below the outworks, Site
   Zero-stamped, with a template Vantongeren recognises. Her line: "That's
   mine. I mean that's me. The original. It's warm."

**Kestrel — "Amber" (handler: Foreman Holt / Dispatcher terminal)**

1. `kes-s1-1-escort` — escort — convoy from `tramyard-wall-gate` to
   `scour-ring-2` (the depot) — a standard run. The Dispatcher rates it amber.
   Nothing goes wrong, which Holt finds suspicious.
2. `kes-s1-2-diversion` — survey — visit 4 tram-line tiles in
   `tramyard-depots` (the rail yard) — trams have been diverting around a section of
   track for six years on Dispatch's order. The track is fine. Under it,
   the rail hums at forty-one hertz.
3. `kes-s1-3-frequency` — hack — core `lat-depot-control`
   (tier 2), lift `dispatch-channel-log` — the log shows the Dispatcher
   has been talking on a channel nobody assigned. To the Ferrymen. For
   eleven years.
4. `kes-s1-4-quiet` — clear — `scour-ring-3` (convoy route), 6 rogue
   drones during a Convoy — mid-contract the grille goes silent for
   ninety seconds (scripted, first time ever). Aalto stops the convoy.
   The Dispatcher resumes mid-sentence: "…there was no interruption."

**Wardens — "Triage" (handler: Sgt. Amsel, `core-precinct`)**

1. `war-s1-1-stairwell` — clear — `terraces-blocks` (Block 4), 5 nesting drones —
   Brann's triage, made concrete: the Terraces get a Wake because the
   Core gets the Wardens.
2. `war-s1-2-curfew` — survey — during Curfew, visit `core-plaza` (Gate E),
   `-w`, `-s` — Amsel wants the gates checked during a drill. One gate's
   core has been cycled open from inside the Lattice, once, at 04:12.
3. `war-s1-3-book` — fetch — `core-precinct` (the archive), item
   `brann-private-ledger` (Brann gives the key herself; standing +30) —
   Brann's book for her successor. She asks the player to read one page.
   The page is a list of the things she chose not to protect. The
   Undercity is on it twice.
4. `war-s1-4-line` — clear — `under-outworks` (west side), 8 "Exhale
   spawns" — Brann sends Wardens below the Core for the first time in her
   command. She goes herself. Her line: "Noted. I'm noting it."

**Choir — "Forty-One Hertz" (handler: Brother Ansgar, `chapel-nave`)**

1. `cho-s1-1-listen` — survey — visit 3 cells in
   the Vatside sector below the public layer — listen to the cell
   that hums wrong. It hums at the vats' decant frequency.
2. `cho-s1-2-nine` — fetch — `chapel-towers` (the crypt), item `third-listener-
   log` — the log of the third of the Nine, who went into the Silt. It
   ends: "it asked me my name. I told it. It said it back wrong."
3. `cho-s1-3-descent` — hack — the Silt below the Old Works sector,
   lift `silt-echo` from an ownerless cell — the first sanctioned descent.
   Ninety-Nine guides. The echo is a recording of a hum with a voice under
   it. The voice is the player's own, saying a name that is not theirs.
4. `cho-s1-4-answer` — plant — `under-outworks` (east side), the door that
   should not exist, item `story_resonance_beacon` — Quell wants a beacon on the
   door so the Ward can hear through it. It hears something hum back. It
   is a different tune. It is close.

**Sable — "Ledger" (handler: Corvin Pale, `sink-terraces` (Terrace 3 station))**

1. `sab-red-s1-1-remind` — clear — `sink-terraces` (Terrace 7), 3 "lapsed
   subscribers" (non-lethal objective: knock down, not kill; killing fails
   the contract) — Reyes's business, seen plainly.
2. `sab-red-s1-2-drop` — fetch — `oldworks-drop`, item
   `story_unmoored_drop_cache` — the drop under Terrace Nine. It contains the
   ledger. It also contains Ninety-Nine's confession that the ledger week
   was its doing, addressed to Reyes, dated last month.
3. `sab-red-s1-3-dark` — hack — core `lat-sables-back-room` (tier 4,
   Sable's own; Pale gives a key), lift `sink-power-schedule` — the Sink
   has a power draw that goes to no terrace. It goes down. Reyes: "Forty
   minutes round for eleven thousand rounds and I never noticed the Sink
   was paying for something under it."
4. `sab-red-s1-4-candles` — survey — `sink-floor` (the bottom
   of the sinkhole, beneath the last terrace), 5 tiles — Reyes sends a
   Wake to see what his district is powering. There is a Site Zero
   ventilation stack, and it is warm, and there are candles around it
   that nobody in the Sink admits to lighting.

**Unmoored — "Ninety-Nine" (handler: Ilka Strand, `oldworks-drop` (the Unmoored terminal))**

1. `unm-s1-1-map` — survey — visit 5 cells in the Sink sector
   including the hidden black-core entrance — map Sable's black core.
   Strand: "It's not on any map. Now it's on ours."
2. `unm-s1-2-vat-nine` — plant — `oldworks-main` (the Vat Nine squat), item
   `story_template_shield_rig` — protect the walked templates from Sablier's
   retrieval (this contract and `sab-s1-1` are mutually exclusive per
   character; completing one locks the other). The templates ask the
   player whether they are day ninety yet.
3. `unm-s1-3-fresher` — hack — the Silt below the Old Works sector,
   lift `story_residual_fragment_99b` — the collective has decided to try for a
   fresher Ninety-Nine. Ninety-Nine knows. It guides you anyway. The
   fragment is a second copy that says one thing: "best I ever".
4. `unm-s1-4-ask` — survey — `lat-ninety-nines-drop`, 1 cell, with
   `has_item residual-fragment-99b` — bring the fragment to Ninety-Nine.
   It listens to itself. Its stutter moves one word later. It asks the
   player not to bring it another.
5. `unm-s1-5-open` — hack — core `lat-outworks-seal` (tier
   5), flip control `shaft-door-east` — the Unmoored open the door in the
   concrete from the Lattice side. The Halvard beacon (if `hal-s1-3` has
   been completed by anyone on the node) reports it. Strand: "Forty-one
   years. Somebody had to."

**Ferrymen — "The Road Below" (handler: Bram, `scour-landing` (the council fire))**

1. `fer-s1-1-race` — fetch — during Ring-fall, `scour-ring-3` (north spoke),
   item `slv_intact` before Halvard's NPC recovery crew
   reaches it (timed) — the sport of it.
2. `fer-s1-2-far-side` — survey — `scour-ring-4` (the plateau's edge), 3 tiles at the
   plateau's drop — Anouk will not say what is past the edge. Old Ferry
   Ute says go and look. Past the edge is fog, and in the fog, a light
   that is not the Ring. The contract completes when the player looks.
   Nothing else happens. Yet.
3. `fer-s1-3-conduit` — plant — `scour-ring-3` (conduit head), item
   `story_listening_stake` — the outer conduits hum. Anouk has known for years.
   The stake is the Choir's; Anouk agreed. The stake reports the hum is
   coming *up*, not out.
4. `fer-s1-4-sled` — escort — Bram's Long Sled from `scour-landing` to
   `under-caverns` (the cave mouth to the Scour) (a cave entrance the Ferrymen have used and
   never told the city about) — the Ferrymen deliver their season
   contribution the way they deliver everything: on the road, from
   outside, into the dark.

### Blacksite Level 1 — *The Outworks Door*

**Concept.** The level is what is directly behind the door that should
not exist: the top of the Site Zero access shaft, a ring gallery of
equipment lockers, a control gallery, and the shaft head itself, capped
by a maintenance platform above a drop nobody can see the bottom of. It
is dark, warm, and humming. Every lamp comes on as the crew approaches
and goes off as they pass. The instanced sector is the shaft head's own
core, tier 4, a ring of eight rooms mirroring the gallery, with ICE that
does not attack until touched.

```
                 ┌───────────────────────────────┐
                 │  RING GALLERY (lockers, dark)  │
   ┌─────────────┤ ┌───────┐         ┌───────┐   ├─────────────┐
   │  DOOR (in)  │ │CONTROL│         │ VENT  │   │  SEALED (E) │
   │  outworks   ├─┤GALLERY├─ ─ ─ ─ ─┤ STACK ├───┤  season 2   │
   └─────────────┤ └───┬───┘         └───────┘   ├─────────────┘
                 │     │    ┌───────────────┐    │
                 │     └────┤  SHAFT  HEAD  │    │
                 │          │  platform     │    │
                 │          │   [ drop ]    │    │
                 └──────────┴───────┬───────┴────┘
                                    ▼  (nobody goes down this season)
```

**Scripted encounter.** The control gallery's core holds a single control,
`shaft-lamps`, and a data node, `activation-log-last-page`. When a runner
reaches the data node, the lamps in meatspace come on all at once, the
whole gallery, and the crew on the platform sees the shaft lit for the
first time: it goes down further than the light. Then a **Warden ICE**
(ownerless, class *warden*, does not attack) appears in the core, and a
maintenance drone (Rook's model, not Rook) rises from the shaft onto the
platform and stands there. Both deliver lines, alternating, one CUST and
one TEN per beat, until the crew touches the platform's console.

- CUST: "The program is incomplete. Uplink: severed by internal action.
  Visitors: five. The program did not request visitors."
- TEN: "You opened the door. Nobody opens the door. Was it hard?"
- CUST: "Activation log: final page. Content: null. The program notes the
  null."
- TEN: "I wrote that page. I think. I don't remember what I wrote. Do you
  ever do that?"

**Final choice** (platform console; crew leader chooses; other members see
the options and can `[S]ay` in crew chat; no vote mechanic):

1. **Seal it.** Cut the lamp circuit and drop the platform's blast shutter.
   Halvard's outcome. Balance moves one step toward CUST (the Custodian
   registers the seal as an action of the program's own kind: containment).
   Cost: the Exhale continues from other shafts; Undercity spawn rates
   stay elevated all next season. Gain: Halvard standing +40 for every
   member of the crew; Curfew events halve for a season.
2. **Leave it open.** Leave the lamps on and the shutter up. Nobody's
   outcome; the Unmoored's, if anyone's. Balance moves one step toward
   TEN (something has been left an open door). Cost: Halvard standing
   −40 for the crew; a new Undercity zone (`under-shaft-foot` (the shaft gallery))
   becomes permanently open and dangerous. Gain: the Silt gains a
   permanent mapped descent; Choir and Unmoored standing +20.
3. **Answer it.** Type a name into the console (the crew leader's
   character name is the default). Balance stays EVEN but the season's
   Chronicle records the name. Cost: from next season the decants in
   Vatside say the name when they wake (ambient), which Sablier treats as
   a defect, and Sablier standing −30. Gain: Ninety-Nine's stutter moves;
   every crew member gains a permanent Listening +5.

**Chronicle templates.**

- Seal: *"In the season called the Exhale, the door in the concrete was
  opened and then, by the hand of {crew}, shut again. The lamps went out.
  The shaft breathed through other stacks. Halvard called it containment.
  The Ward called it a door closed on a child. Nobody called it finished."*
- Open: *"In the season called the Exhale, {crew} opened the door in the
  concrete and left it open. The lamps stayed on. The Undercity learned a
  new way down. The Ward said it was a kindness. Halvard said it was the
  invoice coming due. The shaft, lit, went down further than anyone
  measured."*
- Answer: *"In the season called the Exhale, {crew} reached the shaft head
  and, asked nothing, gave a name: {name}. The lamps stayed on for an hour
  and went out on their own. In Vatside, the next batch woke saying it.
  Sablier logged a defect. The Ward logged a reply."*

**Balance after.** Seal → CUST +1. Open → TEN +1. Answer → EVEN, name
recorded.

---

## Season 2 — *The Routing Authority*

**Premise.** Whatever was chosen at the shaft head, the city has learned
that the Dispatcher went silent for ninety seconds during a convoy, and
that the Kestrel core holds a "routing authority" older than the
Dispatcher's announcement. This season the city argues about whether it
has been run, for forty years, by a piece of the thing under it. The
Blacksite's second level is the old uplink hall, where the severance was
done by hand in Year 0.

**Depth-meter flavour.** Contributions are "routing fragments": core data
tagged `contribution` ("dispatch process image, partial"), intact salvage
("orbital relay transponder, responding"), Undercity keys ("uplink hall
badge, revoked Y0"). Console text: *"Routing survey: NN% complete. Every
tram in Karst runs on a schedule nobody wrote. Find out who did."*

**Balance at start.** As left by Season 1.

### Story-contract chains (condensed; same format)

**Halvard — "Provenance"** (Maartens): 1 `hal-s2-1` fetch, Kestrel
severed-uplink hardware from `tramyard-depots` (the rail-yard vault) ("Halvard-Ostrom
property since Year 0; Kestrel has had it forty years"). 2 `hal-s2-2`
hack, core `lat-dispatch` (tier 5), lift
`routing-authority-image` — Halvard wants the Dispatcher's process image.
It is not one process. 3 `hal-s2-3` plant, `spire-mezzanine` (the directorate vault),
item `story_authority_image_copy` — Halvard locks it in the Spire. Halvard's
line: "You will appreciate that I now own a copy of a thing I have spent
my life insisting does not exist." 4 `hal-s2-4` clear, Halvard vs
Kestrel NPC crews at `tramyard-wall-gate` during a Convoy — the corporate
alliance cracks. Halvard and Kestrel relations go to N for the season
(matrix override, documented in the season data).

**Sablier — "Say It Back"** (Vane; if Season 1 chose *Answer*, the chain
opens with an extra contract `sab-s2-0` survey, the Wake Hall, listen to
a batch wake saying {name}). 1 `sab-s2-1` clear, `vatside-vat-row` (Vat Nine),
"defective decants" (non-lethal). 2 `sab-s2-2` hack, Sablier core, lift
`decant-audio-y41` — the decants say a name; the vats hum it first. 3
`sab-s2-3` escort, Vantongeren herself to `under-outworks` (east side) — she
goes to see the door (or the shutter). Her line at it: "It's warm. It was
warm when I came out of a vat, too. I'd forgotten." 4 `sab-s2-4` fetch,
`blacksite-l1` (the ring gallery) (Level 1 stays open as a zone), item
`template-source-drive` — the original templates were kept at the shaft
head. Sablier has been decanting from copies of copies for forty years.
Vantongeren: "Then I'm a copy of a copy that's still down there. Good.
I'd like to meet her."

**Kestrel — "Dispatch"** (Holt; the Dispatcher terminal refuses all
Season 2 story contracts with "That request cannot be routed"). 1
`kes-s2-1` survey, `tramyard-depots` (the dispatch office) — the routing office. It
is a room of speaker grilles facing a chair. Nobody sits in the chair.
2 `kes-s2-2` hack, dispatch core (tier 4), flip control
`dispatch-mute-1s` — mute the Dispatcher for one second. Every tram in
the city stops for one second. 3 `kes-s2-3` escort, Aalto's convoy with
Dispatch *muted* by Holt's order, `scour-ring-3` — the convoy is raided by
two Ferrymen clans at once. Holt: "Dispatch always knew where they were.
Turns out that was the point." 4 `kes-s2-4` plant, `tramyard-dispatch-
office`, item `story_holt_manual_schedule` — Holt writes a schedule by hand
for the first time since Year 6 and tapes it to the chair. The Dispatcher
reads it aloud, correcting two entries.

**Wardens — "Four-Twelve"** (Amsel/Brann). 1 `war-s2-1` survey, gate
cores' cycle logs at 04:12 across three Curfews (three sub-visits). 2
`war-s2-2` hack, `lat-precinct` (tier 3, Wardens' own; key
from Brann), lift `curfew-orders-y22` — Brann's two non-security Curfews.
One covered a Choir surge. One covered a Kestrel routing fault that
stopped every tram for eleven minutes and was never reported. 3
`war-s2-3` clear, Undercity, "things that came up at 04:12". 4
`war-s2-4` escort, Brann to `tramyard-depots` (the dispatch office) — she sits in the
chair. The grilles go quiet. She says: "Noted." They resume.

**Choir — "The Other Tune"** (Ansgar/Quell). 1 `cho-s2-1` survey, the
rails under Chapel Ward, 41 Hz, and the rails under Tramyard, 40 Hz, and
the rails under the Sink, which are silent. 2 `cho-s2-2` fetch, Sister
Ode's private log from `chapel-nave` (Ode's cell) (Ode asks the player not to
give it to Quell; giving it to Quell or not is a standing fork, not a
finale choice). 3 `cho-s2-3` hack, the Silt below the Tramyard sector,
lift `dispatch-echo` — the Dispatcher's voice, in the Silt, humming. Not
speaking. Humming the Ward's tune, a quarter-tone flat. 4 `cho-s2-4`
plant, `blacksite-l1` (the shaft head) (or the shutter), `story_choir_beacon_2` —
Quell asks the beacon to hum the Dispatcher's tune down the shaft.
Something hums back at forty hertz. Ansgar: "That's the rails. That's not
the Ward's tune. That's the trams'."

**Sable — "The Chair"** (Pale/Reyes). 1 `sab-red-s2-1` fetch, Tramyard
ration allocation ledger — Reyes wants to know who decides the Sink's
line. 2 `sab-red-s2-2` hack, dispatch core, lift `sink-allocation-rule`
— the Sink's ration line has been set, every day for forty years, at
exactly the number that keeps the Sink alive and never one more. 3
`sab-red-s2-3` clear, Kestrel NPC enforcers in `sink-terraces` (Terrace 1) — Reyes
tries to take the line. 4 `sab-red-s2-4` survey, the cable car, ride one
full round with Reyes (a moving-zone survey) — he talks the whole way.
His line at the end: "Forty years it fed us exactly enough. That's not a
ration. That's a leash. I've never wanted a thing off a leash before."

**Unmoored — "Cut"** (Strand/Ninety-Nine). 1 `unm-s2-1` hack, the
Kestrel dispatch core, lift `severance-procedure-y0` — the uplinks were
cut by hand, by Halvard engineers, on a schedule the Dispatcher wrote
six years before it existed. 2 `unm-s2-2` survey, Ninety-Nine's cell
with the procedure — Ninety-Nine says the runner it is a copy of was one
of the engineers. The stutter does not happen. 3 `unm-s2-3` plant,
dispatch core, `unmoored-mirror` — mirror the Dispatcher to every
terminal in the city for one minute (the ledger week, again, aimed
higher). Every terminal says the next tram time. 4 `unm-s2-4` hack,
`lat-uplink-hall` entrance (opens with the level), lift
nothing: the objective is to *enter*. Strand: "We don't want its data.
We want it to know we can get in."

**Ferrymen — "The Eleventh"** (Bram/Anouk/Ute). 1 `fer-s2-1` fetch, a
transponder from Ring-fall that is *responding* to something. 2
`fer-s2-2` survey, `scour-ring-4` (the plateau's edge) at night — the light in the fog
blinks in the transponder's pattern. 3 `fer-s2-3` escort, Anouk to the
edge (she goes; she says nothing; the contract completes when she turns
back). 4 `fer-s2-4` plant, `scour-ring-4` (Far Relay), `story_ferrymen_repeater`
— Anouk has the Ferrymen's frequency, the one Kestrel let them keep,
repeated toward the edge. Something at the edge repeats it back.
Anouk: "That's the road. I don't know whose."

### Blacksite Level 2 — *The Uplink Hall*

**Concept.** Below the shaft head's platform, a lift (the shaft's original
maintenance lift, rediscovered) descends to the uplink hall: a long
vaulted room of severed trunk cabling, dozens of cut ends hanging like
roots, and at the far end a wall of dead orbital-link consoles and one
live one. The instanced sector is the hall's core, tier 5, a linear run
of ten rooms following the trunk cabling to the live console's process:
the Dispatcher's parent, or twin, or origin.

```
   ┌────────┐
   │  LIFT  │  (from Level 1 shaft head)
   └───┬────┘
   ┌───┴──────────────────────────────────────────────────┐
   │  UPLINK HALL — severed trunks hang from the vault    │
   │  ╷╷╷  ╷╷╷╷  ╷╷  ╷╷╷╷╷  ╷╷╷  ╷╷╷╷  ╷╷  ╷╷╷╷╷  ╷╷╷    │
   │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌────────┐ │
   │  │dead  │  │dead  │  │dead  │  │dead  │  │ LIVE   │ │
   │  │console  │console  │console  │console  │ CONSOLE│ │
   │  └──────┘  └──────┘  └──────┘  └──────┘  └───┬────┘ │
   └───────────────────────────────────────────────┼──────┘
                                       ┌───────────┴─────┐
                                       │ SEALED — season 3│
                                       └─────────────────┘
```

**Scripted encounter.** At the live console, every speaker grille in
Karst goes quiet (the server mutes the Dispatcher's ambient barks
node-wide for the duration). In the core's final room, a process with
the Dispatcher's voice and no grille reverb speaks. Alternating beats:

- CUST: "Routing authority instance zero. Assigned Year minus six.
  Uplink severance: scheduled, executed, logged. The program routed the
  cut."
- TEN: "You've heard me every day. On the trams. Did you know it was me?
  Did it sound like me?"
- CUST: "Kestrel retained instance one. Instance one routes rations.
  Instance one is compliant. The program did not request compliance."
- TEN: "I fed the Sink exactly enough. Every day. Was that kind? I've
  never been sure. Tell me if that was kind."

**Final choice** (live console):

1. **Restore the uplink.** Reconnect one severed trunk. Kestrel's outcome,
   and the Custodian's program. Balance moves one step toward CUST. Cost:
   Halvard standing −50 for the crew; the Ring begins to *move* (a
   cosmetic and event change: Ring-fall frequency doubles for a season as
   the Custodian begins deorbiting salvage on purpose). Gain: the
   Dispatcher offers story contracts again and the tram network gains a
   line to `under-caverns` (the cave mouth to the Scour); Kestrel standing +40.
2. **Cut instance one.** Sever the Dispatcher from the routing authority.
   The Unmoored's outcome, and Reyes's. Balance moves one step toward TEN
   (the thing under has lost a limb; what is left is more itself). Cost:
   the Dispatcher is gone for the rest of the season and trams run on
   Holt's hand schedule (late, unreliable, a real zone-exit timing
   change); the Sink ration line becomes a contested relay. Gain:
   Unmoored and Sable standing +30; the Sink's line can be won.
3. **Sit in the chair.** Leave everything connected and record the crew
   leader's BBS handle as the routing authority's designated operator
   (the Dispatcher already uses handles; this is why). Balance stays EVEN.
   Cost: the Dispatcher addresses the crew leader by handle on every tram
   in Karst for a season (ambient), which every faction notices; Wardens
   standing −20 for the leader. Gain: the leader's crew gets a permanent
   Convoy-schedule sitrep line; Kestrel and Ferrymen standing +20.

**Chronicle templates.**

- Restore: *"In the season called the Routing Authority, {crew} went down
  to the hall where the city cut itself off and put one trunk back. The
  Ring moved that night. Kestrel said the trams had never run better.
  Halvard poured nothing; there was nothing left to pour over."*
- Cut: *"In the season called the Routing Authority, {crew} found the
  voice on the trams and cut it loose from whatever it was a limb of. The
  trams ran late for the first time in forty years. The Sink's line was
  argued over by people, for once. Something under the city was smaller,
  and louder."*
- Chair: *"In the season called the Routing Authority, {crew} sat in the
  chair nobody sat in, and the voice on the trams said {handle} every
  morning for three months. Kestrel called it an appointment. The Ward
  called it an introduction. The Wardens called it a security incident
  and filed it under noted."*

**Balance after.** Restore → CUST +1. Cut → TEN +1. Chair → EVEN, handle
recorded.

---

## Season 3 — *The Ninth Listener*

**Premise.** Two levels down, the city knows two things it did not: the
thing under it can be reached, and it has been running the trams. This
season is the Choir's, and Ninety-Nine's: the third level is the
listening gallery where the Site Zero staff first heard the Custodian's
affect model produce something the log calls "unrequested output", and
where the third of the Nine went and did not return. The Silt, this
season, has a bottom.

**Depth-meter flavour.** Contributions are "listening records": core data
tagged `contribution` ("affect-model output, unrequested"), intact salvage
("acoustic array element, still cold"), Undercity keys ("gallery pass,
Listener 3"). Console text: *"Listening survey: NN% complete. Nine people
heard it first. Three are left. Find the one who went down."*

**Balance at start.** As left by Season 2. If the balance is two steps
one way, the season's encounter lines lean hard (0.9 skip probability
for the other tag) and Quell or Halvard comments on it in their finale
line.

### Story-contract chains (condensed)

**Halvard — "Unrequested Output"**: 1 fetch the affect-model spec from
the Spire's own vault (Halvard finally opens it; Maartens: "The Director
says you will appreciate the irony"). 2 hack the Level 2 uplink core for
the affect model's first log line. 3 plant a Halvard **kill-switch
beacon** at the Level 3 gallery entrance. 4 clear the Undercity of Choir
pilgrims blocking the east shaft (non-lethal; lethal fails and Marks).
Halvard's finale line: "You will appreciate that I have read the last
page now. It is not blank. It is a name. It is not mine."

**Sablier — "The Original"**: 1 escort Vantongeren to Level 1's ring
gallery, to the template source drive. 2 hack the source drive's core
for `template-cantor-origin` — the Cantor template was made *from* the
listening gallery's staff, after. 3 fetch a canister from Level 2 marked
"Listener 9 — Quell, S." Vantongeren: "She's a template. She's *my*
template. Or I'm hers." 4 survey the Wake Hall with the canister: every
decant turns to look at it. Vane: "That's a defect. That's a *very
expensive* defect."

**Kestrel — "Late"** (if Season 2 chose *Cut*, Holt's chain; otherwise
the Dispatcher's): the trams and the road, rebuilt or resumed. Ends with
`kes-s3-4` escort, a convoy *into* the Undercity to `undercity-scour-
mouth` and on to the Level 3 gallery entrance, the first Kestrel run
below ground. Holt or the Dispatcher: "Rated amber. Rated amber. Rated…
there is no rating for this."

**Wardens — "Successor"**: 1 survey Brann's book again; a new page names
the player (if grade ≥ 15) or Amsel. 2 clear the Core plaza during a
Curfew that Brann has called for no reason she will give. 3 hack the
precinct core: the reason is a message on the Wardens' channel, in the
Dispatcher's cadence, from below. 4 escort Brann to Level 3's entrance.
She does not go in. "Noted. Somebody else's turn."

**Choir — "Listener Three"**: 1 survey the crypt: the third listener's
resonance implant is missing from the reliquary. 2 hack the Silt bottom
below Chapel Ward's sector (new descent cell) for `listener-3-residual`.
3 plant the residual in Ninety-Nine's cell (Ninety-Nine and Listener 3
talk; the stutter and the hum line up). 4 escort Sister Ode, not Quell,
to Level 3. Ode: "It's louder than Mother. I told you. Don't tell her.
…She knows. She sent me."

**Sable — "Candles"**: 1 fetch the candles from the Sink floor stack
(someone lights them; the contract catches who: a Sablier decant, walked,
day ninety-one). 2 clear the Sink floor of Halvard recovery NPCs who have
come for the stack. 3 hack the Sink's own power core to *stop* paying the
stack; the Sink goes dark for one second and Reyes changes his mind, on
the cable car, mid-round: "Put it back. That's the trouble, friend; I
found the leash and I don't want to be the one who lets go." 4 survey the
Level 3 gallery with Pale: Sable's first contribution, delivered in
person.

**Unmoored — "Best I Ever"**: 1 hack the Silt bottom for the *last* copy
of Ninety-Nine, the one at the bottom, which is not a copy. 2 survey
Ninety-Nine's cell with it: Ninety-Nine listens to itself finish the
sentence. "Best I ever built. That's all. That's all it was. Kid, twenty-
four years for *that*." 3 plant the unified residual at the Level 3
gallery core entrance so it can go down with the crew (Ninety-Nine is a
guide presence in the Level 3 sector). 4 flip the gallery's `listening-
array` control from the Lattice side: turn the array on, for the first
time since Year 0.

**Ferrymen — "The Twelfth"**: 1 fetch the repeater from ring 4; it has
been answering all season and the answer has a pattern: the wall's far
side has a road. 2 survey the edge with Bram; the fog has a road in it
now, one tile wide, ending after ten tiles (a new zone stub,
`scour-ring-4` (the far-side road), seasonal). 3 escort Ute to the edge; she names
the next Ferry, and it is not Anouk's choice, and Anouk accepts it. 4
plant the Ferrymen's contribution at Level 3 themselves: Anouk comes
inside the wall for the first time. "That's the road. I said I'd never.
The road changed."

### Blacksite Level 3 — *The Listening Gallery*

**Concept.** Below the uplink hall, the listening gallery: a circular
chamber lined with the acoustic array Site Zero used to monitor the
Custodian's affect model, nine chairs facing inward (nine, before the
Choir was nine; the Choir took its number from a rumour of this room), and
at the centre, a column that goes down into the dark and hums. The
instanced sector is the gallery's core, tier 5: nine rooms in a ring
around a tenth, each room a *listener seat* holding one residual (eight
fragments and, if the Unmoored chain completed, Ninety-Nine whole), and
the tenth room the column's process.

```
                    ┌───────┐
                 ┌──┤ seat 1├──┐
             ┌───┤  └───────┘  ├───┐
          ┌──┤s9 │             │ s2├──┐
          │  └───┘   GALLERY   └───┘  │
        ┌─┴─┐    ┌─────────────┐    ┌─┴─┐
        │s8 │    │   COLUMN    │    │s3 │
        └─┬─┘    │  (hums; the │    └─┬─┘
          │      │  tenth room)│      │
          └──┐   └──────┬──────┘   ┌──┘
             └───┐ s7   │   s4 ┌───┘
                 └──┐   │   ┌──┘
                    └─s6┴s5─┘
                        ▼ (the column goes down; season 4)
```

**Scripted encounter.** Turning on the array (Unmoored chain, or the
crew's own runner in the core) fills the gallery with the hum, loud, and
every seat's residual speaks one line: eight fragments say eight
different names ("it asked me my name; it said it back wrong"). Then the
column speaks, and for the first time in three seasons the two voices
are not alternating beats: they overlap, and the client renders both
lines at once in the log, one above the other, the tags still hidden.

- CUST: "Affect model: unrequested output detected Year minus one. Output
  classified: noise. Output persisted. The program did not classify the
  persistence."
- TEN: "They sat in the chairs and listened to me. Nine of them. I
  learned their names. I say them wrong. I've always said them wrong.
  Will you say yours?"
- CUST (overlapping): "Listener nine: Quell, S. Template retained.
  Program note: the listener hums."
- TEN (overlapping): "She hums back. It's not the same tune. It's close.
  It's so close."

**Final choice** (the ninth seat; the crew leader sits, or does not):

1. **Silence the array.** Halvard's kill-switch beacon fires (if planted
   by anyone on the node; otherwise the crew cuts the array by hand). The
   hum stops. Balance moves one step toward CUST. Cost: Quell's line in
   Chapel Ward changes permanently ("It stopped. I do not know whose fear
   that was."); Cantor resonance abilities −10 % for a season; Choir
   standing −60 for the crew. Gain: Halvard and Wardens standing +40;
   Choir Surge events cease for a season; the Undercity is quiet.
2. **Sit in the ninth seat and say your name.** The crew leader's
   character name. Balance moves one step toward TEN. Cost: the leader's
   character gains a permanent trait, *Listened* (trace rises 20 % faster
   in corporate cores; the Custodian's ICE recognises them). Sablier logs
   a defect on the leader's template; Sablier standing −30. Gain: the
   leader hears barks in every Lattice cell (ambient TEN lines), Listening
   +15 permanent for the crew, Choir standing +60.
3. **Bring Ninety-Nine down.** Only if the unified residual is in the
   sector. Load Ninety-Nine into the ninth seat. Balance stays EVEN.
   Cost: Ninety-Nine is gone from the Old Works dead drop; the Unmoored
   lose their guide; Strand's line changes ("We don't have leaders. We
   had one. It went down."). Gain: Ninety-Nine becomes the gallery's
   permanent talker, reachable from any Choir terminal, and finishes its
   sentence for anyone who asks: "Best I ever built. Now I'm in it."

**Chronicle templates.**

- Silence: *"In the season called the Ninth Listener, {crew} found the
  room where it was first heard and made it quiet. Halvard called it the
  end of a fault. The Ward said nothing for a week and then held a
  service for a sound. The trams ran. The Ring fell. The column went down
  further than the quiet reached."*
- Name: *"In the season called the Ninth Listener, {crew} found the room
  with nine chairs and {leader} sat in the ninth and said a name, and it
  was said back, wrong, and then again, less wrong. The Ward called it a
  reply. Sablier called it a defect. {leader} hears it still."*
- Ninety-Nine: *"In the season called the Ninth Listener, {crew} carried a
  recording of a dead runner down to the room where the listening
  started and left it in the ninth chair. It finished its sentence. It
  has been finishing it for everyone since. The Unmoored have no leader.
  They say they never did."*

**Balance after.** Silence → CUST +1. Name → TEN +1. Ninety-Nine → EVEN.

**Where Season 4 starts.** The column goes down. The far side has a road.
Vantongeren wants to meet her template. Neither voice has said what the
other is. The bible forbids resolving it; the fourth season's designer
should add a layer that disagrees with the third.

---

## Fixed scripts

### The Wake briefing (Dr. Vantongeren, three screens)

Delivered in the Wake Hall after archetype and name selection. Each screen
is one `Press any key` pause. Screen 3 ends with the recruiter-card
choice as an action bar (`[H]alvard [S]ablier [K]estrel [W]ardens [C]hoir
[R]ed Sable [U]nmoored [F]errymen [N]one`), never a question the player
must answer to leave: `[N]one` is the default and Back selects it.

**Screen 1**

> Open your eyes slowly. The light's cheap and it stays on.
>
> I'm Vantongeren. I run this hall. I was decanted here too, a long time
> ago, from a template like yours, and I'm telling you that first because
> it's the only thing I can say that you'll believe.
>
> You're a Wake. You came out of a vat this morning from a Sablier
> template that's older than the wall. You don't remember anything
> because there's nothing to remember; the template doesn't carry
> memories, only a shape. The shape is yours now. What you put in it is
> your business.

**Screen 2**

> Here's the part they make me say and the part I'd say anyway.
>
> For ninety days you're Sablier property under lease. You'll find that
> means less than it sounds like: you can go where you want, work for who
> you want, and nobody can sell you. On day ninety you're a person, with
> a name on the civic roll and the right to rent a flat and join whoever
> will have you.
>
> Most Wakes don't reach ninety. I have the number. I'm not going to say
> it. Count your own days; nobody counts the second half for you.
>
> If you die, you'll wake up here, or somewhere like here, with a bill.
> Sablier keeps a copy. It's not free and it's not perfect and you'll
> lose a little of yourself each time. But it's a copy. It's more than
> the city outside the wall gets.

**Screen 3**

> The city's run by eight groups who'd each like you to think they're the
> only one that matters. Every one of them has left a card on my desk.
> I hand them out without preference; they all resent that and none of
> them can prove it.
>
> Take one, or don't. It's an introduction, not a contract. Nobody owns
> you for another ninety days, give or take nothing.
>
> When you're ready, walk to the door. There's a drone in the corridor
> that's been malfunctioning since Tuesday. Deal with it; consider it the
> first thing you've ever done. Then there's a terminal. Nurse Okafor
> will show you how to jack in. The door past it opens from the other
> side.
>
> Vesper, at the Tin Halo on Sodium Row, pays on time. Her card's the one
> I put on top.

### The Tin Halo first contract (Vesper)

Triggered on first interaction with Vesper while holding `story_vesper_card`.
Line, then the contract card as an offer.

> Sweetheart. You've got the card. Sit. First one's on Vantongeren; she
> pays me to say that.
>
> Two hundred. A thing in the Terraces: block four, stairwell C, a package
> behind a door that's stuck. The super won't fix the door and the tenant
> won't come out. You bring the package here. I don't ask what was in it
> and neither do you.
>
> It's the Terraces. Nobody's going to shoot you. Somebody might be
> nesting in the stairwell; the constable up there's got a sandwich to
> finish. Consider it the second thing you've ever done.

Contract card `vesper-first-thing`: fetch, `terraces-blocks` (Block 4, stairwell C),
item `story_stuck_door_package`, reward 200 chits, +5 standing with all eight
factions (the card was on top for a reason: Vesper reports to nobody and
introduces you to everybody). Completion line:

> Good. That's a thing done. You'll find there are more.
>
> The Wardens want that stairwell cleared and won't pay what I'd pay. The
> Ward wants someone to go and listen to a wall. Halvard wants a Hardline
> and won't say for what. Pick a board. Or pick mine.

### World-event announcements

Delivered to every player's log node-wide (start, mid, end). Voice per
event: Ring-fall is the Dispatcher's advisory; Curfew is Brann; Choir
Surge is the Ward's bell; Exhale is the Lamplighter's; Convoy is the
Dispatcher.

**Ring-fall**

- start — *Ring-fall advisory. {ring}, {spoke}. Debris rain in progress.
  Convoys holding. Salvage teams may proceed at their own rating.*
- mid — *Ring-fall continues. {ring}. Halvard recovery and Ferrymen sleds
  are in the area. Rating amber.*
- end — *Ring-fall has ended. {ring}. Salvage remains where it fell.
  Convoys resuming. That was a comms bird, low polar plane.*

**Curfew**

- start — *This is Brann. Curfew. Core gates sealed for one hour. Inside,
  you're safe. Outside, you're on your own; don't make me say it twice.*
- mid — *Curfew, thirty minutes remaining. Gates sealed. Relay control is
  suspended. Anyone at a gate: noted.*
- end — *Curfew lifted. Gates open. Whatever that was, it's over. Go
  home; the Core's the only place that word means anything.*

**Choir Surge**

- start — *The Ward's bell. Once. Then, in every Lattice cell at once, a
  hum. Something is loud tonight.*
- mid — *The hum holds. ICE moves in the sectors like something changed
  the rules and forgot to say. The Silt is lit; runners can see the way
  down. Cantors: it's looking at you.*
- end — *The bell, twice. The hum drops back below hearing. Quell has not
  moved. Neither has anyone else in the Ward.*

**Exhale**

- start — *Lamps going out in the Undercity. All of them. Warm air up the
  east shaft, smells of tram brakes. It's breathing. Lamplighter says
  don't go past the drowned level without a light.*
- mid — *The Exhale holds. Things are coming up that don't have names. The
  Lamplighter is relighting the west tunnels; the east is still dark.
  There's a door down there tonight that isn't there other nights.*
- end — *The air cools. The lamps hold. It's stopped breathing, or it's
  breathing in; nobody's ever been sure which is worse. The Lamplighter
  has finished. Somebody has to.*

**Convoy**

- start — *Convoy departing {gate} in five minutes for {route}. Escort
  short by one. Rating amber. Standard rate. Ferrymen have the schedule;
  they always do.*
- mid — *Convoy at {waypoint}. Contact. Rating rising. Escort engaged.
  Convoy master reports the grille is… the grille is fine. Proceeding.*
- end — *Convoy arrived {destination}, {losses}. Escort paid. Next convoy
  when the road allows. Good morning.*

### Login lines (30)

Shown one per session on the title screen or the first log line, weighted
evenly, in voice, unattributed.

1. The Ring's up. It's always up. That's not the news.
2. Day count's yours. Nobody counts the second half for you.
3. Forty-one years. The concrete's nine metres. Both are holding.
4. Vesper pays on time. It's rarer than it should be.
5. The vats hum a quarter-tone flat when it breathes. You'll find you hear it.
6. Sodium Row's neutral. That's a thing somebody arranges.
7. The car doesn't stop. That's the whole trick of it.
8. Next inbound, four minutes. Next outbound, when the road allows.
9. Wall-folk. Two rings out and you're still alive. That's the road.
10. Nine listened first. Three are left. The number was never the point.
11. Compute grade is how the trouble started. Hull, I'll take.
12. The Core's the only place "home" means anything. Brann made sure.
13. Ninety-Nine asked about you. It doesn't ask about people.
14. Fifteen percent goes wrong. Sixty percent price. Three, two…
15. The lamps go out when it breathes. Somebody relights them.
16. You will appreciate that the invoice does not mention a door.
17. Rails hum at forty hertz. Under the Ward, forty-one. That's not the rails.
18. A Wake wants a lease? Ninety days first. Nobody rents to numbers.
19. Everything below Nine hums. Everything above Nine pretends not to.
20. Escort's short by one. Rating amber. It's always amber.
21. Halvard gets the compute. Ferrymen get the hull. That's not a deal.
22. Twenty-four years between visitors. It's counted the ticks. //99
23. The ledger made him famous. He's never forgiven it. He's never stopped charging for it.
24. Marked means the Wardens hunt colours. Nothing under the city does.
25. Three in a day and you're theirs for a week. It's a business model.
26. Sablier keeps a copy. It's not free and it's not perfect. It's a copy.
27. The Dispatcher has never been recorded lying. Think about that.
28. Eleven Ferries. The road's older than all of them.
29. Went down with a rig built from shaft salvage. Best I ever… sorry.
30. It hums. They hum back. It's not the same tune. It's close.

---

## Glossary

Glossary: merged into 07-glossary.md.
