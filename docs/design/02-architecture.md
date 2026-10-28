# Blacksite — Technical Architecture

How the game runs as a native NetBBS door: one long-lived, authoritative
game service per node and one thin door client per caller, joined by a
versioned local protocol. This document is the contract every slice in
`docs/plan/slices/` builds against. `docs/upstream/` records the platform
requests and their released outcomes. Section 8 defines the supported
integration; the external runner remains an operator-managed alternative.

---

## 1. Constraints from the platform

Verified on 2026-10-22 against released NetBBS v7.33.0, source commit
`f354e898dc2664b13c35a4e2cbbbbfa80d84776d`: its door guide, Developer
Handbook and `src/netbbs/doors/{runtime,profiles,services,outbound,events}.py`.
[Platform catch-up](../plan/01-netbbs-platform.md) links the exact sources,
release history and Blacksite implementation gaps reported in issue #56.
The S31 supported installation floor is **NetBBS >= 7.31.0**.

- A door is a **subprocess per caller**, launched with argv, never a shell,
  under the service account. Profile `time_limit` and `cpu_seconds` each
  accept 0-86400; zero removes NetBBS's corresponding ceiling. Defaults
  remain 3600 wall seconds and 300 accumulated CPU seconds. Host hard
  limits still apply. A finite CPU ceiling has equal soft/hard limits:
  exhaustion can kill the client without a cleanup signal or warning.
- Caller memory defaults to 256 MiB and is configurable; `RLIMIT_NPROC`
  remains shared by the UID. Caller `stop_grace_seconds` is 1-60, default
  5, distinct from the companion service grace. Reaping is bounded even
  if a descendant holds output open: grace plus about four seconds.
- Blacksite uses native **stdio**, `encoding: utf-8`. Since v7.14.0 NetBBS
  transcodes output for CP437 callers; UTF-8 inside the subprocess does
  not mean every terminal uses UTF-8. PTY `OPOST|ONLCR` is irrelevant to
  this profile. ANSI colour/cursor addressing remains the game floor.
- `NETBBS_DOOR_INFO` supplies identity/geometry, `color_depth` (including
  `16`), integer `door_api`, boolean `unicode_style`, `transport`, node
  display `timezone`, `node_name`, stable opaque `node_id`, and an optional
  positive `session_limit_seconds`. Absence of the latter means no host
  deadline. There is no published `node_fingerprint`, guest flag or user
  level. A third-party door receives the shared guest account's identity.
- Native stdio resize uses rewritten door info plus opt-in `SIGUSR1`
  (`resize_signal: true`). Custom profile environment uses `DOOR_*`,
  including `DOOR_BLACKSITE_INSTALL_DIR` and an optional
  `DOOR_BLACKSITE_SESSION_LIMIT`; old `BLACKSITE_*` aliases are standalone
  conveniences, not valid custom profile keys.
- The native subprocess receives a minimal environment, not its parent's
  `PYTHONPATH`. Install Blacksite in the exact interpreter named by the
  profile; changing a development server's import path never updates a
  separately installed client. S22's native harness verifies the isolated
  interpreter's version and Python source digest before accepting proof.
- A profile permits one supervised companion service (§3.1), with its
  own memory limit and no NetBBS CPU-seconds limit. Persistent data stays
  in the operator-owned installation directory. Node backup copies of
  that directory are opt-in, unquiesced and never automatically restored.
- Door presence already names the door, visible only to callers allowed
  to enter it. Optional outbound board/chat/event/standings file drops
  exist, but require the door's minimum play level to be zero (§8.3).

Blacksite still consists of two programs and a directory. These are
verified platform facts and planned S28-S31 integration contracts, not
claims that the remaining Blacksite work is already implemented.

## 2. Components

```
NetBBS node process
 ├─ caller session A ── stdio ── blacksite.door (client A) ─┐
 ├─ caller session B ── stdio ── blacksite.door (client B) ─┤  local socket
 └─ NetBBS door service supervisor ───────────────────────┼─► blacksite.server
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
  argv = `-m blacksite.door`, profile environment
  `DOOR_BLACKSITE_INSTALL_DIR` (standalone: `BLACKSITE_INSTALL_DIR`).
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
  run/            socket, blacksite.pid, port file (created/removed by server)
  secrets/        door.secret, admin.secret (0600, created on first start)
  logs/           server.log (rotating), audit.log
  backups/        created by `blacksite admin backup`
```

