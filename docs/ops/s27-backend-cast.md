# S27 backend and cast checkpoint

Issue #27, resumed through issue #82 after the owner merged P3 (#103,
`205f852460871738b31e3f9735b8bd5d27e51701`). This checkpoint finishes the
backend and authors the cast. It does not complete S27's held delivery
and native acceptance.

## Delivery boundary

All 44 dialogue records and the two ambient text assets belong to the
`s27-cast` **authoring** bundle. No shipped NPC template, zone object or
Lattice cell acquires a dialogue binding here. No geometry, map,
presentation renderer, trial switch or faction pitch changes.

The engine uses P3's existing contract input route: committed mission
actions first, named dialogue second, ordinary boards third. The same
read-only decision supplies focus and dispatch. A fixture can bind a
talker to an object, NPC or occupied Lattice cell; production placement
awaits the approved anchors. Speech goes through `Session.emit`, with
`kind=speech`, a speaker and its presented class. Actor speech uses P4's
disclosure helper; terminal/object speech uses class `service`.

The pure bark scheduler and authored barks are available to P8. There is
no second emission loop. P8 must use the single ambient emitter and its
derived per-zone RNG, preserve the six-tile audience and interaction
suppression, and apply the caller's ambient budget. S27 ticking neither
emits a bark nor consumes simulation randomness.

## Authored inventory

| Group | Records | Source |
|---|---|---|
| Ordinary fixed cast | Vantongeren, Brann, Halvard, Quell, Reyes, Anouk, Dispatcher, Ninety-Nine, Vesper | Dramatis personae Part I |
| Scripted encounter bank | `machine-mind-encounter` | Part I, both internal voice registers |
| Minor cast | All 27 entries, Amsel through Aalto | Part II |
| Additional recruiters | Vael, Achterberg, Quaye, Iloh, Vance, Achebe-Roux, Kettle | Factions document; Vantongeren is the eighth recruiter |
| Ambient text | Ten Tin Halo lines and the graffiti set | Found texts, verbatim |

The encounter bank is excluded from ordinary contacts. It is not a
Custodian or Tenant actor. S26 must consume both required finale
registers explicitly; choosing one first-match line cannot satisfy that
requirement. Voice tags never reach a caller.

The nine ordinary fixed talkers have first-meeting, Marked, Wake, enemy,
settled-finale and fallback lines. Ninety-Nine retains `//99` throughout.
Wren has neither voice tag. Future-outcome examples are adapted to
settled public records, rather than assuming the listener participated,
asserting a particular ending or
muting the Dispatcher before settlement. Static example day counts and
unsupported fare/rate promises are not runtime dialogue.

Every one of S19's 33 Season 1 evidence records has a required reaction
at its faction's fixed talker and named handler. Each requires that
viewer's `has_evidence` fact. The lines distinguish the observation,
the source's claim and the question left open; they require no quiz.
Immediate Marked and enemy warnings retain priority. First introductions,
the viewer's evidence and Wake status precede a global settled-finale
line, so a late arrival still hears their own situation. Newest eligible
evidence precedes ordinary returning greetings. Each reaction belongs to
its speaker's own voice and attributes claims without copying a source's
third-person attribution into the claimant's mouth.

This is deliberate content priority: a returning Wake hears the lease
line instead of a generic public-finale reaction when no more specific
personal progress applies. Discharged callers can hear the public-finale
line. Vesper's paid first-job acknowledgement is personal progress and
precedes both. These finale reactions are flavour, not the required
finale instructions or the two encounter registers. S26's Chronicle and
settlement records remain their own authoritative surfaces.

Work hotkeys open the existing local board; clinic and trade hotkeys
resolve a nearby server-owned counter, including reusable vendor
templates without an `object_id`. Recruitment opens the existing terms
and verbatim pitch. Missing counters and unmet owner-system checks
remain refusals. No offer grants membership, buys an item, starts work,
reserves a worker allocation or grants a route credential by itself.

Roles without an existing commissioned counter (for example Wren's
barter and some named vendors) have authored speech and no invented
vendor or exchange. Placement/content binding must connect only real
owning-system affordances. Terminal talkers can speak from their
occupied cell; physical work and counter actions require the physical
counter. Terminal placement is still held.

Vesper's neutral board waives a story giver's minimum standing only when
the caller's faction has relation H to the giver (game 7.2 / 9.1). Low
personal standing alone does not qualify. Grade, other factions' standing,
items, predecessor or paid branch receipts, membership, events and personal
branch limits stay with S19.
The live broker and each participant's relation are rechecked at proposal
and start. Service work remains local. Turn-in keeps the commissioning
faction's reward and atomic once-only payment. Crew consent and paid-helper
rules are unchanged.

The Wake's existing three briefing assets and faction pitches remain
the verbatim onboarding sources. Vesper's first-card line requires both
first meeting and her actual card; the chosen work card supplies the
full objective, reward and danger terms.

## Engineering validation scenarios

These are deterministic headless fixtures, not native or visual proof.

1. Bind a fixture Vesper at the Tin Halo counter. Inspect focus repeatedly:
   no RNG draw, meeting flag, transfer or menu appears. Press E. Only a
   successful storage commit records the introduction; a failed write
   leaves first meeting available to retry.
2. Choose C, V, S or J from a fixture talker. The corresponding owner
   opens its current card/counter/terms. Back leaves without payment,
   work acceptance, surgery or faction membership. A counter template
   without an object ID still resolves its actual local object.
3. Bind fixture Ninety-Nine to the occupied public Lattice cell. Its
   speech has the `lat` channel, structured speaker metadata and `//99`.
   Back leaves the talker, preserving the network presence.
4. At an exposed fixture talker, a second caller's ordinary deliberate
   shot can still injure the listener. Repeat in the precinct's safe
   pocket: the same safety rules refuse damage. Dialogue grants neither
   safety nor permission to attack.
5. Offer a neutral story at Vesper. Check retained grade, item, receipt,
   membership and event conditions; move away before start and verify
   refusal. Complete and turn in through the broker: pay once, to the
   original commissioning faction. Public service allocations stay local.
6. Load the shipped cast. Resolve every authored reference, exercise all
   fixed-cast situations and all 33 personal evidence reactions, and
   verify the second caller's empty journal reveals none of them.

## Outstanding acceptance

The presentation integration plan section 6.1 and issue #82 hold speaker
placement, ambient emission and presentation-dependent native steps for
P8 and S25c anchors (P4 is merged). There is no S27 real-terminal or
NetBBS transport acceptance in this checkpoint, and no visual, layout,
navigation-comprehension or human-pacing approval. The full S27 slice
remains in progress. Issue #104 remains queued after this backend/cast
work, for P5; it is not folded into this checkpoint.
