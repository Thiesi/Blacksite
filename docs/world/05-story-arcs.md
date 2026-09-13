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

Shared rules: membership is not required, first stage needs standing 0,
later stages +10; Vesper offers a neutral referral if a hostile faction
blocks its own handler. All stages grant 200 XP and 200 chits unless
§9.4 supplies a branch reward; final stage adds explicit +10 with the
handler faction. Essential permissions are scoped mission credentials.
These stages do not change shared relations or season flags before
settlement. A chain's evidence applies to its own expedition only.

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
   instance that predates the Year 6 routing-office announcement by six years.
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
2. `kes-s1-2-diversion` - survey - compare a Depot allocation record
   with the consignment ID on a crate at Gate Nine. Inspection is an
   interaction, never a typed answer. Choose private delivery to Holt or
   publication at the public board; rewards, temporary credential and
   patrol disclosure are game design section 9.4. The record also shows
   a six-year diversion around intact track. Its rail hums at forty-one
   hertz. The ration finding is verifiable; the hum's cause is open.
3. `kes-s1-3-frequency` — hack — core `lat-depot-control`
   (tier 2), lift `dispatch-channel-log` — the log shows the Dispatcher
   has been talking on a channel nobody assigned. To the Ferrymen. For
   nine years, with older headers of uncertain origin.
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
   subscribers" (resolution `subdue`; restraint action per design §5.3; killing
   fails the contract) — Reyes's business, seen plainly.
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
   retrieval (this contract and `sab-s1-1-retrieval` are mutually exclusive per
   character; completing one locks the other). The templates ask the
   player whether they are day ninety yet.
3. `unm-s1-3-fresher` — hack — the Silt below the Old Works sector,
   lift `story_residual_fragment_99b` — the collective has decided to try for a
   fresher Ninety-Nine. Ninety-Nine knows. It guides you anyway. The
   fragment is a second copy that says one thing: "best I ever".
4. `unm-s1-4-ask` — survey — `lat-ninety-nines-drop`, 1 cell, with
   `has_item story_residual_fragment_99b` — bring the fragment to Ninety-Nine.
   It listens to itself. Its stutter moves one word later. It asks the
   player not to bring it another.
