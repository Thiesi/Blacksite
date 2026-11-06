# S40 — Tick gate: find and fix the character-write stall

**Status:** in progress (approved by the owner 2026-11-05)
**Primary model:** Codex · **Reviewer:** automated review, technical lead
**Depends on:** S11 · **Milestone:** service health
**Issue:** https://github.com/Thiesi/Blacksite/issues/158

The owner queued this right after S38 (#159). That is queue order: S40
has no code dependency on S38.

Canon: architecture's performance table allows a tick p99 of 40 ms at 16
players and 6 active zones. S11's acceptance step 6 (`admin status` tick
p99 under 10 ms with all hub zones active) is a tighter gate of its own,
not canon, and every p99 below is inside the 40 ms budget. The owner
decided on 2026-11-05 to keep the 10 ms gate. Where this file and canon
differ, canon wins.

## Goal

S11's tick gate fails intermittently on hosted runners, in the final
all-hub profile, after every gameplay step has passed. The owner decided
these failures don't block the PRs they landed on, and that the gate
stays at 10 ms. After this slice we know what blocks inside the write
stage, the gate's result can be audited, and the stall is fixed.

## What is known

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

The cause is unknown. Scheduling, blocking I/O and GIL contention are
all still open. A hosted runner's own scheduling may be part of it.

## Scope

1. **Measure.** Find what blocks inside the write stage: the exact
   operation, and whether the time is off-CPU wait, GIL contention or
   I/O. Measurement must not change what is written or when, and its
   own cost must be small enough not to move the gate.
2. **Make the gate auditable.** The profile serialises the exact
   `loop.timings` samples and the count the gate used, so a result can be
   reproduced from the artifact.
3. **Fix the stall** in the operation the measurement names. If the fix
   changes what is persisted or when, the PR says so explicitly and the
   technical lead reviews it against the persistence rules in
   architecture.

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

- The measurement and the fix have unit tests, without timing
  assertions that could themselves flake.
- A test that the profile's serialised samples reproduce the reported
  p99 and count.
- Persistence tests still pass, including crash and restart behaviour.
  If the fix defers or batches a write, a new test proves that nothing
  is lost across a restart.

## Definition of done

Roadmap §7, plus:

- The PR names the operation that stalled, with the artifacts showing
  it, and separates what was observed from what was inferred.
- The S11 job passes at both sizes in five service runs at the final
  head. Every run counts: a failure is reported with its artifact, and
  is not replaced by a retry. Five passes are a sanity check, not proof
  that the failure rate is zero, so the named operation above is the
  main evidence.
- If the cause is outside the game, the section above applies instead of
  the five runs.
- No golden or mechanics fingerprint moves.