The content tree is copied out of the installed package on first start
(so an operator can read and override it) and re-synced when the package
version changes; `content.local/` is never touched. This bootstrap is
S03's job (the server bootstrap); S05's runner uses the same startup
path, so it exists before the first zone loads.

## 3. Process lifecycle

### 3.1 Primary: released NetBBS door service supervision

S31 ships one primary preset requiring NetBBS >= 7.31.0. Companion
services shipped in v7.3.0; the block is no longer speculative:

```json
{
  "argv": ["-m", "blacksite.server", "--install-dir", "{install_dir}"],
  "start": "with_node",
  "stop_grace_seconds": 10,
  "service_memory_mb": 512,
  "health": {"kind": "socket", "path": "{install_dir}/run/blacksite.sock"}
}
```

Those five keys are the complete service field set. The program is the
door's `executable_path`, with `argv` after it; `{install_dir}` is the
only substitution. `install_dir` is required and is the working directory.
The narrow environment includes `NETBBS_DOOR_SERVICE=1`. `start` can also
be `on_first_caller`; the primary preset uses `with_node`. Grace is 1-60
seconds; memory is 64-4096 MiB, default 512. There is no service CPU cap.

NetBBS restarts with 1/2/4/.../60-second backoff. Five failures in five
minutes trip the breaker; SysOp Start/Restart clears it. Socket health
probes connect without a game hello; S31 verifies they do not create a
player or hold a session. Admission refuses down/unhealthy services before
launching a caller client. Shutdown stops services concurrently, first,
with SIGTERM then the configured grace and SIGKILL.

### 3.2 Alternative: externally managed service

`blacksite serve` remains a foreground command and the repo ships example
`rc.d` (NetBSD) and `systemd` units in `deploy/`. Remove the `service`
block when choosing this alternative; never run both owners. The door
client, when it cannot connect, tells the caller "The city is dark right
now" and asks the SysOp (in the log) to start the service. The client
**never** spawns the server: doing so from inside NetBBS's reaped process
group would let a caller's exit kill the world. Historical older-node
setups are not a second supported release preset or an excuse to omit the
minimum-version line. This external path also supports local development.

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
  HMAC is over canonical door_info bytes with `secrets/door.secret`:
  UTF-8 JSON, keys sorted, compact separators (`,` and `:`), Unicode
  unescaped, no non-finite numbers or duplicate keys. The hex secret is
  decoded to 32 bytes before HMAC-SHA256. Sign the object as sent,
  before normalizing NetBBS's `user_id` to `bbs_user_id`; conflicting
  identity fields are rejected. This does
  not defend against a hostile process running as the service account (nothing
  can); it defends against a stray process on a multi-user development
  box and against a misconfigured install pointing at the wrong
  directory.
- Identity is `bbs_user_id` from door_info; the handle is display. A
  player record is keyed on `(origin, bbs_user_id)`.
- S31 sets the door registration's `min_play_level` above the actual
  guest account level (normally 1 for a level-0 guest), excluding guests.
  Third-party guests share one ID; do not create persistent
  characters for them, guess from a handle, or read NetBBS's database.
  This is a registration gate, not a `DoorProfile` field (§8.3).
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

S04 uses the shipped keymap spellings `pgup`, `pgdn` and their `shift-`
forms. Cancelling a line prompt sends `intent {name: "prompt_cancel",
args: {id}}`, never an empty line submission. Delta add/replace/remove
operations use JSON pointers against the last `{kind, body}` view; an
invalid patch or base mismatch requests `intent {name: "resync", args:
{}}` without partially changing the displayed view.

