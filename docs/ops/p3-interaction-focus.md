# P3 interaction focus acceptance

P3 implements architecture 5.4 and 5.5.2. Codex (GPT-6) implements the
Opus-assigned slice. The E/J queries and input handlers share the selected
target in the existing subsystem order. Selection is separate from sight
disclosure: an unseen winner is masked without advertising another
target. Modal consumers can own a key without a world target.

Zone views carry `focus` and `jack_focus`; published Lattice views carry
the corresponding inspection, uplink and return targets. Actor labels
use the caller's existing name disclosure. Hidden exits remain own-tile
only. No interaction ordering, game number, content, map or renderer
changes are proposed. The existing zone hint row names the E/J targets.
The shared chrome fits that row by whole groups and shortens only labels
when E/J context alone overflows. Keys and verbs remain intact. Help is
retained when it fits after context. Channel progress owns the row.

The presentation lead's [wording review](https://github.com/Thiesi/Blacksite/pull/103#issuecomment-6510595595)
is being addressed before another acceptance request. Exit hints say
`go to`, unlabelled rig actions say `jack in` / `jack out`, contract fetch
says `take`, object planting says `plant at`, and tile objectives say
`here`. The [distinct matrix label set](captures/p3-interaction-focus/focus-labels.json)
contains 116 pairs with provenance assertions. Fifteen unnamed selected
objects (eight fixture objects, three clinic doors and four Wake vats)
keep their input target without a focus label. No content or input log
is renamed as part of this wording correction.

## Playable acceptance

Run from the committed worktree with NetBBS available to the script
interpreter and the current Blacksite wheel in a private door interpreter:

```text
python scripts/accept_p3_netbbs.py --root <fresh-directory> --door-python <wheel-python> --show
```

The script checks installed-client/source identity and uses a private
real NetBBS node with a registered native stdio door. It runs both 80x24
and 132x50 in 16, 256 and truecolor with a wide character in the name.
NPCs, funds, rules and the clock stay normal. Movement and actions use
ordinary caller keys; there are no placement or inventory fixtures.

1. Create an Operator, read/skip the Wake briefing and take no recruiter
   card. Enter Wake Hall.
2. Walk through the corridor and explicitly skip the training fight
   with B. Reach the outfitter at (34, 15).
3. Before E, read `E open Sablier Wake Outfitter` and
   `J jack in at Tutorial terminal` in the hint. Press E. The outfitter
   buy menu opens with the predicted target id. Esc returns.
4. From that same tile press J. The adjacent tutorial terminal enters
   the Lattice. J returns to the street.
5. Walk to (36, 15), outside the counter's interaction range. Read
   `E jack in at Tutorial terminal` before pressing E. E enters the
   Lattice, whose published body includes its E/J focus fields.
6. Press J to return, then leave cleanly with Ctrl-X. Repeat at both
   sizes in all three colour tiers.

## Deterministic coverage

The input matrix adds the three fixture zones to the full shipped game
and covers them and all ten hubs. Every authored object, exit and
spawned NPC tile, plus each in-bounds neighbour, runs in physical and
loaned-rig presence states. E and J run as keys and intents: 10,704 cases.
Unwalkable positions are declared input fixtures, not movement proof.
The actual consuming handler matches the prediction. Outcomes match an
independent pre-P3 execution, pinned in
`tests/presentation/interaction-baseline.json`.

Additional tests cover query purity, sight masking without fallback,
hidden exits, S25a's underfoot/passive cases, apartment doorsteps, modal
and disabled states, vi's Ctrl-O, and every shipped Lattice cell. Six
glyph/style comparisons at both sizes and all colour tiers change only
the existing hint rectangle. No golden or mechanics baseline changes.

## Evidence and gates

The [capture packet](captures/p3-interaction-focus/README.md) contains 24
live text captures, 72 payload hashes and exact CI artifact references.
Raw ANSI and style JSON remain in CI. Current-head hosted root tests and
the separate clean local run are distinguished in their receipts.

The initial automated Sonnet 5.5 reviews found no actionable issue. Their
non-blocking night-window observation is resolved by importing the zone
simulation's named constants. Optional caching and code-style changes
are deferred without a practical failure. The packet records the actual
upstream commit resolved from the acceptance workflow's release tag.

Presentation-lead wording approval is pending. The wording corrections
require fresh native captures and another automated review. Channel
mechanics keep their existing behaviour. Technical review and the owner's acceptance
and merge remain separate gates. These engineering receipts grant no
layout, content, pacing or balance approval.
