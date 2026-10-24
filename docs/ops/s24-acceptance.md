# S24 event acceptance

S24 is delivered in [PR #65](https://github.com/Thiesi/Blacksite/pull/65).
The PR discussion records the final-head CI/artifact merge gate.
The exact-worktree code-graph refresh was attempted but its transport
was closed. Structural checks used direct source reads; no ready index
is claimed.

## Runtime and evidence boundaries

Package 0.0.20 uses additive `meta.events_state` in world schema 4.
Committed plans own forecasts, chosen sites/variants, public event offers,
source receipts and revisions. A failed transfer publishes neither its
items nor its event state. Simulation uses an injected clock.

Runtime `7dc7ed9` passes full root pytest locally: 1,524 tests, one
skipped, in 407.68 seconds. CI on that runtime passes 1,525 tests on
Ubuntu and 1,524 plus one skip on Windows (run 40064707085). The focused
event/NPC receipt gate passes 66 tests. Final-head checks are linked in
the PR before merge; these results do not replace human pacing review.

Both local native runs pass with wide names through NetBBS Telnet ->
registered native stdio, using `--show` PTYs. Host source is NetBBS
7.31.0, commit `d04170aa998b459b9f5ca6b9bca9ea63a17f7ab9` (not an
exact-tag claim; its stale installed distribution metadata says 3.0.0).
The installed 0.0.20 wheel matches the complete runtime Python tree:
`c433d37aebf8401ae8cb3db766608337018752fd325eff8adcf112cf556bbd1e`.
Wheel SHA-256:
`620c66f63294e69615ba69c36543a636bf288a7cf2e0777465e8eed6ff5002d8`.
ZIP CRC, all five events, 15 announcement assets and isolated installed
content validation pass. Local evidence in the S24 worktree:

| Size | Evidence directory | PTY writes | Maximum write |
|---|---|---|---|
| 80x24 | `.test-tmp/s24-native-8/80x24` | 2,244 | 0.016 s |
| 132x50 | `.test-tmp/s24-native-9/132x50` | 2,254 | 0.016 s |

Both exit zero with `s24-results.json`, `native-client.json` and fully
drained `console-output.json`. Neither has a failure trace. Hosted
acceptance artifacts and independent archive checks are linked in the
PR's final merge-gate comment.

`scripts/accept_s24_netbbs.py` exercises:

- A saved committed forecast, server restart, the same plan/site, and
  ten source-owned Ring-fall nodes without a second roll.
- Real outward Core walking and an actual refused inbound attempt,
  while safe-zone protection remains intact.
- Actual jack-in and a readable five-second local warning before a
  compatible nonblack Ticker swap, preserving damage and phase state.
- Real abilities-menu assignment and a Cantor cast with +30% relief
  and the ordinary cooldown.
- A completed Sump work order, independent relay ownership, Exhale
  activation/restart with one key source, and cancellation that retains
  the service map/allocation and relay owner.

Run the script with an installed matching wheel as `--door-python`,
`--size 80x24` or `--size 132x50`, and `--show` on a real terminal.
The harness checks package version and the complete normalized Python
tree before launching the registered door. Hosted acceptance builds its
own wheel and uploads results/screens/input traces at both sizes.

## Disclosed fixtures and remaining play gates

The native script uses S19's explicit service bay and temporary Ring-fall
and Exhale sites on Vatside Clinics. It supplies a scheduler trigger,
deterministic UTC-slot phase/advance, grade/pools and Ferrymen +90 Kin.
The slot starts five minutes past a boundary so an unrelated random
reservation cannot take the forced Exhale scope during this short run.
Real tick/combat/warning/cast waits are unchanged. Walking, menu choices,
assignment, casting, repair and restart use real inputs. No teleport,
reward, progress, defeat or combat-clock fixture is used.

The production `s24-future-events` bundle remains authoring. S25 must
resolve actual Ring-fall fields, impact regions/recovery crews, Exhale
key/shortcut anchors, Convoy waypoints, relay readers and public/free
approaches before activation. Hub fixtures do not prove those locations.
S25/S26 retain real commerce/clinic, earning/travel and human pacing
acceptance. Human play must still assess challenge, useful decisions,
waiting, affordability and reasons to return on another evening.

## Review triage and operations

The delivered first review is Claude Sonnet 5.5, confirmed in job
initialization, on `999cdfa` ([review](https://github.com/Thiesi/Blacksite/pull/65#issuecomment-6379484499)).
Its unavailable-source finding is accepted: expected source failures
must not escape the event subsystem and stop the city. Regression cases
cover a blocked reservation region, a missing published start source,
and a failed cancellation save. Failed candidates consume their roll
boundary without publishing a forecast. Published failures commit a
cancellation/correction without retaining a proposed reward claim.
Structured diagnostics are drained by the server's I/O logging layer.
Force-command hint suggestions are deferred; existing scope/cooldown
enforcement already preserves intended behaviour and caller state.

The broader re-review also identified a reachable Beacon target that
could stall the greedy walker, and unbounded whole-history rewrites.
Both are accepted. Convoys now follow cached paths around obstacles;
detours expire after 60 seconds. The hot receipt retains 128 closed
plans plus live/current transitions. Each caller keeps 128 recent
forecast reads and compact final outcomes, including unread corrections
after shared history retirement and restart. Tests cover a long wall,
blocked-detour expiry/save failure, 1,000 events/reads and both-size held
menus after retirement/restart. Both updated native sizes pass.

The next broader pass identified accumulated ended-event NPC spawn
slots. This is accepted: event cleanup now commits slot retirement with
its event source, retaining static/active slots and pending death slots.
Both cleanup and death receipts snapshot NPC state at storage prepare,
preserving ordinary spawns and serial increments while a save waits.
Six regression cases cover rollback, late spawns, pending deaths,
1,000-slot restart cleanup and a real SQLite transaction failure.
The combined event/NPC focused gate passes 66 tests. Root and both
installed-wheel native results above include this fix.

The targeted and broader reviews of `7dc7ed9` report no actionable
findings. Actual reviewer model is Sonnet 5.5, confirmed in job
initialization. The bounded public Beacon ambush concern is retained
for S25/S26 real-route counterplay assessment, without inventing an
escort-only permission rule from a speculative scenario.

Minor diagnostic repetition is deferred: retries are bounded, memory is
drained by I/O, and repeated warnings during a persistent failed save
expose an ongoing operator problem. Such a failure may log once per
second until saving recovers.

An incompatible authored event definition cancels its published plan on
restart. Unfinished Convoy jobs then close; completed objectives retain
their one-hour turn-in window. Deploy content between active event
windows when possible. Inspect `event list` first and tell callers about
planned cancellation. No stale forecast is silently redirected.

In-game notices and local warnings remain independent of NetBBS host
publicity. #56's positive registered-only publication gate stays with
S26/S31; S24 introduces no host callback or required BBS chat message.