S03 wire spellings: `line.id` identifies the prompt, `caps.tier` is
`"16"`, `"256"` or `"truecolor"`, and `caps.unicode` is `true`.
Terminal dimensions are integers, at least 80×24 and at most 1000×1000.
Timestamps `t` are nonnegative integer client milliseconds. `rev` and
`base` are nonnegative integers; an ack beyond the last sent revision
is ignored. `request_id` and `expected_revision` are required for
stateful selections, optional for ordinary movement. Both directions
reject duplicate object keys and non-finite JSON numbers.

`admin.status`, `admin.who` and `admin.stop` have no required payload.
Their result is a private `view` of kind `text`; the body's `lines`
contains the JSON result. Every accepted operator command is audited.
An operator hello never replaces a caller with the same user ID.

Bye reasons are strings, not a closed enum: `maintenance` for a service
stop, `timeout` for an idle hello, `slow_consumer` for queue overflow,
`banned`, `auth`, `protocol`, `forbidden`, `replaced` and `logout`.
A stalled authenticated writer is closed without attempting another
frame on that writer. Clients must handle unknown reasons as a generic
disconnect rather than assuming that every disconnect is an auth error.

### 5.3 Server → client

| type | fields | notes |
|---|---|---|
| welcome | proto, server_version, player (summary), keymap, palette, motd | |
| view | rev, kind (zone, lattice, menu, wake, dead, text), body | full snapshot |
| delta | rev, base, ops[] | JSON-patch-like ops on the last view; the client falls back to requesting a full view if base does not match |
| log | lines[] {channel, text, role, at, id?}, replay? | opaque line IDs suppress replay duplicates |
| prompt | id, kind (key, line), label, max_len | |
| toast | text, role, seconds | transient banner |
| bye | reason, text | |
| pong | t | |

The server sends at most one `view` or `delta` per session per tick, and
only when something the session can see changed. It coalesces if the
client is more than 3 revisions behind (`ack`), sending a fresh `view`
instead of stacking deltas. This keeps a slow Telnet link from filling
its pipe.

S09 keeps 500 authorized log lines per session and transfers that ring
once to a reconnect within the 60-second grace period. Reconnect and
view resync replay the last 50 lines with their original opaque IDs and
`replay: true`. Clients keep a 500-line ring and ignore repeated IDs.
History is not persisted across service restarts. Chat strips terminal
commands and controls, normalizes NFC, and caps each transmitted text at
200 display columns with a UTF-8 byte budget for the 64 KiB frame limit.

Social state stays in the pure core. Player reports leave through an
outbox: the I/O layer commits the reports row and database audit row in
one transaction, appends `logs/audit.log`, then acknowledges `Reported.`.
A failed write never reports success. Ignore and sitrep privacy live in
player settings; ignore keys are stable BBS identity IDs, not handles.
S20 supplies faction membership and S22 installs crew routing membership.

### 5.4 View models

`ZoneView.body`:

```
viewport: {x, y, w, h}            zone-tile rectangle the client should draw
tiles: [[legend index, ...], ...] visible now; -1 unseen, -2 remembered
remembered: [[legend index, ...], ...] last known terrain; -1 unknown
legend: [{id, glyph, role}]      tile types in stable ID order
actors: [{id, x, y, glyph, role, name?, stance, hp?}]
objects: [{id, x, y, kind, state, glyph}]
me: {name, handle, faction, grade, hp, hp_max, sta, sta_max, shock, chits, marked_until, heat_until, zone, zone_name, safety, clock, cooldowns{}, effects[]}
target: {id, name, faction, hp_pct, range, cover, relation} | null
nearby: [{id, name, role, relation}]
crew: [{id, name, zone, hp_pct, jacked}]
event: {name, remaining} | null
hint: text                         one-line contextual key help
```

`remembered` matches the viewport and contains only terrain previously
seen by this player. The renderer uses it when `tiles` contains `-2`;
hidden actors and current object state never enter either memory grid.
The viewport clips to the zone's extent and at most 4096 cells, bounding
snapshots for unusually large terminals. Usual layout dimensions and
four-tile scrolling are unchanged. Camera changes send a full snapshot;
other updates use the JSON-pointer operations in section 5.3.

