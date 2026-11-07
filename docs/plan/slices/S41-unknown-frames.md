# S41 — Doors ignore frames they don't know

**Status:** in progress (requested by the owner 2026-11-07)
**Primary model:** Codex · **Reviewer:** automated review, technical lead
**Depends on:** nothing unmerged · **Milestone:** protocol
**Issue:** https://github.com/Thiesi/Blacksite/issues/173

The owner asked for this to be scheduled. It follows S39 and comes ahead
of P11 (#164). There's no code dependency either way, but P11 has a
deployment-order dependency on this slice: S41 must reach operators in an
earlier upgrade than P11. Canon: architecture 5.1 and 5.3 (framing and
frames). Where this file and canon differ, canon wins.

## Goal

A door that receives a frame it doesn't recognise should carry on. Today
it treats that as a protocol error, disconnects and redials, so one new
server frame makes every older door reconnect again and again. After this
slice, the server can add a new kind of frame without breaking a door
that doesn't know it yet.

## What happens today

- `validate` raises `ProtocolError` on an unknown frame type
  (`server/protocol.py:172`) and on an unknown view kind (`:234`).
- `ProtocolError` is a `ValueError`, which `door/client.py:174` handles as
  a disconnect, and the door then redials.
- Unknown fields inside a known frame already survive. Only new types
  and new view kinds break.

## Scope

- **Door side only.** While reading from the server, an unknown frame type
  is dropped, and the door carries on. It logs once per type, not once
  per frame, so a chatty server can't fill the log.
- **Unknown view kinds.** The door keeps showing what it has and stays
  connected. Say on the PR exactly how the revision and acknowledgement
  logic behaves here. A delta built on a view the door dropped must not
  cause a reconnect loop or a resync storm, and there's a test for that.
- **Everything else stays strict:**
  - A known frame with invalid fields is still a protocol error.
  - Malformed JSON, the 256 KiB limit, duplicate keys and non-finite
    numbers are all unchanged.
  - The handshake still needs `welcome` or `bye` first.
  - The service stays strict about everything it receives. A client still
    can't send an unknown frame.
  - `encode` stays strict, so the server can't send an unknown type by
    accident.
  - `PROTOCOL_MAJOR` still rejects a real incompatibility.
- **One mechanism.** Add this as an explicit tolerance on the door's read
  path, not by weakening `validate` for everyone. The service and the
  door share that code, so a test must show the service side didn't move.
- **Canon.** State the rule in architecture 5.3.

## Out of scope

- The audit's other changes (`docs/design/proposals/graphical-client-audit.md`).
- A general compatibility or version-negotiation scheme. Upgrades stay
  lockstep as the supported path; this makes a mismatch survivable, not
  supported.
- P11's `place_card` frame, which adds itself when P11 is built.
- Any game behaviour, display change or new frame.

## Tests

- An unknown server frame type is dropped, the door stays connected, later
  frames still apply, and a thousand of them log once.
- An unknown view kind doesn't disconnect, the screen keeps its last state,
  and a following known view works. Include a delta against the dropped
  view.
- A known frame with invalid fields still disconnects, as today.
- The service still rejects an unknown frame from a client, and `encode`
  still refuses an unknown type.
- The handshake still rejects anything but `welcome` or `bye`.
- With no unknown frames, rendering and frames are byte-identical to before.

## Definition of done

Roadmap §7, plus: the mechanics fingerprint and goldens don't move. Native
evidence isn't needed beyond the existing door workflows passing, because
nothing a caller sees changes, unless the PR finds otherwise.
