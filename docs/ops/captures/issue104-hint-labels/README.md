# Issue 104 terminal and label evidence

Execution source: `03dad628af71fbdd5cb2128d9b01bcb7c79d4ab5`, based on
owner-merged main `5f0c993afb82c468acd533656b7282d5336faa7e`.
These captures predate the owner's S27 merge at `85d3dda`. They are
historical during the current integration check. Fresh captures and
receipts for the combined runtime are being prepared; do not use this
packet as proof of the rebased runtime's source identity yet.

## Native captures

[Hosted run 41031110108](https://github.com/Thiesi/Blacksite/actions/runs/41031110108)
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

The [117-pair regenerated label list](focus-labels.json) includes the
seven requested naming scopes. All target IDs stay stable. Its 10,704
input outcomes keep the pre-P3 hash, and the P1 mechanics baseline is
unchanged. No text or style goldens were rebaselined.

The [strict packet summary](strict-packet-summary.json) records 33
passing checks, 99 cases and zero CP437 failures at the clean execution
head. The compact-row regression tests also retain E at 80 columns when
only its J alias no longer fits.

These receipts grant no human gate. The presentation lead's wording
approval and technical review are required on the PR. S25 layout, S27
placement and later human acceptance remain held; only the owner merges.
