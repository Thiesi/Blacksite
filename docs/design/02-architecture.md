# Blacksite — Technical Architecture

How the game runs as a native NetBBS door: one long-lived, authoritative
game service per node and one thin door client per caller, joined by a
versioned local protocol. This document is the contract every slice in
`docs/plan/slices/` builds against. `docs/upstream/` lists what Blacksite
needs from NetBBS itself; nothing here depends on those requests landing
first, because §8 defines an interim path.

---

## 1. Constraints from the platform

Facts about NetBBS's door subsystem as of NetBBS v6.0.x
(`docs/NetBBS-door-guide.md`, `src/netbbs/doors/runtime.py` in the NetBBS
repository):

- A door is a **subprocess per caller**, launched with an argv list (never
  a shell) under the NetBBS service account, with `RLIMIT_CPU` 300 s,
  `RLIMIT_AS` 256 MiB (profile-configurable), `RLIMIT_NPROC` 16 (shared
  by the UID), a wall-time cap of 3600 s (profile `time_limit`, capped at
  3600), and unconditional reap of the process group on every exit path.
- The caller's terminal is relayed as raw bytes over stdio (or a PTY, or
  an inherited DOOR32 socket). NetBBS does not touch door output. Input
  arrives byte by byte as the caller types.
- `NETBBS_DOOR_INFO` names a JSON file with `handle`, `user_id`,
  `terminal_width`, `terminal_height`, `color_depth` (`truecolor` or
  `256`), and `node_name`. Nothing else about the caller is passed.
- Terminals speak UTF-8. Resize events are not forwarded to running
  doors. Telnet, SSH, and the web (xterm.js) transports all reach the door
  the same way.
- A profile may set `max_sessions` (default 1) and `multinode_certified`.
- Persistent door data lives in the door's **installation directory**,
  operator-owned, outside NetBBS's own state.