S07 adds `me.grade`, `chits`, `lease_days`, `legal_at`, `xp` and
`discharge_xp`. Lease days and the early-discharge XP target are separate
visible fields; personhood does not remove grade-based protection.
`WakeView.body` is `{kind: "menu" | "text", body, stage, hint}`. The nested
body uses the existing menu/text renderer and input contract. Art remains
the S33 extension. A name prompt shows its BBS-derived default; an empty
submission accepts that default on the server.

`LatticeView.body`: `cells` (positions and edges in view), `presences`,
`me` (integrity, trace, rig slots with cooldowns), `room` (data, controls,
ice with integrity), `hint`.

S15 control rows include `state` and `reset_in`; entrance cells include
`offline`. `lat.flip {control}` starts a three-second interruptible
procedure. Its completion rechecks room, content revision, permission
and the selected work-order layout. Hardware uses a content-first menu
and a chosen Cut power action followed by the final Y keystroke. Closing
that menu changes no power state. The door renders the dimmed `[C?]`
marker from server state. Private manifests expose only unsecured stored
units; resident core logs paginate through authoritative menu cursors.


S13 adds `sector`, `layout_size`, explicit `edges`, cell access/labels and
uplink markers. Hidden cells and their edges are omitted until found.
`me` includes body HP, hit serial, movement ticks and bounded escape
progress; `body_safety` stays visible. The body remains a physical actor,
while its session subscribes to a sector. Social menus preserve this
subscription and resume the Lattice view on close. Optional three-frame
`transition {direction, frame}` decoration does not delay mechanics.
Ordinary sector updates use the same revisioned delta path as zone views;
kind/sector changes, overlay return and resync start with a full snapshot.
Operators use `admin.lattice.who` (no payload) or the audited debugging
`admin.lattice.reveal {player, sector, cell}`; callers cannot send either.

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

The character subsystem loads pure snapshots at boot and returns a write
outbox. Only the I/O layer executes it through storage. Creation commits
the player, item grants, identity state and instance serial in one
transaction; only its successful receipt attaches the body and exposes
rewards. Failure returns the card screen for an explicit retry. Deletion
commits removal of the player and owned items while retaining identity
history before the Wake restarts. A failed proposal cannot fall through
into a later periodic flush.

Safe/pocket logout removes the body and flushes immediately. Elsewhere a
sleeper stays for 60 seconds; reconnect reclaims that same body. Its UTC
offline timestamp reconciles remaining sleeper time at restart before
input. Expiry follows authored zone links to the nearest safe/pocket zone;
the Wake Hall is the fallback while the city graph is incomplete. S10
supplies combat flags and clone-debt consequences; S07 has no combat.

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
  NetBBS's optional directory copy neither quiesces the service nor
  guarantees matching database/WAL generations. S28 must keep a completed
  consistent snapshot and verify restore with the service stopped and
  the exclusive lease held. A node backup reporting success is not proof
  that its copied live game directory is recoverable.
- Migrations: numbered Python modules under `blacksite/server/storage/migrations`,
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

Local acceptance must use an installed current client, as deployment does.
Run the profile interpreter with `-I` to check its installed Blacksite
version before launching a node. The native harness writes
`native-client.json` and refuses a version or source mismatch. Retain that
receipt with the terminal transcripts; a source server paired with an old
protocol-compatible client is a compatibility test, not current-client
rendering acceptance. This enforces S31's existing minimal-environment
contract without weakening the NetBBS profile.

### 8.1 Registration

Native stdio door, `max_sessions` raised to the node's player cap (16
by default), `multinode_certified: true`, `encoding: utf-8`,
`resize_signal: true`, `install_dir: <DIR>`, `memory_mb: 128`, caller
`stop_grace_seconds: 5`, and the service block in §3.1. The long-session
primary policy explicitly sets `time_limit: 0` and `cpu_seconds: 0`:
no unannounced finite accumulated-CPU cutoff on an unbounded session.
Host hard limits remain, and S29 measures the unchanged 120 CPU-seconds
per hour efficiency target before S31 certifies the preset. An operator
choosing a finite wall cap must size any finite CPU cap from measured
whole-session CPU plus headroom, not mistake it for a per-hour budget.

