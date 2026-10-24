# S29 — Load and latency: bot client, 16-bot hour, profiling, delta compaction if needed

**Status:** planned
**Primary model:** Opus · **Reviewer:** Astra (independent read of the profiling conclusions)
**Depends on:** S15, S22, S24, S26 · **Milestone:** M6
**Issue:** https://github.com/Thiesi/blacksite/issues/29

S22 [PR #61](https://github.com/Thiesi/Blacksite/pull/61) installs actual
crew membership and remote HP/integrity/zone/beacon
views. Include split-layer crews in the sixteen-caller profile and
measure crew view composition before proposing optimizations. Preserve
the source-verified installed-client receipt in native evidence. UI 5.3's
200ms lone-Escape framing grace handles observed fragmented native input;
it does not relax the server tick/latency or CPU targets below.

## Goal

Prove the architecture's performance budget with real numbers: sixteen
scripted bots playing for an hour must keep the server's tick under
40 ms p99 and each client under the platform's CPU ceiling, and the
view-delta traffic under its budget on a Telnet-class link. Where the
budget is missed, fix the hot path or switch `ZoneView` deltas to the
compact encoding the protocol reserves. The bot is also the regression
tool every later slice runs.

## Spec references

- `docs/design/02-architecture.md` §11 (budgets: tick ≤ 40 ms p99 with
  16 players and 6 active zones; delta ≤ 2 KiB typical, ≤ 16 KiB worst;
  client render ≤ 5 ms at 80×24; client CPU ≤ 120 s per hour; server RSS
  ≤ 200 MiB; start ≤ 3 s), §5.1 (`enc: "compact"` reservation), §5.3
  (one view or delta per session per tick; coalescing when > 3
  revisions behind), §6.1 (dormant zones), §7 (client renders at most 10
  times per second), §10 (Load), §1/§8.1 (configurable cumulative CPU
  ceiling and the explicit long-session policy).
- `docs/design/00-game-design.md` §14 (20 inputs per second per
  session).
- `docs/design/03-terminal-ui.md` §6 (rendering rules, diffing).
- `docs/upstream/02-session-limits.md` (released outcome) and
  `docs/plan/01-netbbs-platform.md` (issue #56 CPU/session policy).

## Scope

- `src/blacksite/bot/`: `blacksite.bot` entry point that speaks the
  client protocol without a terminal: `--count 16 --minutes 60
  --script mixed`, scripts `walker` (random movement in a zone),
  `fighter` (targets and fires at NPCs and other bots in a contested
  zone), `runner` (jacks in, walks cells, fights ICE), `talker` (chat
  every 5 s), `mixed` (round-robin). Bots respect the input rate limit
  and `ack` every view.
- A `blacksite.bot --render` mode that runs the real renderer over a
  fake terminal at 80×24 for one bot, to measure client CPU without a
  NetBBS session.
- Server instrumentation: per-tick timing histogram (p50/p95/p99),
  per-subsystem timing (inputs, zones, sectors, NPCs, publish,
  persistence), delta sizes per session, RSS sample; exposed by
  `status --json` and written to `logs/perf.log` once a minute when
  `--perf` is set.
- The hour run: 16 bots, 6 zones active by script (`core-plaza`,
  `sink-rim`, `tramyard-depots`, `scour-ring-1`, `under-service`, plus
  one sector), on the user's NetBSD node and on a Windows dev box;
  results recorded in `docs/ops/perf-baseline.md` with the machine
  description.
- Fixes as needed, in order of preference: algorithmic (visibility
  caching per zone, dirty-rectangle publish, NPC behaviour throttling in
  zones with no players), then structural (compact delta encoding as
  `enc: "compact"`, arrays instead of objects for tiles and actors),
  then policy (lower publish rate for far-away actors). Each fix has a
  before/after number in the PR.
- Client-side: measure `render()` at 80×24 and 132×50 on the fake
  terminal; if over 5 ms, optimise diffing (row hashing, colour-run
  coalescing) before touching the view model.
- Persistence lag under load (flush time with 16 dirty players every
  5 s) measured and kept under one tick.

## Out of scope

- Network-level tuning of NetBBS's transports (platform).
- New game features. Any change to view-model semantics; encoding only.
- Multi-node load (S32 territory).

## Data and content

- `docs/ops/perf-baseline.md` (new): the table of measured numbers per
  budget line, machine, date, package version, and the command lines.
- No content changes.

## Protocol and view models

- If compaction is needed: `delta {rev, base, enc: "compact", ops}`
  where tiles are run-length rows and actors are positional arrays with
  a documented column order; the client accepts both encodings; golden
  frames added for the compact form; protocol major unchanged (additive).

## Tests

- `test_bot_scripts_obey_input_rate_limit`
- `test_bot_acks_every_view_and_survives_reconnect`
- `test_tick_histogram_reports_p50_p95_p99`
- `test_delta_size_typical_under_2k_for_walker_in_core_plaza`
- `test_delta_size_worst_case_under_16k_with_16_actors_in_view`
- `test_coalescing_sends_full_view_when_3_revisions_behind`
- `test_dormant_zone_costs_zero_ticks`
- `test_compact_encoding_roundtrip_equals_json_encoding` (if built)
- `test_client_render_under_5ms_at_80x24` (marked slow; fake terminal;
  asserts against a generous CI multiplier)
- `test_persistence_flush_16_dirty_players_under_one_tick`
- `perf_hour_run` (not a unit test: a script under `scripts/` with a
  documented invocation; its output is the baseline document)

## Acceptance script

1. On the NetBSD node with the service running, start `blacksite bot
   --count 16 --minutes 60 --script mixed --perf`.
2. Meanwhile log in as a real caller over SSH at 80×24 into
   `sink-rim`, where fighters are active: movement feels immediate
   (under ~250 ms perceived), the log keeps up, no tearing on redraw.
3. After the hour, `blacksite admin status --json` shows tick p99 ≤ 40
   ms, RSS ≤ 200 MiB; `logs/perf.log` shows delta sizes within budget;
   the `--render` bot reports client CPU ≤ 120 s.
4. Repeat for ten minutes on the Windows dev box with the TCP fallback
   to confirm nothing is platform-specific.
5. The numbers are in `docs/ops/perf-baseline.md` and match the PR.

## Definition of done

- Baseline document committed with numbers inside every budget line, or
  a design-doc change to a budget with the reason.
- Tests green; bot documented in the admin reference (S28's file gains
  a "Load testing" section).
- Astra review of the profiling conclusions attached to the PR.
- Slice file marked done with PR number.

## Implementer notes

- NetBBS `cpu_seconds` accepts 0-86400, defaults to 300 and is cumulative
  per client, not per hour. Finite exhaustion may SIGKILL with no warning
  or save callback. Primary unlimited sessions explicitly use zero;
  host hard limits still apply. Keep the 120 CPU-seconds/hour efficiency
  target. Measure the real renderer at both sizes on NetBSD, record
  effective host/profile limits and size any finite operator policy from
  whole-session CPU plus headroom. A headless socket bot alone does not
  establish the real client's budget. Block on input; do not hide a busy
  loop by raising limits. S31 consumes the measured deployment guidance.
- NetBSD's Python may lack `os.sched_getaffinity` and some
  `resource` fields; keep instrumentation to `time.perf_counter_ns` and
  `resource.getrusage`.
- Sixteen bots on a Unix socket are trivial for the OS; the cost is the
  simulation and JSON. Profile with `cProfile` under a 5-minute run
  before an hour run.
- Do not optimise the fixture world; profile the shipped content, which
  has 200 × 100 zones.

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

Profile populated contract/journal/budget meta and active mission bodies.
Source callbacks must finalize before after_settle flushes deferred impacts;
a two-NPC regression proves that reversing this loses objective progress.
Preserve owning receipts while optimizing. Timer/view invalidation must
still work for a stationary caller.
<!-- s19-services:end -->

### S23 market handoff

Retain [PR #38](https://github.com/Thiesi/Blacksite/pull/38)'s realistic
product-impact standard. Profile market/menu tick and source costs with
thousands of retained listings and bids as well as a fresh world. S23
bounds menu frames to 12 rows and operator list pages to 100 records;
the full financial history remains stored. Include escrow expiry and
bounty death payouts under load, without weakening atomic settlement,
exact item identity or acknowledgement ordering.

PR #64 review adds a mandatory populated-world gate: use at least 10,000
closed listings and 40,000 historical bids, plus live auctions and bounty
posts queued behind death settlement. Measure public and own-history
menus, source fork/diff/commit costs, expiry and normal combat under the
same tick/input budgets as fresh worlds. S23 maintains a held-bid lookup,
formats only the visible page and copies live financial records while
sharing immutable closed history. Linear selection/delta scans and
active-state copy costs remain. Measure and optimize or bound remaining
costs before S29 is done. S31 cannot release without this gate.
Populate a large item table with carried, stored, impounded and cached
items, plus realistic interlock/service state. Empty inventories do not
exercise the remaining item and state copy costs.

<!-- s24-handoff:start -->
### S24 event integration and acceptance handoff

Reference: [S24 #24](https://github.com/Thiesi/Blacksite/issues/24),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

Include two active/planned events, public Convoy attendance/death/jobs,
salvage/key receipts, composed service/relay/season layers, and long
scheduler history in the workload. The derived live-plan index remains
bounded by two; durable records are authoritative. Exercise failed
storage acknowledgement without duplicate effects or payouts.
Retain the actual native 80x24/132x50 wide-name gates separately from
headless load and focused tests. No accelerated fixture closes human
travel or earning acceptance.
<!-- s24-handoff:end -->


<!-- s24-review-policy:start -->
### S24 practical review follow-up

Reference: [PR #65](https://github.com/Thiesi/Blacksite/pull/65), retaining
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and #56.

The hot event receipt is now bounded at 128 closed plans plus live/current
transitions; personal reads are bounded at 128. Exercise 1,000-event/read
histories and held outcomes after retirement/restart. Include long obstacle
routes, cached replanning and a blocked Beacon that expires at 60 seconds;
normal traffic must not force a full BFS every tick.
Include repeated event spawn/end/death cycles and historical expedition
instances. Ended-event slots must retire without erasing static/active
slots or pending death receipts; measure remaining slot scan/copy costs.
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

Exercise the complete 34-map city, member/standing/pass alternatives and
source-owned story routes under reconnect and concurrent expiry. Include
route-permission provider cost in the populated season workload; permission
checks remain on the ordinary travel path and preserve Curfew/control
restrictions.
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

Profile the actual 34-map population, three additional ordinary
counters and 24 private rooms. Exercise hardware cuts and overlapping
layouts while public services and escape routes remain usable. The new
NPC grades are initial hypotheses, not a substitute for real pacing.

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
<!-- s25-city-decisions:end -->
