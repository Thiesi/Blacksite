# P8 — Voice and ambience: one emitter for barks and zone ambience

**Status:** done (PR #230)
**Primary model:** Claude Opus 5.5 (the engineer) · **Reviewer:** automated review, technical lead, presentation lead (presentation acceptance)
**Depends on:** P4, S27 engine (both merged) · **Milestone:** presentation track
**Issue:** https://github.com/Thiesi/Karst41/issues/209

Canon: architecture 5.5.3 (log kinds and the ambient emitter), game
design 13.4 (barks), terminal UI 2.5 (log rules). Plan 03 §P8 sets the
purpose. Where this file and canon differ, canon wins.

## Goal

The place should speak without drowning danger. On `main` it is
silent:
- the S27 bark scheduler (`server/dialogue.py` `BarkScheduler`) exists
  but nothing calls it (`dialogue_runtime.py`: "dormant until P8");
- the authored zone ambience in `looks/*.json` (`ambient`, for example
  three Sodium Row lines) is loaded but never emitted.

In round 3 the owner called the Row's barks "pretty much right
spot-on". The demo spoke through a demo-only path (`demo_speech`, on
`demo/sodium-row-round3`). This slice gives `main` the real path. The
demo is a guide only.

## Scope

### 1. One emitter

- One ambient emitter per zone instance serves both sources: talker
  barks and the zone's `looks.ambient` lines. Nothing else emits
  ambient lines.
- **Its own random stream,** derived per zone instance, for example
  from the zone instance id and a fixed salt. It never draws from
  `zone.rng`, so the simulation's draws and P3's digest don't move
  because ambience exists.
- It runs on ticks (AGENTS.md §4), with no wall-clock reads, so tests
  step it without sleeping.
- Session state is dropped on detach. Reconnect never replays ambience.

### 2. Barks

- Barks follow game design 13.4: a player within six tiles
  (`BARK_RADIUS`), the talker's interval (90 s by default, or the
  authored `min_interval_seconds`), silence while anyone is
  interacting with that talker, and the authored weights.
- A bark is speech: kind `speech`, with `speaker` and `speaker_role`
  as presented to **that recipient** (5.5.4). A covered NPC barks under
  its cover name and presented class to callers it hasn't acted
  against. A caller it has revealed itself to (it attacked, arrested or
  hunted them) sees its true name and class, consistent with the rest
  of that caller's view.
- Only talkers with active dialogue and an NPC in the zone bark. On
  `main` that is the Sodium regulars (`row-street-regular`). Other
  speakers arrive with their content.

### 3. Zone ambience

- A zone with `looks.ambient` emits one of its lines to callers in it
  now and then, as kind `ambient`.
- The cadence is a per-zone constant in code for this slice. Pick one
  that keeps the Row lively without nagging, for example at most one
  ambient line per caller per minute, and state it in the PR.

### 4. Budget and suppression

- **Per-caller budget:** across barks and ambience together, a caller
  receives at most one line per N seconds (state N; propose a value).
  Lines over budget are dropped, never queued.
- **Who pays for a drop.** A talker's interval and its weighted pick are
  consumed when the scheduler fires, whether or not any recipient
  receives the line. The budget and suppression are then applied per
  recipient at emit time: one bark can reach some callers and be dropped
  for others. So a busy spot thins out instead of bursting when the
  budget reopens, and no talker retries every tick.
- **Suppressed** for a caller in combat (threatened, a DANGER state, a
  hazard) or travelling. The canon wording is "suppressed in combat
  and travel".
- **Never pushes danger out:** no ambient or bark line pushes a
  `danger` or `combat` line out of view within ten seconds (5.5.3,
  terminal UI 2.5). Use P12's whole-entry log rule if it has merged;
  otherwise implement against today's rule and note it.

## Out of scope