Custom environment uses `DOOR_BLACKSITE_INSTALL_DIR=<DIR>`; a separate
game session cap is optional. A preset JSON is shipped in `deploy/` for
import on the Compatibility screen. S31 records the registered-only
play level separately, tests Check setup and both service ownership paths,
and publishes the minimum NetBBS version in the install guide.

### 8.2 Wall-time cap

S30 represents the deadline as optional. A positive host
`session_limit_seconds` always bounds the launch. A positive explicit
`DOOR_BLACKSITE_SESSION_LIMIT` (standalone `BLACKSITE_SESSION_LIMIT`)
can shorten it; zero/unset means no additional game cap. Use the minimum
positive bound. If neither exists, omit countdowns and timeout exit;
do not silently insert the current client's 3600-second fallback.
Zero is a profile/override opt-out, not a valid positive host deadline.
With a deadline, toast at five minutes/one minute and leave five seconds
early. A reconnect never resets the host launch clock. The established
body/sleeper and reconnect rules remain authoritative.

### 8.3 Presence

NetBBS already names the door in Who's online, respecting its access
gate. The game's own `sitrep` remains authoritative for world presence.
See [upstream 05](../upstream/05-door-presence-and-outbound.md), not 04.

API 3 supplies board file drops, API 4 adds live chat, and API 5 adds
events/standings. Requests are picked up during a live caller session,
roughly every two seconds. Match receipts by their `request` field,
never a constructed result filename. Optional publication uses committed
semantic facts only; paths, credentials and receipt-file I/O stay in the
client I/O adapter, outside simulation and the game protocol.

**Default policy: no BBS publication.** NetBBS accepts posts, chat and
events only while `min_play_level == 0`; nonzero rejects even previously
allowlisted destinations. That conflicts with safe registered-only play
on the current third-party guest contract. Do not lower the gate, invent
guest identities or bypass NetBBS's audience policy to enable publicity.
S21/S26 expose in-game committed facts/standings independently; S31 may
add an opt-in adapter only after a guest-safe, audience-compatible host
contract exists. That enhancement does not block the release or S17.
The [catch-up plan](../plan/01-netbbs-platform.md) preserves the exact
event/standings/receipt requirements for that future optional work.

### 8.4 Platform API and terminal admission

`door_api` is a single integer, independent of Blacksite's protocol
major. Historical missing fields mean legacy API 2; API 3 shipped with
v7.3.0, 4 with v7.12.0, 5 with v7.31.0. S31 supports API 5 for the
certified release, clearly refusing older/missing, malformed (including
boolean) and newer unknown versions before world entry. Ignore unknown
additive fields within a supported version and permit optional fields
to be absent; do not guess unknown-version semantics. A future API bump
requires a bounded compatibility review, not silent acceptance.

S30 honors the boolean `unicode_style`. False means the caller requested
ASCII styling; explain the ANSI graphic requirement and return cleanly
before world entry, inviting selection of Unicode or CP437 in NetBBS.
Do not force a preference change or add an ASCII tier. True permits the
CP437-compatible glyph set, and the modern tier when the first-play check
confirms it (terminal UI §1); absence is unknown and uses the
existing graphic default. S31 tests actual CP437 transcoding as well as
UTF-8, resize and 16-colour output. `node_id` is not a credential or a
Link fingerprint; S32 may not assume the absent `node_fingerprint`.

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
  16 bots for an hour keep tick time under 40 ms. Measure actual client
  CPU at both terminal sizes against §11; record configured/inherited
  ceilings and whole-session headroom separately. A CPU limit is not a
  per-hour allowance, and SIGKILL is not graceful logout.
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
| Client CPU per hour of play | ≤ 120 s; efficiency target, independent of configurable accumulated CPU ceiling |
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

