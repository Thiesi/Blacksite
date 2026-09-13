# S21 — Relays and territory: capture rules, influence, buffs, relay vendors, season tally

**Status:** planned
**Primary model:** Opus · **Reviewer:** none
**Depends on:** S20, S15, S17, S18, S22 · **Milestone:** M4
**Issue:** https://github.com/Thiesi/blacksite/issues/21

## Goal

Give factions something to fight over. Sixteen relays in contested and open
areas with a control terminal and a core, capture by holding plus hacking (3
min) or holding alone (8 min), influence per hour to the holding faction as
the season score, per-relay zone buffs and relay vendors, Scour relays
paying triple, Curfew claim pauses, and core ownership flowing down to S15's
control persistence. After this slice the two-crew relay fight from the
architecture's test list is a real evening.

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
- `docs/world/01-gazetteer.md`: physical placement and atmosphere for
  the sixteen relays. Game design section 7.7 owns effects and core tiers.
- `docs/world/02-factions.md`: relay interests per faction, the
  Sodium Row "no relay" agreement, Sable's war rule.
- `docs/world/03-lattice.md` §2 (Scour public uplinks always exist;
  ownership grants optional shortcuts), §3.11 (Relay Uplink core template).

## Scope

- `content/relays.json`: the sixteen exact IDs, zones, tiers, rates
  and typed benefits in game design 7.7. Core IDs are `lat-relay-<id>`;
  they are distinct from a nearby named service core. Use the central
  table, not a universal tier-2/3 template. Shaft opens with S26's door.
- `server/relays.py`: explicit active claims. The holder is a conscious
  faction member adjacent to the terminal, in physical space and
  channelling. A jacked body does not count. A runner of any faction or
  Freelance may explicitly support that named claim. A current-window
  core lift plus 3 min hold captures; without a runner, 8 min. Opposing
  active claims freeze clocks; bystanders do not contest. Absence over
  5 s aborts. The clinic relay stands in the contested street; the clinic counter
  remains protected.
- On capture, update ownership, logs and receipts atomically. Use design
  7.4's 100 XP, +15 member/-15 former-owner deltas and same-identity,
  same-relay 24 h reward limit. Presence alone grants no participation
  reward. Public Scour uplinks remain reachable under neutral ownership.
- Curfew: new capture attempts refused and existing clocks paused while S24's Curfew
  is active (flag read from the event engine; default false).
- Influence: settle whole elapsed points at 10/hour, Scour 30/hour,
  Shaft 20/hour, carrying fractions and stopping at season end. Treasury
  receives the same amount. Daily login share is floor(1% treasury),
  capped 200, debited once per BBS identity per UTC day in one transaction.
- Buffs: implement exactly game design 7.7 using the relevant subsystem's
  modifier API. Range gains use tiles, fabrication caps at 1.15, salvage
  grade increase caps below intact, and route telemetry grants neither
  immunity nor exclusive basic geometry. Travel holds keep design 6.4's
  bounds; ownership cannot lock a public service or safe zone. Optional
  event/season consumers are completed by S24/S26 and tested there.
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
- `tests/test_relays.py::test_opposing_active_claims_freeze_bystanders_do_not`
- `tests/test_relays.py::test_freelance_cannot_hold`
- `tests/test_relays.py::test_curfew_refuses_capture`
- `tests/test_relays.py::test_influence_lazy_hours_times_rate_scour_triple`
- `tests/test_relays.py::test_flip_sets_core_owner_and_controls_persist`
- `tests/test_relays.py::test_public_scour_uplink_remains_under_neutral_ownership`
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
2. A third caller starts an opposing claim at the terminal: the
   relay shows "contested" and A's clock stops until one leaves.
3. The relay vendor at the terminal is usable by A and B, refused for
   the third caller.
4. In the deterministic manual-clock harness, advance 2 hours: the relays
   menu shows the faction's influence increased by 20 (or 60 for a
   Scour relay).

## Definition of done

Roadmap §7, plus: every gazetteer relay effect is either implemented
as a flag consumed by a landed slice or listed in the PR as "flag
present, consumer pending" with the consuming slice ID.

## Implementer notes

Capture clocks freeze without losing progress under opposition/Curfew.
Hardware and private-core permission rules still apply to relay owners.
Test conscious holder plus Freelance runner, solo eight-minute capture,
passers-by, death, competing active claims, daily payout races, recapture
farming, fractional accrual and settlement cutoff. All sixteen benefits
must resolve to their named consumer; a pending consumer is not a
working feature and must be closed by S24/S26 before release.
