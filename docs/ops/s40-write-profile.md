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

The canonical windows use `WriteProfile(trace_writes=False)`: only the
synchronous status snapshot is added. No per-operation clocks, write
wrappers or SQLite proxy are installed. The original coarse subsystem,
GC and flush probes remain as before S40. Normal service execution
imports no probe and has no probe branch in its tick/persistence paths.

After the final canonical result has been saved, including a failed
result, a separate 120-second all-hub diagnostic installs the detailed
collector. It delegates each write synchronously and restores all
bindings, including failures. It adds no player input or gameplay
fixture. No snapshot contents, SQL text or player/item IDs enter labels.
The diagnostic's timings are never substituted for acceptance.
For the default two-size command, detailed capture follows only the
last size's final gate, or a failed final gate before the run aborts.
CI runs each size in its own service, so each gets a diagnostic and no
earlier diagnostic can precede a later canonical window.

Collection keeps raw clock/counter tuples. Per-operation dictionaries,
counter deltas and unit conversion are built only when records are
exported after the diagnostic window. This reduces observer work but
does not remove clock reads or all capture overhead.

`npc-write-diagnostic-<size>.json` retains at most the latest 6,000
write calls from the supplementary all-hub window. The real heat wait
has no detailed probe. Neither detailed capture, retained objects nor
export precedes or enters the canonical windows. No forced GC or
clock reset is used. Detailed capture/GC effects remain limits of the
supplementary diagnostic; it does not define an acceptance gate.
The two gate profiles retain their exact sample vectors and coarse
timings; their `write_calls` array is empty and `trace_writes` is false.
Long-trace export is compact and streams one expanded call at a time.
It does not allocate a second full trace of dictionaries or one full
JSON string; the retained raw trace is still bounded by 6,000 calls.
The small `npc-write-shape-<size>.json` manifest records its SHA-256,
byte count, export duration and richest call's labels/parent indices.
The benchmark reads that manifest instead of loading the whole trace.

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

The diagnostic's `write_calls` groups operations by the processed tick and
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
to the measured callback. No measured time is subtracted or waived.
Detailed operation clocks are confined to the later diagnostic. The
original subsystem, GC and flush overhead remains included in the
canonical gate and its profile.

The CPU/counter reads fall inside those brackets. Their delta interval
is not exactly the wall interval, so tiny spans can show more CPU than
wall time. Do not treat that difference as negative wait or sum nested
spans as independent costs.

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
The six-span fixture does not bound a write-heavy native tick; the
first native measurement below exposed that limit.

## First native measurement: 90a6981

[Service run 42274954910](https://github.com/Thiesi/Blacksite/actions/runs/42274954910)
used released NetBBS v7.45.0, Telnet to registered native stdio. It
passed actual 600-second heat expiry and local response at both sizes.
Each of the four gate vectors has 100 samples; selecting index 98
reproduces the reported p99 exactly. The committed
[summary](s40-evidence/90a6981.json) retains those vectors, hashes and
the original GitHub artifact pointers.

| Size | Initial p99 | Final p99 | Result |
|---|---:|---:|---|
| 80x24 | 1.935121 ms | 4.716198 ms | pass |
| 132x50 | 6.399963 ms | 10.568753 ms | **fail** |

The failed final window remains a failure at the unchanged 10 ms gate.
No retry, subtraction or waiver replaces it. In the largest nearby
132x50 tick, total wall/thread CPU were 11.082925/10.587962 ms; writes
were 4.993338/4.501309 ms. The largest captured final SQLite commit
was 2.013769/0.615348 ms with nine voluntary switches and 368 output
blocks. These are observations. This predominantly CPU-heavy failure
does not demonstrate the cause of the historical 30-160 ms off-CPU
stalls, or establish that the cause lies outside the game.

The first probe formatted each span inside the write stage. In one
nearby slow tick its clock/counter brackets alone sum to 0.476027 ms
across 76 operations, with other bookkeeping cost unquantified. This
could matter to a borderline gate; no unchanged-outcome claim follows
from the earlier six-span Windows benchmark. Record export now happens
after collection, and raw readings use immutable tuples.

The service job also runs `scripts/benchmark_s40_probe.py` after native
acceptance, when a profile exists. It replays the richest recorded call
shape with synthetic callbacks, alternating capture/baseline order,
and publishes `probe-overhead.json` with the native artifact. No game
operation, payload, SQLite write or heat wait is replayed. It measures
capture allocation/GC and clocks; it neither bounds all wrapper cost
nor proves that a real gate would have the same outcome. It never
subtracts a duration or changes acceptance.

A Windows comparison of the first and deferred-export collectors on
that 76-span shape (three rounds of 500 calls) observed median extra
wall time fall from 329.995 to 225.841 microseconds/call. Thread CPU
fell from 312.5 to 250 microseconds/call, at coarse Windows accounting
resolution. This is a synthetic observer measurement, not Linux native
acceptance. The updated head still needs its own native results. No
game or persistence fix, root cause, or slice completion is claimed.

## Second native measurement: cd16740

[Service run 42282914816](https://github.com/Thiesi/Blacksite/actions/runs/42282914816)
passed actual heat expiry/local response at both sizes, and S24 passed
both sizes without retrying the old failed job. Its
[summary](s40-evidence/cd16740.json) preserves the second timing failure.

| Size | Initial p99 / n | Final p99 / n |
|---|---:|---:|
| 80x24 | 3.388407 ms / 100 | 6.969807 ms / 100, pass |
| 132x50 | 5.069048 ms / 101 | 10.110753 ms / 101, **fail** |

All four vectors reproduce p99 exactly. Same-runner synthetic capture
cost was 0.622849/0.613626 ms per 76-span call. That is material beside
a 0.110753 ms miss, but it is not a value to subtract from p99. Neither
probed failure is erased or dispositioned by a later result.

The clinic heat traces held 5,620/5,597 calls, at most 15 spans each,
and were 11,730,871/11,676,638 bytes. They parsed correctly. No SQLite
commit or write-root pause at least 10 ms was captured; maxima were
0.872063/0.533210 ms. Thus that wait did not exercise the write-heavy
final all-hub path or identify the historical off-CPU cause.

These observations motivated the separation described above: original
canonical gates with status-only sample capture, followed by detailed
all-hub diagnostics. It prevents the new operation observer from
entering acceptance and avoids the unrepresentative clinic trace.
No estimator, threshold, heat wait, canonical workload or persistence
rule changes. A diagnostic cannot turn a failed gate into a pass.