- There is no supervised long-lived door process, no inter-session
  channel, and no door-to-BBS callback. §16 of the NetBBS design document
  (issue #200) records that shared state is the door's own responsibility.

Blacksite therefore consists of two programs and a directory.

## 2. Components

```
NetBBS node process
 ├─ caller session A ── stdio ── blacksite.door (client A) ─┐
 ├─ caller session B ── stdio ── blacksite.door (client B) ─┤  local socket
 └─ (upstream: door service supervisor) ───────────────────┼─► blacksite.server
                                                           │     ├─ simulation (10 Hz)
   SysOp shell ── blacksite admin ──────────────────────────┘     ├─ SQLite world.db (WAL)
                                                                  └─ content (read-only)
```

### 2.1 `blacksite.server` (the game service)

- One process per node. `python -m blacksite.server --install-dir DIR`.
- Owns the world: content loaded at start, live simulation in memory,
  persistent state in `DIR/world.db`.
- Listens on `DIR/run/blacksite.sock` (Unix domain socket; `127.0.0.1`
  TCP with a port file `DIR/run/port` on Windows development hosts only).
- Runs the tick loop, the event engine, persistence, and the admin
  endpoint.
- Restartable at any time: persistence is designed so a crash loses at
  most the last write-behind interval (§6).

### 2.2 `blacksite.door` (the caller client)

- One process per caller, launched by NetBBS as a native stdio door:
  executable = the interpreter of the venv Blacksite is installed in,
  argv = `-m blacksite.door`, environment `BLACKSITE_INSTALL_DIR`.
- Reads `NETBBS_DOOR_INFO`, connects to the socket, authenticates (§4),
  then runs two loops: terminal input → protocol commands, protocol
  view models → terminal output.
- Owns everything about the terminal: capability tier, layout, rendering,
  diffing, key decoding, prompts, local menus' cursor state.
- Holds no game state beyond the last view model. If the server
  restarts, the client reconnects with backoff for up to 60 s and
  resumes; if it cannot, it says so and exits 0.

### 2.3 `blacksite admin` (operator CLI)

- `python -m blacksite.admin --install-dir DIR <command>` talks to the
  same socket with an operator credential (§4) and runs commands: status,
  who, kick, mute, ban, unban, teleport, refund, give, reports, characters
  allow (raise a user's character cap), event force, event cancel, season
  status, season advance, reload zones, backup, restore check, verify
  (content and database invariants), secrets rotate, chronicle append,
  export leaderboard, export chronicle, stop. Every command is written to
  `logs/audit.log` with operator, command, target, and outcome.
- Never touches `world.db` directly while the server runs; a `--offline`
  mode exists for backup/restore and migrations when the server is down.

### 2.4 The installation directory

```
DIR/
  content/        the shipped content tree (zones, sectors, cores, tables, text, art)
  content.local/  operator overrides (same layout; wins on ID collision; may be empty)
  world.db        SQLite, WAL mode
  world.db.sessions   advisory-lock sidecar (same pattern War Dialer uses)
  run/            socket, pid, port file (created at start, removed at stop)
  secrets/        door.secret, admin.secret (0600, created on first start)
  logs/           server.log (rotating), audit.log
  backups/        created by `blacksite admin backup`
```

The content tree is copied out of the installed package on first start
(so an operator can read and override it) and re-synced when the package
version changes; `content.local/` is never touched. This bootstrap is
S05's job (the interim service runner), so it exists before the first
zone loads.

## 3. Process lifecycle

### 3.1 Target: NetBBS door service supervision

`docs/upstream/01-door-services.md` asks NetBBS for a **door service**:
a companion process declared in the door's profile that NetBBS starts
with the node, restarts on failure with backoff, stops at shutdown, and
shows on a SysOp screen. Blacksite's profile would declare
`service: {"argv": ["-m", "blacksite.server", "--install-dir", "{install_dir}"]}`.

### 3.2 Interim: self-hosted service

Until that lands, `blacksite serve` is a foreground command and the repo
ships example `rc.d` (NetBSD) and `systemd` units in `deploy/`. The door
client, when it cannot connect, tells the caller "The city is dark right
now" and asks the SysOp (in the log) to start the service. The client
**never** spawns the server: doing so from inside NetBBS's reaped process
group is exactly the failure mode the upstream request exists to avoid.

### 3.3 Server start sequence

1. Acquire the exclusive lease on `world.db.sessions`; refuse to start if
   another server holds it.
2. Load and validate content (`content/` then `content.local/`); fail
   loudly on any invariant in `01-entities.md` §5.
3. Open `world.db`, run migrations (schema version in `meta`).
4. Rebuild live state: zone instances, relay ownership, core states,
   season pointer, event cooldowns.
5. Create secrets if missing, bind the socket, write pid, start the tick
   loop, the persistence task, and the event engine.
6. Log "world open" with content hash and season.

### 3.4 Server stop

`SIGTERM` or `blacksite admin stop`: stop accepting, tell clients
`bye {reason: "maintenance"}`, apply the sleeper rule to everyone as if
they had logged out, flush persistence, remove `run/` files, exit 0.
Hard limit 10 s, then exit anyway; persistence is crash-safe.

## 4. Authentication and trust

- Everything runs as the same OS user. The socket is `0600`. Trust is
  the filesystem, exactly as NetBBS's door guide states for native doors.
- The door client presents `hello {proto, door_info, hmac}` where the
  HMAC is over the door_info bytes with `secrets/door.secret`. This does
  not defend against a hostile process running as the service account (nothing
  can); it defends against a stray process on a multi-user development
  box and against a misconfigured install pointing at the wrong
  directory.
- Identity is `bbs_user_id` from door_info; the handle is display. A
  player record is keyed on `(origin, bbs_user_id)`.
- The admin CLI presents `secrets/admin.secret` the same way and is
  marked `operator` on its session.
- Rate limits from `00-game-design.md` §14 are enforced per session on
  the server.

## 5. Protocol

### 5.1 Framing

Length-prefixed JSON: 4-byte big-endian length, then a UTF-8 JSON object.
Maximum frame 256 KiB. One object per frame. `proto` is an integer; the
server rejects a `hello` with a major it does not speak. Additive fields
are always allowed; removal or meaning change bumps the major.

JSON over msgpack because the frames are small, the link is local, and
readability in tests and logs wins. If profiling in the load-test slice
shows serialisation matters, `ZoneView` deltas may switch to a compact
array form under the same frame type with `enc: "compact"`.

### 5.2 Client → server

| type | fields | notes |
|---|---|---|
| hello | proto, door_info, hmac, client_version, caps {width, height, tier, unicode} | first frame |
| resize | width, height | if the platform ever forwards it |
| key | k (normalised key name), t (client ms) | movement, actions; the server maps keys to intents using the session's keymap so a rebind is a server-owned setting |
| intent | name, args, request_id, expected_revision (for stateful selections) | explicit intents: move, sprint, target, fire, interact, use item, jack, program, chat, emote, menu open/close/select, contract accept, market action, crew action, settings |
| line | prompt id, text | answer to a line prompt |
| ack | rev | last view revision rendered (flow control) |
| ping | t | |
| bye | reason | |

`key` exists so the client can stay dumb and fast for movement and fire;
`intent` exists for everything with arguments. Both are accepted for the
same actions. Menu navigation is three intents: `menu_cursor` (delta or
absolute row), `menu_select` (row id plus action key), `menu_close`.

Frame types prefixed `admin.` are reserved for operator sessions
(`admin.status`, `admin.who`, `admin.stop` from S03/S05; later slices
add more) and `peer.*` for a future federation bridge; a caller session
that sends either is disconnected.

### 5.3 Server → client

| type | fields | notes |
|---|---|---|
| welcome | proto, server_version, player (summary), keymap, palette, motd | |
| view | rev, kind (zone, lattice, menu, wake, dead, text), body | full snapshot |
| delta | rev, base, ops[] | JSON-patch-like ops on the last view; the client falls back to requesting a full view if base does not match |
| log | lines[] {channel, text, role, at} | |
| prompt | id, kind (key, line), label, max_len | |
| toast | text, role, seconds | transient banner |
| bye | reason, text | |
| pong | t | |

The server sends at most one `view` or `delta` per session per tick, and
only when something the session can see changed. It coalesces if the
client is more than 3 revisions behind (`ack`), sending a fresh `view`
instead of stacking deltas. This keeps a slow Telnet link from filling
its pipe.

### 5.4 View models

`ZoneView.body`:

```
viewport: {x, y, w, h}            zone-tile rectangle the client should draw
tiles: [[tile id, ...], ...]      only cells visible now; -1 for unseen, -2 for remembered
actors: [{id, x, y, glyph, role, name?, stance, hp?}]
objects: [{id, x, y, kind, state, glyph}]
me: {name, handle, faction, grade, hp, hp_max, sta, sta_max, shock, chits, marked_until, heat_until, zone, safety, cooldowns{}, effects[]}
target: {id, name, faction, hp_pct, range, cover, relation} | null
nearby: [{id, name, role, relation}]
crew: [{id, name, zone, hp_pct, jacked}]
event: {name, remaining} | null
hint: text                         one-line contextual key help
```

`LatticeView.body`: `cells` (positions and edges in view), `presences`,
`me` (integrity, trace, rig slots with cooldowns), `room` (data, controls,
ice with integrity), `hint`.

`MenuView.body`: `title, kind, columns[], rows[] (cells + id), cursor,
actions[] (key, label), page, pages, detail (text for the selected
row)`. Cursor movement is an `intent` so the server can keep the menu's
state authoritative and the client stateless; the client renders the
cursor at the row the server says.

`TextView.body`: `title, lines[], page, pages` for found texts, the
Chronicle, help.

## 6. Simulation and persistence

### 6.1 Tick loop

- 10 Hz. Each tick: drain session inputs (bounded), advance every
  **active** zone instance and sector (one with at least one presence or
  a pending timer), run NPC behaviours in active zones, resolve combat
  and program actions whose cast timers expired, apply hazards, advance
  event timers, then publish views.
- Zones with no players and no pending timers are **dormant** and cost
  nothing. Spawner and relay timers wake them lazily (compute elapsed
  time on wake, like War Dialer's lazy clocks) so the world moves while
  nobody is watching without simulating everything constantly.
- Determinism: each zone instance has its own seeded RNG; tests can run
  a zone forward with scripted inputs and assert outcomes.

### 6.2 Persistence

- SQLite in WAL mode with a single writer task. Live entities are marked
  dirty; the writer flushes dirty players every 5 s, world state every
  30 s, and immediately on: death, trade, market action, item transfer,
  relay change, contract state change, season change, logout, evidence
  publication, work-order allocation, contribution, ballot, settlement
  and event-plan commitment.
- Every flush is one transaction. A crash loses at most 5 s of position
  and health. Rewarded actions and their receipts are committed before
  success is acknowledged or broadcast; ordinary dirty-state flushes
  cannot make that guarantee on their own.
- Backups: `blacksite admin backup` uses SQLite's online backup API into
  `backups/<timestamp>/world.db` plus a manifest with content hash and
  schema version, the pattern War Dialer established.
- Migrations: numbered Python modules under `blacksite/storage/migrations`,
  applied in a transaction at start; refuse to open a newer schema.

### 6.3 Content loading

- Content is data files (`01-entities.md` §1). A validator runs every
  invariant at load and as a test over the shipped tree.
- `content.local/` overrides by ID. `blacksite admin reload zones`
  hot-swaps zones with no players in them; everything else requires a
  restart.

## 7. Client rendering and input

Detailed in `03-terminal-ui.md`. Architectural points:

- The client keeps a **cell buffer** (glyph, fg, bg, attrs per terminal
  cell), renders each view model into it, and emits only the cells that
  changed since the last frame, with cursor-movement minimisation. Full
  redraw on `view`, on tier change, and on a client-side `Ctrl-L`.
- Display width of every glyph is measured with the same East Asian
  width rules NetBBS uses; the client never assumes one column per code
  point. Names from the BBS may contain anything.
- Key decoding handles CSI/SS3 arrows, function keys, `Esc` timeouts,
  bracketed paste (discarded), and mouse reports (discarded, and mouse
  reporting is never enabled).
- The client sends `key` for movement and fire immediately on decode;
  everything else goes through intents. Local typing for a line prompt
  is echoed locally and sent on Enter.
- The client is a pure function of (view models, log, prompts, caps). It
  is testable headless with a fake terminal that records the cell buffer.

## 8. NetBBS integration

### 8.1 Registration

Native stdio door, `max_sessions` raised to the node's player cap (16
by default), `multinode_certified` true, `time_limit` at the platform
maximum, `memory_mb` 128 (the client is small), environment
`BLACKSITE_INSTALL_DIR=<DIR>`. A preset JSON is shipped in `deploy/` for
the SysOp to import on the door's Compatibility screen. Installation
lives in the SysOp guide.

### 8.2 Wall-time cap

The client watches its own runtime against the profile's limit (passed
as `BLACKSITE_SESSION_LIMIT` in the profile environment, defaulting to
3600) and toasts at five minutes and one minute. Re-entering the door
resumes the session; the server treats a reconnect within 60 s as the
same session (no sleeper penalty).

### 8.3 Presence

NetBBS shows callers "in a door"; the game's own `sitrep` shows who is
in the world. `docs/upstream/04-door-presence-and-outbound.md` asks for
the door's name to be shown in NetBBS's who-is-online and for a narrow
outbound hook (posting a season result to a board). Neither is required
for v1.

## 9. Federation readiness (designed, not built)

Decisions that cost nothing now and prevent a rewrite later:

- **Origin.** The server's world has a stable `origin` id created at
  first start (random 128-bit, stored in `meta`). All instance IDs carry
  it. Player identity is `(origin, bbs_user_id)`.
- **Authority.** Every zone, sector, core, relay, and faction state row
  has an `authority` field, currently always the local origin. A future
  bridge assigns remote authorities to remote regions and proxies views.
- **Protocol reservation.** Frame types `peer.*` are reserved. The
  server's session model already distinguishes `caller`, `operator`, and
  (reserved) `peer` roles.
- **No global state without an owner.** Season depth, leaderboards, and
  the Chronicle are per authority; a federated season would be a merge
  rule, not a shared row.
- **Transport-agnostic core.** The simulation never touches sockets;
  sessions are objects with a send queue. A Link-relay transport
  (NetBBS issue #168's real-time relay) would be one more session
  factory.

## 10. Testing strategy

- **Unit**: rules from `00-game-design.md` as pure functions (to-hit,
  damage, trace, standing deltas, rent, clone debt) with the numbers
  asserted from the design doc.
- **Content**: the validator over the shipped tree; every zone loads;
  every core's controls resolve; every asset referenced exists; the
  relations matrix matches the documented asymmetries.
- **Simulation**: a headless server driven by a test harness that
  creates sessions, injects intents, and steps ticks deterministically.
  Multi-session scenarios (two players see each other, combat between
  two sessions, relay capture with a runner and a holder, cut-power
  during a run).
- **Client**: the renderer over a fake terminal at 80×24, 132×50, and a
  wide-character handle; key decoder tables.
- **Protocol**: golden frames; version rejection; delta/ack coalescing.
- **Load**: a bot client (`blacksite.bot`) that plays a scripted loop;
  16 bots for an hour must keep tick time under 40 ms and client CPU
  under the platform's 300 s budget per hour of session.
- **Ops**: backup/restore round trip; migration from every shipped
  schema; server restart with players connected.

The test runner is `pytest`; there are no network tests that leave the
machine.

## 11. Performance budget

| Item | Budget |
|---|---|
| Tick (16 players, 6 active zones) | ≤ 40 ms p99 |
| View delta per session per tick | ≤ 2 KiB typical, ≤ 16 KiB worst |
| Client render per frame | ≤ 5 ms at 80×24 |
| Client CPU per hour of play | ≤ 120 s (40 % of the platform's cap, leaving headroom) |
| Server RSS (16 players, full content) | ≤ 200 MiB |
| Server start (full content) | ≤ 3 s |

## 12. Observability

- `logs/server.log`: structured lines (JSON per line), rotating, levels.
- `logs/audit.log`: every operator action and every player report.
- `blacksite admin status`: uptime, players, active zones, tick p50/p99,
  persistence lag, event state, season depth.
- No telemetry leaves the machine.

## 13. Security and abuse

- Server-authoritative everything. The client cannot assert state.
- Input validated by type and range before it reaches the simulation.
- Chat and names are sanitised for control characters and width; the
  client renders them through the same width-safe path as everything
  else. ANSI in chat is stripped.
- No filesystem paths, shell commands, or BBS credentials ever cross the
  protocol.
- Bans key on `bbs_user_id`; a banned caller sees a fixed message and the
  door exits 0.

## 14. Packaging

- A single Python package `blacksite` with `server`, `door`, `admin`,
  `bot` entry points, `content/` as package data, and `deploy/` templates
  in the sdist.
- Python 3.12+, no runtime dependencies outside the standard library
  (SQLite, asyncio, json). Test dependencies: pytest.
- Installed into its own venv (recommended) or NetBBS's; both work
  because the door profile names the interpreter explicitly.
- Versioning: semantic. The protocol major is independent of the package
  version and is asserted by both ends.

## 15. Operational contracts from the lore

### 15.1 Actions and readable state

Add typed intents to the existing protocol, not a command parser:
`journal.open`, `evidence.inspect`, `evidence.publish`,
`work_order.reserve`, `work_order.perform`, `work_order.allocate`,
`lat.survey`, `lat.sample`, `expedition.enter`, `expedition.resume`,
`finale.choose`, and `calibration.set`. Each includes a target ID where
needed. Physical position, permissions, costs, expiry, safety and the
stage's input verb are checked by the server. Text fields are names or
chat, never secret answers. Duplicate request IDs return stored results.

A stale allocation, market purchase or finale selection returns the
current detail view without spending resources or selecting a different
row. The player's chosen hotkey opens the concrete cost/consequence
preview; confirmation is the last action only where irreversible.

`ZoneView` and `LatticeView` add `objective` (next action, target, cost,
progress, retry rule), `hazards[]` (scope, warning, active duration,
escape), `service` (state, allocation, expiry) and `escape` (available
route/action). `LatticeView` includes body safety and black-ICE risk.
`MenuView` detail can show a record's observation, source, claim,
publication choices, expiry and expected revision. Required information
has a compact summary; paginated source prose is optional.

The server reveals only authorized journal records, visible geometry
and public forecasts. Opponents' ballots, unchosen names, sealed
publication and hidden core data never appear in a view or generic log.

### 15.2 Atomic effects and restart

The pure simulation returns proposed state deltas, receipts and outbound
messages. The storage layer commits a stateful rewarded action and its
receipt in one transaction; the I/O layer publishes success only after
commit. While commit is pending, the affected action key is reserved.
Failure releases it with a retryable result. Ordinary movement remains
on the dirty-state schedule. Tests inject commit failure before and
after durable write, then resend the same request.

One settlement transaction consumes the season's eligible ballots,
freezes rankings, writes the winning choice or tie, applies one bounded
balance delta, records the Chronicle and installs next-season modifiers.
Personal finale receipts change only that identity's standing/benefits.
A second caller, repeated run or recovery cannot repeat either effect.

Persist committed event plans and seeds before selling their forecasts.
At restart, reconcile wall-time expiry before input; resume uptime timers
without catching up an offline backlog. Rebuild expeditions from their
safe checkpoint. Service reservation, allocation, public control expiry,
relay ownership and season/event overlays remain separate fields so
removing one layer cannot undo another. Their composed map must preserve
essential services, outward travel and safe-zone immunity.

### 15.3 Delivery boundaries

S02 defines the full closed data schema and validates explicit bundle
manifests. A fixture bundle may omit city content; an activated release
bundle may not have unresolved references. S19 delivers contract stages,
receipts, evidence and work orders; S24 supplies scheduled event overlays;
S25 authors all remaining ordinary city maps; S27 supplies dialogue and
records. S26 activates and validates the complete Season 1 bundle and its
solo/crew finale. Seasons 2 and 3 remain design specifications until their
own complete bundles and acceptance runs exist.
