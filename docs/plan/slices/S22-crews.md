# S22 — Crews: invite/leave/kick, crew chat and panel, beacon, loot modes, shared XP

**Status:** in progress
**Primary model:** Sonnet · **Reviewer:** none
**Depends on:** S09, S10, S13, S16 · **Milestone:** M4
**Issue:** https://github.com/Thiesi/blacksite/issues/22

S18 housing permissions remain personal: crew membership, shared loot,
scouting and beacons do not grant entry or storage/safe/terminal/bed
access. Private room bodies and resident drones remain hidden from
outside scouting and target views. A key or Passkey opens only a
30-second delivery vestibule. Keep the existing victim-cache recovery
regression separate from protected apartment impound. See game design
8.7, [S18](S18-apartments.md) and accepted
[PR #38](https://github.com/Thiesi/Blacksite/pull/38).

## Goal

Make the crew the unit. Crews of two to five with a leader, invites,
crew chat, the side-panel crew list with health and zone, the Operator
beacon across zones, loot modes for caches and core data, shared XP
within five grades, and the crew as the identity that shares a Silt
seed and a Blacksite instance. After this slice two callers can crew
up, split between the street and the Lattice, and see each other's
state.

## Spec references

- `docs/design/00-game-design.md` §10 (2–5, leader invite/accept/
  leave/kick, crew chat, panel with health and zone, Operator beacon,
  loot free-for-all default or round-robin, XP shared full within 5
  grades else scaled), §1 pillar 5, §3.2 (Operator crew beacon), §5.2
  (jacking cover), §5.4 (pick-up of a downed crew member in 5 s), §6.5
  (crews share a Silt seed).
- `docs/design/01-entities.md` §3.7 (crew: leader, members, invites,
  loot mode, beacon target, chat), §2.1 (`crew_id` live only).
- `docs/design/03-terminal-ui.md` §2 (CREW panel section: name, HP bar,
  zone or "jack"), §5.1 (`G` crew, `T` crew chat).
- `docs/design/02-architecture.md` §10 (multi-session scenarios).

## Scope

- `server/crews.py`: `Crew` per `01-entities.md` §3.7; intents
  `crew.invite <name>` (leader or any member if the leader allows;
  default leader only), `crew.accept`, `crew.decline`, `crew.leave`,
  `crew.kick <name>` (leader), `crew.promote <name>`, `crew.loot
  <ffa|round_robin>`, `crew.beacon <name>` (Operator only); invites
  expire in 60 s; size 2–5; a crew dissolves when one member remains;
  leader passes to the longest-serving member on leader logout.
- Crew relation: members are never hostile to each other for S10's
  attack legality (friendly fire refused with a log line) and S20's
  Marked check; members show as `player_crew` role and `+` tag.
- Crew panel: `ZoneView.crew[]` with name, hp_pct (or integrity when
  jacked), zone name (or "jack" with the sector), `beacon` flag; sorted
  leader first; updates every tick that changes.
- Beacon: an Operator crew member marks one crew member; the marked
  member's zone and tile are shown to the crew as a `beacon` object in
  their zone view when in the same zone, and as "zone · direction" on
  the panel otherwise; only one beacon per crew.
- Loot modes: `ffa` (default: caches and core data first come first
  served, subject to S10's 60 s non-killer wait, which crew members
  bypass for their crew's kills) and `round_robin` (a cache or data
  item is offered to the next member in rotation for 10 s, then falls
  through); mode changes take effect on the next drop.
- Shared XP follows game design 10: local participation (within six
  tiles for ten seconds, or a relevant action/heal in the last 60 s),
  then the grade-gap multiplier, once per reward receipt and identity.
  Merely occupying the same large zone or joining at turn-in is not
  participation. Contract/relay rewards use their own fixed rosters.
- Pick-up: any crew member adjacent to a downed member may `E` to
  pick up within the 5 s window (S10's down state); `Ninefold` hymn
  and `con_sablier_pickup` modify per catalog.
- Crew chat: channel `crew` (S09) with its own colour role; `T` opens
  the line prompt on it.
- Silt joining uses its explicit shared instance entrance and roster,
  never a remote beacon. S26 expedition IDs/rosters are persistent and
  independent of the live social crew; leaving, kicking, dissolving or
  restarting a crew cannot reassign ballots or destroy checkpoints.
- Sitrep (S09) shows crew membership as a column.
- Persistence: none (live only); crews vanish on server restart, which
  is acceptable and logged.

## Out of scope

- Contract crew scaling: S19.
- Relay hold mechanics: S21.
- Blacksite instancing: S26.
- Voice-style emotes or crew emotes beyond S09's list.
- Persistent guilds or crews across sessions: design doc §16 excludes.

## Data and content

- No structured content files. Text: invite, accept, leave, kick, promote, beacon
  set, loot mode lines in voice (≈ 15 lines in `content/text/crew.md`).

## Protocol and view models

- `ZoneView.crew[] {id, name, hp_pct, zone, jacked, beacon, leader}`;
  `ZoneView.objects` `beacon` entry; `me.crew {id, leader, loot}`.
- `MenuView` kind `crew`: members with health/zone, pending invites,
  actions invite / leave / kick / promote / loot mode / beacon.
- `toast` on invite received with the accept key.
- Log lines on every crew event; shared XP lines say "crew".

## Tests

- `tests/test_crews.py::test_size_2_to_5`
- `tests/test_crews.py::test_invite_expires_60s`
- `tests/test_crews.py::test_leader_only_kick_and_promote`
- `tests/test_crews.py::test_leader_passes_on_logout`
- `tests/test_crews.py::test_dissolve_at_one_member`
- `tests/test_crews.py::test_friendly_fire_refused`
- `tests/test_crews.py::test_members_never_marked_by_each_other`
- `tests/test_crews.py::test_round_robin_offers_10s_then_falls_through`
- `tests/test_crews.py::test_ffa_crew_bypasses_60s_wait_on_crew_kill`
- `tests/test_crews.py::test_shared_xp_full_within_5_grades_scaled_after`
- `tests/test_crews.py::test_shared_xp_requires_same_zone_or_sector`
- `tests/test_crews.py::test_operator_beacon_only_one_per_crew`
- `tests/test_crews.py::test_seed_nonce_shared_within_5min`
- `tests/test_sim_multi.py::test_panel_shows_health_and_zone_across_zones`
- `tests/test_sim_multi.py::test_jacked_member_shows_integrity_and_sector`
- `tests/test_sim_multi.py::test_pickup_downed_member_within_5s`
- `tests/test_sim_multi.py::test_crew_chat_reaches_only_members`
- `tests/test_sim_multi.py::test_beacon_object_visible_to_crew_in_same_zone`
- `tests/test_door_menus.py::test_crew_menu_golden_80x24`
- `tests/test_door_views.py::test_crew_panel_shrinks_from_bottom_at_24_rows`

## Acceptance script

1. Caller A opens the crew menu (`G`), invites caller B by name; B sees
   the toast and accepts; both panels show the other's name and HP bar.
2. B walks to another zone: A's panel shows B's zone name; B jacks in:
   the panel shows "jack · Core" with an integrity bar.
3. A (Operator) sets a beacon on B; A's panel shows direction; when A
   enters B's zone a beacon glyph marks B's tile.
4. A is downed by a fixture drone; B walks adjacent and presses `E`
   within 5 s; A stands up with a log line.
5. A kills a drone: B, two grades apart and in the zone, gets the same
   XP line marked "crew"; A shoots at B: "You don't shoot crew."

## Definition of done

Roadmap §7, plus: the six multi-session scenarios pass with
deterministic ticks and the panel golden holds at 80×24 and 132×50.

## Implementer notes

- The XP scaling formula past five grades and the round-robin timer are
  canonical numbers in game design section 10; use them directly.
- Crews are live-only by design; do not add a table. Log the dissolve
  on restart so the SysOp guide can explain it.
- The crew relation must be checked before the faction relation in
  S10's legality function; add a test there too.
- The beacon across zones needs a "direction" from zone exits: use the
  city graph's exit toward B's zone (S08), or "elsewhere" if no path.

### Implementation decisions

The deterministic live registry is `server/crews.py`; `crew_engine.py`
binds sessions, consent, views and source receipts. Invitations create no
one-person crew, do not refresh on repeated input, and cannot flood the
recipient's log. Member order survives promotion and determines the next
leader. Removing either beacon endpoint clears it. Missing/deleted
characters leave the live registry before a roster is published.

Marked red names compose with the crew plus tag. Friendly fire, indirect
controls and owned drones use controller identity before faction checks.
Pickup now requires current crew membership and the actual five-second
window; the pre-S22 neutral-caller fallback is removed. Medic drones,
Relay terminals and hymn range use the same membership authority.

Source owners join eligible crew XP and identity caps to their existing
transaction. A failed save pays nobody. Guarding uses elapsed injected
ticks, including a delayed service tick; walking out of range resets the
continuous guard interval. Completed useful actions remain eligible for
sixty seconds, including a control of the linked core. Contract/relay
owners still freeze and settle their own rosters in S19/S21.

Cache offers freeze at drop creation and retain actual-victim recovery.
Drone kills name the controller as killer. Shared core data freezes its
offer at a valid lift, after blocking ICE permits access; the ten seconds
must not run out while the data is still blocked. Rotation advances on
the owning commit. Identity/mission data stays personal. Absolute UTC
deadlines preserve existing offers across a restart without persisting
the live social crew.

An authorized, consenting entrant can reuse the first descent's frozen
roster/seed at its same entrance for five minutes. That scene remains
available for the window; later crew joins do not gain it. This live Silt
sharing is independent of S26's durable expedition/checkpoint/ballot IDs.

Native acceptance uses a version- and source-verified installed client.
The original development interpreter loaded an old client once NetBBS
removed PYTHONPATH; those runs are compatibility evidence only. The
harness now rejects mismatches and retains `native-client.json`. The
Windows subprocess startup check allows sixty seconds for cold content
bootstrap, reproduced with unchanged S20; Linux and gameplay latency
targets remain unchanged.

Actual native input exposed a pre-existing 50ms framing failure: a split
Right arrow became Esc, left bracket and C, opening Say during movement.
UI 5.3 now gives sequences 200ms to complete; the decoder and input pump
share that constant. A lone Escape still leaves without effects, after
the framing grace. Byte-split regressions exercise the observed delay.
This is a transport usability fix, not a combat or simulation timing
change. S04's reference and the common UI contract are reconciled here.


### S20 faction integration handoff

Reference: [PR #38](https://github.com/Thiesi/Blacksite/pull/38) and S20.

Preserve S20 faction outcomes and Marked body attribution when adding crew
affiliation. Crew relation overrides compose with the shared matrix rather
than editing faction membership. Keep the PR #38 actual-victim cache
regression and individual consent gates.
