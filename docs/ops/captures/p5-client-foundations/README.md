# P5 native review packet

Execution head: `547ce7c418c19c60e5726adda081a01f05911ce2`.
The evidence commit changes documentation only; runtime, content,
tests, acceptance scripts and workflows remain identical to this head.

Transport: real NetBBS v7.45.0 Telnet to a registered native stdio door,
using a source-matched isolated Blacksite wheel and
`DOOR_BLACKSITE_PRESENTATION=1`. The runner's stdout is an attached
Linux PTY whose size is checked against the selected size. The private
node/world/accounts are isolated; NPCs, rules, funds, clock, ordinary
creation, movement, targeting, firing and menu keys remain normal.

This is engineering execution evidence, not creative or human approval.
S25 layout and full S27 human/presentation gates remain held.

## Scenarios

Six cases cover 80x24 and 132x50, each in 16/256/truecolor. Each has eight
captures:

1. `wake`: the ordinary archetype screen before naming the character.
2. `wake-hall`: the new character on the live rule map.
3. `training-drone`: the selected private training drone during the fight.
4. `training-complete`: the fight completed using Tab and F.
5. `meridian-plaza`: arrival after ordinary walking through the Clinic.
6. `inventory`: the inventory menu.
7. `contracts`: the contracts menu.
8. `help`: local full-width help.

The live wide field is the **Blacksite character name** (`P界132`, for
example). The BBS account/door handle is ASCII (`S10P132`), as released
NetBBS requires. The headless goldens additionally cover a synthetic
wide BBS handle. The technical lead
[accepted this distinction](https://github.com/Thiesi/Blacksite/issues/106#issuecomment-6526049298).
All four required live size/tier combinations contain the wide name;
the 132x50 zone captures show the complete differing ASCII handle next
to it. `manifest.json` records twelve verified pinned-row examples.

## Provenance and verification

- [Native run 41083554221](https://github.com/Thiesi/Blacksite/actions/runs/41083554221).
- [80x24 artifact 12990284280](https://github.com/Thiesi/Blacksite/actions/runs/41083554221/artifacts/12990284280).
- [132x50 artifact 12991501332](https://github.com/Thiesi/Blacksite/actions/runs/41083554221/artifacts/12991501332).

`source-receipts.json` copies the run's success, attached-terminal
dimensions and installed-wheel receipt, and hashes each original
`result.json`. `manifest.json` names every text, raw ANSI and style
capture with its original SHA-256. The Python tree hash is
`15caec2f1a3272270a98c40ec7bfd656a941aa0ec4aabaca102cc9db4ba0b921`.

All 144 original file hashes were checked. Each accumulated ANSI stream
was independently replayed from its alternate-screen entry through the
test terminal; its glyph/style grid and text matched the producer's
snapshot. The installed Python tree matches the committed execution
head. Both console receipts match the sizes used by all six cases.

The 48 untrimmed full-screen texts and native manifest total 293,996
bytes before this README and the small source receipts. This exceeds
the approximately 200 KB evidence guideline because all eight required
steps, two sizes and three tiers are retained. Large style grids, raw
ANSI and console streams stay in the artifacts.

Text files preserve the terminal's blank last cell, including trailing
spaces. Do not trim them: their hashes must match the original snapshots.
Whitespace checks exclude only these verbatim `.txt` captures.

CPU/frame-budget reports are separate `p5-budget-comparison` artifacts.
The current measured verdict, full CI and review links are recorded on
[PR #110](https://github.com/Thiesi/Blacksite/pull/110). No budget miss or
human gate is waived by this packet.
