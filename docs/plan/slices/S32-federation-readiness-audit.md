# S32 — Federation readiness audit (design only): origin/authority invariants, protocol reservations, a written bridge design against NetBBS #168

**Status:** planned
**Primary model:** Fable · **Reviewer:** Astra (independent critique of the bridge design)
**Depends on:** S21, S26 · **Milestone:** M6
**Issue:** https://github.com/Thiesi/blacksite/issues/32

S18 adds origin-prefixed tenancy IDs, server-issued item `key_for` and
`key_tier`, and protected apartment/impound ownership records. Audit
these together with `unit_hacks`: the physical unit's rolling 24-hour
theft allowance survives re-letting, while old keys and private cores
expire. Local `zone:door` unit IDs have authority only inside their
origin's world. Visitors and crews never inherit resident permissions;
safe/bank chits are outside the theft manifest. See entity 2.3, game
design 8.7 and accepted [PR #38](https://github.com/Thiesi/Blacksite/pull/38).

## Goal

Before 1.0, verify that the "per node now, federation designed in"
decision actually held through implementation, and write the design
for a cross-node bridge over NetBBS's real-time Link relay so that a
future slice can build it without touching the simulation core. This
slice produces documents and tests only; it changes no game behaviour.

## Spec references

- `docs/design/02-architecture.md` §9 (origin, authority fields on
  zone/sector/core/relay/faction state, `peer.*` frame reservation,
  `peer` session role, per-authority season state, transport-agnostic
  core), §5 (protocol), §4 (identity `(origin, bbs_user_id)`).
- `docs/design/01-entities.md` conventions (instance IDs carry the
  origin), §5 (disjoint ID spaces invariant), §2.11 (world meta origin).
- `docs/design/00-game-design.md` §13 (seasons per authority), §7.4
  (relays), §16 (cross-node explicitly out of v1).
- `docs/upstream/04-door-info-enrichment.md` (released `node_id`;
  `node_fingerprint` was not shipped) and the issue #56 catch-up plan.
- NetBBS: issue #168's closed design (real-time Link relay: bounded
  resource limits, concurrent-pair cap, byte-rate limits, protocol-
  agnostic idle timeout, bounded pending-rendezvous table, rendezvous
  frame types, v1 fallback UX) as recorded in the NetBBS design
  document §16; the Link protocol docs for identity (node key
  fingerprints) and the reliable-nodes roster.
- The bible §13 (no way out of Karst: federation must be framed in-
  fiction as other cities' Lattices reachable through the Silt, or as
  parallel Karsts; this slice picks one and records it as a bible
  change proposal, not a change).

## Scope

- **Audit checklist** (`docs/design/06-federation-audit.md`, new), each
  item answered with evidence (file and test names):
  1. Every instance ID in persistent tables carries the origin prefix;
     a test creates two worlds with different origins and asserts
     disjoint ID sets after identical scripted play.
  2. Every row type listed in architecture §9 has an `authority` column
     populated with the local origin; no code path reads a row without
     honouring it (grep for direct table reads outside storage).
  3. The simulation package imports nothing from `asyncio`, `socket`,
     or `time` (a test asserts the import graph).
  4. Sessions are created only through a factory; a fake `peer`-role
     session can be attached in tests and receives views.
  5. `peer.*` frame types are rejected by the current server with a
     specific error, not a generic one, and the protocol document lists
     them as reserved.
  6. Season, leaderboard, and Chronicle rows are keyed by authority.
  7. Player identity uses `bbs_user_id` and origin, never handle; a
     handle change on the BBS does not create a second player.
  8. No content ID collides with an instance ID pattern.
  9. Chat channel names are namespaced so a remote faction channel
     cannot alias a local one.
  10. The admin CLI's moderation targets are `(origin, bbs_user_id)`.
- **Bridge design** (`docs/design/07-bridge-design.md`, new), an
  outline good enough to file as a future epic:
  - Topology: each node remains authoritative for its own world; a
    bridge exposes a chosen set of **remote regions** (initially: one
    shared Scour ring and the Silt) whose authority is a peer node.
  - Transport: a `peer` session per remote node over the #168 relay
    rendezvous, framed with the same length-prefixed JSON, within the
    relay's byte-rate and idle limits; reconnect and partition
    behaviour (remote regions go dark, local players in them are moved
    to the nearest local zone with no penalty).
  - State: view models for remote regions are proxied, not merged;
    inputs from local players in a remote region are forwarded as
    intents; combat between players of different origins is resolved
    by the region's authority; item transfer across origins is by
    escrow with both authorities confirming.
  - Identity and trust: the game's own key pair or an explicitly verified
    future host facility. Door info has no `node_fingerprint`; opaque
    `node_id` and mutable `node_name` are not cryptographic identity.
    Use a per-pair allowlist the
    SysOp edits; abuse cases (a hostile peer spoofing kills or chits)
    and the rule that nothing a peer says changes local persistent
    state except through escrow.
  - Seasons: per-authority depth; a federated finale is out of scope;
    the Chronicle can carry a "from the Lattice of {node}" paragraph.
  - Fiction: proposal for how other nodes appear in Karst (recommended:
    through the Silt, as other cities' severed Lattices, which keeps the
    bible's "no way out" intact).
  - Sizing: which slices it would take (a rough S34–S38 list) and which
    NetBBS work it needs beyond #168 (likely: a relay-backed local
    socket adapter).
