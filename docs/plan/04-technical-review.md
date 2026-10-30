# Technical review

Every implementation PR gets two reviews before it is merged:

1. The **automated Claude review** (`.github/workflows/claude-code-review.yml`)
   checks ordinary code correctness. It is unchanged by this document.
2. The **technical review** checks the PR against the whole project:
   the slice spec, canon, the approved presentation and interaction
   design, shared abstractions, player experience and integration. The
   technical lead does it.

Neither review replaces the other, and neither replaces a human gate.
The owner alone grants human acceptance gates (including S25's withheld
layout approval). The owner merges, or the technical lead merges under
the delegation in §7.1.

## 1. Scope

The technical review applies to every PR that changes code, content,
canon or a slice file: slices, foundation and content PRs, and fixes
such as #67. It does not apply to design proposals (for example #69 and
#70), which go to the owner; the technical lead comments on their
engineering consequences instead.

## 2. Requesting a review

Nothing starts a review automatically (see §8). A review happens when
it is requested:

1. The PR author, usually Codex, pushes the head to be reviewed, waits
   for the automated review and triages it as `AGENTS.md` §3 says.
2. The author adds the label `needs-technical-review` and posts a PR
   comment `Technical review requested at <head SHA>`, listing the
   evidence in §4 or saying which of it is missing.
3. The owner tells the technical lead session, or the technical lead
   finds the label when it next lists open PRs. Nothing reviews a PR
   while no technical lead session is running; a request waits until one
   is.
4. The technical lead posts a decision record (§6) and removes the
   label. A record of `changes required` is answered by a new push and a
   new request.

## 3. What the reviewer reads

Before every review, refresh the PR state, its head and its base, and
review the current head in a clean worktree, never a stale checkout or
an earlier review's notes. Then read:

- the slice file and its acceptance criteria, its dependencies, and the
  roadmap entries and gates that name it;
- the canon the change touches, top-down: bible, game design, entities,
  architecture, terminal UI, assets, world expansions;
- the approved presentation and interaction design. Approved means
  adopted into canon or recorded as an owner decision. A proposal is
  context, not a contract;
- the existing implementations and shared abstractions the change uses
  or should use;
- the diff and its effect beyond the modified files: callers, views,
  persistence, protocol, other slices' acceptance;
- test results, the automated review and its triage, captures and
  acceptance evidence.

## 4. Evidence the PR supplies

| Change | Evidence |
|---|---|
| Any | `pytest` result at the head; the automated review and its triage. |
| Caller-facing | The slice's acceptance script through a NetBBS node at 80x24 and one larger size (roadmap §7), and what was run on which transport. |
| Visible on screen | Captures of the affected screens at 80x24 and 132x50, in truecolor, 256 and 16 colours, taken from live play rather than a composed frame, and named by scenario. |
| A significant player experience, new or changed | A representative playable acceptance scenario: a written sequence of steps a person plays from a stated starting point, with the expected result at each step. |
| Rules, numbers or protocol | The canon section changed in the same PR, and any fingerprint or golden rebaseline named and justified. |

Where evidence lives:

- **Commit to the repository:**
  - the plain-text renderings of captures (`.txt`);
  - a manifest naming each capture, its scenario and its SHA-256;
  - small JSON summaries.
- **Keep as CI artifacts:** raw `.ans` streams and large JSON snapshots. Name them from the manifest by run and artifact.
- **Size limit:** a PR adds at most about 200 KB of evidence to the repository, unless the review explains why it needs more.

Missing evidence is never a pass. The reviewer records it as
`insufficient evidence`.

## 5. What the reviewer checks

### 5.1 Engineering and architecture

- The slice delivers its acceptance criteria, and nothing outside its
  scope (`AGENTS.md` §8: do not widen a slice).
- Established behaviour elsewhere is preserved.
- Shared services and abstractions are used rather than duplicated. A
  second copy of common behaviour (layout geometry, focus, chrome, RNG,
  log emission) is a finding.
- Architectural boundaries hold: server authority, no runtime
  dependency, `world.db` only through the storage layer, door and server
  separation, determinism through each zone's seeded RNG.
- Security, concurrency, persistence, simulation and performance
  requirements are met, including frame byte budgets.
- Complexity and maintenance debt are proportionate.