A physical terminal's optional `params.cell` names a public cell of
`params.sector`; omission uses that sector's ordinary entry. Content
validation and admission both reject gated, hidden or absent cells.
This permits a local loan terminal beside a mission cabinet without
granting a key, discovering a hidden route or altering district uplinks.
Vesper's parcel latch has one physical objective and a typed linked
control. Its manual release joins `interlock_state` and
`contracts_state` in one write; a committed Lattice flip advances the
same objective. Switching methods before completion consumes no branch
receipt. A combined contract/vendor counter keeps a Trade hotkey so
commissioning a board does not remove its shop.

Contract prerequisites are checked against current authoritative facts
both when proposing and when starting. The card and refusal message
describe unmet requirements in ordinary language. A paid story helper
can assist without re-earning entry standing, while retaining zero
additional reward and no rewritten branch. Future event predicates use
`Contracts.event_active`, bound by S24 to committed event state.
Unavailable dialogue/season context fails closed until its owner binds
it; authoring content does not publish offers.

Permanent program learning uses one pure acquisition rule for contract
rewards, counters and data. It writes `known_programs` and current-season
`program_acquisitions` with the owning reward/payment/source receipt.
The Lattice binds Commerce's current-season provider; it does not infer
a season from the story's age. Acquisition restrictions do not revoke
previously learned programs or turn faction loans into permanent copies.

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
route/action). `LatticeView` includes body safety and black-ICE risk. Its optional
`runner_target` names only a selected co-located, same-instance runner,
with server-derived integrity percent and `burn_allowed`; remote crew
markers never become local combat targets.
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

S19 forks its pure contract state before an action. The source joins
`contracts_state` to the same Commerce write as items, participant
patches, identity caps and other source state; its success callback
installs that draft before another queued proposal runs. Storage owns
the meta record and clears an older dirty snapshot after commit. Live
enrollment proposals create no mission actors or rewards; only the
confirmed accepted roster becomes durable. Journals, branch choices,
service effects and their owning reward receipts follow this boundary.
Finalize the source callback before flushing deferred impacts: those
impacts can immediately propose another source write. The next proposal
must see both the retired source and the installed contract draft.
Mission lifts bind their supplied items before inventory stacking and
record the exact instance, stage, attempt and source in
`progress.mission_sources`. Expiry, withdrawal, retry and turn-in retire
obsolete payloads, player/identity source receipts and the source's
availability record together; failed cleanup writes retain all of them.
Acquired journal evidence remains available. Permanent cash, programs
and schematics belong to an explicit contract reward rather than a
temporary mission source. Cleanup runs after the source's own callback,
so it cannot recreate a retired source after the cleanup commits.

S21 commits `relays_state` with affected player/identity rewards and
`interlock_state` through the same source boundary. Explicit claims are
live channels; restart aborts them rather than counting offline capture
time. Successful runner control receipts bind the original named claim.
The ledger retains exact fractional influence, ownership history for
rent, rolling capture reward limits and daily identity payout receipts.
Only committed, attributed captures enter its capture-fact log.
Failed capture proposals retry after one injected-clock second, with one
holder notice per failed claim episode. Ended claims drop the retry marker;
another ready claim can use the writer while the first is cooling down.
Authenticated `admin.relay.list {}` and
`admin.relay.set {relay, faction}` use typed IDs, with `neutral` clearing
ownership. Set acknowledges its committed source write and awards no
capture credit. Callers cannot use either operator frame.

Optional fare choices commit a wallet debit and route-bound
`progress.paid_passes` receipt together. `paid_trip` binds the exact pass
to persisted S08 transit. Both live and offline arrival consume that
pass in the arrival checkpoint; a stop before departure retains it.
An untagged exit retains ordinary S08 travel. `Exit.relay` explicitly
opts a cable or outbound gate into its price/free-route card; content
validation requires the corresponding relay and a public cable fallback.
Silt contract sources are authored as `mission_data` on the contract.
The generated band resolves their sector/band/data binding into its
own visible cells. The source site stays stable across layout seeds;
the verified lift adds the exact mission custody. No client supplies
a generated room address as authority. An inactive chain adds neither
an offer nor a Silt source.
In the Lattice, E inspects the server's current public
cell or normal core room for accepted survey objectives, without an
extra channel or cooldown. Capture the objective attempt and location
before queuing its atomic receipt; later acceptance cannot count an
earlier inspection. Movement discovery remains a separate S16 receipt.
Actual nearby guards from S22's participation window may contribute to
a source action; the contract ledger still filters its frozen roster.
One final action may award ordinary run XP and fixed work-order XP;
compose the latter over the source's player/identity draft in that same
transaction. Work-order allocation and payment never run as a later
notification. An expiring clinic discount invalidates an older confirmed
quote without charging or drawing a surgery roll.

