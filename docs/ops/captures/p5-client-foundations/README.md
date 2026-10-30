# P5 native review packet

Execution head: `b9896d4375b90f94f8b762fba84bc25a08911b25`.
This packet is now historical for notice behavior: its log-row notices
were rejected at `cf48304`. TR-3 and the corrected UI 2.5 notice lifecycle
need new evidence. The accepted word wrap, bands, centring, relation tags
and other unchanged screens remain reference evidence; this packet does
not establish the later corrections or current acceptance.
This packet replaces the pre-correction captures reviewed at `450d918`.
It records TR-1 and the five creative corrections, without granting
technical, creative or human acceptance.

Transport: real NetBBS v7.45.0 Telnet to a registered native stdio door,
using a source-matched isolated Blacksite wheel and
`DOOR_BLACKSITE_PRESENTATION=1`. The runner's stdout is an attached
Linux PTY whose size is checked against the selected size. The private
node/world/accounts are isolated; NPCs, rules, funds and clock remain
normal. Creation, movement, targeting, firing and menus use ordinary keys.
S25 layout and full S27 human/presentation gates remain held.

## Scenarios

Six cases cover 80x24 and 132x50, each in 16/256/truecolor. Each has eight
captures: `wake`, `wake-hall`, `training-drone`, `training-complete`,
`meridian-plaza`, `inventory`, `contracts` and `help`.

After the Clinic, the probe walks normally to (31, 5), beside the shipped
Plaza patrol route, before saving the Plaza capture and opening menus.
It changes no actor position or NPC state directly. In truecolor it also
checks a live NPC glyph against Paint's lifted `npc_wardens` colour.
The 80x24 receipt shows `#2563eb` becoming
`#8291ff`: L* distance 46.062 becomes
63.521, above the people floor 63.385.
The recorded terminal cells contain that actual RGB colour.

The live wide field is the **Blacksite character name** (`P界132`, for
example). The BBS account/door handle is ASCII (`S10P132`), as released
NetBBS requires. Headless goldens additionally cover a synthetic wide BBS
handle. The technical lead
[accepted this distinction](https://github.com/Thiesi/Blacksite/issues/106#issuecomment-6526049298).
The manifest records twelve pinned rows with the full differing name and
handle together at 132x50.

## Requested correction evidence

| Capture | What to inspect |
|---|---|
| `wake-hall-80x24-256` | Small horizontal axis centred, whole hint groups, notice in log, rule-only separator. |
| `wake-hall-132x50-256` | Both small axes centred, notice in log, intact separator junction. |
| `training-drone-80x24-16` | Explicit relation tags, shared word wrap and whole hint groups. |
| `meridian-plaza-80x24-truecolor` | Live person lift in the original style grid. |

`review-corrections.json` lists every changed P5 golden and every native
text/style capture compared with the fresh `450d918` run. It also records
the truecolor Plaza lift measurements and terminal cells. The 39 changed
goldens are dead, lattice, menu, talker, text and Wake at both sizes in all
tiers, plus zone at 132x50 in all tiers. No switch-off golden or mechanics
fingerprint was rebaselined.

The corridor training sentence is a P4 notice, not a structured objective.
It uses the log rather than becoming an invented objective. Structured
objectives use P3's hint at 80 and NOW at 132; focused tests assert exactly
one visible objective for both direct and Wake-wrapped zone bodies.

## Provenance and verification

- [Native run 41108032615](https://github.com/Thiesi/Blacksite/actions/runs/41108032615).
- [80x24 artifact 13003186149](https://github.com/Thiesi/Blacksite/actions/runs/41108032615/artifacts/13003186149).
- [132x50 artifact 13002672267](https://github.com/Thiesi/Blacksite/actions/runs/41108032615/artifacts/13002672267).

`source-receipts.json` copies success, attached-terminal dimensions and
the installed-wheel receipt, and hashes each original `result.json`.
`manifest.json` names every original text, ANSI and style capture with
its SHA-256. Full JSON style grids, raw ANSI and console streams remain
in the artifacts named above; selected style cells are not a replacement
for those complete captures.

Python tree SHA-256:
`1b10d6365afd302cae9f9bbd2e8b3a9b156976c4072e4447b0a8ff6ec9fe786e`.

All 144 original file hashes were checked. Each accumulated ANSI stream
was independently replayed from alternate-screen entry through the test
terminal; all 48 glyph/style grids and texts matched the producer's
snapshots. The installed Python tree matches the execution head. Both
console receipts match their exact dimensions for all six cases.

The 48 untrimmed texts and manifest total 301,637 bytes, before this
README and small receipts/change list. The existing evidence exception
retains all eight required steps, two sizes and three tiers. Large style
grids and ANSI stay in artifacts. Texts preserve the terminal's blank
last cell and trailing spaces; their hashes must match the originals.
Whitespace checks exclude only these verbatim `.txt` captures.

CPU/frame-budget reports are separate `p5-budget-comparison` artifacts.
The current measured verdict, comparison with `450d918`, full CI and
review links are recorded on [PR #110](https://github.com/Thiesi/Blacksite/pull/110).
No budget miss or acceptance gate is waived by this packet.
