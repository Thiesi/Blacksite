# 02 — Per-door CPU and wall-time limits for service-backed doors

**NetBBS issue:** (to be filled in when filed)
**Blocks:** nothing hard. Blacksite S30 (session-limit UX) and S29 (client CPU budget) work around it.
**Recommended model for the NetBBS side:** Sonnet (small, well-bounded change in `runtime.py`, `profiles.py`, the profile editor, and the door guide).

## The gap

`netbbs.doors.runtime` applies `RLIMIT_CPU` of 300 s to every door and
caps wall time at `min(profile.time_limit, 3600)`. Both are right for a
classic door where an hour is a long session and CPU is idle waiting for
keys. A real-time client renders continuously (bounded at 10 frames per
second) and a player may want to stay in the world for an evening.
Blacksite budgets its client at 120 CPU-seconds per hour and warns at
the wall-time cap, but a SysOp cannot choose otherwise today.

## Requested change

- Add `cpu_seconds` to the door profile (default 300, the current
  constant), applied as the `RLIMIT_CPU` value for that door's caller
  processes.
- Let `time_limit` exceed 3600 when the profile is explicit
  (`time_limit: 0` meaning "no wall cap" is acceptable if NetBBS prefers
  an opt-out to an arbitrary maximum); the watchdog still bounds a hung
  process through caller-disconnect detection.
- Surface both on the Compatibility screen and in **Check setup**, and
  document the risk (a door that never ends holds a caller slot) in the
  door guide.

## Non-goals

No change to the default constants for existing doors.

## What Blacksite does meanwhile

The client warns at five and one minutes before the cap, reading the
cap from the profile environment variable `BLACKSITE_SESSION_LIMIT`
(default 3600) because the platform does not tell the door; the server
treats a reconnect within 60 s as the same session with no penalty.