- The log verbosity setting: S30b, per plan 03.
- New bark or ambience content. Lines arrive with their speakers (S44's
  enforcers, the creative lead's population PR).
- Any change to talk pages, notices or S44's rules.

## Tests

- The emitter never draws from `zone.rng`: the draw count per tick is
  unchanged with ambience on, and P3's 10,704-case digest and the
  mechanics fingerprint don't move.
- Barks:
  - radius, interval, authored interval and weights;
  - silence while a talker is in use;
  - a covered NPC barks under its cover name and class to an unrevealed
    caller, and under its true name and class to a caller it revealed
    itself to, in the same tick.
- Drops: a dropped bark still consumes its talker's interval; with
  several talkers in range and the budget full, nothing bursts when the
  budget reopens; one bark reaches one caller and is dropped for another
  whose budget is spent.
- Zone ambience: emitted only in zones that author it, at the stated
  cadence.
- Budget: one line per caller per N seconds across both sources;
  over-budget lines are dropped.
- Suppression: none while threatened or travelling.
- Log: a danger or combat line stays in view for 10 s with ambience
  flowing. Goldens at 80x24 and 132x50 in both renderers.
- Reconnect: no ambience replay, and session state is cleared on
  detach.
- Determinism: the same seed and inputs give the same lines on the same
  ticks.

## Definition of done

Roadmap §7, plus native evidence through NetBBS Telnet to native stdio
at 80x24 and 132x50, in all three tiers: stand on Sodium Row and see a
regular's bark and a Row ambience line arrive, then see them stop
during combat. The presentation lead accepts from the captures,
against plan 03 §10.3 item 8. S10, S11 and S24 still pass. This is
runtime-changing, so under #194 a CPU near miss blocks. (Since 2026-11-12, owner: S11 blocks at p99 20 ms and warns from 10 ms; #194's interim rule has ended. See #229.) Keep the
emitter cheap and say what it costs.

H1 and S25 layout approval are not part of this slice and aren't granted
by it.

## Implementation notes (PR #230)

- **The emitter.** `server/ambience.py`, owned by the dialogue runtime,
  runs once a second (every P8 number is whole seconds). Each zone
  instance has its own `Random` seeded from `sha256(salt + zone id)`. It
  never touches `zone.rng`, and a test shows the zones' `zone.rng` states
  are identical with the emitter on or off.
- **One gate.** `Ambience.admit(session, tick)` holds the per-caller
  budget and every suppression in one function. S48's runner can call it
  and decide whether its lines pay into the budget.
- **Numbers.** Technical lead accepted these as proposed.
  - N = 20 s: one bark or ambient line per caller per 20 s.
  - Zone ambience: once every 60 s plus 0–30 s from the zone's stream.
  - Danger hold: 10 s.
- **Suppression** reads server state only:
  - travelling;
  - a channel;
  - a hostile presented target;
  - a hazard warning in sight;
  - a down or dead stage;
  - 10 s after any danger or combat line sent to that caller, from a
    per-session `danger_serial`.
  HUNTED or MARKED alone does not suppress. The server-side hold
  complements P12's whole-entry rule (which covers the presentation
  renderer); it also protects the default renderer, which has no such
  rule.
- **Barks.**
  - Each NPC instance keeps its own interval (`BarkScheduler.choose`
    gains `key`).
  - A bark speaks through `sim.speak`, so disclosure follows
    `revealed_to`, S44's truce reveals included.
  - Silent while any caller has that talker's page open.
- **No replay.** `emit(..., replay=False)` keeps barks and ambience out of
  the session ring, so reconnect never replays them. Emitter state is
  dropped on detach.
- **Cost.** Measured in CI by the `p8-cost` job
  (`scripts/measure_p8_cost.py`): about 5 µs a tick averaged, 0.2–0.4% of
  the headless loop, on the shipped Row with one and three callers.
- **Evidence.** `scripts/accept_p8_netbbs.py` and
  `.github/workflows/p8-acceptance.yml`.
