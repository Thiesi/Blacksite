# S31 — NetBBS integration and release: supervised preset, safe admission, packaging and first release

**Status:** planned
**Primary model:** Sonnet · **Reviewer:** Human (install on the ReLink test node)
**Depends on:** S26, S28, S29, S30, S32, S33 · **Milestone:** M6
**Issue:** https://github.com/Thiesi/blacksite/issues/31

## Goal

Turn the repository into something a SysOp installs: a wheel with the
content inside it, a door profile preset they import on NetBBS's
Compatibility screen, an install guide that goes from a bare service
account to a playing caller, a release checklist, and the first tagged
release. Require NetBBS >= 7.31.0 and integrate its already released
companion service. Keep the external runner as an explicit alternative,
not a second speculative future-version preset.

## Spec references

- `docs/design/02-architecture.md` §2 (components, install directory
  layout, content copied out on first start), §3 (target and interim
  lifecycle), §8 (native stdio, 16 sessions, `DOOR_*` environment,
  explicit limits, registered-only admission, API 5 and presence), §14
  (packaging: single package, entry points, content as package data,
  Python 3.12+, no runtime deps, semantic versioning, independent
  protocol major).
- `docs/upstream/01-door-services.md` (the `service` profile block),
  `02-session-limits.md`, `04-door-info-enrichment.md` (`door_api`),
  `06-third-party-door-install.md` (released outcomes in their headers).
- `docs/plan/01-netbbs-platform.md`: issue #56 decisions, verified
  upstream references and required acceptance matrix.
- `docs/design/04-assets.md` §5 (operator-facing assets), §6 (player-
  facing README section).
- NetBBS `docs/NetBBS-door-guide.md`: "Register and test inside NetBBS"
  (import of a repository JSON on the Compatibility screen, argv
  substitutions `{install_dir}` and friends, `max_sessions`, **Check
  setup**, **Test as SysOp**), "Native doors" (interpreter doors),
  "Trust and filesystem layout" (install directory ownership).
- `AGENTS.md` §6 (working with NetBBS), §9 (repository layout).

## Scope

- `pyproject.toml`: package `blacksite`, `requires-python >= 3.12`, no
  dependencies, `[project.scripts]` `blacksite = blacksite.cli:main`
  (dispatching `serve`, `door`, `admin`, `bot`), `[tool.setuptools.
  package-data]` including `content/**` and `deploy/**`, version from
  `blacksite/__init__.py`.
- `python -m blacksite.door`, `python -m blacksite.server`, `python -m
  blacksite.admin`, `python -m blacksite.bot` all work as module
  invocations (NetBBS profiles use `-m`).
- `deploy/netbbs-door-profile.json`: the importable profile with
  `executable_path` placeholder `/path/to/blacksite-venv/bin/python`,
  `args` `["-m", "blacksite.door"]`, `profile` `{version: 1, adapter:
  native, endpoint: stdio, encoding: utf-8, width: 0, height: 0,
  install_dir: "/var/games/netbbs/blacksite", time_limit: 0,
  cpu_seconds: 0, memory_mb: 128, stop_grace_seconds: 5,
  max_sessions: 16, multinode_certified: true, resize_signal: true,
  environment: {DOOR_BLACKSITE_INSTALL_DIR:
  "/var/games/netbbs/blacksite"}}`, plus description and architecture
  3.1's exact five-key `service` block. No implicit finite CPU cutoff
  on an unlimited session; S29 validates efficiency and operator sizing.
- Service uses the door interpreter and argv `-m blacksite.server
  --install-dir {install_dir}`, with_node start, 10 s service grace,
  512 MiB service memory and socket health. Validate only the released
  service keys/substitution. The external alternative removes this
  block and uses S05's rc.d/systemd unit; never run both owners.
- Content bootstrap: first server start copies `content/` out of the
  package into `DIR/content/` and records the package version; a
  version change re-syncs and never touches `content.local/`
  (architecture §2.4) — implement here if S03/S05 left it as a stub.
- `docs/ops/install.md` (or the install chapter of the SysOp guide):
  create the service-account-owned venv and install dir per the NetBBS
  guide's ownership rules; `pip install blacksite-x.y.z-py3-none-any.whl`;
  first `blacksite serve --install-dir DIR` to create secrets and
  content; register the door (SysOp → Doors, minimum play level 255
  first), import the preset, set the interpreter path, **Check setup**,
  **Test as SysOp**, then lower only to above the actual guest level
  (normally 1). Minimum play level is registration, not a profile key.
  Third-party guests share an ID: no persistent guest pool or handle
  heuristic. Cover the supervised and external paths, upgrade (stop,
  pip install, `blacksite admin migrate --dry-run`, start); backups.
