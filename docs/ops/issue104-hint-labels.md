# Issue 104 hint-row label polish

This follow-up implements issue #104's seven wording items on main's P3
route. Codex (GPT-6) implements it. The existing target queries, input
handlers, target IDs, geometry, rules and dispatch order stay unchanged.

The execution head also integrates the owner's S27 backend merge
`85d3ddabaf104c656824696ca857e5260bfbc164`. Both dialogue and inspection
validation remain in force. The combined hint, dialogue, referral and
validation checks pass 106 tests. The cast stays dormant; these P3
captures grant none of S27's held native or human acceptance.

- The same target and verb produce one E/J group, or E/Ctrl-O in vi.
  Different IDs or verbs retain their separate groups. Both producer and
  fitter use the same presentation-only grouping helper. If the combined
  group cannot fit beside an objective but E can, drop only the J alias.
- Objective/cost priority stays intact; the generic E act group is
  removed and Q retains its job-panel help.
- Sablier Clinic and The Tin Halo lose their internal parenthetical notes
  in object, vendor and NPC display names. The named hardware and controls
  use sentence case, including their corresponding Lattice labels.
- The three public terminals use the presentation lead's suggested
  `Public terminal (Plaza 3)`, `Public terminal (Row 2)` and
  `Public terminal (Blocks 1)` wording. Their IDs stay unchanged.
- Four Wake Hall vats are named `Decant vat`; three clinic doors are
  named `Clinic door`.
- Vantongeren, the concierge and the drug dealer have the authored
  `inspect_verb: look at` display override. It affects only an inspection
  hint, never another verb or the consuming handler. The validator limits
  it to `inspect` or `look at` (entities 1.1).

The regenerated [label list](captures/issue104-hint-labels/focus-labels.json)
contains 117 distinct verb/label pairs. The 10,704-case interaction matrix
retains its frozen outcome hash
`05213f386e4ca644479f8ff80d43ca4e27ebd0acd0013e644b2072a9b9c59185`.
The mechanics projection omits only the existing display name and the
new inspection wording field. Its frozen baseline remains unchanged;
rule-bearing and unknown parameters remain guarded.

## Acceptance and gates

The P3 native acceptance script now checks the combined group at the
Wake Hall terminal, with no generic E group. It still walks with ordinary
keys through creation and training, opens the predicted outfitter with E,
enters its adjacent terminal with J, and enters the isolated terminal with
E. The run covers 80x24 and 132x50 in 16, 256 and truecolor through a real
NetBBS Telnet node and registered native stdio door, with a source-matched
installed wheel. No placement, inventory or simulation fixtures apply.

Run from a clean committed tree with the matching installed door wheel:

```text
python scripts/accept_p3_netbbs.py --root <fresh-directory> --door-python <wheel-python> --show
```

The [capture packet](captures/issue104-hint-labels/README.md) contains six
hosted text captures, their 18 exact ANSI/style payload hashes, the
matching local TTY run and strict packet receipt. All six native cases
passed on both hosts. No text or style golden was rebaselined.
Automated review, technical review and the presentation lead's
wording approval remain separate gates. This work grants no S25 layout,
S27 placement, pacing or other human approval. Only the owner merges.
