# S20 — Factions: membership, standing, relations, Marked, Warden heat, ranks and perks, faction chat

**Status:** planned
**Primary model:** Opus · **Reviewer:** none
**Depends on:** S11, S12, S16 · **Milestone:** M4
**Issue:** https://github.com/Thiesi/blacksite/issues/20

## Goal

Make the eight factions real in the rules. Standing per faction with
deltas from contracts, kills, relay actions, and interlock; the
relations matrix as the truth for who may shoot whom; joining and
leaving; the Marked rule and Warden heat; rank titles at four standing
thresholds with one perk at +90 each; faction chat, vats, vendors, and
colours. After this slice a contested district behaves the way the
bible says it does.

## Spec references

- `docs/design/00-game-design.md` §7.1 (standing −100..+100, Wake
  recruiter +10, contracts/kills/relay deltas with allies and enemies
  halved, join at +30 and legal discharge, one faction, leave −50 and 7-day
  cooldown, member benefits, ranks and +90 perks never a flat combat
  multiplier), §7.2 (relations matrix; symmetric except documented
  asymmetries; data file is truth), §7.3 (Marked: 15 min, anyone may
  attack anywhere outside safe zones without being Marked, Wardens
  engage in contested zones, red name, killing a Marked player gives
  Warden standing, nothing marks in open zones, Freelance and below
  grade 5 protected), §5.5 (Warden heat 10 min), §11 (faction
  channel), §14 (grade-5 griefing rules).
- `docs/design/01-entities.md` §1.9 (faction file), §2.1 (faction,
  standing, marked_until, warden_heat_until), §2.5 (faction state).
- `docs/design/03-terminal-ui.md` §1 (faction colour roles), §8
  (relation tags `!`, `~`, `+`).
- `docs/world/02-factions.md`: ranks at +30/+50/+70/+90 per faction,
  +90 perks (Custodial Officer, Attending vat choice, Route Master reservation, Inspector telemetry,
  Ninth variant preview, Hand stock reservation, Deep loan and Kin
  forecast; numeric rules are design 7.6), recruiter NPCs, hall slugs, colours with
  256/16 fallbacks, relations rationale, Freelance page, chat culture.
- `docs/world/00-bible.md` §7.

## Scope

