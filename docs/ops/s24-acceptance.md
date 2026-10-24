# S24 event acceptance

S24 is under review in [PR #65](https://github.com/Thiesi/Blacksite/pull/65).
Final review-fix, exact-head CI and both-size native gates remain open.

## Runtime and evidence boundaries

Package 0.0.20 uses additive `meta.events_state` in world schema 4.
Committed plans own forecasts, chosen sites/variants, public event offers,
source receipts and revisions. A failed transfer publishes neither its
items nor its event state. Simulation uses an injected clock.

The pre-review runtime passed root pytest on Ubuntu (1508 tests) and
Windows (1507 tests, one skipped), run 40058204491. Focused source-failure,
receipt, Convoy, Curfew and relay tests pass after the first review fix
(28 tests). These are different gates; final counts will be recorded
after the updated head runs.

The local pre-review native run at 80x24 completed all event scenarios
with wide names through NetBBS Telnet -> registered native stdio. It used
NetBBS source 7.31.0, commit `d04170a`, and the installed 0.0.20 wheel
with normalized Python-tree SHA-256
`64326202d0e52867eb7dabe94ad5ebcde289670ee53de1c7f249a532680f74fa`.
The result and fully drained PTY output are retained under
`.test-tmp/s24-native-6/80x24` in the S24 worktree. This is preliminary
evidence, not proof of the subsequent review-fix runtime.

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
and Exhale sites on Vatside Clinics. It supplies a scheduler trigger/UTC
advance, grade/pools and Ferrymen +90 Kin. Walking, forecast/menu choices,
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

An incompatible authored event definition cancels its published plan on
restart. Unfinished Convoy jobs then close; completed objectives retain
their one-hour turn-in window. Deploy content between active event
windows when possible. Inspect `event list` first and tell callers about
planned cancellation. No stale forecast is silently redirected.

In-game notices and local warnings remain independent of NetBBS host
publicity. #56's positive registered-only publication gate stays with
S26/S31; S24 introduces no host callback or required BBS chat message.
