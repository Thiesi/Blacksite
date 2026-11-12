# S47 — Off-loop storage writer: database saves never stall a tick

**Status:** planned (filed 2026-11-12; the owner merges the filing)
**Primary model:** Claude Opus 5.5 (the engineer) · **Reviewer:** automated review, technical lead
**Depends on:** S40 (design), S43, S44, S48 (lands first; owner 2026-11-12) · **Milestone:** headroom
**Issue:** https://github.com/Thiesi/Karst41/issues/212

Canon: architecture §6.2 (persistence; acknowledgement after commit),
§3.4 (server stop), AGENTS.md §4 (the simulation stays synchronous) and
S11's 10 ms gate. The design basis is S40's note, PR #166 comment
6698930471. This file carries every point from that note that the build
must honour; the note adds the reasoning. Where this file and the note
differ, this file wins. Where either differs from canon, canon wins,
except for the edits §7 below tells the build to make.

## Why

The owner held this worker on 2026-11-07 (S40). On 2026-11-12, after
four S11 failures caused by commit stalls, they scheduled it to follow
S44; the same day they put the first evening (S48) ahead of it, so it
follows S48. Each failure spent nearly all its over-limit time in one SQLite
commit in `Storage.commerce_write`, on the event loop:

| PR | Tick | Commit |
|---|---|---|
| #188 | 21.7 ms | 15.4 ms |
| #198 | 17.4 ms | 11.3 ms |
| #206 | 355 ms | 350 ms |
| #206 | 61.6 ms | 56.9 ms |

A 350 ms freeze is about three and a half ticks in which nobody moves.

## Goal

No SQLite call runs on the event loop while the server is admitting
callers. The simulation stays synchronous, and nothing a caller sees is
shown as done before its commit.

## Scope

### 1. One owner thread

- A single worker thread creates, uses and closes the one live
  connection, including startup migrations, seeds and the final close.
- It keeps `synchronous=FULL` and the existing SQL transactions and
  schema. No new migration is needed for the writer itself.
- No `asyncio.to_thread` against today's connection, and no
  `check_same_thread=False` used as a stand-in for ownership.
- The offline CLI keeps its synchronous `Storage` under the exclusive
  lease, in its own process.

### 2. Every write path, in one bounded FIFO

These all go through the worker, in today's order (the character
outbox before commerce):
- `commerce_write`;
- `character_write`, including create, delete, identity and immediate
  saves;
- dirty flushes (`mark_dirty`, `flush_due`, `_flush`, `flush_now`);
- reports and the SQL audit.

The JSONL audit and event sinks move off the tick too, through the same
ordered I/O path.

Commands are frozen on the loop as immutable values, carrying their
originating tick. Workers never receive live `Actor` or `Player`
objects, the simulation clock or closures. The queue is bounded, and
the PR states the bound and what a caller sees when it's full: today's
pending text and limits.

### 3. The settlement barrier

A receipt's commit isn't the end of its turn. Before any later
overlapping save, receipt or flush is submitted, the loop applies:
- `Commerce.committed`;
- `after_settle` and any deferred work;
- the re-recording of queued saves.

Later saves are re-frozen from the settled player. An older snapshot
must never overwrite a durable reward. The `can_commit` deletion check
runs before dispatch. Deleting the recipients of a receipt still in
flight waits until it settles.

### 4. Reads off the loop

- Startup reads (origin, character state, metadata) come back from the
  worker's bootstrap as snapshots.
- `status`'s season lookup and authentication's `Storage.banned` read
  from a loop-side cache.
- A committed change to metadata or a ban updates that cache on the
  loop before it is acknowledged.

### 5. What callers see while waiting

- Nothing appears before its commit: no item, debit, credit,
  attachment, report acknowledgement or reward.
- Input and views that don't conflict keep flowing.
- A disconnect can't cancel an outcome that is already durable.
- **Pending combat.** The deferred second shot, which today drains
  synchronously from `Commerce.committed`, may now wait several ticks.
  Its legality and liveness checks run when it actually executes. If
  tests show a change in what players see, such as a dropped shot or a
  burst, stop and bring it to the technical lead. Don't choose a new
  combat rule in this slice.

### 6. Failures and shutdown

- The worker returns a typed success or error for each command.
  - A failed commit rolls back and keeps its original error.
  - A failed commerce write settles false.
  - A rejected create restores the earlier dirty map.
  - A failed flush keeps its dirty state, without an endless retry.
  - Fatal errors still reach the server's stop path.
- A commit whose reply is lost is an unknown outcome. Never report it
  as rolled back, and never retry it automatically.
- Shutdown:
  - stop admissions;
  - freeze the sleeper snapshots;
  - drain accepted work within the existing single 10 s total deadline;
  - close on the owner thread.
- Never close the connection from another thread, and never release the
  lease explicitly while the writer can still write.
- **At the hard deadline, the process exits** (architecture §3.4: "Hard
  limit 10 s, then exit anyway; persistence is crash-safe").
  - Cancelling a future doesn't cancel an fsync, so the worker must not
    keep the interpreter alive past the deadline. Make it a daemon
    thread, or end the process explicitly.
  - The OS drops the lease with the process. No live write survives it.
  - On restart, WAL recovery applies. Anything not acknowledged counts
    as not committed, and a commit whose reply was lost follows the
    unknown-outcome rule above.
  - A stop that hits the deadline logs which commands were still queued
    or in flight.

### 7. Canon

AGENTS.md §2: canon changes first, in the same PR. The implementation
PR updates architecture:
- **§6.2:** the line "SQLite in WAL mode with a single writer task" now
  names the connection-owning worker thread. It also gets the one
  ordered queue, the settlement barrier and the loop-side read cache.
- **§3.4:** the stop sequence drains the writer queue within the
  existing 10 s, then exits as in §6.

This filing doesn't edit canon. It names the edits the build must make.
Until then, read "single writer task" in §6.2 as this owner thread, not
an asyncio task.

## Out of scope

- The checkpoint-only alternative from the S40 note. Use it only if the
  worker can't be made safe, and with the technical lead's agreement.
- Any change to the S11 gate, the interim CPU rule (#194), or game
  rules.
- Online backup. It belongs to the worker later, as a queued operation.

## Tests

Deterministic, with manual completion gates and no sleeps:
- Hold a commit while ticks advance. No early reward, attach, report or
  admin success, and the loop keeps ticking.
- FIFO across ordinary saves, then a receipt, then saves after its
  callback.
- Races between deletion or disconnect and an in-flight receipt.
- The deferred second shot: legality, duplicates and cooldown across a
  held commit.
- A rejected create never flushes later.
- Rollback, fatal flush errors and lost replies.
- A shutdown drain that succeeds, and a held commit that hits the
  deadline.
- Restarts against real storage, with a crash before commit, after
  commit but before the callback, and with ordinary state still queued.
  No acknowledged reward is lost, no stale overwrite happens, and no
  source settles twice.
- A test that fails if any SQLite call runs on the loop thread after
  admission.

## Definition of done

Roadmap §7, plus:
- S11 passes at both sizes. The PR reports the writes segment's wall
  time per tick, which should now be near its CPU time.
- S10, S24 and the persistence suites pass.
- Every write path above is listed in the PR with its new owner.

This changes runtime code, so under #194 a CPU near miss blocks. After
this slice, a stall like the four above should no longer show up in
S11. If one does, the technical lead looks into it before ruling.

H1 and S25 layout approval are not part of this slice and aren't
granted by it.
