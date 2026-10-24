# S27 — Dialogue and named NPCs: dialogue engine, all major and minor NPC files, ambient logs

**Status:** planned
**Primary model:** Sonnet (engine) · Gemini or Sonnet (content) · **Reviewer:** Sonnet reads every talker file; Opus reads the ten fixed-cast files
**Depends on:** S19, S20, S24 · **Milestone:** M5
**Issue:** https://github.com/Thiesi/blacksite/issues/27

## Goal

Give every named NPC a voice. Implement the talker engine exactly as
the dramatis personae document specifies (one right line for the
situation, offers as hotkeys, barks to the zone log, never a question
the player must answer to leave), then author the talker files for the
ten fixed cast members, the minor named cast, the two terminal talkers,
and the ambient bar lines. The engine is small; the content is most of
the work.

## Spec references

- `docs/world/04-dramatis-personae.md` Part III "Dialogue system notes"
  (talker shape, the closed condition set, `CUST`/`TEN` tags with the
  optional-line weighting from main design 13.4, offers and their hotkeys, delivery rules,
  terminal talkers, content validation list); Parts I and II for every
  NPC's lines.
- `docs/design/01-entities.md` §1.11 (dialogue file; this slice replaces
  the placeholder node/response shape with the talker shape and updates
  the entity doc in the same PR), §1.8 (NPC template `dialogue` field).
- `docs/design/00-game-design.md` §3.4 (grade 5), §7 (standing,
  membership, relations), §7.3 (Marked), §13 (season stages), §11
  (channels).
- `docs/design/02-architecture.md` §5.4 (`MenuView`; a talker interaction
  is a `MenuView` with the line as detail and offers as actions).
- `docs/design/03-terminal-ui.md` §4 (no questions; `Esc`/`B` leaves).
- `docs/world/08-found-texts.md` (Tin Halo bar lines), `docs/world/05-
  story-arcs.md` (Wake briefing and Tin Halo first-contract scripts are
  talker content for Vantongeren and Vesper).

## Scope

- `src/blacksite/server/dialogue.py`: `Talker` loader, `evaluate(talker,
  player, world) -> line`, `eligible_offers(...)`, `bark_scheduler`
  (one bark per talker per 90 s by default, only with a player within
  6 tiles, suppressed during interaction), balance-tag weighting with
  design 13.4's optional-line weighting using the seeded RNG.
- Condition evaluators for the closed set: `first_meeting`,
  `grade_below/at_least`, `is_wake`, `standing_below/at_least`,
  `member_of/not_member_of`, `enemy_of_me`, `marked/not_marked`,
  `has_contract/contract_stage/completed_contract`, `has_item`,
  `season_stage`, `chronicle_choice`, `event_active`, `archetype`,
  `balance`, `legal/not_legal`, `has_evidence`, `receipt`, `service_state`.
  Unknown condition names fail content validation, not
  runtime.
- Offers → action-bar hotkeys `[C]ontract`, `[V]endor`, `[S]ervice`,
  `[J]oin`, `[T]ravel`, each dispatching to the owning subsystem (S19
  contracts, S12 vendors, S16 surgery and detox as services, S20
  recruiters, S08 travel). A contract offer opens the S19 contract card.
- Interaction records `first_meeting` per player per talker
  (persistent set on the player row).
- Terminal talkers: the Dispatcher (Kestrel terminals) and Ninety-Nine
  (Old Works drop terminal and its Lattice presence in the hidden cell,
  with the `lattice` delivery flavour: colour prefix and `//99` suffix).
- Content: `content/dialogue/<slug>.json` for Vantongeren, Brann,
  Halvard, Quell, Reyes, Anouk, the Dispatcher, Ninety-Nine, Vesper, and
  the machine-mind encounter lines (Tenant/Custodian are never talkers;
  their lines are attached to scripted encounters and tagged), plus
  every minor named NPC in Part II (~25), plus the faction recruiters
  and handlers named in `02-factions.md`. Each fixed-cast file carries
  at least the five required situational lines from the validation
  list.
