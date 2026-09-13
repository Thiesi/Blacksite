# S03 — Server core: socket, framing, hello/auth, sessions, tick loop, event bus, persistence layer

**Status:** planned
**Primary model:** Opus · **Reviewer:** Astra (protocol and auth critique before start)
**Depends on:** S01, S02 · **Milestone:** M0
**Issue:** https://github.com/Thiesi/blacksite/issues/3

## Goal

Build the game service's skeleton: a process that owns the install
directory, listens on the local socket, authenticates door clients,
keeps sessions, runs a 10 Hz tick loop with an event bus, and persists
through a single-writer SQLite layer with migrations. After this slice
a client can connect, be welcomed, echo intents into the log, and be
told goodbye on shutdown; no game rules exist yet.

## Spec references

- `docs/design/02-architecture.md` §2.1, §2.3, §2.4 (server, admin
  endpoint, install dir), §3.3–§3.4 (start/stop), §4 (auth), §5
  (protocol), §6.1–§6.2 (tick, persistence), §9 (origin/authority),
  §11 (budget), §12 (logs), §13 (security).
- `docs/design/01-entities.md` §2.11 (world meta), §3.6 (session).
- `docs/design/00-game-design.md` §14 (rate limits).

## Scope

- `src/blacksite/server/app.py`: `Server` with `start()`, `stop()`,
  the start sequence of §3.3 (lease on `world.db.sessions` using the
  War Dialer sidecar pattern; content load via S02; migrations; live
  state rebuild hook; secrets; bind; pid; tasks; "world open" log with
  content hash and season), and the stop sequence of §3.4 (10 s hard
  limit).
- `src/blacksite/server/transport.py`: Unix socket listener at
  `DIR/run/blacksite.sock` (mode 0600, stale socket file removed after
  a failed connect probe); `127.0.0.1` TCP fallback with `DIR/run/port`
  when `os.name == "nt"` or `--tcp` is passed.
- `src/blacksite/server/protocol.py`: framing (4-byte big-endian length,
  JSON, 256 KiB max), `Frame` dataclass, encoder/decoder, all
  client→server and server→client types from §5.2–§5.3 as typed
  records with validation (`type`, required fields, ranges), and
  `PROTOCOL_MAJOR` assertion on `hello`.
- `src/blacksite/server/auth.py`: `door.secret` and `admin.secret`
  creation (32 random bytes, hex, mode 0600), HMAC-SHA256 of the
  door_info bytes, constant-time compare, role assignment (`caller`,
  `operator`, reserved `peer`), ban check hook.
- `src/blacksite/server/sessions.py`: `Session` per §3.6 of the entity
  model: id, role, player id (None until S07), caps, input queue
  (bounded 64), rate counters (20 inputs/s, 4 chat/5 s, 1 market/s),
  view revision and `ack` tracking, coalescing rule (>3 revisions behind
  → next send is a full `view`), send queue with backpressure (drop
  `delta`s, never `bye`), reconnect grace: a new `hello` for the same
  `bbs_user_id` within 60 s replaces the old session and inherits its
  player.
- `src/blacksite/server/clock.py`: `Clock` protocol (`now_tick`,
  `now_utc`) with a real and a manual implementation; the simulation
  never reads wall time otherwise.
- `src/blacksite/server/loop.py`: 10 Hz tick loop driven by the clock;
  each tick drains inputs, calls registered subsystem `tick(ctx)`
  hooks in order, then publishes views; measures p50/p99 tick time.
- `src/blacksite/server/bus.py`: in-process event bus (`publish(event)`,
  `subscribe(kind, handler)`), synchronous within a tick, used for
  logs, persistence dirty marks, and later subsystems.
- `src/blacksite/server/storage/db.py`: SQLite open in WAL, single
  writer task, `mark_dirty(kind, id)`, flush cadence (players 5 s, world
  30 s, immediate list from §6.2 via `flush_now()`), one transaction
  per flush, `meta` table (schema version, origin id, created_at,
  season pointer, event cooldowns, rng seeds).
- `src/blacksite/server/storage/migrations/__init__.py` with
  `0001_initial.py` creating `meta`, `players` (columns per entity
  §2.1, JSON blobs for nested fields), `items`, `audit`, `bans`,
  `mutes`, `reports`; refuse to open a newer schema.
- `src/blacksite/server/admin_endpoint.py`: operator-role frames
  `admin.status`, `admin.who`, `admin.stop` (the rest arrive in S05/S28).
