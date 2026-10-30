# P3 acceptance evidence

Source and native execution head:
`93641f5dc5db6dc7a60124de200d1033ac12d686`.
Base: owner-merged P4/main `9907c90a66c036c0876803a180c22f9d53b403d3`.

[Hosted native run](https://github.com/Thiesi/Blacksite/actions/runs/40976696170)
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

- [132x50](https://github.com/Thiesi/Blacksite/actions/runs/40976696170/artifacts/12942158814)
- [80x24](https://github.com/Thiesi/Blacksite/actions/runs/40976696170/artifacts/12942633653)

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

The broader [service/shared-zone run](https://github.com/Thiesi/Blacksite/actions/runs/40976696156)
is recorded job by job in `full-native.json`. The four S19 manual/network
cases at both sizes retain their existing `Next:` assertion and timeouts.
`hint-regression.json` preserves the earlier failure artifact and the
technical/presentation leads' resolution under terminal UI 11. The active
objective and current cost now precede E/J context. Names retain their
first word; J and then E drop before objective target text shortens.
`Next:`, its verb and current cost remain intact.
The two `s19-first-objective-network-*.txt` captures show that complete
cost at both widths. `s19-objectives.json` hashes the text and raw ANSI,
links the exact CI artifacts and records their verified archive hashes.

The [116-pair matrix label set](focus-labels.json) lists every distinct
pair selected by the 10,704-case initial-state matrix. Each named target
is checked against its object's authored name, per-caller actor name,
destination zone name or Lattice cell label. Empty labels occur only on
the requested short rig phrases. Fifteen unnamed selected objects keep
their input target without a focus label. Active contract stages and
the carried-rig start are supplementary cases, not matrix coverage.

The presentation lead requested whole-group fitting, shorter route, rig
and contract phrases, no id fallback, the label list, and channel-only
progress hints. These corrections and the confirmed UI 11 priority are
implemented. The tests check twelve size/tier/keymap comparisons,
objective/cost retention, name shortening and group dropping. The pre-P3
input digest is unchanged. The subsequent unnamed recruitment-board
crash is reproduced and fixed: input uses the selected object/actor id,
independent of whether it has a display focus.
For renewed wording review, read `outfitter-before-e-80x24-truecolor.txt`
and `terminal-before-e-132x50-truecolor.txt`.

`review-triage.json` links the written Sonnet 5.5 reviews and their triage.
Presentation wording approval and the technical decision record are pending.
The leads' agreed priority is implemented; final wording approval and
the technical record are still required. Existing human gates remain.
Raw worlds, node databases and authentication files are absent. These
receipts grant no human presentation, layout, content or pacing gate.