- `content/factions.json` per `01-entities.md` §1.9 with the eight
  factions, relations matrix from the design doc (the data file is the
  truth; a test asserts the doc's matrix and lists the intended
  asymmetries explicitly: the file may declare none), colours per tier
  and palette variant, halls mapped to gazetteer IDs (`spire-atrium`,
  `vatside-clinics`, `tramyard-depots`, `core-precinct`,
  `chapel-nave`, `sink-terraces`, `oldworks-main`, `scour-landing`;
  reconcile against the factions doc's slugs), vats, recruiters, ranks.
- `server/factions.py`: `standing(player, faction)`, `apply_delta
  (player, faction, delta, reason)` propagating +delta / 2 to allies
  and −delta / 2 to hostiles of that faction; sources wired: contract
  turn-in (S19 emits), NPC kill (−5 with the NPC's faction, +2 with
  its hostiles), player kill (−10 with victim's faction if not hostile
  to yours; +5 with the Wardens if the victim was Marked), relay
  capture (S21 emits +15 / −15), cut-power (S15 hook: −10 with the core
  owner), private-core theft (−10 with the Wardens if reported by the
  resident).
- Join: recruiter `talker` action when standing >= 30 and legal_at set;
  sets `faction`, grants member benefits; leave: −50 standing,
  `faction_cooldown_until` +7 days, loses benefits at once.
- Relations: `relation(a, b)` returns H/N/A for faction pairs with
  Freelance treated as N to all; used by S10's attack legality, S11's
  aggro, S13's presence colour, and the Marked check.
- Marked: apply game design 7.3 at hostile action commitment, including
  misses, remote controls, drones and burning. Below grade 5, contested
  PvP is refused in both directions before marking. For eligible actors,
  nonhostile/Freelance attacks mark for 15 min; an already Marked target
  is exempt. Safe/pocket harm is always refused and safety rechecked at
  impact. Open zones never mark; permission to post a bounty grants no
  combat exemption. NPC missions use their own standing/permit rules.
- Warden heat: 10 min after the documented trigger, doubled for new heat
  during Curfew. Safe-zone response is a warning only; pursuit deals
  damage in contested/open zones, never safe/pocket. Legal personhood
  does not remove the independent under-grade protection.
- Ranks: titles at +30/+50/+70/+90 and exactly the eight perks in game
  design 7.6. Use daily receipt keys and the owning subsystem's typed
  interface. Perks stop below +90 or on leaving; no combat multiplier,
  forced player displacement, public-service ban or essential story
  gate. Choir Ninth has no population cap; Charter at +70 is a title.
  Preview/reservation perks consume S24's committed plans after it lands;
  S24 must complete that integration before reporting them usable.
- Faction chat: channel `faction` (S09 channels) for members only;
  colour role per faction; a member leaving loses it at once.
- Faction vats (S10 respawn list gains the member's hall vat), faction
  vendors (S12 `member` tier resolves via `player.faction`), faction
  colours on glyphs and names (S06/S13 read `faction.colour`).
- Sitrep (S09) gains faction column and rank; Inspector sees Marked
  players' zones city-wide.
- Persistence: standing map, faction, cooldown, marked_until,
  heat_until; flush on join/leave and on Mark.

## Out of scope

- Relay capture, influence, and treasury payouts: S21.
- Crew relations (crew members are never hostile to each other): S22.
- Warden NPC behaviour itself: S11 (this slice sets the flags they
  read).
- Season relation overrides (`relations_override` in seasons): S26.
- Recruiter dialogue prose: S27 (this slice uses the pitch text from
  the factions doc as a `TextView`).

## Data and content

- `content/factions.json`; recruiter pitch texts `content/text/
  faction-<id>-pitch.md` (verbatim from the factions doc); rank titles;
  chat-culture samples are not content (they are for NPC barks, S27).

## Protocol and view models

- `ZoneView.actors[].role` uses `player_hostile`, `player_neutral`,
  `player_crew`, `player_marked`; `nearby[].relation` tag; `me.faction`,
  `me.rank`, `me.marked_until`, `me.heat_until`.
- `MenuView` kind `faction` (standing list with bars, rank, join/leave
  actions with confirmation keystroke, cooldown).
- Log lines: standing change with reason (throttled to one line per
  faction per 10 s), Marked start and end, heat start and end, join,
  leave.

## Tests

- `tests/test_factions_content.py::test_matrix_matches_design_doc`
- `tests/test_factions_content.py::test_asymmetries_are_exactly_the_declared_ones`
- `tests/test_factions_content.py::test_halls_and_vats_resolve_to_gazetteer_zones`
- `tests/test_standing.py::test_delta_propagates_half_to_allies_and_hostiles`
- `tests/test_standing.py::test_clamped_minus100_plus100`
- `tests/test_standing.py::test_wake_card_sets_plus_10`
- `tests/test_standing.py::test_join_requires_30_and_legal_discharge`
- `tests/test_standing.py::test_leave_minus_50_and_7_day_cooldown`
- `tests/test_marked.py::test_attack_non_hostile_in_contested_marks_15min`
- `tests/test_marked.py::test_undergrade_contested_pvp_refused_both_directions`
- `tests/test_marked.py::test_attack_hostile_faction_does_not_mark`
- `tests/test_marked.py::test_open_zone_never_marks`
- `tests/test_marked.py::test_attacking_marked_player_does_not_mark_attacker`
- `tests/test_marked.py::test_killing_marked_gives_warden_plus_5`
- `tests/test_marked.py::test_wardens_engage_marked_in_contested_only`
- `tests/test_heat.py::test_heat_10min_and_doubles_under_curfew_flag`
- `tests/test_ranks.py::test_titles_at_thresholds_per_faction`
- `tests/test_ranks.py::test_no_perk_touches_combat_numbers`
- `tests/test_ranks.py::test_inspector_sees_marked_citywide_in_sitrep`
- `tests/test_ranks.py::test_hand_reserves_optional_stock_without_blocking_public_vendor`
- `tests/test_sim_multi.py::test_two_sessions_marked_name_turns_red_for_the_other`
- `tests/test_sim_multi.py::test_faction_chat_only_reaches_members`
- `tests/test_sim_multi.py::test_hostile_faction_members_fight_unmarked_in_sink`

## Acceptance script

1. Two callers at grade ≥ 5 in `sink-terraces`, one Sable, one Freelance.
2. The Sable caller shoots the Freelance caller: the Sable name turns
   red on the other screen with the `!` tag; a Warden NPC in the zone
   turns on the Sable caller; the sitrep shows "Marked 14:52".
3. A third caller (any faction) kills the Marked player: log shows
   +5 Wardens and no Mark.
4. A Halvard member at +30 talks to the recruiter, joins, sees the
   faction channel appear; types in it; the Freelance caller does not
   see it. The member leaves: −50, cooldown 7 days in the faction menu.

## Definition of done

Roadmap §7, plus: the matrix test names every asymmetry the data file
declares (currently none) and the combat-number test for perks passes.

## Implementer notes

Main design 7.1 and 9.3 own standing propagation: explicit multi-faction
outcomes apply once without secondary propagation. Ordinary single-source
reputation propagates halves toward zero. A perk receipt keys on BBS
identity, so relogging or changing character cannot refresh it. The hall
and vat mapping is reconciled in the faction dossier; do not create old
alias zones. Relations use one function and the canonical matrix.

Add tests for missed shots, indirect attacks, grade-4 legal residents,
safe-body effects, daily perk races and every perk's loss-of-standing
path. A Freelance can finish every main-season objective.
