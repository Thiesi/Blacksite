# P3 — Interaction focus

**Status:** implementation in progress (PR #103); wording acceptance pending
**Primary model:** Opus · **Reviewer:** automated review, technical lead, presentation lead (wording)
**Depends on:** P1 · **Milestone:** presentation track
**Issue:** https://github.com/Thiesi/Blacksite/issues/94

From `docs/plan/03-presentation-integration.md` §3.5, §4 Refactor 2 and
§7.3, adopted by the owner on 2026-10-28 (D-T1). The canon is
architecture §5.5.2 and D-T4.

## Goal

The game can say what E will do before it is pressed, and that answer
is always what E actually does. This removes obstacle 2.

## Scope

- Each subsystem that consumes E exposes a pure query beside its
  `input` handler: what E would do for this session now, as a target
  id, label and verb, or nothing.
  - The list of subsystems is in plan §3.5: events, market, contracts,
    factions, crews, relays, apartments, progression, lattice,
    interlock, combat, fabrication, commerce, npcs, chat, the Lattice
    terminal, and `simulation.interact`.
  - Find any handler the plan missed, and list it in the PR.
- `server/core.py` composes the queries in today's dispatch order. E
  dispatch and the view both use the composed result.
- The order includes S25a's fallback rules (#83):
  - an interactive prop underfoot wins over an adjacent public terminal;
  - light, camera and salvage-field markers do not intercept;
  - a dedicated doorstep selects its apartment door;
  - a hidden exit is used only by Interact on its own tile.
- `ZoneView.focus` (architecture §5.4) carries the composed target. The
  J target is exposed the same way.
- The hint line names what E would do (UI §3, HERE) using the existing
  hint area. The presentation lead approves the wording.

## Out of scope

- **Any change to what E does.** The dispatch order stays as it is,
  including the Wake Hall terminal/outfitter id ordering. Changing the
  order is a rule change, made only by an explicit owner decision, as
  its own commit with its own test.
- New chrome or a HERE panel. Those are P5 and later.

## Tests

- A matrix test: the predicted handler equals the dispatched handler
  over every interactable tile, and each neighbour of one.
  - It covers the fixture world and the shipped hubs, in physical and
    jacked states.
  - It includes S25a's fixtures (prop underfoot, passive markers,
    doorstep, hidden exit).
- Disclosure:
  - focus never names an object outside the caller's sight;
  - it names a hidden exit only while the caller stands on its tile,
    never from an adjacent tile (D-T4).
- The mechanics fingerprint is unchanged.
- Goldens change only in the hint line. Name each rebaseline and
  justify it.

## Acceptance

Automated review, technical review, and the presentation lead's
approval of the wording.

On a real terminal, the Wake Hall script at 80x24 and at 132x50 must
show the hint line naming what E opens before E is pressed, and E must
then do exactly that. Supply captures in three tiers.

Run `python scripts/accept_p3_netbbs.py --root <fresh-directory>
--door-python <installed-wheel-python> --show` from the committed
worktree, with NetBBS available to the script interpreter. It creates a
private node and world, checks that the native wheel matches the server
source, and runs both sizes in all three colour tiers. It uses ordinary
creation, movement, E, J and menu-close keys with normal NPCs, funds,
rules and clock. The script's captures are evidence for the presentation
lead's wording decision, not that decision itself.

The dispatch matrix in `tests/presentation/interaction_matrix.py` adds
the three fixture zones to the shipped game and covers them and the ten
hub zones. It includes every authored object, exit and spawned NPC tile,
and each tile's eight neighbours within zone bounds. Positions on an
unwalkable object are declared input fixtures, not movement acceptance.
Each point runs physical and loaned-rig presence states, E and J, as keys
and intents: 10,704 cases. The outcome baseline was also executed against
pre-P3 source; its provenance and digest are in
`tests/presentation/interaction-baseline.json`.

Additional consumers found beneath the plan's subsystem list are
contract stage actions, work-order caches, and Lattice encounter menus.
Clinics, drones and the skill menu under progression can also consume a
key without a world target. They participate in the same composition.
No E ordering, rule, number or mechanics fingerprint baseline changes.

The [acceptance notes](../../ops/p3-interaction-focus.md) describe the
playable path and deterministic coverage. The [capture packet](../../ops/captures/p3-interaction-focus/README.md)
contains current-source hosted and local native receipts, exact CI raw
artifact links, test counts and automated-review triage. Presentation
wording approval and the technical decision record are pending.