S16 reward and skill-use functions operate on player/identity drafts.
NPC defeat joins XP to the spawn retirement and loot receipt; data-lift
XP joins the source decrement and item transfer. A post-commit callback
may announce a reward but never decides or pays it. Per-identity core
days, PvP windows and relay hold caps commit with the player. Generated
Silt visits and training cannot create discovery or use rewards.
PvP death includes both players and both identity records in that one
receipt: the victim's clone/debt settlement and the winner's reward/cap.
Clear stale write-behind identity records for every committed recipient.
The I/O writer cancels transfers whose player or secondary recipient was
deleted or is being deleted. Character deletion also blocks later ordinary
save snapshots from background actors and old callbacks. A periodic drone
checkpoint cannot recreate the deleted player or its owned items.

One pure `Modifiers` collector composes installed items, substance phases
and optional ability/event layers from the supplied UTC time. Consumers
read effective stats through it, never raw implant maps. Permanent skill
groups remain separate. Surgery, doses, Chrome ejection and detox state
are committed before effects appear. Detox uses an existing clinic
pocket and persisted UTC deadline, including after logout/restart.

S24 binds `core.progression.surge_preview(player) -> str | None` to the
committed public event forecast. An enabled producer returns useful text,
including when no Surge is announced. Before that producer exists, S16
returns `None` and the Tenant's Ear detail pane says its forecast has no
effect yet. The hook grants no event, answer, stat bonus, or authority.

One settlement transaction consumes the season's eligible ballots,
freezes rankings, writes the winning choice or tie, applies one bounded
balance delta, records the Chronicle and installs next-season modifiers.
Personal finale receipts change only that identity's standing/benefits.
A second caller, repeated run or recovery cannot repeat either effect.

Persist committed event plans and seeds before selling their forecasts.
The `meta.events_state` receipt stores scheduler position, cooldowns,
plans, allocations and claimed sources. Plan activation, surplus salvage
and event key caches join one commerce transaction. Publish warnings,
forecasts and active effects only after it commits. End/cancel removes
only event-owned surplus, uncollected caches and geometry layers; it
never removes items already collected or restores an old service map.
Allocations freeze impact footprints, route waypoints and event-only
offer terms before previews. A definition signature detects incompatible
deployment changes; restart commits cancellation and a revision before
applying geometry. No table migration is required for this additive
world-schema-4 metadata. Public Convoy death/checkpoints join contract
facts to the same event receipt. Beacon consumption and its detour
revision also commit together. A failed save publishes neither side.
Expected source failures stay inside the event subsystem. Persist the
failed roll boundary; discard an unpublished candidate. Rebuild a failed
published start from committed state, then atomically cancel it without
retaining a proposed reward claim. The I/O layer drains structured
diagnostics, including failures encountered before the listener opens.
The hot receipt retains live plans, monotonic serials and cooldowns plus
128 recent closed plans. Current transition records remain through their
commit/notification before retirement. Closing a held plan atomically
saves a compact personal outcome; personal reads are separately bounded
at 128. The held menu can display that outcome without loading old
global plans. Long-term Chronicle/publication consumers must retain the
facts they need in their own ledgers, not scan this bounded hot history.
Retire ended-event NPC spawn slots in the same committed source path.
Keep static/active slots and any slot awaiting its death receipt. Retry
retirement after that receipt, including after restart. Snapshot NPC
state immediately before storage so intervening ordinary spawns and
their monotonic serial survive; successful cleanup removes only its
retired keys from live state. Failed saves remove nothing.
At restart, reconcile wall-time expiry before input; resume uptime timers
without catching up an offline backlog. Rebuild expeditions from their
safe checkpoint. Service reservation, allocation, public control expiry,
relay ownership and season/event overlays remain separate fields so
removing one layer cannot undo another. Their composed map must preserve
essential services, outward travel and safe-zone immunity.

