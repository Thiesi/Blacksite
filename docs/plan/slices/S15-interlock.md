# S15 — Interlock: controls, hardware, cut-power, private cores, core ownership

**Status:** planned
**Primary model:** Opus · **Reviewer:** none
**Depends on:** S14, S11 · **Milestone:** M2
**Issue:** (filled in when filed)

## Goal

Join the two layers. Flipping a control in a core changes one object in
one zone immediately and tells everyone there; a crew at a core's
hardware can cut its power and throw every runner out; relay-held cores
keep their controls flipped; and private apartment cores can be hacked
for one unsecured item a day with the resident told. This is the slice
that makes the two-layer pillar true.

## Spec references

- `docs/design/00-game-design.md` §6.4 (all four interlock rules:
  immediate control effect with zone log line, 5–30 min reset unless
  owned by the relay-holding faction, cut-power = jack-out with shock
  100 and 10 min offline, private-core theft of one unsecured item per
  day with notice), §5.6 (interactions: hardware object).
- `docs/design/01-entities.md` §1.4 (ControlSpec: target zone/object,
  action, reset), §2.9 (core state: controls, offline_until,
  owner_faction), §3.2 (zone instance object live state).
- `docs/design/02-architecture.md` §6.2 (flush on relay change and
  item transfer), §10 (scenario: cut-power during a run).
- `docs/world/03-lattice.md` §3 (every core's `object @ zone` control
  list and hardware location), §7 (Shiv reports; owner notifications).
- `docs/world/01-gazetteer.md`: the target objects (gates, turrets,
  shutters, cable cars, pumps, lifts, cameras).

## Scope

- `server/interlock.py`: a registry built at content load mapping every
  `ControlSpec` to a live zone object; validator fails on any control
  whose target does not exist (entity invariant §5).
- Control actions: `open`, `close`, `disable`, `enable`, `toggle`, `call`
  applied to object kinds: `door` (open/close/lock), `turret`
  (enable/disable; turrets are NPC actors from S11 with a `powered`
  flag), `camera` (Warden sight in `core-plaza`: disable blinds Wardens
  to one attack for 10 s), `shutter` (curfew shutters), `tram_stop`
  (call/stop; a stopped tram exit refuses transit for the reset window),
  `cable_car` (stop/run), `pump` (Sump: water tiles spread or drain over
  an hour, S24 timer style), `lift` (lockdown), `light` (on/off changes
  zone sight radius locally), `patrol_beacon` (diverts the next patrol
  crew 15 min, S11 spawner hook), `vat` (Vatline controls: S10's vat
  respawn location toggles), `gate` (Gate Nine schedule, toll).
- Zone log line on every flip in the affected zone in voice ("The gate
  cycles open. Nobody touched it."), and a runner-side log line.
- Reset timers per control (5–30 min from the core file) unless the
  core's `owner_faction` (set by S21 when a relay above it is held;
  until S21, always null) matches the runner's faction, in which case
  the state persists until reset by another runner or the relay
  changes hands.
- Hardware objects: `hardware` object kind at each core's hardware
  location; `E` on it by any player opens a `MenuView` with one action
  **Cut power** (confirmation keystroke), 5 s channel time interruptible
  by damage; on completion: every presence in that core is jacked out
  with shock 100, the core is `offline_until` now + 10 min (entrance
  cell shows `[C?]` dimmed; `lat.enter` refused with a log line), the
  zone gets a log line, and the actor gains the standing consequences
  S20 defines (hook `on_cut_power(actor, core)`).
- Shaft core exception: one core with two hardware locations
  (`spire-shaft-head` and `under-shaft-foot` per the gazetteer); either
  cuts it.
- Private cores: instantiate the private-core template per apartment
  (S18 supplies apartments; here a fixture apartment) at tier 1–3 in
  the Terraces sector under one entrance cell per rented apartment; the
  data room lists the resident's **unsecured** storage manifest; a
  successful lift takes exactly one unsecured item, once per apartment
  per 24 h (`last_hacked_at`), moves it to the runner's inventory, and
  writes a `hack_log` entry the resident sees on next login and in
  their apartment menu ("Someone was in your core at 03:12. They took a
  Sablier Med Patch."). Passkey opens the door control without a fight
  per the program table. Secured items and banked chits are never
  visible.
- Owner notifications: black-sector and Shiv reports resolve to the
  owning faction's channel (S20 faction chat; until then a zone log to
  the hall zone).
