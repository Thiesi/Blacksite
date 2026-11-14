# S48c1a creation captures (#241)

New native captures for the screens S48c1a changes, beside the accepted originals
(the #104 way): the originals in `../p5-client-foundations/` are untouched, and
`capture-repins.json` records each replacement with its reason and PR.

Transport: real NetBBS v7.45.0 Telnet to a registered native stdio door, run
locally on Windows with Python 3.12.10 from the #241 head. The P5 frames come
from `scripts/accept_p5_netbbs.py --size 80x24` (all three tiers); the issue 67
frames from `scripts/accept_issue67_netbbs.py --tier 256` (both sizes). CI
produces the full matrix as artifacts.

- `wake-record-80x24-*`: the decant record's template menu, reached with E
  beside the street door (was the Wake screen, `wake-80x24-*`).
- `wake-hall-80x24-*`: the hall after creation.
- `issue67-recruiters-*-256`: the card table in the hall.

Acceptance is the presentation lead's, from this record. H1 and the S25 layout
approval are not granted by these captures.