Story settlement rechecks the character's completed-template receipt,
including parallel crew copies accepted before the first payout. A
second completed copy closes with zero reward in a durable transaction;
failed closure retains the old state. Historical paid publication cards
quote their recorded option. Original workers may explicitly resume
generated/story participation without resetting another worker's progress
or changing frozen terms; withdrawals discard prior participation credit.
Work orders retain their separate reservation/withdrawal rules.
Typed permits default to personal custody. An explicit public audience
also supports a fixed story branch's bounded public route record. All
workers in that accepted instance share one expiry; another payout
cannot extend it. Fixed branch consent remains personal at acceptance.

S23 market sources add changed `market_listings`, `market_bids` and
`bounties` rows and their serial allocation to the same commerce receipt
as bank escrow, item ownership, S18 impound and S21 treasury. A sale adds
Kestrel treasury, never influence. Row deltas avoid rewriting all auction
history on each bid. Closed/claimed rows make expiry and death payouts
idempotent after restart. Bounty poster IDs remain in operator audit,
not caller views.

The death hook stages bounty payouts in the existing death receipt and
preserves combat, Marked and victim-cache rules. Retirement releases its
market obligations before the existing character deletion. Failure keeps
the character and escrow; an intermediate crash leaves returned items
in the character inventory for retry.

Market and bounty mutations require `request_id` and
`expected_revision`, current terminal access and the shared per-session
one-action-per-second budget. Optional `terminal` identifies the service
object; `bounty.post.target` is the local character ID. Operator frames
are `admin.market.list`, `admin.market.cancel {listing}`,
`admin.bounty.list` and `admin.bounty.refund {bounty}`. List requests accept
an optional positive `page` (default 1), return at most 100 records and
include `page`, `pages` and `total`. Market list pages include only current
held bids for their selected listings; historical records remain stored.
This bounds protocol frames in long-running worlds. These commands share the
existing operator admission and completion audit. S28 wires the CLI.

Closed listing, bid and bounty records are immutable financial history.
Proposals clone open listings, held bids and active bounties, sharing
terminal history without modifying it. The held-bid lookup is derived
from stored rows, never a second escrow authority. Delta generation skips
identical shared history and persists only changed rows. Any future state
that remains mutable must be copied as live data before mutation.

### 15.3 Delivery boundaries

S02 defines the full closed data schema and validates explicit bundle
manifests. A fixture bundle may omit city content; an activated release
bundle may not have unresolved references. S19 delivers contract stages,
receipts, evidence and work orders; S24 supplies scheduled event overlays;
S25 authors all remaining ordinary city maps; S27 supplies dialogue and
records. S26 activates and validates the complete Season 1 bundle and its
solo/crew finale. Seasons 2 and 3 remain design specifications until their
own complete bundles and acceptance runs exist.

From S08, `m1-zone-preview` is the active ten-zone hub bundle. Its name
is retained for installed overrides. Future S25 connections are visible
construction objects without dangling exit targets. Faction lean remains
lore until S20 supplies faction records. Map services remain anchors until
their consuming slices land. This is the M1 development world, not the
complete city release.

The ordinary service starts S07 persistent characters and the Wake.
`serve --spawn-zone <id>` selects temporary S06 bodies for movement probes;
it does not create saved characters. Both modes share S08 travel.

S08 changes zone ownership and listeners together, resets the camera and
view store on arrival, and persists per-zone memory/discovery separately.
Timed travel uses injected UTC deadlines, removes the body from both
zones, and saves the exact exit and arrival deadline in player progress.
Disconnect before boarding cancels the wait. Disconnect in flight keeps
the ride; restart reconciles arrival before destination logout rules.
SQLite remains exclusively in the storage/I/O layer. Item template IDs
are loaded with character state for pass/key requirements.
