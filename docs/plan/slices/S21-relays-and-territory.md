# S21 — Relays and territory: capture rules, influence, buffs, relay vendors, season tally

**Status:** planned
**Primary model:** Opus · **Reviewer:** none
**Depends on:** S20, S15 · **Milestone:** M4
**Issue:** https://github.com/Thiesi/blacksite/issues/21

## Goal

Give factions something to fight over. Sixteen relays in contested and
open zones with a control terminal and a core, capture by holding plus
hacking (3 min) or holding alone (8 min), influence per hour to the
holding faction as the season score, per-relay zone buffs and relay
vendors, Scour relays paying triple, Curfew immunity, and core
ownership flowing down to S15's control persistence. After this slice
the two-crew relay fight from the architecture's test list is a real
evening.

## Spec references

- `docs/design/00-game-design.md` §7.4 (relay = control terminal +
  core; capture = member holds 3 min AND runner hacks the core open in
  that window, OR 8 min hold with no runner; influence per hour; zone
  buff and vendor for members; no capture during Curfew; Scour triple),
  §6.4 (controls persist while the relay above is owned), §13 (season
  leaderboard: influence per faction), §3.4 (relay XP), §7.1 (relay
  standing deltas).
- `docs/design/01-entities.md` §2.4 (relay state), §2.5 (faction
  state: treasury, influence), §1.1 (`relay` object kind).
