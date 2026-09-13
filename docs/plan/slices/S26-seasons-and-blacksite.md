# S26 — Seasons: Depth meter, descent consoles, leaderboards, the Chronicle, Blacksite level 1 (instanced zone and sector)

**Status:** planned
**Primary model:** Opus · **Reviewer:** Fable (level design and finale review before merge)
**Depends on:** S21, S19, S24, S25, S27, S22 · **Milestone:** M5
**Issue:** https://github.com/Thiesi/blacksite/issues/26

## Goal

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
