# NetBBS platform catch-up: issue #56

Status: accepted implementation plan; runtime work remains in its owning
slices. This document updates the platform assumptions, not game balance
or the slice dependency graph. S17 is not blocked by it.

Report: [Blacksite #56](https://github.com/Thiesi/Blacksite/issues/56).
Architecture sections 1, 3, 6.2 and 8 are the authoritative contracts.
The PR #38 issue checklists and S19/S25 deferred field gates still apply.

## 1. Verified sources and release boundary

Checked 2026-10-22 against released
[NetBBS v7.33.0](https://github.com/Thiesi/NetBBS/releases/tag/v7.33.0),
source commit `f354e898dc2664b13c35a4e2cbbbbfa80d84776d`:

- [Door guide](https://github.com/Thiesi/NetBBS/blob/f354e898dc2664b13c35a4e2cbbbbfa80d84776d/docs/NetBBS-door-guide.md):
  companion services, backup, registration and outbound audience gate.
- [Developer Handbook](https://github.com/Thiesi/NetBBS/blob/f354e898dc2664b13c35a4e2cbbbbfa80d84776d/docs/NetBBS-Developer-Handbook.md):
  integer API, optional metadata, requests/receipts, events and standings.
- [Profiles](https://github.com/Thiesi/NetBBS/blob/f354e898dc2664b13c35a4e2cbbbbfa80d84776d/src/netbbs/doors/profiles.py),
  [runtime](https://github.com/Thiesi/NetBBS/blob/f354e898dc2664b13c35a4e2cbbbbfa80d84776d/src/netbbs/doors/runtime.py),
  [services](https://github.com/Thiesi/NetBBS/blob/f354e898dc2664b13c35a4e2cbbbbfa80d84776d/src/netbbs/doors/services.py),
  [outbound](https://github.com/Thiesi/NetBBS/blob/f354e898dc2664b13c35a4e2cbbbbfa80d84776d/src/netbbs/doors/outbound.py)
  and [events](https://github.com/Thiesi/NetBBS/blob/f354e898dc2664b13c35a4e2cbbbbfa80d84776d/src/netbbs/doors/events.py).
- [Character preference](https://github.com/Thiesi/NetBBS/blob/f354e898dc2664b13c35a4e2cbbbbfa80d84776d/src/netbbs/net/unicode_style_preference.py):
  `unicode_style` is false for ASCII, true for Unicode/CP437 decoration.

S31's supported minimum is **NetBBS >= 7.31.0**, door API 5. This avoids
promising a matrix of old hosts with different output, callback and stop
semantics. Services/limits/metadata/presence/install support already
shipped in v7.3.0; chat arrived in v7.12.0, CP437 output conversion in
v7.14.0, events and bounded stop refinements in v7.31.0. Historical
request bodies stay archived, with released outcomes in their headers.

## 2. Current implementation versus remaining work

| Area | Current Blacksite state | Owning follow-up |
|---|---|---|
| Profile environment | S04 reads `DOOR_BLACKSITE_*` aliases | S31 corrects preset keys; original `BLACKSITE_*` names remain standalone aliases |
| Session ceiling | S04 takes the tighter positive host/override limit, but defaults to 3600 and rejects zero | S30 models no deadline and zero game-cap opt-out; S31 tests unlimited profile |
| CPU | Existing efficiency target is 120 CPU-seconds/hour; stale prose assumes fixed 300 | S29 measures actual renderer CPU and inherited limits; S31 sets explicit policy |
| Supervisor | Server and external runner exist; no released game preset yet | S31 uses released service schema and tests admission/restart/shutdown |
| API | Metadata is retained but not version-gated | S31 checks integer API 5, rejecting legacy/malformed/unknown versions clearly |
| Backups | Full S28 consistent snapshot/restore is still planned | S28 keeps SQLite backup API, lease and restore verification; raw node copy is insufficient |
| Guests | Persistent identity keys assume one real BBS user | S31 excludes shared guests by registration level; S30 explains admission policy |
| Unicode | Metadata retained, hello always advertises graphic support | S30 honors false with clear refusal; S31 verifies UTF-8 and CP437 physical output |
| Resize/16 colours | S04 already supports aliases, SIGUSR1 and `16` | S31 preserves and tests through real NetBBS; no new rendering tier |
| BBS presence | Host feature already released | S31 verifies allowed callers see the correct door name |
| Outbound | Credentials filtered out; no publication adapter | S21/S26 provide committed semantic facts; S31 records policy gate and defers default publication |
| Node identity | Game origin is independent; `node_id` metadata exists | S32 treats node ID as opaque provenance, not a key fingerprint |
| PTY | Blacksite uses stdio | No PTY newline conversion change; test only if a future PTY profile is introduced |

This plan does not claim these pending client/preset/admin changes are
already fixed by updating documentation.

## 3. Concrete installation and lifecycle decisions

One primary `deploy/netbbs-door-profile.json` uses the service block in
architecture 3.1. There is no second future-version preset to maintain.
The interpreter is the same venv Python for client and service. Service
argv is `-m blacksite.server --install-dir {install_dir}`; the process
is never spawned by the door client. The server already accepts that
module invocation. `install_dir`, not an arbitrary substitution, sets
the service working directory and socket health path.

The profile includes `resize_signal: true`, caller memory 128 MiB,
service memory 512 MiB, caller grace 5 seconds, service grace 10 seconds,
`max_sessions: 16`, `multinode_certified: true`, and `DOOR_*` custom keys.
The long-session policy is explicit `time_limit: 0`, `cpu_seconds: 0`.
It avoids a finite cumulative CPU kill eventually ending an unlimited
session. The host's hard limits still apply. S29 must verify the existing
120 CPU-seconds/hour efficiency budget and publish measured guidance
for operators who select finite limits; raising limits is not a fix for
a busy loop. A finite CPU cap gets no assumed last-second warning.

The external rc.d/systemd alternative remains, with the profile's
service block removed and exactly one world owner. Both alternatives
still require the supported NetBBS version for release certification.
Older manual setups are historical, not a new support promise.

Real acceptance must distinguish:

1. Supervised down/unhealthy admission: NetBBS refuses entry and returns
   to its door list before the Blacksite client starts.
2. External service down: the client starts, shows the city-unavailable
   text and returns cleanly under the existing bounded reconnect policy.
3. Existing clients during service/node stop: authoritative state and
   ordinary body lifecycle survive; shutdown grace is bounded. Caller
   stop/reap and service stop are separate budgets.
4. Backoff/breaker/operator restart and passive socket probes, with no
   fake character created by a health connection.

## 4. Guests, audience and optional publication

No temporary guest world is added to the multiplayer game. The current
third-party drop-file has no authenticated guest discriminator; shared
guests must not acquire another caller's persistent character pool.
The default installation gate is above the node's actual guest account
level (normally minimum play level 1 for a level-0 guest). This belongs
to door registration, not the `profile` JSON field set. Rehearsal starts
at level 255; normal registered-only operation still has a positive gate.

NetBBS outbound requires minimum play level 0. The allowlist being
present does not override this: posts/chat/events are refused while
gated. Therefore publicity is **disabled in the default deployment**.
No test, preset or guide may lower the gate to enable it and expose the
shared identity. No guest-handle heuristic, direct BBS database access,
or external bot bypass is an acceptable workaround.

S21/S26 retain real capture facts, season results and in-game standings.
An optional host publication adapter can be implemented only after a
guest-safe admission contract and an audience policy compatible with
that deployment exist. It is not a release dependency and adds no edge
to S17 or the slice graph. Until then, honest disabled-path coverage and
ordinary in-game/CLI results satisfy this part of S31. This plan neither
changes NetBBS policy nor silently assumes a new upstream feature.

The future adapter contract, when that condition is met:

- Use only host-advertised capabilities in a supported API version and
  operator-approved destinations. Keep all drop paths/receipt I/O in a
  client adapter; only bounded semantic intents cross the game link.
  Do not restore forwarding of raw outbound capabilities/credentials.
- Report committed, current earned facts, not login/migration history.
  S21 can report an actually credited capture; S26 can report a newly
  settled season. No invented player credit for a faction-only result.
- Events are `rank`, `achievement`, `medal`, `capture`, `perfect`.
  Ordinary events use `user_id`; medals use 1-3 `user_ids`, gold first.
  Respect advertised limits (defaults: 12 events/hour, title 80, ten
  standings rows); NetBBS words announcements and filters identities
  that opted out, guests, disabled/pending users and rehearsals.
- A standings snapshot replaces the last without consuming the event
  rate. Publish one explicitly named canonical metric, not a new sum
  of contribution/influence/XP. One local BBS identity per row; no
  remote identities. An empty snapshot clears a reset season. In-game
  standings remain authoritative if publication is unavailable.
- API 4 chat uses one plain line, at most 4000 UTF-8 bytes, with the
  advertised separate ceiling (default 30/hour). Do not mirror private
  player chat or use chat to evade event limits/privacy filtering.
- Requests are picked up roughly every two seconds while a caller is
  launched. Results are discovered and matched by `request`, never by
  guessing filenames. Handle accepted/dropped/rejected, rehearsal and
  temporarily unreadable receipts. No gameplay rollback on rejection,
  no unbounded backlog or blind retry after an ambiguous publication.
  This hook is not an exactly-once reward transport or an unattended
  service callback when no caller is running.

## 5. Terminal and version rules

`door_api` is an integer, not Blacksite's protocol major or a semver.
For the certified release S31 supports API 5. Recognize missing as the
legacy API-2 case for a useful upgrade message, then refuse unsupported
old/new/malformed versions before creating or attaching a world session.
Optional fields may be absent and additive fields ignored within API 5.

S30 uses the tighter positive host/game session bound, or no deadline.
An explicit game override zero removes only the game cap, never a host
deadline. Missing host limit plus unset/zero game override must not
produce the current implicit hour cutoff. Test finite/unlimited cases,
reconnect and shorter overrides with a fake clock.

`unicode_style: false` is a requested ASCII style. Respect it with an
explanatory return before world entry; invite the caller to select
Unicode/CP437 in NetBBS. Do not change their preference. ANSI graphic
output remains the floor, so there is no new ASCII tier or weakened
width rule. Native output stays UTF-8 and NetBBS converts it for CP437.
S31 real acceptance includes both physical encodings, a wide name,
80x24/132x50, SIGUSR1 resize and 16-colour mode. S33 assets retain their
CP437-compatible glyph validation and measured target bounds.

## 6. Ownership and completion evidence

| Slice | Required evidence |
|---|---|
| S21 | Capture facts emitted after the owning transaction; publicity absent/disabled cannot affect capture, reward or ownership |
| S26 | Committed local standings/settlement independent of BBS output; canonical metric and identity mapping; no history replay |
| S28 | Consistent online snapshot under writes, stopped/exclusive restore, integrity/manifest checks; guide explains opt-in unquiesced node copy and manual restore |
| S29 | NetBSD real-renderer CPU at both sizes, hour duty plus longer-session policy, inherited hard limits, existing tick/RSS/traffic targets; no invented measurements |
| S30 | Optional deadlines, ASCII-preference refusal and required-field/version UX; no duplicate game rules |
| S31 | Primary profile contract validation, registered-only guest isolation, disabled outbound gate, supervisor/external admission, crash/breaker/shutdown, all real terminal transports and release assets |
| S32 | Missing fingerprint remains unknown; `node_id` is not cryptographic identity; no new bridge or BBS credentials |
| S33 | Graphic assets fit actual layout and survive host CP437/16-colour paths, with clear ASCII admission refusal supplied by S30 |

S04/S05 completion is not revoked. Existing tests/fixtures record what
they actually proved; S30/S31 own the remaining runtime changes. The
full pytest/validator/review gates still apply to their implementation.
