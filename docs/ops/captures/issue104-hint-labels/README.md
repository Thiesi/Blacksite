# Issue 104 terminal and label evidence

Execution source: `ca1e2831d2147423f4d9c3bf81e78b6495e66ddb`, based on
owner-merged main `85d3ddabaf104c656824696ca857e5260bfbc164`.
This execution includes the owner-merged S27 backend, with its cast
still dormant and all S27 presentation/native/human gates held.

The subsequent whole-tree wording correction changes terminal names and
inspection metadata outside the captured Wake Hall, plus label/audit
evidence and tests. Python runtime, renderer, Wake Hall content and
capture-producing scripts remain unchanged. The presentation and
technical leads requested a regenerated label list and explicitly said
[new captures are not needed](https://github.com/Thiesi/Blacksite/pull/109#issuecomment-6520713225).
The receipts below describe their recorded execution head, not a new
native execution of the later content correction.

## Native captures

[Hosted run 41036525447](https://github.com/Thiesi/Blacksite/actions/runs/41036525447)
ran the actual NetBBS Telnet node and registered native stdio door at
80x24 and 132x50 in 16, 256 and truecolor. Every case uses ordinary
creation, movement and action keys, normal NPCs, funds, rules and clock.
The independent local `--show` run passed all six cases in an attached
PTY, using the same Python-source tree and a fresh installed wheel.
NetBBS is pinned to v7.31.0, commit
`3d90efcc05cc1397d6adeb1c567674045fed1cd8`.

| Size | 16 colours | 256 colours | Truecolor |
|---|---|---|---|
| 80x24 | [text](terminal-before-e-80x24-16.txt) | [text](terminal-before-e-80x24-256.txt) | [text](terminal-before-e-80x24-truecolor.txt) |
| 132x50 | [text](terminal-before-e-132x50-16.txt) | [text](terminal-before-e-132x50-256.txt) | [text](terminal-before-e-132x50-truecolor.txt) |

All six captures show `E/J jack in at Tutorial terminal` once and no
generic E group. The full script also verifies E at the outfitter and J
at its adjacent terminal, with different targets kept separate.

The [manifest](manifest.json) records 18 SHA-256 payload hashes and the
exact artifact link for each capture. Only plain text and small receipts
are committed. The original ANSI and full style JSON stay in the named
CI artifacts; styles, colour and terminal controls are not inferred
from plain text. [Hosted receipts](native-ci.json) and the
[local TTY receipt](native-local-tty.json) distinguish both executions.

## Labels and preservation

The [118-pair regenerated label list](focus-labels.json) includes the
seven requested naming scopes. The [whole-tree audit](wording-audit.json)
records all 15 generic public terminals and 12 person-shaped objects,
found by full-content grep and a read of all 129 zone objects plus the
six private-room template objects. Two regression
guards enforce the public name form, declared person inspection verbs
and known person roles while things retain `inspect`.
All target IDs stay stable. The 10,704
input outcomes keep the pre-P3 hash, and the P1 mechanics baseline is
unchanged. No text or style goldens were rebaselined.

The [strict packet summary](strict-packet-summary.json) records 33
passing checks, 99 cases and zero CP437 failures at the clean execution
head. The compact-row regression tests also retain E at 80 columns when
only its J alias no longer fits.

These receipts grant no human gate. The presentation lead's wording
approval and technical review are required on the PR. S25 layout, S27
placement and later human acceptance remain held; only the owner merges.
