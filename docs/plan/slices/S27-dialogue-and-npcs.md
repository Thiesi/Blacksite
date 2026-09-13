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