5. `unm-s1-5-open` — hack — core `lat-outworks-seal` (tier
   5), flip control `shaft-door-east` — the Unmoored open the door in the
   concrete from the Lattice side. The Halvard beacon (if `hal-s1-3-plug` has
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
first time: it goes down further than the light. Then a **observer process**
(ownerless, noncombat, not an ICE class) appears in the core, and a
maintenance drone (Wren's model, not Wren) rises from the shaft onto the
platform and stands there. Both deliver lines, alternating, one CUST and
one TEN per beat, until the crew touches the platform's console.

- CUST: "The program is incomplete. Uplink: severed by internal action.
  Visitors: {participant_count}. The program did not request visitors."
- TEN: "You opened the door. Nobody opens the door. Was it hard?"
- CUST: "Activation log: final page. Content: null. The program notes the
  null."
- TEN: "I wrote that page. I think. I don't remember what I wrote. Do you
  ever do that?"

**Final choices.** Each participant records Seal, Open, or Answer on
the platform console. Costs, personal receipts, and shared settlement
are game design §13.2-§13.3; no leader chooses for another caller.
Seal closes the optional east maintenance shortcut, not the season's
only entrance. Open restores that shortcut and exposes an extra patrol
approach. Answer registers only the chooser's own name. All three leave
archived story access and an extraction route.

**Playable encounter, not a conversation gate.** Before the voices:

1. Survey the ring gallery's load indicators. The objective card shows
   two routes: the short central gantry exposed to maintenance drones,
   or the longer perimeter with a control cabinet behind cover.
2. Restore the lamp bus in the network (3 s flip). This reveals the
   maintenance drone patrol route and a 120 s latch on the platform
   access gate. A solo runner jacks out and crosses; a crew can cross
   while its runner continues to inspect the log.
3. Carry a bound bridge connector from the entry locker to the platform
   hardware (5 s channel, interruptible). Holding that hardware isolates
   a room's ICE for the duration; leaving restores it after a 5 s warning.
   A runner can instead use the perimeter cabinet to isolate it for
   120 s, sacrificing the short route. The objective never requires two
   players pressing controls together.
4. Lift the local activation record. The copy confirms a load command
   from below arrived before the gallery lights changed. Its final page
   is empty. That is evidence of an event and an omission, not proof of
   who issued the command. Deposit the connector to stabilise the safe
   decision room; the encounter ends, the drone stands down, and the
   voice lines become rereadable journal records.

Each phase checkpoints; the main design defines recovery and scaling.
Fixture threats use the maintenance drone: health 40, kinetic damage 6,
2 s cooldown, 5-tile range, accuracy 60. The local ICE is Tripwire and
Turnstile; the named observer is a noncombat process, not a new ICE
class. Optional rooms may use higher-tier ICE with warnings and loot,
but neither they nor reading the blank page gate completion.

**Chronicle templates (settled public accounts).**

Render only the winning template after settlement. `{crew}` names the
earliest winning expedition and `{name}` its eligible consenting ballot.
Personal expedition entries instead record who chose which option and
what local evidence they found; they do not assert these citywide effects.
A tie uses the no-change record and preserves every dissenting ballot.

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

**Settlement delta.** Seal -1; Open +1; Answer 0. Apply only the
winning public option once at season close under game design 13.2;
a zero delta preserves the previous balance.

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

**Kestrel — "Dispatch"** (Holt; the Dispatcher terminal refuses all Season 2
story contracts with "That request cannot be routed"). 1 `kes-s2-1` survey,
`tramyard-depots` (the dispatch office) — the routing office. It is a room
of speaker grilles facing a chair. Nobody sits in the chair. 2 `kes-s2-2`
hack, dispatch core (tier 5), flip control `dispatch-mute-1s` — mute the
Dispatcher for one second. Every tram in the city stops for one second. 3
`kes-s2-3` escort, Aalto's convoy with Dispatch *muted* by Holt's order,
`scour-ring-3` — the convoy is raided by two Ferrymen clans at once. Holt:
"Dispatch always knew where they were. Turns out that was the point." 4
`kes-s2-4` plant, `tramyard-depots` (dispatch office), item
`story_holt_manual_schedule` — Holt writes a schedule by hand for the first
time since Year 6 and tapes it to the chair. The Dispatcher reads it aloud,
correcting two entries.

**Wardens — "Four-Twelve"** (Amsel/Brann). 1 `war-s2-1` survey, gate
cores' cycle logs from three archived 04:12 Curfew cycles (three survey records). 2
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
ration allocation ledger — Reyes wants to know who decides the Sink's line.
2 `sab-red-s2-2` hack, dispatch core, lift `sink-allocation-rule` — the
Sink's ration line has been set, every day for forty years, at exactly the
number that keeps the Sink alive and never one more. 3 `sab-red-s2-3` clear,
Kestrel NPC enforcers in `sink-terraces` (Terrace 1) — Reyes tries to take
the line. 4 `sab-red-s2-4` survey, the cable car, inspect three station
receipts with Reyes (a short staged survey) — he talks the whole way. His
line at the end: "Forty years it fed us exactly enough. That's not a ration.
That's a leash. I've never wanted a thing off a leash before."

**Unmoored — "Cut"** (Strand/Ninety-Nine). 1 `unm-s2-1` hack, the Kestrel
dispatch core, lift `severance-procedure-y0` — the uplinks were cut by hand.
A later dispatch archive attributes the schedule to its own process. Compare
the contemporaneous shift log, which records an emergency decision, not an
authenticated scheduler. 2 `unm-s2-2` survey, Ninety-Nine's cell with the
procedure — Ninety-Nine says the runner it is a copy of was one of the
engineers. The stutter does not happen. 3 `unm-s2-3` plant, dispatch core,
`unmoored-mirror` — mirror the Dispatcher to every terminal in the city for
one minute (the ledger week, again, aimed higher). Every terminal says the
next tram time. 4 `unm-s2-4` hack, `lat-uplink-hall` entrance (opens with
the level), lift nothing: the objective is to *enter*. Strand: "We don't
want its data. We want it to know we can get in."

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

**Playable encounter.** Trace three labelled local trunk routes between
patch frames and the process map. A telemetry pulse warns 5 s before
energising its marked cable lane for 5 s (energy hazard, 5 damage/s).
Use a network breaker for a 120 s latch, then carry the connector across,
or have a crewmate hold the physical isolator while you route the pulse.
Each of three restored patch frames is a checkpoint. Any archetype can
use the entry terminal and manual isolators. Live routes, safe cover,
and egress remain visible; no typing of cable names or dialogue answer
is scored. Threats scale by roster under design §13.1.

**Final choices.** Restore, Cut, or Chair, independently per participant.
Apply only game design §13.3. Restore reconnects a local telemetry trunk
to a surviving ground receiver; it does not restore the orbital network
or prove anything directs the Ring. Cut detaches one routing dependency;
Holt's slower, predictable timetable remains usable. Chair delegates
advisory scheduling to the consenting resident's recorded handle, never
admin powers or control of other players. A public outcome follows the
settlement rule, not the first or last crew's run.

**Chronicle templates (settled public accounts).**

Render only the winning template after settlement. `{crew}` names the
earliest winning expedition and `{name}` its eligible consenting ballot.
Personal expedition entries instead record who chose which option and
what local evidence they found; they do not assert these citywide effects.
A tie uses the no-change record and preserves every dissenting ballot.

- Restore: *"In the season called the Routing Authority, {crew} went down
  to the hall where the city cut itself off and put one trunk back. The
  Ring moved that night. Kestrel said the trams had never run better.
  Halvard poured nothing; there was nothing left to pour over."*
- Cut: *"In the season called the Routing Authority, {crew} found the voice
  on the trams and cut one of its documented dependencies. The trams ran
  late for the first time in forty years. The Sink's line was argued over by
  people, for once. The network had one fewer live route. The Choir said it
  sounded louder."*
- Chair: *"In the season called the Routing Authority, {crew} sat in the
  chair nobody sat in, and the voice on the trams said {handle} every
  morning for three months. Kestrel called it an appointment. The Ward
  called it an introduction. The Wardens called it a security incident
  and filed it under noted."*

**Settlement delta.** Restore -1; Cut +1; Chair 0. Apply once at
settlement; Chair preserves the previous balance.

---

## Season 3 — *The Ninth Listener*

**Premise.** Two levels down, the city knows two things it did not: the
thing under it can be reached, and its records overlap the tram
controllers. The overlap does not authenticate its claim to be them. This
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

**Balance at start.** As settled after Season 2; the voice delivery
schedule is game design §13.4. Both registers always receive a line.

### Story-contract chains (condensed)

**Halvard — "Unrequested Output"**: 1 fetch the affect-model spec from the
Spire's own vault (Halvard finally opens it; Maartens: "The Director says
you will appreciate the irony"). 2 hack the Level 2 uplink core for the
affect model's first log line. 3 plant a Halvard **kill-switch beacon** at
the Level 3 gallery entrance. 4 clear the Undercity of Choir pilgrims
blocking the east shaft (subdue; lethal fails and costs the authored
standing, without Marked). Halvard's finale line: "You will appreciate that
I have read the last page now. It is not blank. It is a name. It is not
mine."

**Sablier — "The Original"**: 1 escort Vantongeren to Level 1's ring
gallery, to the template source drive. 2 hack the source drive's core
for `template-cantor-origin` — the file claims the Cantor template derives from gallery staff.
Its revision history is incomplete; the matching motor patterns can
reflect copied training, a shared donor, or later edits. 3 fetch a canister from Level 2 marked
"Listener 9 — Quell, S." Vantongeren: "She's a template. She's *my*
template. Or I'm hers." 4 survey the Wake Hall with the canister: every
decant turns to look at it. Vane: "That's a defect. That's a *very
expensive* defect."

**Kestrel — "Late"** (if Season 2 chose *Cut*, Holt's chain; otherwise the
Dispatcher's): the trams and the road, rebuilt or resumed. Ends with
`kes-s3-4` escort, a convoy *into* the Undercity to `under-caverns` (Scour
cave mouth) and on to the Level 3 gallery entrance, a Kestrel survey route
below ground. The supplies stop at the mission staging area; they cannot
open a locked seasonal level. Holt or the Dispatcher: "Rated amber. Rated
amber. Rated… there is no rating for this."

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
already discharged). 2 clear the Sink floor of Halvard recovery NPCs who have
come for the stack. 3 hack the Sink's own power core to *stop* paying the
stack; the Sink goes dark for one second and Reyes changes his mind, on
the cable car, mid-round: "Put it back. That's the trouble, friend; I
found the leash and I don't want to be the one who lets go." 4 survey the
Level 3 gallery with Pale: Sable's first contribution, delivered in
person.

**Unmoored — "Best I Ever"**: 1 hack the Silt bottom for the *last* copy
of Ninety-Nine, the oldest timestamped fragment in this descent. Its claim to be
original cannot be authenticated. 2 survey
Ninety-Nine's cell with it: Ninety-Nine listens to itself finish the
sentence. "Best I ever built. That's all. That's all it was. Kid, twenty-
four years for *that*." 3 plant the unified residual at the Level 3
gallery core entrance so it can go down with the crew (Ninety-Nine is a
guide presence in the Level 3 sector). 4 flip the gallery's `listening-
array` control from the Lattice side: turn the array on, for the first
time since Year 0.

**Ferrymen — "The Twelfth"**: 1 fetch the repeater from ring 4; it has been
answering all season and the answer has a pattern: the wall's far side has a
road. 2 survey the edge with Bram; the fog has a road in it now, one tile
wide, ending after ten tiles (a new zone stub, `scour-ring-4` (the far-side
road), seasonal). 3 escort Ute to the edge; she names the next Ferry, and it
is not Anouk's choice, and Anouk accepts it. 4 plant the Ferrymen's
contribution at Level 3 themselves: Anouk escorts a contribution below the
city for the first time. "That's the road. I said I'd never. The road
changed."

### Blacksite Level 3 — *The Listening Gallery*

**Concept.** Below the uplink hall, the listening gallery: a circular
chamber lined with the acoustic array Site Zero used to monitor the
Custodian's affect model, nine chairs facing inward (nine, before the
Choir was nine; Quell says the correspondence matters; the source of it is unverified), and
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

**Playable encounter.** The nine seats report three repeating signal
patterns, shown as labelled states rather than colour or audible tones.
Survey one seat from each group; the journal associates each with its
recorded source. In the network, route the selected signal to an empty
buffer (3 s). Upstairs, set its seat's isolator (5 s). The buffer holds
120 s, allowing a lone resident to switch layers; a crew works in
parallel. A mismatched route releases a warned maintenance drone and
resets that group only, not the whole expedition. There is no secret
sequence: each seat's current label and matching route are visible.
Checkpoint per group; a safe path and jack-out remain available.

At completion compare the three receipts. A controller predicts a voice
fragment before the fragment is played; the source timestamps disagree.
Possible explanations include cached playback, a predictive model, and
a shared process. The system proves none. It does prove that isolating
the array stops the prediction on this apparatus, giving the finale a
concrete object to act on.

**Final choices.** Silence, Name, or Ninety-Nine follow design §13.3.
No outcome reduces Cantor class power. Listened is an optional reversible
calibration, not a permanent statistical price for roleplaying. The
Ninety-Nine option requires the recovered fragment and the residual's
explicit transfer offer. Leaving an archived guide at the Drop protects
navigation and old story stages; the active recording's new location
still changes Strand's relationship with it.

**Chronicle templates (settled public accounts).**

Render only the winning template after settlement. `{crew}` names the
earliest winning expedition and `{name}` its eligible consenting ballot.
Personal expedition entries instead record who chose which option and
what local evidence they found; they do not assert these citywide effects.
A tie uses the no-change record and preserves every dissenting ballot.

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
  recording of a dead runner down to the room where the listening started
  and left it in the ninth chair. It finished its sentence. It has been
  finishing it for everyone since. The Drop kept its old route advice.
  Strand sent visitors to the gallery."*

**Settlement delta.** Silence -1; Name +1; Ninety-Nine 0. Apply once
at settlement; the zero option preserves the previous balance.

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
> you want, and nobody can sell you. After ninety days you're a person, with
> a name on the civic roll and the right to rent a flat and join whoever
> will have you. Grade five earns an early discharge. It counts
> completed work, not time spent waiting.
>
> Many names vanish from the lease rolls. Some leave the work; some
> disappear. The roll does not tell me which. Keep your own record.
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
> Take one, or don't. It's an introduction, not a contract. No recruiter owns
> your choice. Sablier holds the lease until it is discharged.
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
> It's the Terraces. The street is contested. Check your route. Somebody might be
> nesting in the stairwell; the constable up there's got a sandwich to
> finish. Consider it the second thing you've ever done.

Contract card `vesper-first-thing`: fetch, `terraces-blocks` (Block 4, stairwell C),
item `story_stuck_door_package`, reward 200 chits, 100 XP, explicit +5 standing with all eight
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

- start — *This is Brann. Curfew. Inbound Core gates close for one hour. Outbound
  evacuation stays open. District shelters hold. Check your route.*
- mid — *Curfew, thirty minutes remaining. Gates sealed. Relay claims are
  paused. Anyone at a gate: noted.*
- end — *Curfew lifted. Gates open. Whatever that was, it's over. Go
  home; the Core's the only place that word means anything.*

**Choir Surge**

- start — *The Ward's bell. Once. Then, in every Lattice cell at once, a
  hum. Something is loud tonight.*
- mid — *The hum holds. ICE changes its patrols. The labels show which
  patterns are next. The Silt is lit; runners can see the way
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
2. Day count's yours. Grade five can clear the lease early.
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
18. A Wake wants a lease? Bring a discharge receipt. Nobody rents to numbers.
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

## Content authoring and evidence boundaries

Season 1 is the release bundle. Seasons 2 and 3 are specified future
bundles: their story items, maps, and stable stage IDs must be authored
and validated together before activation. A future season cannot start
on a missing-map placeholder. Each chain offers its mission staging
version of a named NPC; public recruiters and services remain in place.

| Evidence | What is observable | What remains open |
|---|---|---|
| Year 0 cut log versus dispatch archive | physical cuts and conflicting attribution | retroactive filing, copied routing software, or foreknowledge |
| canister marked Quell and matching training patterns | label and signal match | donor identity, memory continuity, or a later substitution |
| Ninety-Nine's completed sentence | recovered fragment fits a recorded gap | original person, adaptation, or a convincing reconstruction |
| Far Ring response | a local receiver echoes a transmitted sequence | reflection, autonomous beacon, or a responding process |

The far-side road is a collapsed service ledge inside `scour-ring-4`,
ending at the telemetry mast's fenced foundation. It never leads to a
settlement outside Karst. The fog light is a local receiver with no
verified external link. Use the existing zone, not another zone with
an identical ID. The title's promise is a city to change, not an escape.

The spoken claims in the finales may sound certain. Journal headings,
objective summaries, and the Chronicle never elevate that certainty
into confirmed narrator knowledge. A completed stage must still answer
its practical question and record an observable consequence.