- Release checklist `docs/ops/release.md`: version bump, changelog
  entry (`CHANGELOG.md`, new), protocol major unchanged or bumped with
  a note, `pytest`, content validator, `perf_hour_run` smoke (10
  minutes), build sdist and wheel, install into a clean venv and run the
  acceptance script of this slice, tag `vX.Y.Z`, GitHub release with the
  wheel attached, README status line updated.
- README: replace the "Design complete" status with install pointers
  and a player section (what to expect, minimum terminal).
- The first release: `v0.1.0` after M4 is merged, or whatever the
  roadmap says at the time; this slice performs the first one.
- Platform API handling: accept integer API 5 for the certified release;
  missing means legacy 2 for a useful upgrade refusal. Reject unsupported
  older/newer, malformed and boolean values before world entry. This is
  independent of Blacksite's protocol major; additive optional fields
  within a supported API remain optional. Do not probe unknown versions.
- Preserve S30's optional deadline, no implicit 3600-second cutoff,
  ASCII-preference refusal, CP437-compatible graphics and resize support.
- Verify host presence already names Blacksite. Optional outbound is
  disabled with the positive registered-only play gate: test that result,
  not a fabricated successful announcement. Do not lower the gate to
  zero. The future opt-in adapter is conditional on a guest-safe,
  audience-compatible host contract; see the platform catch-up plan.

## Out of scope

- The SysOp guide's operational chapters (S28). The rc.d/systemd units
  (S05). Any NetBBS-side change (upstream).
- Publishing to PyPI (a GitHub release with the wheel is the
  distribution channel).

## Data and content

- `CHANGELOG.md`, `deploy/README.md`, one supervised preset JSON, version
  constant, `docs/ops/install.md`, `docs/ops/release.md`.

## Protocol and view models

- None new. The client asserts the protocol major at `hello` (already
  in S03/S04); this slice adds the package version to `welcome` for the
  settings/help "About" line.

## Tests

- `test_wheel_contains_content_and_deploy_trees` (build in tmp,
  inspect)
- `test_module_entry_points_run_help` (subprocess `-m` for the four
  modules)
- `test_preset_json_validates_against_netbbs_profile_fields` (the field
  set in `netbbs.doors.profiles.DoorProfile` as documented in
  architecture §1; keep a copy of the field list in the test with the
  NetBBS version it was taken from)
- `test_service_schema_argv_health_and_distinct_stop_budgets`
- `test_registered_only_gate_blocks_shared_guest_identity`
- `test_external_alternative_has_no_companion_service`
- `test_content_bootstrap_copies_once_and_resyncs_on_version_change`
- `test_content_local_never_touched_by_resync`
- `test_client_refuses_unsupported_integer_door_api_before_world_entry`
- `test_unlimited_and_shorter_effective_session_deadlines`
- `test_ascii_preference_refusal_and_outbound_disabled_policy`
- `test_version_constant_matches_pyproject`

## Acceptance script

1. On the ReLink test node (NetBSD), as the service account: create the
   venv and install dir per `docs/ops/install.md`, install the wheel,
   run the first `blacksite serve`; secrets and content appear.
2. In NetBBS as SysOp: register "Blacksite", import
   `deploy/netbbs-door-profile.json`, set the interpreter path, **Check
   setup** reports no problems, **Test as SysOp** shows the title screen
   at your terminal size; leave; lower only to the registered-only gate.
   A guest cannot reach character selection or another guest's records.
3. Two callers over SSH and one over the web transport enter the door
   at once; all three see each other in `core-plaza`; `max_sessions`
   permits it.
4. Supervised: stop/unhealth the service; NetBBS refuses new admission
   before launching the game client. Verify backoff, breaker and SysOp
   recovery. External: remove the service block, use the external unit,
   stop it; the client shows city-unavailable and returns within its
   bounded policy. Verify passive socket health creates no player.
   Test node shutdown with connected callers and distinct stop budgets.
5. Upgrade path: install a rebuilt wheel with a bumped version, restart;
   `DIR/content/` is re-synced and a file placed in `content.local/`
   survives.
6. Tag and publish the release; download the wheel from the GitHub
   release into a clean venv on the Windows dev box; `python -m
   blacksite.door` prints the minimum-terminal message when run without
   `NETBBS_DOOR_INFO`.
7. At 80x24 and 132x50 with a wide name, test real UTF-8 and CP437
   callers, 16 colours and SIGUSR1 resize. ASCII preference gets an
   explanatory return, not damaged output or an unrequested new tier.
