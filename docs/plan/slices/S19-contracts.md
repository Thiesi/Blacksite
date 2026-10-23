# S19 — Contracts: template engine, six types, boards, crew scaling, story chains, Vesper

**Status:** in progress (PR #62)
**Primary model:** Opus (engine) · **Reviewer:** Gemini or Sonnet writes the content half from the world docs; Opus reviews it
**Depends on:** S11, S14, S15, S16, S22 · **Milestone:** M3
**Issue:** https://github.com/Thiesi/blacksite/issues/19

## Goal

Build replayable jobs whose physical and Lattice actions produce visible
consequences: six composable verbs, evidence, branch receipts and four
public service work orders. Deliver Vesper's first job and author the
Season 1 chains for activation with the complete world in S26.

## Spec references

Game design sections 7.5, 9 and 18; entity model sections 1.10, 2.7,
2.12-2.13; architecture section 15; terminal UI section 11; world story
arcs for Vesper, all eight Season 1 chains and their attributed evidence.

## Scope

- `server/contracts/engine.py`: deterministic template instantiation,
  resolved target pools, frozen rosters, offered/active/complete/failed/
  turned-in states, retries, limits, expiry and atomic reward receipts.
  Implement the board/reward schedules exactly from game design 9.
- Compose fetch, hack, escort, clear, plant and survey stages. Clear
  declares lethal/subdue resolution; escort uses willing mission actors
  who wait at their source positions until recruited;
  survey can inspect a labelled object, compare recorded IDs or observe
  telemetry. No natural-language input or moral-answer scoring.
- Keyed mission data is scoped to its instance and roster, persisted
  through restart and removed on expiry; other players' evidence and
  public core loot are separate. Supplied items are bound and cannot be
  sold, stockpiled or consumed by someone outside the job.
- Generated objectives scale by the frozen accepted roster; rewards
  use the documented factor, paid once to that roster under participation
  rules. Joining for turn-in cannot add an eligible recipient. Story
  forks and work orders use their fixed listed rewards.
- Evidence journal records observation, source claim, location, open
  question and next action separately. Inspecting acquires the record;
  reading its optional prose is not required. Publication shows its
  exact route/credential/standing consequence before commitment.
- Mutually exclusive choices share a branch-group receipt. A replay,
  another handler, another crew or reconnect cannot collect both sides.
  Explicit multi-faction deltas do not also propagate by relationship;
  ordinary single-faction deltas use design 9.3's rule once.
- Implement the four service-node state machines from design 7.5:
  normal, fault, repairing, allocated; uptime timers, bounded reservation,
  NPC restoration, supplied units, public/worker layouts and expiry.
  Use S15 typed controls; changing allocation updates the actual map or
  service and journal, with warning/escape. Minimum clinics, food, water,
  public uplinks and outward travel never become rewards to withhold.
- Boards at halls and Tin Halo, Vesper's non-member pool and six own
  templates. New Wakes complete the equal-reward two-route first job.
  First-job evidence and costs appear in the default compact UI.
- Author at least three generated templates per faction and all Season
  1 chains. Bundle manifests distinguish usable hub jobs from inactive
  authored chains awaiting S25 maps and S27 dialogue. S26 activates the
  complete validated Season 1 bundle; nothing live may dangle.

## Out of scope

S20 consumes standing deltas and membership; S24 schedules world events;
S25 authors remaining city maps; S27 supplies named dialogue; S26 owns
season settlement and integrated story-chain acceptance. This slice
implements all contract/work-order logic and fixture scenarios now.

Implementation decisions (game design 7.5/9 and architecture 15.2):
crew proposals hold no public order; reservation and accepted roster freeze
on the first committed start. Disconnect preserves progress to the original
deadline. The final repair action commits allocation and fixed worker
rewards together, composing over any ordinary source reward. Clinic fee
changes require a fresh confirmation; Depot cap changes retain hourly
spending across allocation expiry and restart. Budget details use meta in
the existing transaction without a SQL schema change. Source callbacks
finalize before deferred impacts can propose another write.

Plant procedures consume bound supplies only in the source write after
the canonical channel. Physical pickups and mission item lifts support
replacement by original workers; benign linked releases remain available
only for missing-supply recovery. Resumable generated/story jobs stay in
the journal after withdrawal, preserving frozen terms and earlier stages.
Story settlement checks completed-template receipts again across parallel
crew copies. Historical publication quotes retain the paid option.

## Data and protocol

The authored pool contains six Vesper commissions, three per faction,
all 33 Season 1 contracts and four service work orders. The first job,
generated hub commissions and Cold Chain use shipped maps. Story chains
and the three other services remain in authoring bundles. Their precise
map, source, dialogue and activation work is recorded in the
[content handoff](../s19-content-handoff.md).

Boards prefer distinct templates and Vesper brokers non-member generated
commissions at the Tin Halo, including their turn-in. This does not waive
story prerequisites. Network surveys use E at the actual cell/core room.
The Ferrymen race starts a disclosed 180-second recovery window at its
launch checkpoint; a retry requires launching again, without a live-event
wait. The shield branch publishes a bounded 20-minute local NPC patrol.

`contracts.json`, service-node records, evidence/text assets and bundle
manifests follow the entity schema. Menus expose offered/active/done,
record provenance, current objective, roster, consequence and expiry.
Use typed contract, evidence and work-order intents from architecture
15, with request ID/revision and atomic completion receipts.

## Tests

- Deterministic pool selection, five offers, 30-min refresh, three active
  generated jobs, 60-min expiry and nonexpiring story jobs.
- Every verb's progress/failure/retry path; subdue never counts a kill;
  willing escort and composed physical/Lattice stages.
- Frozen-roster scaling and participant rewards; no late-join or crew
  multiplication; no duplicate reward after commit failure/restart.
- Both branches of walked templates and ration discrepancy, independently:
  exact explicit standing/rewards, source claims, public effects/expiry,
  mutually exclusive receipts and continued main-story availability.
- Each work-order state and both allocations, unattended restoration,
  reservation race/expiry, bound supplies, map reachability, safe-body
  protection, stacked control layers and offline restart.
- Active bundle rejects missing references. Inactive future bundles
  cannot publish offers. All eight chains have resolved stage sequences
  and fixture execution; full shipped-map end-to-end acceptance is S26.

## Acceptance script

1. At 80x24 a fresh Wake follows the card to Vesper and completes the
   first job using its labelled physical route. A second Wake uses the
   Lattice route. Both receive the same stated base reward and evidence.
2. Two callers accept a generated four-target clear job: six required
   targets, both accepted participants receive their disclosed reward.
   Invite a third at turn-in and verify no added reward eligibility.
3. In the Sump fixture, reserve a public repair, carry the supplied unit,
   flip its controller and watch the dry route open with its expiry.
   Complete the worker variant separately; observe the salvage niche.
4. Exercise each other service fixture and both evidence forks. Inspect
   the Chronicle-independent journal; a second claimant/reconnect cannot
   repeat a payout or overwrite the completed branch.
5. End a session during a repair and after an acknowledged turn-in;
   reconnect to the recorded progress/reward without loss or duplication.

## Definition of done

The [earning receipt report](../../ops/s19-earnings.md) extends S16 with
actual job, loot-sale, core-cash and clinic-quote paths. Its session
cadence and gross affordability remain explicit assumptions, including
the difference between a crew lifter's personal cash and support income.
It preserves the complete-city human pacing gate after S25/S26.

S16 balance handoff: extend its assumed XP schedules with actual contract,
loot and vendor-sale chit income. Report time to afford canonical weapons,
implants, surgery and detox, distinguishing solo and crew earnings. Compare
jobs and runs with the street schedule so continuous low-risk combat does
not become the only efficient progression loop. Keep assumed activity
separate from measured human pacing; section 18's full-city playtests
remain required after S25/S26 integrate the remaining sources.

Roadmap section 7; all verbs, four service nodes and branch invariants
pass in fixtures, Vesper's job works in the shipped hub, and every
inactive Season 1 dependency is declared for S26 integration.


### S20 faction integration handoff

Reference: [PR #38](https://github.com/Thiesi/Blacksite/pull/38) and S20.

Use S20 Factions.standing_patch with Reward.standing_mode in the owning
reward transaction. Do not pay reputation from an after-commit notification.
Keep the program-source contract, acquisition guards and actual income
report from PR #38; membership never revokes already learned programs or
installed hardware.

Unmoored public board/recruiter use oldworks-main; hall/vat use oldworks-
drop. A board must not be derived from FactionSite.hall for this faction.

### S22 crew integration handoff

Reference: [PR #61](https://github.com/Thiesi/Blacksite/pull/61).

Use the live registry through `game.crews` / `progression.crew_of` as the
membership authority, then freeze the accepted objective roster in the
contract receipt. Later joins, kicks and leadership changes do not create
turn-in credit. Contract rewards own their roster/scaling transaction;
`Crews.add_rewards` intentionally handles kill/run XP only. Preserve the
PR #38 source/acquisition and actual-income obligations above.
