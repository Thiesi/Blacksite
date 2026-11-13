# Release notes for SysOps

Operator-visible changes, newest first.

## S48a: the new presentation is the default

The door now starts in the new presentation for every caller. **An unset
`DOOR_KARST41_PRESENTATION`, or the value `1`, now means the new
presentation.** Until this change, unset meant the old renderer.

To keep the old screens for now, set `DOOR_KARST41_PRESENTATION=0` (or
`false`, `off`, `no`, in any case) in the door profile's launch
environment and relaunch. Any other value gives the new presentation.
Callers see nothing about the setting. It's a fallback for one release
step: the old renderer is removed in a later cleanup. Details are in
[door-client.md](door-client.md#renderer-s48-step-one-of-two).
