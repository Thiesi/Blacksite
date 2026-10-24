# S26 — Seasons: Depth meter, descent consoles, leaderboards, the Chronicle, Blacksite level 1 (instanced zone and sector)

**Status:** planned
**Primary model:** Opus · **Reviewer:** Fable (level design and finale review before merge)
**Depends on:** S21, S19, S24, S25, S27, S22 · **Milestone:** M5
**Issue:** https://github.com/Thiesi/blacksite/issues/26

## Goal

<!-- presentation-review-hold:start -->

S25 human layout approval is **not granted** (user review, 2026-10-24).
[Issue #68](https://github.com/Thiesi/Blacksite/issues/68) requires a
separate comprehensive presentation review against the world bible and
terminal UI specification. Preserve the verified simulation/mechanics;
do not perform an ad hoc visual overhaul or treat technical validation,
navigation or mechanical receipts as visual acceptance. The
[review brief](../02-presentation-review.md) identifies independent
engineering acceptance and presentation-dependent work on hold.
This slice's completion cannot silently bypass the S25 human gate.

<!-- presentation-review-hold:end -->

Ship Season 1, The Exhale, as a complete playable bundle: contribution,
solo or crew expedition, individual choices and one durable public
settlement. Activate all eight story chains against the complete city.
A crew leader never chooses another player's name, standing or ballot.

## Spec references

Game design sections 9, 13 and 18; entity model 1.13, 2.8, 2.12 and 2.14;
architecture 15; terminal UI 11; story arcs Season 1 phase plan and
Chronicle voices. Main design 13.3 owns all outcome numbers and effects.

## Scope

- `server/seasons.py`: contribution receipts, configurable target,
  leaderboards, door state, expeditions, personal ballots, settlement,
  archive and operator advance. Default small-node target 10,000;
  standard 100,000 and large 250,000 are explicit operator presets.
  Each unique data/intact/key contributes 250/500/1,000 with one XP
  receipt; repeating the same source or transaction cannot multiply it.
- Consoles at all halls, Tin Halo and the season door accept Freelance
  players equally. Show target, contribution value, ranking, personal
  records, open/archive access and settlement status before actions.
- Freeze an expedition roster of 1-5 at entry. It is independent of
  social crew ID and leadership. At most four active instances with a
  FIFO queue. Every archetype can use a public loan rig and finish solo
  by using 120 s latches; a crew can operate physical/Lattice controls
  concurrently. Required tools are available before entering.
- Persist instance seed, roster, phase and checkpoint. Empty instances
  expire after 10 min; resume/restart rebuilds at safe entry from the
  last checkpoint without replaying loot or applying recovery death debt.
- Author `blacksite-l1` zone, sector and core as separate instanced
  content. The public Shaft's two hardware locations are not cloned into
  the expedition core. Build the four operational phases in story arcs:
  inspect, lamp/bypass latch, connector/isolation and activation record,
  then decision room. NPC/ICE counts and actions use design 18.
- The observer uses existing ICE classes; no undefined warden ICE.
  Alternate CUST/TEN lines are attributed and optional. Both registers
  receive the guaranteed line; balance changes optional weighting only.
- Each participant sees their own Seal/Open/Answer consequences, submits
  one ballot keyed by origin+BBS user+season and gets only their own
  stated standing/benefit. Answer publishes only their own consenting
  display name. Commit choice, personal journal, reward and receipt
  atomically; repeat visits may explore but cannot earn another ballot.
- At operator season advance, settle eligible votes by plurality. A tie
  or no votes has no world/balance change. Otherwise apply the winning
  delta once, clamped -3..+3; a zero delta preserves previous balance.
  Chronicle shows attributed expedition accounts, individual choices,
  dissent and the single settled result. Apply only the bounded public
  modifiers listed in design 13.3, never the last crew's flags.
- Freeze leaderboards and reset seasonal relay/influence counters while
  retaining identity, character progression and personal receipts. The
  suggested 90-day season never automatically closes unfinished work.
  Archived finales remain replayable under the archive rules. Missing
  next-season content parks progression between seasons, not into an
  unresolved map; the archived Season 1 story remains accessible.
- Integrate S19 story-chain manifests, S25 ordinary maps and S27 NPCs,
  dialogue and records. Validate and activate every Season 1 reference.
  Test both walked-template/ration forks and all eight chains end to end.
- Admin status, audited set-depth recovery aid, advance confirmation,
  Chronicle append (operator attribution), leaderboard export, archive
  status. No fake clock-changing production CLI for acceptance tests.

## Out of scope

Issue #56 BBS integration: authoritative in-game standings and committed
settlement facts remain available without outbound. A future optional
API-5 adapter may export one declared canonical metric, at most the
advertised rows and one local BBS identity per row; no undocumented sum
or remote identities. Clear the snapshot on reset and never replay old
awards on login. Publication failure cannot roll back a choice or reward.
Default registered-only admission conflicts with NetBBS's level-0
outbound requirement, so S31 records a disabled path until a compatible
guest-safe host contract exists. See `docs/plan/01-netbbs-platform.md`;
do not build filesystem callbacks into the season engine.

Season 2/3 playable bundles require future content slices and full
acceptance. Their lore/rules are specified now, but no flag may unlock a
missing map. Federation merge is S32; relay/event/contract engines are
existing dependencies, integrated here without alternative rule copies.

## Data and protocol

`seasons/1.json`, complete expedition zone/sector/core, contribution
items and receipt IDs, encounter records, Chronicle/evidence/voice
assets, branch groups and the active Season 1 bundle manifest. Use
`expedition.enter/resume`, `finale.choose`, contribution and Chronicle
menus with request IDs and expected revisions. The server owns every
cost, permission, ballot and computed result.

## Tests

- All target presets, unique contribution credit and Freelance access.
- Every archetype finishes a seeded solo route with the loan rig; 2-5
  participants use the same phase rules, bounded threats and safe exit.
- Four-instance cap, FIFO queue, fixed roster, disconnect/empty timeout,
  checkpoint rebuild and safe restart without debt or duplicate rewards.
- Five people choose independently; leader cannot submit for another.
  Same BBS identity via a new character/crew cannot acquire another vote.
- Exact Seal/Open/Answer personal deltas; no public modifier before
  settlement. Plurality, ties, zero delta at nonzero balance, clamp and
  repeated advance all behave exactly once.
- Inject failure at ballot and settlement commit boundaries. Reconnect
  returns the durable receipt or permits a clean retry, never half an
  outcome, double standing or a leaked unchosen name.
- Chronicle preserves dissent and source attribution; optional lines
  never omit an objective or claim the true identity of either voice.
- All eight Season 1 chains run on shipped maps, including explicit
  forks, nonlethal contracts, service layouts and stacked event effects.
- Archive/no-next-content retains story access and existing character
  state. Full-tree validator rejects every missing active reference.

## Acceptance script

1. At 80x24 on the 10,000 preset, a Freelance player delivers intact
   telemetry (500): Depth rises by 5 percentage points. Resend/reconnect
   cannot repeat the same source's contribution or XP.
2. Set Depth to 9,999 through the audited recovery command and deliver
   one valid data item. The public door opens for all eligible callers.
3. A fresh solo non-Ghost takes a loan rig and completes all four phases
   using visible action labels and latches, then chooses Answer. Verify
   only that identity's receipt and no premature public settlement.
4. On a separate fixture season, five callers complete an expedition:
   three Seal, one Open, one Answer. Verify each personal result, then
   advance: Seal settles once and Chronicle retains the dissent/name
   consent. Repeat advance and reconnect; no duplicated effect.
5. Repeat with tied ballots and nonzero prior balance: neither changes.
   Restart during a phase and resume safely; repeat a completed run with
   another crew and confirm no extra personal reward or ballot.
6. Walk every faction's Season 1 chain on actual maps; inspect both
   evidence forks in independent fixtures. Close the season without a
   Season 2 bundle; archived Season 1 remains usable.

## Definition of done

Roadmap section 7, Fable level/finale review, full Season 1 bundle and
all chains validated, solo plus multiplayer terminal acceptance at both
sizes, and recorded human pacing/challenge feedback. No claim that later
season bundles or the game balance are already complete.


### S20 faction integration handoff

Reference: [PR #38](https://github.com/Thiesi/Blacksite/pull/38) and S20.

Keep immutable event plan IDs and current rank eligibility when settling
event/season state. Expire Convoy reservations explicitly. Free Kin
information remains +90, with paid/public fallbacks. Seasonal relation
overrides compose at the shared relation source, without another
faction-membership authority.

### S22 crew integration handoff

Reference: [PR #61](https://github.com/Thiesi/Blacksite/pull/61).

Live crew IDs and five-minute Silt sharing do not identify a persistent
expedition. Freeze consenting player/identity IDs under the expedition's
own durable ID; retain individual ending/ballot choices. Leave, kick,
promotion, dissolution and service restart must not reassign ballots or
erase checkpoints. Preserve the accepted PR #38 personal/public outcome
and inactive later-season authoring requirements.

<!-- s19-services:start -->
### S19 source and service handoff

Reference: [S19 PR #62](https://github.com/Thiesi/Blacksite/pull/62),
[acceptance record](../../ops/s19-acceptance.md) and
[PR #38](https://github.com/Thiesi/Blacksite/pull/38).

S19 supplies the implemented source interfaces, 68 authored contracts
and four service nodes. Full root pytest passed 1344 tests with one
skip. Installed native acceptance covers both sizes and allocations,
forks, repair reconnect and paid restart. Consume the merged PR;
S25/S27/S26 still own real geography, referrals and activation.

Reuse the frozen consenting roster, personal branch receipts, source-
attributed journal and scoped permits. Public telemetry reveals NPC/ICE
routes, never players. A completed helper sees zero additional reward and
retains the earlier personal choice. Ordinary source XP and work-order XP
compose in one transaction; callbacks cannot pay again.
<!-- s19-services:end -->

S19 Silt source handoff: activate authored `mission_data` with its chain
bundle. Typed `silt_data` targets bind sector/band/data, and the actual
generated graph places a guaranteed visible copy. Keep mission custody,
stable source sites and journal evidence separate. Never replace these
with copied room coordinates or a rare-drop prerequisite. Permanent
story items required by a later contract belong to the explicit reward;
temporary lifted payloads retire with their owning job.

Activate the authored 33-contract Season 1 bundle only after the
[S19 content handoff](../s19-content-handoff.md), S25 map bindings and S27
neutral referrals pass integrated acceptance. Replay both paid forks
into their shared continuations. Verify the shield's public NPC route
expires without being extended by another worker. The Ferrymen recovery
has a checkpointed 180-second field window; disconnect/restart preserves
its deadline, failure returns to launch and recovered-item delivery is
untimed. Pure S19 receipt replays do not replace full-city human pacing.

Follow the [S21 relay handoff](../s21-relay-handoff.md): bind Shaft's
level-opening/telemetry provider and Outworks' floored Depth contribution
without extra XP or ballot. Join the relay cutoff/reset to the committed
season settlement, retaining earned treasury and rolling reward limits.
Close the S25/S26 human relay/earning/clinic pacing gate with actual play.

<!-- s24-handoff:start -->
### S24 event integration and acceptance handoff

Reference: [S24 #24](https://github.com/Thiesi/Blacksite/issues/24),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

Bind `Events.tuning(event_id, kind)` to committed season modifiers:
`weight` (1..10), `spawn_rate` (1..3), `wave_cap_bonus` (0..2), and
`surge_variants` (false disables swaps while other Surge effects remain).
The adapter owns bounds; season content owns option-to-effect mapping.
Use independent named geometry layers for optional seasonal routes;
event cancellation must preserve them. No finale-choice names belong
in S24's engine. Settlement joins the existing commerce receipt.

Consume the physical `key_undercity` once for its canonical contribution,
never its saved forecast or a fixture cache. S25's real Exhale route,
Convoy rewards and return-time measurements remain a prerequisite for
honest pacing assessment. Publicity remains behind #56's registered-only,
positive opt-in gate; gameplay warnings stay in game.
<!-- s24-handoff:end -->


<!-- s24-review-policy:start -->
### S24 practical review follow-up

Reference: [PR #65](https://github.com/Thiesi/Blacksite/pull/65), retaining
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and #56.

The hot event receipt retains 128 closed plans plus live/current
transitions. Personal forecasts retain 128 recent reads and compact final
outcomes. Retain any required long-term Chronicle facts in the season ledger
when they commit; do not reconstruct a season by scanning bounded recent
plans. A saved forecast is information, never another reward or contribution
source.
Retire instance-owned NPC spawn slots when the corresponding expedition
instance is retired/reset. Preserve pending death receipts and monotonic
spawn serials; do not retain one permanent slot set per historical
instance. S24's event cleanup does not own expedition lifecycle state.
<!-- s24-review-policy:end -->

<!-- s25-access:start -->
### S25 physical route access handoff

Reference: [S25 #25](https://github.com/Thiesi/Blacksite/issues/25),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and platform #56.
Game 5.6 and entities 1.1 now specify typed member/story credentials,
alternative requirements and a missing-credential message. This bounded
runtime support is necessary to commission the canonical physical city;
S25 otherwise remains content work. Missing NPC profiles use the
initial values documented in game 5.5 and require pacing acceptance.

Bind `Characters.route_permissions(player)` to committed story/season
sources. The Shaft cage (`shaft-cage`) remains closed in both directions
until the owning finale phase authorizes it; `halvard-service-lift` permits
the declared mission route. Define scope/lifetime from committed phase,
roster and mission receipts, never arbitrary progress flags. Preserve
already-departed journeys on expiry/restart. The season-door object must
show live Depth/Chronicle status when this slice lands.
<!-- s25-access:end -->

<!-- s25-city-decisions:start -->
### S25 commissioning decisions (in progress)

Reference: [S25 #25](https://github.com/Thiesi/Blacksite/issues/25),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

The draft uses game 5.6's carried key OR exact local open-latch state for
the optional Drowned bulkhead. Ordinary Outworks/Shaft Foot travel is
free; a key is retained, not consumed. Hidden physical exits allow
explicit Interact on their tile and never auto-travel on a walk. All
Undercity base sight is five before carried light. Whole-zone `pocket`
safety protects clinics, just as an authored pocket does.

The existing Terraces sector expands from 36 to 48 cells: a public
register wing supplies 24 distinct apartment addresses without reusing
entry/uplink cells or changing existing hidden/gated routes. Halvard's
member hall, vat and counter are in the Mezzanine; public recruitment,
care and banking remain in the Atrium. Three secondary ration/flare and
salvage counters bring ordinary vendors to 22; only Landing retains its
20% salvage premium. New NPC profiles and gantry damage are documented
initial values in game 5.5/6.4 and must pass actual-city pacing.

Use the same committed physical permissions and optional routes in
season missions. Do not reintroduce a consumed key or event wait on the
ordinary Shaft Foot approach. Measure the initial NPC grades and earning
loops during the required human pacing pass; refine canon if needed.

These are in-progress decisions, not a claim of merge, native acceptance
or completion of the Shaft Foot/Far Ring and broader human pacing gates.
The real walled apartments also exposed a geometry-admission bug:
a closed private door must not freeze unrelated public controls.
Housing supplies the occupant's explicit Interact-to-leave doorstep as
the escape origin; occupied tiles remain passable and private entry
permissions still apply. Retain that proof under tenants, visitors,
restart and overlapping effects. The Lobby's five inert private-door
props are replaced by the real 24-unit Block Street pool.

S25 places `ferrymen-corpse`, `choir-shrine`, `unmoored-dead-drop` and the
empty Far Ring artifact sites as physical source hooks. S27 owns the
corpse's one-time personal map and the shrine's daily claim receipt;
S26 owns season artifact activation. A prop label alone grants no reward.
Permanent hazards are excluded from salvage-node placement because
incoming damage interrupts the harvest channel. If an optional opening
closes over a saved position, reconnect recovers to the nearest free,
non-hazardous tile in the public spawn component, respecting housing
entry permissions. Include both in actual-city restart and event tests.

Mezzanine physical admission does not grant a Citadel network credential;
its loan terminal keeps the normal network gate. The Far mast uses the
Scour sector and cannot bypass Static's Ring-fall gate. All 16 relay
sites are mapped, but Shaft Relay retains `requires_level`; S26 must bind
its availability to the committed level phase, alongside the story-route
providers. Mapping never pretends that this seasonal gate is open.

Native city commissioning also preserves fallback Interact on a physical
prop underfoot before any adjacent public network terminal. Shaft Foot
therefore reports its sealed season-console status; explicit J still
jacks in. Retain this actual-map regression through S26 activation and
later interaction handlers. See PR #66, alongside PR #38 and issue #56.

A dedicated apartment doorstep chooses its door ahead of adjacent
dropped goods; a prop underfoot still owns Interact. Native delivery-key
testing exposed the previous accidental core-log action. Preserve this
public/private interaction through future handlers. Full-city salvage
checks allocate a proposal only when a field deadline is due; seeded
respawns and the tick p99 below 10 ms requirement stay in force.

The Citadel's executive lift lockdown closes only the Atrium inbound
lift for 300 seconds. Gatehouse restores the same physical panel, with
the latest committed operation winning. The Plaza exit and Mezzanine
return remain available; machinery restoration grants no credentials.
Disabled controls report a control lock instead of a missing credential.
Retain this binding, return path and refusal distinction through seasonal
activation, help, operator diagnostics, load tests and federation replay.
See [PR #66](https://github.com/Thiesi/Blacksite/pull/66), alongside the
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) product review.

Full-city pacing changes Gate Nine's ordinary opening to 60 seconds
per 120-second UTC cycle (game 7.7). The former 300-second cycle allowed
a 240-second idle wait; an actual native free-gate journey took 265
seconds including its approach. The fixture-free first rifle/ammunition
upgrade also left zero chits. Ordinary free waiting is now at most 60
seconds; the 25-chit fast option, owner benefits and free inward route
remain. Keep this schedule in seasonal controls, dialogue/help, operator
views, load and federation checks. This is a product pacing correction,
not a shortened capture clock or an accelerated acceptance fixture.
Reference: [PR #66](https://github.com/Thiesi/Blacksite/pull/66), retaining
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

A deterministic quiet-zone replay found all four Shaft Foot maintenance
units targeting their own crew and taking damage before caller contact.
Game 5.5 now excludes the same server-bound local spawner crew from NPC
hostility, including explicit hostile wildlife and machines. Outsiders
still face the ordinary hostility rules. Use full-strength packs/cohorts
in seasonal waves, dialogue, field pacing and load checks; never rely on
self-inflicted damage to make those encounters affordable. This is a
deliberate gameplay correction, not a claim that the new AI replay is
byte-identical to the old one. See
[PR #66](https://github.com/Thiesi/Blacksite/pull/66), retaining
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).
<!-- s25-water:start -->

Game 5.2 now gives destination terrain a data-driven movement cost:
ordinary ground is 1 and water is 2 (400 ms walking / 200 ms sprinting
before other modifiers). Pump layouts use the live tile, so draining
restores dry timing and reflooding restores the penalty. The original
S25 requirement promised slower water but the engine only checked
passability. Seasonal layouts, NPC/dialogue guidance, operator views,
load scenarios and help must preserve this meaningful route choice.
Use exact cooldown tests for the rule; scripted route time is not a
human earnings or challenge measurement. See
[PR #66](https://github.com/Thiesi/Blacksite/pull/66), retaining
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).
<!-- s25-water:end -->
<!-- s25-city-decisions:end -->

<!-- s25-worker-passage:start -->

Relay Zero reserve now grants only `lat-relay-zero/worker_return`, opening
the optional Old Works Main workshop passage for 20 minutes. The closed
passage retains the public street; opening it saves at least eight steps.
Opening requires a current worker credential; walking the opened door
is public. Preserve the separate, ordinary public `relay_open` capture
control. The former reserve binding to that public control supplied no
meaningful reward. Retain this distinction in seasonal activation,
dialogue/help, operator views, load and federation checks. Reference:
[PR #66](https://github.com/Thiesi/Blacksite/pull/66), retaining
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).
<!-- s25-worker-passage:end -->
The shortcut saving is checked from the actual relay repair mast to the
public Old Works counter, rather than arbitrary street mouths. Every
ordinary spawn candidate and patrol point must retain a public escape
without a locked shortcut. Sealed spawn rooms otherwise leave unrelated
core latches permanently pending; S25 repairs the map paths while
retaining the safety checks. Preserve this through future placements.
