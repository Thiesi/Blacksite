# 01 — Door services: a supervised long-lived companion process per door

**NetBBS issue:** https://github.com/Thiesi/NetBBS/issues/466
**Blocks:** Blacksite S31 (target integration). S05 ships the interim path.
**Recommended model for the NetBBS side:** Opus 5 (touches `netbbs.doors.runtime`, the SysOp door screens, shutdown ordering, and NetBSD rc.d behaviour; needs the shutdown-hang lessons from PRs #228/#283).

## The gap

NetBBS's door model is one subprocess per caller, reaped unconditionally
on every exit path, with `RLIMIT_NPROC` shared by the service UID. That
is the right model for classic doors and for War Dialer's play-by-post
world. A real-time multiplayer door needs a process that outlives any
caller: an authoritative simulation that keeps running while nobody is
connected, that every caller's door process connects to, and that stops
when the node stops. Today nothing in NetBBS can own such a process, so
the SysOp would have to install and manage a separate daemon by hand,
which contradicts the SysOp-frictionless rule NetBBS applies everywhere
else.

## Requested change

Add an optional **service** to the door profile:

```json
"service": {
  "argv": ["-m", "blacksite.server", "--install-dir", "{install_dir}"],
  "start": "with_node",
  "stop_grace_seconds": 10,
  "health": {"kind": "socket", "path": "{install_dir}/run/blacksite.sock"}
}
```

- `argv` uses the door's `executable_path` as the program (so a
  Python-module door and its service share one interpreter) and the same
  substitutions as door argv (`{install_dir}` at least). `start` is
  `with_node` or `on_first_caller`.
- NetBBS starts the service when the node starts (or lazily on the first
  caller), under the same service account, in the door's installation
  directory, with the same environment rules as door launches (never the
  full parent environment).
- Restart on exit with exponential backoff (1 s, 2 s, … capped at 60 s)
  and a circuit breaker after N failures within a window; the SysOp sees
  the state on the door detail screen.
- Stop on node shutdown: `SIGTERM`, wait `stop_grace_seconds`, then
  `SIGKILL`, with the shutdown ordering placed so it cannot extend the
  shutdown-hang windows fixed in PRs #228 and #283 (bounded wait, never a
  join on an unbounded drain).
- Health: optional check (socket connect, or pid alive) surfaced as a
  status word on the door detail and the SysOp status overview.
- Resource limits: the service gets its own memory ceiling (profile field
  `service_memory_mb`, default 512) and no CPU-seconds limit (it is
  long-lived by definition); `RLIMIT_NPROC` behaviour unchanged.
- SysOp screen: on the door detail, a **Service** section with state,
  uptime, restart count, last exit code, last 8 KiB of stderr, and
  action-bar hotkeys Start / Stop / Restart, each behind a confirmation
  keystroke, audit-logged like other door actions. No dialog chains
  (design doc §3.5).
- Door launch: if a profile declares a service and the health check
  fails at launch time, the caller sees a one-line "this door's service
  is not running" and returns to the door picker; the failure is logged
  with the door name.
- Backups: `netbbs.backup` treats the service's install directory as the
  door's persistent data, as it already does for War Dialer's world,
  without any new activation step.

## Non-goals

- No inter-session channel inside NetBBS; the service's own socket is
  the channel.
- No privilege separation beyond what native doors already have.
- No generic process manager; one service per door, at most.

## What Blacksite does meanwhile

`blacksite serve` runs in the foreground and the repo ships `rc.d` and
`systemd` examples. The door client never spawns the server. See
`docs/design/02-architecture.md` §3.2.