- Tests added under `tests/federation/` for items 1, 3, 4, 5, 6 of the
  checklist.

## Out of scope

- Building any part of the bridge. Changing the bible. Any NetBBS
  issue beyond a pointer comment on #168 if the user wants one.

## Data and content

- Two new design documents; no content.

## Protocol and view models

- Document the reserved `peer.*` types and the `peer` role precisely in
  architecture §5 (a small additive edit in the same PR).

## Tests

- `test_two_origins_produce_disjoint_instance_ids`
- `test_simulation_package_has_no_io_imports`
- `test_peer_role_session_receives_views_via_factory`
- `test_peer_frames_rejected_with_specific_error`
- `test_season_rows_keyed_by_authority`
- `test_handle_change_does_not_create_new_player`

## Acceptance script

This slice is a document review:

1. The user reads `06-federation-audit.md`: every checklist item has a
   yes/no and evidence; every "no" has a follow-up issue filed in this
   repository.
2. The user reads `07-bridge-design.md` and can answer, without asking:
   which node owns a fight in a shared ring, what happens to a caller
   when the relay drops, how chits move between nodes, and how the
   bible survives.
3. Astra's critique is attached to the PR and each point is answered.
4. The tests pass on `main`.

## Definition of done

- Both documents merged; follow-up issues filed for every audit "no";
  slice file marked done with PR number.

## Implementer notes

- The #168 relay is designed and closed but not built in NetBBS
  (memory: "Implementation not yet filed as its own issue"); the bridge
  design must not assume its API beyond the frame types and limits
  recorded in the NetBBS design document §16.
- Do not let the audit drift into refactoring; a "no" is filed, not
  fixed, unless it is a one-line change.
- The reliable-nodes roster at `www.netbbs.org/reliable-nodes.json` is
  the discovery mechanism NetBBS already has; the design should reuse
  it rather than invent a game-specific directory.

### S22 crew integration handoff

S22 [PR #61](https://github.com/Thiesi/Blacksite/pull/61)'s live crew IDs
include a per-service-boot nonce. They are not durable federation or
expedition identities. Keep node_id opaque and preserve source-owned
loot/reward entitlements separately from social membership.

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

Treat mission IDs, accepted roster, branch choices, service allocations and
source receipts as authority-owned state. Public route publication exposes
authored NPC/ICE telemetry only. Keep Origin/Source identity and ownership
boundaries; a native door NodeID remains an opaque session identifier.
<!-- s19-services:end -->

### S23 financial history handoff

[S23 PR #64](https://github.com/Thiesi/Blacksite/pull/64) retains the
accepted [PR #38](https://github.com/Thiesi/Blacksite/pull/38) source and
ownership boundaries. Closed listings, bids and bounties are immutable
history. Proposals copy open listings, held bids and active bounties;
terminal history may be shared read-only. A new mutable federation state
must be copied as live data before mutation. The held-bid lookup is
derived from stored records, never a remote monetary authority. Preserve
sale-time item snapshots, private audit and exact-instance delivery.

<!-- s24-handoff:start -->
### S24 event integration and acceptance handoff

Reference: [S24 #24](https://github.com/Thiesi/Blacksite/issues/24),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

Audit event authority by committed plan/source ID, not process-local
crew IDs or wall-clock reads inside simulation. The injected clock,
seeded variants/sites, explicit revisions, reward receipts and event-only
contracts are authoritative. Independent source layers must not undo
another node's service/control/relay/season state. Preserve identity
deduplication and atomic item/receipt settlement when designing transfer;
do not turn a preview, telemetry flag or host announcement into authority.
<!-- s24-handoff:end -->


<!-- s24-review-policy:start -->
### S24 practical review follow-up

Reference: [PR #65](https://github.com/Thiesi/Blacksite/pull/65), retaining
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and #56.

The hot event receipt is a bounded working set, not a permanent global
archive: 128 closed plans plus live/current transitions. Personal forecasts
hold compact outcomes and cannot authorize another payout. A federation
bridge that needs older provenance must retain the required committed
facts/receipts in its own ledger.
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

Physical story permissions are derived from the local committed
mission/season source through `Characters.route_permissions`; membership has
its own character authority. Do not accept route flags from client frames,
arbitrary progress or an untrusted remote peer. Audit source identity,
scope/lifetime, alternatives and already-departed journey preservation.
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

Keep local open-latch credentials tied to their exact zone/object.
Future peers cannot assert route flags, private housing-cell ownership
or permissions on behalf of this authority. Audit the 24 distinct unit
addresses without exposing private interior state.

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
<!-- s25-city-decisions:end -->