- `docs/world/01-gazetteer.md`: the sixteen relays and their effects
  (Shaft Relay in `spire-shaft-head`; Cold Chain in Vatside: surgery
  discount; Depot: vendor restock ×2; Gate Relay Nine: gate on demand
  and toll; Cable: free rides and stop; Sump: pumps; Bell: +10 % hymn
  range; Relay Zero: −10 % trace Lattice-wide; Yard: +5 % fabrication
  quality; Block: rent −10 %, +1 private ICE slot; Cavern: cavern map;
  Outworks: Descent +10 %, Exhale capture is a season event; Mile:
  convoys safe on Wall Ring road; Beacon: Ring-fall sites 5 min early;
  Crash: Ring Three salvage +1 grade; Far: hear the Custodian's carrier).
- `docs/world/02-factions.md`: relay interests per faction, the
  Sodium Row "no relay" agreement, Sable's war rule.
- `docs/world/03-lattice.md` §2 (Scour uplink cells exist only while
  the relay is held), §3.11 (Relay Uplink core template).

## Scope

- `content/relays.json`: sixteen relays with zone, terminal object,
  core (instantiated from the Relay Uplink template at tier 2, tier 3
  for Scour and Outworks), influence rate (base 10 per hour; Scour
  relays 30; Shaft Relay "Halvard-tier": 20 and story-gated by S26),
  buff spec (one typed effect each from the list above, implemented as
  modifiers through S16's aggregator or as hooks into the owning
  slice), vendor inventory id (a relay vendor object appears at the
  terminal for members of the holder).
- `server/relays.py`: capture state machine per relay: `neutral |
  held(faction) | contested(faction, since, holder_present, hacked)`.
  A member (S20 faction, not Freelance) adjacent to the terminal
  pressing `E` starts a hold; the hold continues while any member of
  that faction stays adjacent (leaving for > 5 s aborts); at 3 min
  with `hacked == True` (a runner of the same faction has lifted the
  uplink core's `relay_open` data during the window, S14 data kind) the
  relay flips; at 8 min without, it flips; members of a different
  faction holding at once reset both (contest: the terminal shows
  "contested" and nobody's clock runs while two factions are adjacent).
  Flip: `captured_at`, `captured_by`, +15 standing with the faction for
  everyone of that faction present, −15 with the loser for the
  capturer, XP 100 to present members, zone and faction log lines,
  core `owner_faction` set (S15 control persistence), Scour uplink cell
  added to the Scour sector (S13).
- Curfew: capture attempts refused with a log line while S24's Curfew
  is active (flag read from the event engine; default false).
- Influence: lazy clock per relay: on any read, pay (elapsed hours ×
  rate) into `faction_state.influence` (season score) and `treasury`;
  members receive a share on login: treasury × 1 % per member login
  per day, capped at 200 chits (a new number; see notes).
- Buffs: applied to members while in the relay's zone (or
  Lattice-wide for Relay Zero, city-wide for Block rent): implemented
  as modifier flags read by S16 (surgery discount, fabrication
  quality), S12 (restock rate), S08 (gate on demand, cable car free
  ride, toll of 25 chits for non-members at Gate Nine), S15 (Sump
  pumps default state), S10 (hymn range), S14 (trace −10 %), S18 (rent,
  ICE slot), S25 (cavern map reveal), S26 (Descent +10 %), S24 (convoy
  safety, Ring-fall warning, Beacon), S17 (Crash grade step), S27 (Far
  Relay carrier text). Each buff is a named flag; consuming slices that
  have not landed ignore it.
- Relay vendor: `vendor` object with `relay: <id>` visible and usable
  only by members of the holder; inventory ids in `relays.json`.
- Sodium Row has no relay (content assertion). Sable's war rule is
  narrative; no mechanics.
- Season tally: `faction_state.influence` resets at season end (S26
  calls `reset_season`); relays return to neutral at season end.
- Admin: `blacksite admin relay list|set <id> <faction|neutral>`.
- Persistence: relay state rows; flush on every state change and on
  influence pay-out.

## Out of scope

- Season end, leaderboard display, the Chronicle: S26.
- Curfew, Exhale, Ring-fall, Convoy events: S24 (this slice reads the
  flags).
- Crew mechanics (a crew holding is just members present): S22.
- Zone maps with relay objects placed: S08/S25 (fixture has two).

## Data and content

- `content/relays.json`, relay objects in zone files, the Relay Uplink
  core template instantiation (S14 template), relay vendor inventories
  (a small member-only list per relay, from the factions doc's vendor
  categories).
- Text: capture, loss, contest, and pay-out lines per faction voice.

## Protocol and view models

- `ZoneView.objects` relay entry with `state`, `faction`, `progress
  {faction, seconds, needs_hack}`; `event` banner reused for "Relay
  contested" in zone.
- `MenuView` kind `relays` (city list with holder, time held, your
  faction's influence this season) from any terminal.
- Log lines on hold start, abort, contest, flip, and influence pay-out.

## Tests

- `tests/test_relays_content.py::test_sixteen_relays_zones_and_cores_resolve`
- `tests/test_relays_content.py::test_sodium_row_has_no_relay`
- `tests/test_relays.py::test_hold_3min_with_hack_flips`
- `tests/test_relays.py::test_hold_8min_without_hack_flips`
- `tests/test_relays.py::test_hold_aborts_after_5s_absence`
- `tests/test_relays.py::test_two_factions_adjacent_contest_no_clock`
- `tests/test_relays.py::test_freelance_cannot_hold`
- `tests/test_relays.py::test_curfew_refuses_capture`
- `tests/test_relays.py::test_influence_lazy_hours_times_rate_scour_triple`
- `tests/test_relays.py::test_flip_sets_core_owner_and_controls_persist`
- `tests/test_relays.py::test_scour_uplink_cell_appears_and_disappears`
- `tests/test_relays.py::test_standing_plus_15_minus_15_and_xp_100`
- `tests/test_relays.py::test_relay_vendor_members_only`
- `tests/test_relays.py::test_buff_flags_per_relay`
- `tests/test_relays.py::test_season_reset_neutral_and_influence_zero`
- `tests/test_sim_multi.py::test_capture_with_holder_and_runner_two_sessions`
- `tests/test_sim_multi.py::test_two_crews_contesting_relay_clock_frozen_until_one_leaves`
- `tests/test_sim_multi.py::test_holder_killed_hold_aborts_other_faction_starts`
- `tests/test_persistence.py::test_relay_state_and_influence_survive_restart`
- `tests/test_door_menus.py::test_relays_menu_golden_80x24`

## Acceptance script

1. Two callers of the same faction in the fixture contested zone (or
   `tramyard-wall-gate`): A stands at the relay terminal and presses
   `E`; the object shows a progress bar; B jacks in, enters the uplink
   core, lifts `relay_open`; at 3 minutes the relay flips, both get
   the log lines and standing.
2. A third caller of a hostile faction walks up to the terminal: the
   relay shows "contested" and A's clock stops until one leaves.
3. The relay vendor at the terminal is usable by A and B, refused for
   the third caller.
4. The SysOp advances the clock 2 hours with the admin CLI: the relays
   menu shows the faction's influence increased by 20 (or 60 for a
   Scour relay).

## Definition of done

Roadmap §7, plus: every gazetteer relay effect is either implemented
as a flag consumed by a landed slice or listed in the PR as "flag
present, consumer pending" with the consuming slice ID.

## Implementer notes

- The influence rate, the treasury share, and the toll are new
  numbers; add to `00-game-design.md` §7.4 and §8.1 in this PR.
- Contest freezes clocks rather than resetting them; a 20-minute
  standoff should be decided by who leaves, not by who arrived first.
- The Shaft Relay is story-gated: capturable only when S26's season
  state allows; until S26, it is present but refuses with "sealed".
- `hacked` must be set by S14's data lift within the current hold
  window only; a lift before the hold started does not count.
