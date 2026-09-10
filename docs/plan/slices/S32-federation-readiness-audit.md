# S32 — Federation readiness audit (design only): origin/authority invariants, protocol reservations, a written bridge design against NetBBS #168

**Status:** planned
**Primary model:** Fable · **Reviewer:** Astra (independent critique of the bridge design)
**Depends on:** S21, S26 · **Milestone:** M6
**Issue:** (filled in when filed)

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
- `docs/upstream/04-door-info-enrichment.md` (`node_id`,
  `node_fingerprint`).
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
  - Identity and trust: node fingerprints from `door_info.json`
    (upstream 04) or the game's own key pair; a per-pair allowlist the
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