8. With profile time/CPU limits zero, no synthetic one-hour deadline
   appears. A shorter positive host/game limit still wins. Record S29's
   actual CPU evidence and inherited host limits, not invented headroom.
9. Outbound: under both rehearsal level 255 and the normal positive
   gate, no announcement escapes. Disabling publication does not affect
   relay/season rewards or in-game standings. A successful public hook
   is not a release gate while the documented guest/audience conflict
   persists; any later adapter must meet the catch-up plan's contracts.

## Definition of done

- Tests green; the release exists on GitHub with the wheel attached;
  the ReLink node runs it; README updated.
- Slice file marked done with PR number.

## Implementer notes

- NetBBS launches doors with a minimal environment (never the full
  parent environment): everything the client needs must come from the
  profile's `environment` map or `door_info.json`.
  S22 [PR #61](https://github.com/Thiesi/Blacksite/pull/61)'s native harness
  checks the profile interpreter with `-I`, including
  version and Python source digest, and saves `native-client.json`.
  Preserve that check: a development PYTHONPATH does not install or update
  the separately launched client. The one game venv must contain the
  released wheel for both service and caller entry points.
- The supported minimum is NetBBS >= 7.31.0, verified against v7.33.0.
  Limits accept zero or 1-86400; zero cannot bypass a host hard limit.
  CPU exhaustion is not graceful logout and supplies no warning signal.
- NetBBS is built and run on NetBSD; test the wheel there, not only on
  Linux or Windows. A NetBSD `pkgsrc` Python 3.12 is the reference.
- Do not put the interpreter path in the preset as anything but a
  placeholder: the SysOp edits it on the Compatibility screen.
- NetBBS installation-directory backups are opt-in, unquiesced copies
  with manual restoration. S28's SQLite snapshot remains the recovery
  source; do not describe a successful raw node copy as a consistent
  live-game backup. No BBS database or Link-secret access is introduced.

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

Retain current installed-client version/source-tree proof, full pytest and
actual native acceptance at both sizes. Verify
contracts_state/vendor_budget_state restore and allocation expiry through
the packaged service. The S19 source checkpoint is not merged or native-
accepted yet; keep the existing NetBBS #56 baseline/preset obligations.
<!-- s19-services:end -->

<!-- s24-handoff:start -->
### S24 event integration and acceptance handoff

Reference: [S24 #24](https://github.com/Thiesi/Blacksite/issues/24),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

Consume committed event facts only through the optional host
publication policy from #56. There is no NetBBS callback in the event
simulation, and essential warnings never depend on BBS chat delivery.
Retain full-suite and installed-wheel native evidence separately from
fixture geography, production transport and human pacing. Release
acceptance must repeat full-city Curfew/Surge/Ring-fall/Exhale/Convoy
composition after S25/S26 activate their actual content. Preserve paid
source receipts, forecast corrections and the one-hour completed-job
return window across upgrade/restart. Record the supported NetBBS floor.
<!-- s24-handoff:end -->


<!-- s24-review-policy:start -->
### S24 practical review follow-up

Reference: [PR #65](https://github.com/Thiesi/Blacksite/pull/65), retaining
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and #56.

Repeat matching-wheel native acceptance at both sizes after event path or
retention changes. Event hot history is bounded to 128 closed plans;
retain required durable host-publication receipts independently under the
#56 policy. Essential warnings and held outcomes stay in game.
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

Repeat physical credential acceptance on the actual city at both terminal
sizes: standing/pass alternatives, friendly nonmember refusal, member
access, default-closed cage, committed S26 opening and expiry/restart of an
in-flight journey. Preserve actual purchases and fixture disclosure; no
invented physical story key or BBS-context permission is authority.
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

Release only after actual-city native acceptance and the required
human review. Include all 34 maps, 22 ordinary vendors, 16 relays and
24 apartments in installed-wheel/artifact verification. Preserve public
services and outward routes under overlapping controls and events.

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

Full-city pacing changes Gate Nine's ordinary opening to 60 seconds
per 120-second UTC cycle (game 7.7). The former 300-second cycle allowed
a 240-second idle wait; an actual native free-gate journey took 265
seconds including its approach. The fixture-free first rifle/ammunition
upgrade also left zero chits. Ordinary free waiting is now at most 60
seconds; the 25-chit fast option, owner benefits and free inward route
remain. Keep this schedule in seasonal controls, dialogue/help, operator
views, load and federation checks. This is a product pacing correction,
not a shortened capture clock or an accelerated acceptance fixture.
Reference: [PR #66](https://github.com/Thiesi/Blacksite/pull/66), retaining
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).
<!-- s25-city-decisions:end -->
