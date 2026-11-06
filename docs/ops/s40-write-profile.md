# S40 write-stage measurements

This is measurement support, not a diagnosis or a persistence fix. The
cause of the intermittent S11 stalls is still unknown. The 10 ms gate,
nearest-rank calculation, workload and real heat wait are unchanged.

## Collecting a profile

Run `scripts/accept_s11_netbbs.py` through its normal released NetBBS
node and source-matched door wheel. `--size 80x24` and `--size 132x50`
exercise the two sizes separately. The existing service workflow runs
both. Its two profile JSON files per size cover the original first and
final all-hub windows; each still warms up for two seconds and samples
for ten seconds.

`WriteProfile` is installed only inside these profile windows. Normal
service execution imports no probe and has no probe branch in its tick
or persistence paths. The probe delegates each write and callback
synchronously, and restores the original instance attributes and
storage-owned SQLite connection on exit, including exceptional exits.
No snapshot contents, SQL text or player/item IDs are recorded in
operation labels.

Use one fixed local proof root, `blacksite-proof/s40` under the system
temp folder. Publish durable evidence as a GitHub artifact, on the PR
or under `docs/`, then delete proof outputs, environments, wheels,
clones and downloads. TEMP is not storage. The merged guard applies.

## Reading the gate

The profile's `gate` object contains:

- `samples_ms`: the exact `loop.timings` vector present in the same
  synchronous admin-status call that returned the asserted p99;
- `count`: that vector's length;
- `reported`: the unmodified p50/p99 result;
- `id`: the token also present in the recorded status response.

The token matters because admin input runs before the current tick's
timing is appended. The client may receive its reply after another
tick. Neither those later samples nor later status calls can replace
the saved vector.

To reproduce the existing p99, sort `samples_ms` and select index
`(count * 99 + 99) // 100 - 1`, or zero for an empty vector. At 99
samples this selects the maximum; at 100 it selects the second-highest.
No estimator or sample-window change is made to smooth that boundary.
Use this vector for the gate, not the nearby `ticks` rows' rounded or
separately bracketed durations.

## Reading write operations

`write_calls` groups operations by the simulation's processed tick and
thread. Each operation has a `parent` index within that call, so nested
JSON encoding, SQLite work and callbacks can be distinguished from
their callers. Labels cover the character-write stage, contract/NPC/
Lattice records, dirty snapshots, encoding, transaction execution and
commit/rollback, receipt callbacks and logging.

Each entry records monotonic start/end nanoseconds, wall milliseconds,
thread CPU milliseconds and process CPU milliseconds. Supported Unix
hosts also supply `RUSAGE_THREAD` deltas for voluntary and involuntary
context switches, minor/major faults and input/output blocks. Windows
has no such resource API; its counter field is null, not a claim that
no switches or I/O occurred. CPU-accounting granularity is platform
dependent.

`sampling_wall_ms` brackets the clock/counter reads separately from
the operation. If that bracket is large, do not attribute its pause
to the measured callback. The real tick gate still includes all probe
overhead; no measured time is subtracted or waived. The existing
subsystem, GC and flush records remain in the profile.

Wall time greater than thread CPU does not by itself identify disk
I/O, GIL contention or the runner. Compare operation nesting, process
CPU, scheduling/fault/block counters, sampling brackets and GC. Keep
observations separate from inferences. If this identifies a cause
outside the game with no game operation to fix, report the evidence on
#158 and stop for the owner's decision, as the slice requires.

## Checks so far

The focused tests cover snapshot freezing and the original flush
deadline, rollback and exception propagation, restoration of pre-bound
callbacks and descriptors, named operation counters, unsupported
counters, slow sampling brackets and serialized p99 reproduction at
the 99/100 boundary after later ticks/status requests.

A local Windows diagnostic benchmark, three rounds of 10,000 ordinary
character-write calls each, measured a median extra thread CPU cost of
0.040625 ms/call and wall cost of 0.043059 ms/call for six measured
operations. This is an overhead observation in that fixture, not
Linux acceptance or a timing assertion. Earlier 200-call rounds were
too short for useful Windows CPU-accounting resolution; no zero-cost
claim is made. The benchmark's private database was removed afterward.
Linux counter overhead and the actual stall still require native
profile evidence.