- `src/blacksite/server/logging.py`: JSON-per-line rotating `server.log`
  and append-only `audit.log`.
- `src/blacksite/server/__main__.py`: `--install-dir`, `--tcp`,
  `--log-level`; installs `SIGTERM`/`SIGINT` handlers.
- Headless test harness `tests/harness.py`: `HeadlessServer` with a
  manual clock, `connect(door_info) -> FakeClient`, `step(n_ticks)`,
  `frames_for(client)`; no sockets.
- Bot stub: `src/blacksite/bot/__main__.py` connects, says hello, sends
  `ping`, prints `pong` latency (grown in S29).

## Out of scope

- Any game rule, zone, or player state (S06, S07).
- Interim service runner and rc.d/systemd (S05).
- Full admin command set, backup/restore (S28).
- Delta generation for view models (S06 introduces the first view).

## Data and content

- `DIR/` layout per §2.4 created on first start; `content/` copied out
  of the package when missing or when `PACKAGE_VERSION` differs from
  `meta.content_package_version`; `content.local/` untouched.

## Protocol and view models

- Implements every frame type in §5.2 and §5.3 at the framing and
  validation level. `welcome` carries `proto`, `server_version`,
  `player: null`, `keymap`, `palette`, `motd` (from `text/motd.txt`, one
  random line). `view`/`delta` are emitted only by later slices.
- Golden frames in `tests/fixtures/frames/*.json` for `hello`,
  `welcome`, `bye`, `ping`/`pong`, an invalid major, an oversize frame.

## Tests

- `tests/server/test_framing.py::test_encode_decode_round_trip`,
  `::test_oversize_frame_rejected`, `::test_partial_frames_reassembled`.
- `tests/server/test_auth.py::test_hello_hmac_valid`,
  `::test_hello_hmac_invalid_gets_bye`, `::test_wrong_major_rejected`,
  `::test_operator_secret_sets_role`, `::test_secrets_created_0600`.
- `tests/server/test_sessions.py::test_rate_limit_inputs_20_per_s`,
  `::test_rate_limit_chat_4_per_5s`, `::test_reconnect_within_60s_replaces`,
  `::test_coalesce_after_3_revisions`, `::test_bye_never_dropped`.
- `tests/server/test_loop.py::test_ten_ticks_per_second_manual_clock`,
  `::test_subsystem_order`, `::test_tick_timing_recorded`.
- `tests/server/test_storage.py::test_migrate_from_empty`,
  `::test_refuse_newer_schema`, `::test_flush_cadence_players_5s`,
  `::test_flush_now_immediate`, `::test_origin_id_created_once`.
- `tests/server/test_lifecycle.py::test_second_server_refused_by_lease`,
  `::test_stop_sends_bye_and_removes_run_files`,
  `::test_content_copied_on_first_start`, `::test_local_content_untouched`.
- `tests/server/test_harness.py::test_headless_connect_welcome`.

## Acceptance script

1. `python -m blacksite.server --install-dir /tmp/bs` → log "world
   open" with hash; `DIR/run/blacksite.sock` exists.
2. `python -m blacksite.bot --install-dir /tmp/bs` → prints a pong
   latency under 5 ms.
3. Second server on the same dir → refuses with the lease message.
4. `kill -TERM` the server → bot receives `bye maintenance`, `run/` is
   empty, exit 0 within 10 s.
5. On Windows: same with `--tcp`.

## Definition of done

- Roadmap §7 holds.
- `02-architecture.md` §5 updated if a frame field changed.
- The Astra critique, if run, is summarised in the PR.

## Implementer notes

- The server is *not* launched by NetBBS in this slice and never by the
  door client (`AGENTS.md` §8). It is started by hand or by S05's
  runner; later by NetBBS's door service (upstream 01).
- NetBBS door processes are reaped as a process group; the server must
  not be a child of a door process, or it dies with the first caller.
- `RLIMIT_NPROC` is shared by the service UID (16 for door processes);
  the server's own threads count against the UID's limit on some
  platforms. Keep the server single-process, asyncio only, no thread
  pools except SQLite's writer if needed.
- Windows has no Unix sockets in Python's asyncio for all versions in
  use; the TCP fallback is for development only and must bind
  `127.0.0.1`.
- Keep the simulation-facing API free of sockets: subsystems receive a
  `TickContext` (clock, bus, sessions view, content) and return nothing.