- Ambient: `content/text/ambient-tin-halo.txt` (the ten bar lines) as a
  zone `lore` bark source for `sodium-tin-halo`; Old Works and Sink
  graffiti as `cache` lore objects (content only, objects placed by
  S08's maps or added here).
- Side panel shows the talker's name and title while interacting
  (`MenuView.title`).

## Out of scope

- Contract generation and cards (S19). Vendor menus (S12). Recruit
  flow's standing checks (S20). Season-finale encounter triggering
  (S26, which consumes the tagged lines).
- Voice for unnamed NPCs (they have no talker; interacting shows a
  one-line template bark from `npcs.json`, S11).

## Data and content

- Talker file shape per Part III: `slug, name, faction, title, lines[]
  {when[], text, tag?}, offers[] {kind, when[], label, ref}, barks[]
  {text, weight, min_interval}`.
- Entities §1.11 rewritten to this shape in the PR.
- Validation (tests below) per the document's "Content validation"
  list, run over the shipped tree.

## Protocol and view models

- Intent `talk {actor or object id}`; response is a `MenuView` with
  `kind: talker`, `title` (name and title), `detail` (the line),
  `actions[]` (eligible offers plus Back), no rows.
- Barks arrive as `log` lines on channel `zone` with the talker's name.
- Lattice flavour lines arrive on channel `lattice`.

## Tests

- `test_first_matching_line_wins_and_fallback_always_exists`
- `test_every_condition_in_closed_set_evaluates` (one case each)
- `test_unknown_condition_fails_validation`
- `test_balance_tag_skip_probability_0_7_with_seeded_rng`
- `test_offers_filtered_by_conditions_and_rendered_as_hotkeys`
- `test_talker_with_no_offers_shows_only_back`
- `test_first_meeting_recorded_per_player_per_talker`
- `test_bark_interval_90s_and_suppressed_during_interaction`
- `test_bark_requires_player_within_6_tiles`
- `test_terminal_talker_bound_to_object_not_actor`
- `test_ninety_nine_lattice_flavour_prefix_and_suffix`
- `test_interaction_does_not_pause_world` (damage applied mid-talk)
- `test_fixed_cast_files_have_required_situational_lines`
- `test_no_line_exceeds_200_chars`
- `test_every_zone_talker_slug_exists`
- `test_cust_and_ten_lines_exist_for_each_scripted_encounter`

## Acceptance script

1. As a fresh Wake at 80×24, walk to Vesper in `sodium-tin-halo` and
   press `E`: the side panel shows "Vesper — fixer", the log shows the
   first-meeting line, the action bar shows `[C]ontract [B]ack`. Press
   `B`: nothing else happens.
2. Return later Marked: the Marked line plays instead.
3. Stand 5 tiles from Vesper for two minutes without interacting: one or
   two barks appear in the log, none while you are talking.
4. Interact with a Kestrel terminal: the Dispatcher's line appears
   without any actor on the map.
5. Jack in from the Old Works drop and find Ninety-Nine's cell: its line
   arrives coloured with the `//99` suffix.
6. Talk to a mission NPC outside safety and let another eligible caller
   shoot you: health drops,
   the talker menu stays open, `B` closes it.

## Definition of done

- Tests green; validator covers every dialogue file and the Part III
  list.
- Entities §1.11 updated; every new proper noun in the glossary.
- Opus review of the ten fixed-cast files recorded in the PR.
- Slice file marked done with PR number.

## Implementer notes

- Lines under ~140 characters wrap cleanly in the log at 80 columns; the
  client wraps by display width, so authors need not.
- The `balance` skip must use the zone RNG, never `random`, or the
  simulation tests become flaky.
- Content batches from Gemini: generate per NPC, validate each file,
  and reject any file that invents a condition, a faction, or resolves
  the Custodian/Tenant question.
- Keep `first_meeting` sets bounded: a set of talker slugs on the player
  row is small; do not store per-line history.

## Lore review integration

Entity model 1.11 and main design 13.4 govern the talker contract; the
world personae supply voice and situational examples. Required warnings,
objectives and both finale registers never disappear through weighting.
`is_wake` means legal_at unset; day-count lines use actual elapsed days
and never fixed sample values. Evidence observations differ from source
claims. No narrator line certifies the Custodian/Tenant, clone origin or
Dispatcher identity. Dialogue adds interest, never a correct-answer gate.

Test Brann in the safe precinct separately: a shot is refused, no damage.
Author all Season 1 NPC/record assets now; S26 activates and tests their
full map/chain bundle. Future-season barks require the relevant settled
condition and remain inactive until their complete content exists.


### S20 faction integration handoff

Reference: [PR #38](https://github.com/Thiesi/Blacksite/pull/38) and S20.

Bind Faction.recruiter to each actual named NPC template and place it at the
faction site recruiter_zone. The Wake desk remains a valid all-eight
admission contact. Unmoored public recruiter/board stay Old Works Main;
hall/vat stay Old Works Drop. Keep the existing verbatim recruiter pitches
and do not duplicate named people to fill unfinished geography.

Preserve recruiter story/contract dialogue by offering the validated
faction.open intent as a chosen talker action. Input dispatch must not let
the pre-S27 E-to-recruitment fallback swallow the named NPC dialogue.

### S22 crew integration handoff

S22 [PR #61](https://github.com/Thiesi/Blacksite/pull/61) owns live crew
consent. Chosen NPC dialogue/admission must preserve individual choices;
talking or joining a faction cannot silently add a crew participant.

<!-- s19-services:start -->
### S19 source and service handoff

Reference: [S19 PR #62](https://github.com/Thiesi/Blacksite/pull/62),
[acceptance record](../../ops/s19-acceptance.md) and
[PR #38](https://github.com/Thiesi/Blacksite/pull/38).

S19 supplies the implemented source interfaces, 68 authored contracts
and four service nodes. Full root pytest passed 1344 tests with one
skip. Installed native acceptance covers both sizes and allocations,
forks, repair reconnect and paid restart. Consume the merged PR;
S25/S27/S26 still own real geography, referrals and activation.

Show the chosen and foregone service allocation before consent. Pending
proposals reserve no public order; roster and reservation freeze on
committed start. A disconnect preserves progress only until the original
deadline. Use the server-owned card and personal publication action without
introducing a group ballot or mandatory lore read.
<!-- s19-services:end -->

Before S26 activates Season 1, implement Vesper's neutral referral when
hostile standing blocks a faction's handler. Route actual deliveries
and turn-in through that broker, waive only the blocked handler standing
gate, and retain prior-job/settled-branch, grade, item and event checks.
Use S19's `receipt GROUP` for a continuation after either paid fork;
an acceptance-only branch flag is insufficient. Keep already-paid
opposite-branch helpers at zero reward without changing their choice.
Native hostile-referral acceptance is part of this dialogue integration,
not proof claimed by S19's inactive authoring bundle.

Use the [S19 content handoff](../s19-content-handoff.md) for its 33
attributed evidence records and named sources. Default cards distinguish
observation from the source's claim, question and next action. Optional
prose cannot become an answer quiz. Vesper's generated-job brokerage is
already live; the hostile-standing story referral above is still required
before S26 activation. Keep the two permissions distinct.

<!-- s24-handoff:start -->
### S24 event integration and acceptance handoff

Reference: [S24 #24](https://github.com/Thiesi/Blacksite/issues/24),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

Dialogue event conditions must read `Contracts.event_active` and
committed event IDs; an announced proposal is not an active event.
Route Master/Ferrymen/Choir offers read S24's immutable EventOffer and
revision. Keep +90 Kin, paid charts and public warnings consistent.
Convoy reservations clear at start/expiry/cancel with a saved offline
notice; they never close another caller's public escort job. Preserve
recorded-cycle/story fallbacks so required progression never waits for
a live Curfew, Ring-fall or Surge. Name actual sources and consequences
without presenting fixture geography or caller telemetry as lore.
<!-- s24-handoff:end -->


<!-- s24-review-policy:start -->
### S24 practical review follow-up

Reference: [PR #65](https://github.com/Thiesi/Blacksite/pull/65), retaining
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and #56.

Read current Convoy arrival/loss revisions rather than announcing an
available escort after its NPC has finished or died. Personal held records
survive global history retirement with compact final outcomes; dialogue and
required story fallbacks must not depend on an old plan remaining in the hot
receipt.
<!-- s24-review-policy:end -->

<!-- s25-access:start -->
### S25 physical route access handoff

Reference: [S25 #25](https://github.com/Thiesi/Blacksite/issues/25),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and platform #56.
Game 5.6 and entities 1.1 now specify typed member/story credentials,
alternative requirements and a missing-credential message. This bounded
runtime support is necessary to commission the canonical physical city;
S25 otherwise remains content work. Missing NPC profiles use the
initial values documented in game 5.5 and require pacing acceptance.

A referral or mission dialogue must not manufacture physical access by
writing a client/saved-progress flag. Consume the typed route permission
source with S26 and existing committed mission permits. Keep Halvard
membership separate from friendly standing, and retain an explicit public
return route.
<!-- s25-access:end -->

<!-- s25-city-decisions:start -->
### S25 commissioning decisions (in progress)

Reference: [S25 #25](https://github.com/Thiesi/Blacksite/issues/25),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

The draft uses game 5.6's carried key OR exact local open-latch state for
the optional Drowned bulkhead. Ordinary Outworks/Shaft Foot travel is
free; a key is retained, not consumed. Hidden physical exits allow
explicit Interact on their tile and never auto-travel on a walk. All
Undercity base sight is five before carried light. Whole-zone `pocket`
safety protects clinics, just as an authored pocket does.

The existing Terraces sector expands from 36 to 48 cells: a public
register wing supplies 24 distinct apartment addresses without reusing
entry/uplink cells or changing existing hidden/gated routes. Halvard's
member hall, vat and counter are in the Mezzanine; public recruitment,
care and banking remain in the Atrium. Three secondary ration/flare and
salvage counters bring ordinary vendors to 22; only Landing retains its
20% salvage premium. New NPC profiles and gantry damage are documented
initial values in game 5.5/6.4 and must pass actual-city pacing.

Place named speakers at the commissioned anchors; replace ambient
stand-ins without creating duplicate services. Explain the hidden
physical routes through visible clues, dialogue or Listening guidance.
Halvard member purchases and the hall vat are in the Mezzanine; public
recruitment and care remain in the Atrium.

These are in-progress decisions, not a claim of merge, native acceptance
or completion of the Shaft Foot/Far Ring and broader human pacing gates.
The real walled apartments also exposed a geometry-admission bug:
a closed private door must not freeze unrelated public controls.
Housing supplies the occupant's explicit Interact-to-leave doorstep as
the escape origin; occupied tiles remain passable and private entry
permissions still apply. Retain that proof under tenants, visitors,
restart and overlapping effects. The Lobby's five inert private-door
props are replaced by the real 24-unit Block Street pool.

S25 places `ferrymen-corpse`, `choir-shrine`, `unmoored-dead-drop` and the
empty Far Ring artifact sites as physical source hooks. S27 owns the
corpse's one-time personal map and the shrine's daily claim receipt;
S26 owns season artifact activation. A prop label alone grants no reward.
Permanent hazards are excluded from salvage-node placement because
incoming damage interrupts the harvest channel. If an optional opening
closes over a saved position, reconnect recovers to the nearest free,
non-hazardous tile in the public spawn component, respecting housing
entry permissions. Include both in actual-city restart and event tests.

Mezzanine physical admission does not grant a Citadel network credential;
its loan terminal keeps the normal network gate. The Far mast uses the
Scour sector and cannot bypass Static's Ring-fall gate. All 16 relay
sites are mapped, but Shaft Relay retains `requires_level`; S26 must bind
its availability to the committed level phase, alongside the story-route
providers. Mapping never pretends that this seasonal gate is open.

Native city commissioning also preserves fallback Interact on a physical
prop underfoot before any adjacent public network terminal. Shaft Foot
therefore reports its sealed season-console status; explicit J still
jacks in. Retain this actual-map regression through S26 activation and
later interaction handlers. See PR #66, alongside PR #38 and issue #56.

A dedicated apartment doorstep chooses its door ahead of adjacent
dropped goods; a prop underfoot still owns Interact. Native delivery-key
testing exposed the previous accidental core-log action. Preserve this
public/private interaction through future handlers. Full-city salvage
checks allocate a proposal only when a field deadline is due; seeded
respawns and the tick p99 below 10 ms requirement stay in force.

The Citadel's executive lift lockdown closes only the Atrium inbound
lift for 300 seconds. Gatehouse restores the same physical panel, with
the latest committed operation winning. The Plaza exit and Mezzanine
return remain available; machinery restoration grants no credentials.
Disabled controls report a control lock instead of a missing credential.
Retain this binding, return path and refusal distinction through seasonal
activation, help, operator diagnostics, load tests and federation replay.
See [PR #66](https://github.com/Thiesi/Blacksite/pull/66), alongside the
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) product review.
<!-- s25-city-decisions:end -->