- Persistence: core state rows with control states and reset
  timestamps, `offline_until`, `last_hacked_at`, `hack_log` capped at 20
  entries; flushed immediately on flip, cut, and theft.

## Out of scope

- Relay capture and the `owner_faction` assignment: S21.
- Apartment rental, storage, safes: S18 (this slice uses a fixture
  apartment and the template).
- Faction standing deltas for cutting power or hacking: S20.
- Turret and Warden NPC behaviour itself: S11.
- Sump water spreading as an event timer: implement the timer here with
  the same lazy-elapsed pattern; S24 does not own it.

## Data and content

- Control entries already in `content/cores/*.json` (S14); this slice
  adds `content/controls.json` only if a shared action table is needed
  (prefer per-core entries).
- `content/text/interlock-*.md`: the zone log lines per action in voice
  (open, close, disable, enable, stop, call, lights, pumps), ~20 lines.
- Fixture world: a door, a turret, a light, and a hardware object wired
  to the fixture tier-3 core; one fixture apartment with a private core.

## Protocol and view models

- `LatticeView.room.controls [{id, label, state, reset_in}]`;
  intent `lat.flip <control>` (3 s, +10 trace).
- `ZoneView.objects` carries `state` so the client redraws a door or
  turret glyph on flip; `hardware` object kind glyph.
- `MenuView` kind `hardware` with the single action; `MenuView` kind
  `apartment` gains a "core log" section (S18 owns the rest).
- Log channel `sys` for interlock lines; `zone` for the in-voice line.

## Tests

- `tests/test_interlock_content.py::test_every_control_resolves_to_zone_object`
- `tests/test_interlock_content.py::test_every_core_has_hardware_object_except_wake_hall`
- `tests/test_interlock.py::test_flip_changes_object_state_same_tick`
- `tests/test_interlock.py::test_flip_posts_zone_log_line`
- `tests/test_interlock.py::test_reset_timer_5_to_30_min_from_content`
- `tests/test_interlock.py::test_owned_core_control_persists_past_reset`
- `tests/test_interlock.py::test_camera_disable_blinds_wardens_10s`
- `tests/test_interlock.py::test_tram_stop_refuses_transit_until_reset`
- `tests/test_interlock.py::test_shaft_core_two_hardware_locations`
- `tests/test_cut_power.py::test_5s_channel_interrupted_by_damage`
- `tests/test_cut_power.py::test_all_presences_jacked_out_shock_100`
- `tests/test_cut_power.py::test_core_offline_10min_enter_refused`
- `tests/test_private_core.py::test_manifest_lists_only_unsecured`
- `tests/test_private_core.py::test_one_item_per_24h_per_apartment`
- `tests/test_private_core.py::test_resident_hack_log_written_and_shown`
- `tests/test_private_core.py::test_passkey_opens_door_control_without_ice`
- `tests/test_sim_multi.py::test_cut_power_during_run_runner_sees_floor_go`
- `tests/test_sim_multi.py::test_runner_opens_gate_crewmate_walks_through_same_second`
- `tests/test_sim_multi.py::test_two_runners_in_core_both_ejected`
- `tests/test_persistence.py::test_control_state_survives_restart_with_reset_clock`

## Acceptance script

1. Two callers at 80×24. Caller A stands at a locked door in the
   fixture zone (or Gate Nine in `tramyard-wall-gate`); caller B jacks in
   and enters the matching core.
2. B flips the gate control (3 s, trace +10). A sees the door glyph
   change and the zone log line the same second, and walks through.
3. A walks to the core's hardware object, presses `E`, chooses **Cut
   power**, confirms; after 5 s B is thrown to the zone view with SHK
   full and a log line; the core entrance shows dimmed for 10 minutes.
4. B (with Passkey) enters the fixture apartment's private core, lifts
   one item; A (the resident) opens the apartment menu and reads the
   hack log; B tries again and is refused for 24 h.

## Definition of done

Roadmap §7, plus: the content validator rejects a core whose control
targets a missing object, and the four multi-session scenarios pass.

## Implementer notes

- Control effects must run inside the target zone's tick even when the
  zone is dormant: wake it, apply, and let it go dormant again with the
  reset timer as a pending timer (architecture §6.1).
- The 24 h private-core limit keys on the apartment, not the runner:
  two runners cannot each take one item.
- Zone slugs in `03-lattice.md` need mapping to gazetteer IDs (see S13
  notes); the validator will catch every mismatch, which is the point.
- Cut-power channel time is interruptible by any damage, including
  from a turret the runner just re-enabled: that race is intended.
