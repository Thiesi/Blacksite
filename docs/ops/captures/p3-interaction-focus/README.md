# P3 acceptance evidence

This packet precedes the lead-directed objective-priority correction.
Fresh captures and check receipts will replace it before renewed review.

Source and native execution head:
`e465b1e2ba3e9104a46656a8ec73b5653ad2c0ab`.
Base: owner-merged P4/main `9907c90a66c036c0876803a180c22f9d53b403d3`.

[Hosted native run](https://github.com/Thiesi/Blacksite/actions/runs/40972867836)
passes all six size/tier cases: 80x24 and 132x50, each in 16, 256 and
truecolor. The 24 text captures come from received native-door output.
Both target names and `? help` fit the 80-column hint before input.
Remaining help groups are whole; the hint never ends in a clipped group.

| Capture | Live scenario |
|---|---|
| `outfitter-before-e-*` | E names Sablier Wake Outfitter; J names the adjacent Tutorial terminal. |
| `outfitter-after-e-*` | E opens the predicted outfitter buy menu. |
| `terminal-before-e-*` | Outside counter range, E names Tutorial terminal. |
| `terminal-after-e-*` | E enters the Lattice; its body includes both focus fields. |

The caller creates an Operator with a wide name, moves by ordinary keys,
explicitly skips training, opens/closes the counter, uses J from beside
that counter, then walks to the terminal's E position and leaves cleanly.
There are no placement, inventory, funds, rule or clock fixtures. NPCs
stay normal. The [playable script](../../p3-interaction-focus.md) gives
the steps and expected results.

The manifest hashes every committed text file and its raw ANSI/style
counterparts. The raw files remain in these exact CI artifacts:

- [132x50](https://github.com/Thiesi/Blacksite/actions/runs/40972867836/artifacts/12941590948)
- [80x24](https://github.com/Thiesi/Blacksite/actions/runs/40972867836/artifacts/12941037756)

Their ZIP digests were verified before extraction. The workflow checks
out the PR head explicitly. It uses NetBBS v7.31.0, resolved by checkout
to `3d90efcc05cc1397d6adeb1c567674045fed1cd8`; the native acceptance log
records that exact upstream commit. Installed door Python and server
Python trees match. The manifest retains text cells, trailing spaces
and the reserved final corner byte for byte.

The separate local run at the same source head passes all six cases
through a real local NetBBS native stdio node, forwarding the received
ANSI to the attached terminal with `--show`. `local-tty.json` records
the current wheel hash, runtime Python tree and cases. Local raw output
stays outside Git.

`root-ci.json` distinguishes current source-head hosted root tests from
the clean local full run at the preceding head. The latter uses a
matching private wheel and a clean detached temporary worktree.
`strict-packet.json` records 99/99 packet cases and zero authored CP437
failures. Every existing glyph/style golden and the mechanics file
matches the owner-merged base; none is regenerated.

The broader [service/shared-zone run](https://github.com/Thiesi/Blacksite/actions/runs/40972867743)
exposes a contract-hint conflict. The network route at 132x50 records its
first objective, then waits for the existing `Next:` feedback. Whole-group
fitting skips that long group after E/J context. Its failure artifact
shows the advanced objective in the side panel and the E/J hints, with
no `Next:` group. `hint-regression.json` records the exact job and
artifact. This is not a green acceptance result. Other job states are
recorded separately in `full-native.json`.

The [116-pair matrix label set](focus-labels.json) lists every distinct
pair selected by the 10,704-case initial-state matrix. Each named target
is checked against its object's authored name, per-caller actor name,
destination zone name or Lattice cell label. Empty labels occur only on
the requested short rig phrases. Fifteen unnamed selected objects keep
their input target without a focus label. Active contract stages and
the carried-rig start are supplementary cases, not matrix coverage.

The presentation lead requested whole-group fitting, shorter route, rig
and contract phrases, no id fallback, the label list, and channel-only
progress hints. These corrections are implemented. The tests check
twelve size/tier/keymap comparisons and preserve the pre-P3 input digest.
For renewed wording review, read `outfitter-before-e-80x24-truecolor.txt`
and `terminal-before-e-132x50-truecolor.txt`.

`review-triage.json` links the written Sonnet 5.5 reviews and their triage.
Presentation wording approval and the technical decision record are pending.
The leads must resolve the contract objective/hint priority before P3
can complete. The existing S19 acceptance assertion remains intact.
Raw worlds, node databases and authentication files are absent. These
receipts grant no human presentation, layout, content or pacing gate.