A local problem may point to a broader weakness. The reviewer
establishes whether that weakness actually exists before saying so. If
it does, and reaches beyond the slice, it becomes a separate foundation
issue planned once at the right level, not a refactor forced into the
current PR, and not a fix repeated screen by screen.

### 5.2 Presentation and player experience

For every player-facing change the reviewer looks at real terminal
output where practical, at the supported sizes and colour tiers, and
asks:

- Does each location have a recognisable identity, and does its
  treatment express the world bible rather than only encoding state?
- Can the player tell where they are, what they can do, who and what is
  near, and what just happened?
- Are threats, objectives, consequences and interactions legible?
- Does anything reveal hidden information: an unseen tile, a disguised
  allegiance, a hidden exit, a private interior?
- Is it coherent with existing screens, keys and interactions?
- Does atmosphere stay out of the way of time-sensitive actions?

A correct map of undifferentiated floor is not acceptable because
navigation, collision and validation pass. A beautiful capture is not
enough if play is hard to read or control.

Creative sign-off belongs to the presentation lead. The technical
review checks compliance with what has been approved; if the two leads
disagree, the owner decides.

### 5.3 Integration and the plan

If an approved decision changes future work, the reviewer updates the
roadmap, the slice files and the dependency graph, top-down and in the
same change as the canon they follow.

## 6. Decision record

One record per reviewed head, posted as a PR comment. The first line
must be the heading below with the **full 40-character head SHA**, and
the recommendation line must keep its exact form: the merge gate (§8)
reads both.

```markdown
## Technical review: <slice ID> at <head SHA>

Base <base SHA>. Reviewed <date>. Previous record: <link or "none">.

| Area | Result |
|---|---|
| Engineering correctness | pass / fail / insufficient evidence |
| Architecture and integration | pass / fail / insufficient evidence |
| Presentation compliance | pass / fail / insufficient evidence / not applicable |

**Acceptance tests.** Each required test and its status: verified by the
reviewer (what was run, where), reported by the author (not
re-run), or missing.

**Human decisions and approvals outstanding.** Gates only the owner can
grant, and decisions the PR depends on.

**Findings.**

- **TR-n, Blocking / Important / Advisory.** Observed: what happens,
  with a link or a capture. Expected: the contract it breaks, with its
  source. Scope: who or what is affected. Correction: what would fix it.
  Mark which statements are inferences rather than observations.

**Carried over.** Earlier findings now resolved, and findings deferred
with their justification and the issue that holds them. They are not
repeated as new findings.

**Recommendation.** Ready to merge / changes required / awaiting
evidence or approval.
```

Severity follows practical consequence:

- **Blocking:** breaks an approved design contract or real gameplay,
  compromises security or data integrity, is a credible severe
  regression, or fails required acceptance.
- **Important:** a significant usability, presentation, architectural or
  maintainability defect to resolve before the slice counts as complete.
- **Advisory:** worth doing, not worth blocking for.
- **Not actionable:** possible in theory, with no credible scenario or
  consequence. Not reported.

Rules for the reviewer:

- Report observations and inferences separately. Never claim to have
  run a test or played a scenario that was not run.
- Few, real findings. No speculative lists.
- When the author disputes a finding and cites design intent, read the
  canonical source before insisting. The aim is a better game, not
  winning an argument.
- After substantive corrections, review the new head, not the original
  diff.
- "Ready to merge" means nothing in this review blocks it. It is not a
  merge, and it does not grant any human gate.

## 7. Order before merge

1. CI green at the head.
2. Automated review delivered and triaged (`AGENTS.md` §3).
3. Technical review record at the same head: ready to merge.
4. Human gates the slice names, granted by the owner.
5. The owner merges, or the technical lead merges under §7.1.

A push after step 3 that changes code, content or canon needs a new
record. A push that only marks the slice file done or fixes a typo in a
PR-local document does not need a new review: the technical lead edits
the record's heading to the new SHA and notes why, which re-runs the
gate.

### 7.1 Delegated merge

Decided by the owner on 2026-10-30. The technical lead may merge a PR
only when every condition holds at the current head:

