# 04 — Enrich `door_info.json`

**NetBBS issue:** (to be filled in when filed)
**Blocks:** nothing hard. Blacksite S04 reads what exists; S32 (federation readiness) wants the node identity field.
**Recommended model for the NetBBS side:** Sonnet (a few fields in `_write_door_info`, the door guide's metadata table, and tests).

## The gap

`door_info.json` carries `handle`, `user_id`, `terminal_width`,
`terminal_height`, `color_depth`, and `node_name`. NetBBS itself knows
more about the caller and the node that a door can use without any
security cost:

| Field | Why a door wants it |
|---|---|
| `unicode_style` (bool) | the caller's existing NetBBS preference; a door can default its glyph style to match |
| `timezone` (IANA name) | in-game clocks and "Curfew at 21:00 your time" |
| `transport` (`telnet`, `ssh`, `web`, `local`) | latency and key-decoding assumptions differ; the web transport may need different escape handling |
| `node_id` (stable, opaque) and `node_fingerprint` (Link identity public-key fingerprint, if Link is enabled) | a stable per-node identifier for a door that keys its world on the node, and the seed of any future cross-node identity; the display name already given can change at will |
| `door_api` (integer) | lets a door refuse an older or newer platform explicitly instead of probing fields |
| `session_limit_seconds` | the effective wall cap for this launch so the door can warn before it hits |

## Requested change

Add the fields above to `_write_door_info` (all optional for the reader;
absence means "unknown"), document them in the door guide's metadata
table, bump `door_api` to 2, and keep the file otherwise unchanged so
existing doors are unaffected.

## Non-goals

No credentials, no email, no user level, no IP address.

## What Blacksite does meanwhile

Treats every field as optional with defaults: Unicode glyphs always,
node-local time from the server, transport unknown, origin id generated
by the game server itself (see `docs/design/02-architecture.md` §9).
