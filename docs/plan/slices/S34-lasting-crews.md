# S34 — Lasting crews: persistent rosters, offline invitations, notes and handoffs

**Status:** planned (approved by the owner 2026-10-31)
**Primary model:** Codex · **Reviewer:** automated review, technical lead, presentation lead (views and wording)
**Depends on:** S22, S19, S23 · **Milestone:** asynchronous presence (#125)
**Issue:** https://github.com/Thiesi/Blacksite/issues/136

Canon: game design §10.1 (lasting crews, notes and handoffs), from #128.
Where this file and canon differ, canon wins.

**Timing (owner, 2026-10-31):** starts after H1, beside C1 and S25c.
Until P10's cutover, every view is built in both presentations.

## Goal

A crew outlasts a session. Members keep their crew across logout and
restart, invite characters who are offline, leave each other notes, and
hand a generated job on to a crewmate with the reward divided fairly.
S22's live rules (pickup, beacon, friendly fire, loot modes, shared XP)
stay, applied to members who are online and present.

## Spec references

- Game design §10 (live crew rules), §10.1 (every bullet), §9.1
  (generated jobs: frozen terms, three-job limit, 60-minute expiry,
  shares paid at turn-in, retry rule), §3.5 (per-identity limits),
  §6.4 (prepared world-state timers), §2 (sleepers).
- Entities: the `crew_id` row (persisted once this slice is built) and
  the crew entity.
- Architecture §6.2 (persistence, flush triggers, migrations), §5.5.4
  (disclosure), §15.2 (atomic effects and restart).
- Terminal UI §2.4 (side panel), §4 (menus), §11 (job view, timers).
- [S22](S22-crews.md): this slice supersedes its "live-only, no table"
  note.

## Scope

- **Persistence.** A migration (numbered in merge order): crews (id, name, leader,
  acting leader, created, became-one-member date, loot mode), members
  (character, joined), name cooldowns (identity, name, frees at),
  invitations, notes and handoff offers. Crew state commits immediately
  on every membership, leadership, invitation, note and offer change,
  in one transaction with its receipt. Restart restores every crew.
- **Lasting roster and leadership.** Membership ends only by leaving,
  kick, retirement or dissolution. Leadership passes on leaving, not on
  logout. The 7-day inactivity handover is checked at every member's
  login. It is temporary: the original leader takes it back at login,
  and until then the acting leader cannot kick them or remove their
  notes. The 30-day all-inactive dissolution and the 14-day crew-of-one
  expiry run on a daily sweep and at login.
- **Naming.** Name rules, node-unique claim at acceptance, "name taken"
  failure, 7-day per-identity cooldown on a released name.
- **Offline invitations.** 7-day wait, the per-identity limit of 5 and
  one per target, a 10-invitation inbox, decline-all, and every recheck
  at acceptance. Ignored invitations never arrive and look to the
  sender exactly like delivered ones, including slot use and the
  full-inbox refusal. The sender may withdraw an invitation at any
  time, with the same result whether it was delivered or ignored.
- **Crew notes.** 20 notes of 200 characters, chat text rules and rate
  limit, author or leader removal, report coverage.
- **Handoffs.** Everything in §10.1's handoff bullets: eligibility
  (single participant, at least one stage done and one left, no live
  escort or open mission instance), at most two offers, the 24-hour
  window, escrow of stage-bound items, paused stage deadlines and
  60-minute expiry, acceptance rechecks, slot and room refusal,
  withdrawal on leaving the crew, and the divided reward at turn-in
  under each identity's own caps.
- **Dissolution and retirement.** Every route withdraws invitations
  and offers and returns offered jobs and items. Retirement ends
  membership. Escrowed items that no longer fit go to a free Kestrel
  collection. **This slice owns the free Kestrel collection record**
  (item instance, owner, reason, kept-until date; 30 days, then S23's
  impound rules) and its collection view at every Kestrel branch, built
  on S23's market collection. [S37](S37-dead-drops.md) reuses it for
  returned and withdrawn drops. Retirement hooks into character retirement (the existing character-delete path in
  `server/characters.py`, through its `before_delete` hook).
- **Admin CLI.** `crew list`, `crew show <name>`, `crew rename`,
  `crew dissolve`, `crew note remove`.
- **Away-report records.** Emit a typed record for every event the away
  report (S35) lists from this slice: invitation left, ended or name
  taken; offer accepted, withdrawn or expired; share paid, capped or
  forfeited; leadership passed or returned; removed from crew; crew
  dissolved; new notes. Records are written to S35's store when it
  exists, or kept in a table S35 adopts.

## Out of scope

- The away report screen itself (S35).
- Changing S22's live rules, loot modes or XP sharing.

## Protocol and view models

- `ZoneView.crew[]` gains `state` (`online`, `away`, `asleep`,
  `offline`) and `acting` for an acting leader. Absent members are
  shown dimmed with the state word, never by colour alone.
- `MenuView` kind `crew` gains pending invitations (received and sent),
  notes (a crew text view opened from the roster), and the leader's
  name controls.
- The job view shows an offer's state word and expiry, paused stage
  time and offers left.
- Wording: the presentation lead's build notes collected on #125 are
  the inputs. The presentation lead signs off the final text.

## Tests

- Persistence: a crew, its notes, invitations and an open offer survive
  a restart byte-identical; a failed commit leaves no partial state.
- Leadership: handover at 7 days, return at login, acting-leader limits,
  30-day and crew-of-one dissolution on a fake clock.
- Invitations: identity limits across characters, inbox of 10,
  decline-all, name claimed at acceptance, ignore indistinguishable to
  the sender (same result, same slots, same refusal), and withdrawal
  gives the same result either way and frees the slots.
- Handoffs: eligibility refusals, the two-offer limit whether or not
  delivered, escrow on offer, withdrawal and expiry return, deadline and
  expiry pause, fresh 60 minutes on acceptance, divided rewards with
  rounding and caps, forfeited share for a retired identity, items
  granted once.
- Dissolution and retirement by every route return jobs and items.
- Live rules: offline members and sleepers are never in loot rosters or
  XP; a sleeper keeps friendly-fire protection.
- Admin verbs, and view goldens at 80x24 and 132x50 in both
  presentations.

## Acceptance script

1. A invites B, who is offline, under the name "Night Shift". B logs in
   the next day, sees the invitation and accepts. The crew survives a
   server restart.
2. A writes a note; B reads it in the crew view; a non-member cannot
   see it anywhere.
3. A completes stage 1 of a generated job and offers it to B. The job
   shows `on offer` with its expiry. B accepts, finishes and turns in.
   A and B each get their share, paid at turn-in.
4. A stays away for 8 days. B logs in and leads, marked "acting". A
   logs in and leads again.
5. An ignored sender's invitation looks to the sender exactly like a
   delivered one.

## Definition of done

Roadmap §7, plus: the persistence and restart tests pass, the
presentation lead signs off views and wording, and S22's note is
updated to say this slice is built.

## Owner decisions

- **Sender withdrawal of an offline invitation:** allowed (2026-10-31),
  now in §10.1. It gives the same result whether or not the invitation
  was delivered or ignored, and frees the sender's slots. Wording from
  the presentation lead: "Withdraw your invitation to Name? (y/n)",
  then "Invitation withdrawn."

## Implementer notes

- Keep `crews.py` pure. Persistence belongs to the I/O layer, as for
  characters (architecture §6.2).
- Every ignore-related path returns the same result object to the
  sender. Test equality of the sender's whole view, not one field.
