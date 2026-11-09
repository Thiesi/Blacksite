# S40 — Tick gate: identify the character-write stall

**Status:** done (PR #166)
**Primary model:** Codex · **Reviewer:** automated review, technical lead
**Depends on:** S11 · **Milestone:** service health
**Issue:** https://github.com/Thiesi/Karst41/issues/158

The owner queued this right after S38 (#159). That is queue order: S40
has no code dependency on S38.

Canon: architecture's performance table allows a tick p99 of 40 ms at 16
players and 6 active zones. S11's acceptance step 6 (`admin status` tick
p99 under 10 ms with all hub zones active) is a tighter gate of its own,
not canon. The historical p99s in the table below are inside the 40 ms
budget; the later captured 113.895432 ms failure is not. The owner
decided to keep the 10 ms gate. Where this file and canon differ, canon
wins.

## Goal

S11's tick gate fails intermittently on hosted runners, in the final
all-hub profile, after every gameplay step has passed. The owner decided
these failures don't block the PRs they landed on, and that the gate
stays at 10 ms. This slice names the stalling operation and makes the
gate's result auditable. On 2026-11-07 the owner approved completing it
with the evidence and design note, without a persistence fix. The
[owner decision] replaces the original fix and five-run requirements.

## Evidence before measurement

| PR, head or run | Size | p99 (limit 10 ms) |
|---|---|---|
| #154 | 132x50 | 10.575 ms |
| #126, attempt 1 | 80x24 | 10.129 ms |
| #126, run 41858928830 | 132x50 | 16.666 ms |
| #144 at 0666dfe | 80x24 | 20.105 ms |
| #159 at d39c7ff, job 127704009383 | 132x50 | 33.837 ms |

Reported by Codex from the retained profiles (#126 6636441662, #159
6677036056):

- `Server._ticks` times `loop.step()` plus `_character_writes()`, and
  the delay is concentrated in the second.
- Wall time far exceeds thread CPU. On #126's worst tick, writes took
  11.41 ms of wall time and 1.59 ms of CPU. On #159, a 33.832 ms frame
  held 29.512 ms of write wall time and 2.389 ms of CPU, and the largest
  frame held 159.913 ms of write wall time.
- On #126's worst tick no GC pause was recorded and `_flush` took about
  0.008 ms, so `_flush` alone doesn't explain it. Other blocking in the
  stage isn't ruled out.
- `app.py`, `loop.py` and `storage/db.py` are byte-identical between
  `main` and #126, and #154 failed with no P6b content. So the stall
  probably predates P6b. That is an inference, not a proof.
- Nearest-rank p99 picks the maximum at n=99 and the second-highest at
  n=100, and the profile doesn't record which samples the gate used. So
  one slow tick can decide the result, depending on the sample count.

At that point the operation was unknown. Scheduling, blocking I/O and
GIL contention were all open; the evidence did not identify the runner
as the cause.

## Scope

1. **Measure.** Find what blocks inside the write stage: the exact
   operation, and whether the time is off-CPU wait, GIL contention or
   I/O. Measurement must not change what is written or when, and its
   own cost must be small enough not to move the gate.
2. **Make the gate auditable.** The profile serialises the exact
   `loop.timings` samples and the count the gate used, so a result can be
   reproduced from the artifact.
3. **Record the outcome and design.** Keep the design note for committing
   off the event loop with `synchronous=FULL`. The owner decided not to
   build that worker now. No save, receipt, acknowledgement or game
   behaviour changes are part of the completed slice.

## Outcome

The [captured failure] at `e6ec3d6`, S11 132x50, names the successful
SQLite commit/context exit in `Storage.commerce_write`: 108.188959 ms
at tick 7183, inside 109.447249 ms of write wall time and 1.503110 ms
of write thread CPU. The unchanged gate failed at 113.895432 ms, with
99 samples. The [retained summary] preserves both final gate vectors,
timer spans and hashes from the [paired evidence], which links the
original artifacts. This identifies the operation, not whether its
wait was sync, checkpoint, locking or host scheduling.

The later [checkpoint baseline] at `fa3a108` ran 4,096 commerce-sized
WAL/FULL commits per size and observed 33 checkpoint/restart cycles
each. No commit exceeded 5 ms. These fresh standalone controls do not
reproduce the aged game's mixed write stream or explain away the stall.

The [design note] stays on file. The owner decided not to build the
separate-thread worker now; commits stay synchronous and
`synchronous=FULL` stays. The [read-only cost analysis] found real skill
rewards, no redundant zero-gain skill receipts, and no convincing small
storage optimisation. No product fix was made. This is not an
outside-game finding. Final-head CI, automated and technical reviews,
and owner merge still follow the roadmap's normal procedure. H1 and
S25 layout approval remain NOT GRANTED.

## If the cause is outside the game

If the evidence shows that the time is lost in the runner or the
operating system, with no operation in the game to fix, stop and report
it on #158 with that evidence. The measurement and the auditable profile
can still merge. What happens to the gate, and whether the slice closes
on that basis, is then the owner's decision.

## Out of scope

- Raising the 10 ms limit, or changing how the p99 is computed.
- Shortening the heat wait, reducing the workload, or changing content.
- Rewriting the storage layer. A fix that needs one comes back to #158
  as a separate proposal.

## Tests

- The measurement has unit tests, without timing assertions that could
  themselves flake.
- A test that the profile's serialised samples reproduce the reported
  p99 and count.
- Persistence tests still pass, including crash and restart behaviour.
  No write is deferred or batched by this slice.

## Definition of done

Roadmap §7, plus the owner's replacement wording, approved as written
on 2026-11-07 in the [owner decision]:

> S40 is done when the PR names the stalling operation with its evidence,
> the gate's samples and commit timer are saved in S11's artifacts, and
> the design note is on file. The worker is reopened if stalls appear on
> real hardware or under real load.

- The PR names the operation that stalled, with the artifacts showing
  it, and separates what was observed from what was inferred.
- No golden or mechanics fingerprint moves.

## S11 failure handling

The owner approved this handling in the same decision:

> - **Commit stall:** if the saved timer shows the over-limit tick was
>   mostly commit wait, with wall time far above CPU, the technical lead
>   can rule it non-blocking and note it on the PR, without a retry. The
>   owner isn't asked each time, and gets these reported in batches.
> - **Any other failure** blocks as normal, including CPU-heavy near
>   misses like the two at 10.1 and 10.6 ms.
> - The 10 ms limit doesn't change. The check still reports a failure,
>   and each failure stays on record.

This is a technical-lead ruling, not an automatic exemption. S24 still
has to pass at the submitted review head without a retry; the S11 rule
does not cover S24 or other acceptance failures. The owner merges this
PR because it records owner decisions and re-scopes a slice.

[owner decision]: https://github.com/Thiesi/Karst41/pull/166#issuecomment-6699732646
[captured failure]: https://github.com/Thiesi/Karst41/pull/166#issuecomment-6697673052
[paired evidence]: https://github.com/Thiesi/Karst41/pull/166#issuecomment-6697704773
[retained summary]: ../../ops/s40-evidence/e6ec3d6.json
[checkpoint baseline]: https://github.com/Thiesi/Karst41/pull/166#issuecomment-6698925746
[design note]: https://github.com/Thiesi/Karst41/pull/166#issuecomment-6698930471
[read-only cost analysis]: https://github.com/Thiesi/Karst41/pull/166#issuecomment-6699245842