1. **Record.** The technical review record says ready to merge at that
   exact head SHA, against the current base. A record retargeted under
   §7 counts only if its retarget note lists every file the push changed
   and each change is a slice-done mark or a typo; otherwise a new
   review is needed. For the technical lead's
   own docs and process PRs, which have no independent technical review,
   the automated review is triaged and either the presentation lead has
   co-signed on the PR or the owner has applied `no-technical-review`.
   An own PR that touches presentation canon needs the presentation
   lead's co-sign in every case. On a PR that does not touch
   presentation, that co-sign covers wording and presentation effect;
   it is not an independent technical review. A co-sign or sign-off is
   an explicit, unconditional approval on the PR; "Presentation lead:
   hold" with a reason is an open objection under condition 5.
2. **Green.** CI is green and the automated review is triaged.
3. **No owner matter.** The PR needs no human gate, changes no game
   bible or game design canon (`AGENTS.md` §2 levels 1 and 2), files or
   re-scopes no slice, changes no adopted plan decision, and moves no
   golden or fingerprint beyond what its slice explicitly allows. A
   class E canon or spec change (plan §10.1) also needs the owner's
   approval of its substance, recorded on the PR or its issue. A PR
   that changes the merge rules themselves always waits for the owner:
   §7, §7.1, §8 and the gate script and workflow, the
   `no-technical-review` rule, the review rules in `AGENTS.md` §3, or
   the roles in plan §8.
4. **Presentation.** A presentation-class PR (plan §10.1 class C) has
   the presentation lead's written sign-off on the PR.
5. **No objection.** No reviewer, agent or the owner has an open
   objection or an unanswered question on the PR.

If any condition is missing, the PR waits for the owner. The technical
lead merges with a squash merge. Afterwards it posts a one-line note on
the PR and on the queue issue (#82), and reports each merge to the owner.
The note links, by URL, the record or co-sign and any owner approval it
relied on. Each must be dated after the last push that changed content;
a co-sign or approval given on an earlier head does not carry over.
Every agent posts through the owner's account, so these links are the
audit trail.
The owner can narrow or revoke this delegation at any time. It never
grants a human gate: S25's human layout approval stays withheld until
the owner grants it.

## 8. Automation

### 8.1 Merge gate (built)

`.github/workflows/technical-review-gate.yml` runs
`scripts/technical_review_gate.py` whenever a PR is opened, pushed,
labelled or commented on. It sets the commit status `technical-review`
on the PR head:

| State | When |
|---|---|
| pending | No record names the current head SHA, or the latest one says "awaiting evidence or approval". |
| success | The latest record for the current head says "ready to merge", or the PR carries the label `no-technical-review`. |
| failure | The latest record for the current head says "changes required", or has no recognised recommendation. |

Only comments from the repository owner's account count, and bots never
do, so the automated Claude review cannot satisfy the gate. Every agent
posts through the owner's account, so collaborators added later cannot
post a record that counts. The gate always
runs the script from `main`, so a PR cannot change the rule that judges
it.

Limits:

- **It enforces the procedure, not the review.** It reads a comment; it
  does not check that a review took place.
- **Authorship.** The technical lead and the coding agents post through
  the owner's account, so the gate cannot tell who wrote a record. Only
  the technical lead writes records, and only the owner applies
  `no-technical-review`, used for PRs outside §1's scope such as design
  proposals and process changes. That rule is in `AGENTS.md`; the gate
  does not check who applied the label, and the label exempts every
  later head of that PR until it is removed.
- **Blocking needs branch protection.** The status only blocks a merge
  if branch protection on `main` requires `technical-review`. That is the
  owner's setting.
- PRs opened before the gate existed get a status on their next push,
  label change or comment.

### 8.2 Not built

1. **Label-triggered review in CI.** A second `claude-code-action` job,
   started by the `needs-technical-review` label, given this document
   as its prompt. It could read canon and the diff and run headless door
   captures. It could not run NetBBS transports, play a scenario or know
   decisions that are not committed, so its record would have to say
   so, and it would add cost per review. Worth trying only after the
   manual procedure has run on a few PRs.
2. **A scheduled check by a local session.** A technical lead session
   that lists labelled PRs on a schedule. It works only while that
   machine and session run, so it must not be described as continuous
   coverage.

Until one of these exists and has been seen working, review coverage is
exactly §2: a review happens when it is requested and a technical lead
session runs. The gate in 8.1 only makes a missing review visible.
