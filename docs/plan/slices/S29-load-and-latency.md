# S29 — Load and latency: bot client, 16-bot hour, profiling, delta compaction if needed

**Status:** planned
**Primary model:** Opus · **Reviewer:** Astra (independent read of the profiling conclusions)
**Depends on:** S15, S22 · **Milestone:** M6
**Issue:** (filled in when filed)

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
  times per second), §10 ("Load" bullet), §1 (platform `RLIMIT_CPU`
  300 s).
- `docs/design/00-game-design.md` §14 (20 inputs per second per
  session).
- `docs/design/03-terminal-ui.md` §6 (rendering rules, diffing).
- `docs/upstream/02-session-limits.md` (why the client CPU budget is
  40 % of the platform cap).

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

- The platform's `RLIMIT_CPU` is 300 s per door process and unchanged
  until upstream 02 lands: a client that busy-loops on `select` will be
  killed mid-session. Block on the socket and stdin; render only on
  arrival.
- NetBSD's Python may lack `os.sched_getaffinity` and some
  `resource` fields; keep instrumentation to `time.perf_counter_ns` and
  `resource.getrusage`.
- Sixteen bots on a Unix socket are trivial for the OS; the cost is the
  simulation and JSON. Profile with `cProfile` under a 5-minute run
  before an hour run.
- Do not optimise the fixture world; profile the shipped content, which
  has 200 × 100 zones.
