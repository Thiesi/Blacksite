# S35 — The away report: persisted public records and the login screen

**Status:** planned (approved by the owner 2026-10-31)
**Primary model:** Codex · **Reviewer:** automated review, technical lead, presentation lead (screen, wording and disclosure)
**Depends on:** S34 · **Milestone:** asynchronous presence (#125)
**Issue:** https://github.com/Thiesi/Blacksite/issues/137

Canon: game design §11.1, "The away report", from #128. Where this file
and canon differ, canon wins.

**Timing (owner, 2026-10-31):** starts after H1, beside C1 and S25c.
Until P10's cutover, every view is built in both presentations.

## Goal

A player who logs in after an hour or more away sees, on one screen,
what happened while they were gone: their own pending business first,
then the public world. Nothing in it reveals more than sitrep and the
public logs already showed.

## Spec references

- Game design §11.1 (the away report, every sub-bullet), §10.1
  (retirement re-keying), §11 (sitrep), §7.6 (Marked zones are a
  Wardens benefit), §6.4 (apartment-theft notice).
- Architecture §5.5.4 (disclosure), §6.2 (persistence), §15.3
  (delivery boundaries).
- Terminal UI §7 (screens outside play), §11 (journal).
- Build notes on #125 (the presentation lead's screen design and
  wording).

## Scope

- **Record store.** A migration (numbered in merge order): a typed, append-only
  table of public records and addressed records, keyed by character
  for addressed ones. This slice adds the writers for features already
  built: relay changes (S21), new Marks (S20), convoy and Ring-fall
  outcomes (S24), crew deaths, the apartment-theft notice (S18), and
  every S34 record. Features built later add their own writer in their
  own slice: public service repairs with allocation and repairer (the
  Grid build slice), dead drops (S37), and anything else the report
  canon lists. A missing writer means that kind is absent from the
  report, never a wrong line. Each record is written in the same transaction as the
  receipt or public log line it mirrors. Records older than 14 days are
  pruned daily.
- **Retirement re-keying.** At retirement, records naming the retired
  character show it as "a resident" from then on, even if the name is
  later reused.
- **The report.** Built at login when the last logout was at least an
  hour ago, looking back to that logout and at most 14 days. Addressed
  items come first, each kind collapsed to one line with a count and
  the next expiry. Public lines follow, newest first, to 12 lines in
  all; a cut report ends with "Older events are not shown". An empty
  report is skipped.
- **Disclosure filter.** No tile positions, no Marked players' zones
  unless the reader is a Warden with that benefit, nothing from
  housing interiors, unvisited zones and cells named by district only,
  and no line naming a character the reader ignores.
- **Journal.** The report shown at login is kept in the journal for
  7 days from that login.

## Out of scope

- Records for tags (S36 has none) and dead drops (S37 adds its own).
- Any new public log line. The report draws only on records the server
  already produces.

## Protocol and view models

- `AwayReportView {since, lines[{kind, text, when, count?,
  next_expiry?}], truncated}`, sent once after login before the first
  `ZoneView`. Any key dismisses it.
- A journal tab entry with the stored report.
- It is a full-width text view, never world log lines or a notice.
  Times are in words ("last night", "two days ago").

## Tests

- Each writer produces exactly one record, in its receipt's
  transaction; a rolled-back action leaves none.
- Window: under an hour away shows nothing; the look-back stops at the
  last logout and at 14 days; pruning on a fake clock.
- Ordering, collapsing with counts and next expiry, the 12-line cap and
  the truncation line.
- Disclosure: one test per rule above, including a Warden and a
  non-Warden reading the same Mark, an ignored character's line, and a
  zone the reader never visited.
- Retirement re-keying, including a reused name.
- Goldens at 80x24 and 132x50 for an empty, a short and a truncated
  report.

## Acceptance script

1. A and B are in a crew. B logs out. A captures a relay, repairs a
   public service and dies in a fight. B logs in two hours later and
   sees each, in words, newest first, after any addressed items.
2. B has three invitations: one line reads "3 invitations; the next
   ends in 2 days".
3. A Marked player's zone is absent from a non-Warden's report.
4. Logging in again within the hour shows no report; the journal still
   holds the last one.

## Definition of done

Roadmap §7, plus: the disclosure tests pass and the presentation lead
signs off the screen and wording.

## Implementer notes

- The world log ring stays in memory; do not persist it. The record
  store is separate and holds only what the report may show.
- Write the record with its receipt, never from a later flush, or a
  crash could show a player something that did not happen.
