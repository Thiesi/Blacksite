# 03 — Forward terminal resize to running native doors

**NetBBS issue:** https://github.com/Thiesi/NetBBS/issues/468
**Blocks:** nothing. Blacksite S04 lays out for the size at launch.
**Recommended model for the NetBBS side:** Opus 5 (touches the session resize path for Telnet NAWS, SSH window-change, and the web transport, plus PTY window-size ioctls and a side channel for stdio doors).

## The gap

The door guide states that PTY geometry is set at launch and dynamic
resizing inside local games is not forwarded. NetBBS's own session
already learns the new size from Telnet NAWS and SSH window-change
messages and from the web client. A full-screen real-time door that
lays itself out from the terminal size would like to follow a resize
instead of forcing the caller to leave and re-enter.

## Requested change

- PTY doors: forward the new size with `TIOCSWINSZ` and `SIGWINCH` to the
  door's process group.
- Stdio and socket doors: no in-band channel exists, so add an
  out-of-band notification the door can opt into via the profile:
  rewrite `door_info.json` with the new `terminal_width` and
  `terminal_height` and send `SIGUSR1` (POSIX) to the door process; a
  door that did not opt in receives nothing.
- Web door mode: when the browser viewport changes while a door runs,
  apply the same path. The guide notes that web door mode sets the
  requested geometry; a resize during play should either be forwarded or
  suppressed consistently, and today it is neither documented nor
  forwarded.

## Non-goals

No change for DOS doors; their geometry is fixed by design.

## What Blacksite does meanwhile

The client reads the size once at start and handles `SIGUSR1` plus a
`door_info.json` re-read if it ever arrives, so the day this lands the
door needs no code change.
