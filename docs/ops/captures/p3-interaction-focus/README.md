# P3 acceptance evidence

Source and native execution head:
`8c72bb127f8522c2f3be0f8c7ba26dbf251f9238`.
Base: owner-merged P4/main `9907c90a66c036c0876803a180c22f9d53b403d3`.

[Hosted native run](https://github.com/Thiesi/Blacksite/actions/runs/40967008739)
passes all six size/tier cases: 80x24 and 132x50, each in 16, 256 and
truecolor. The 24 text captures come from received native-door output.
Both target names fit the 80-column hint before input.

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

- [132x50](https://github.com/Thiesi/Blacksite/actions/runs/40967008739/artifacts/12938272617)
- [80x24](https://github.com/Thiesi/Blacksite/actions/runs/40967008739/artifacts/12937349394)

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

The broader [service/shared-zone run](https://github.com/Thiesi/Blacksite/actions/runs/40967008793)
also completes at this source: 28 jobs pass and the door-only subset is
skipped by scope selection. `full-native.json` names each job.

`review-triage.json` links the written Sonnet 5.5 reviews and the resolved
shared-night-constant observation. Wording approval, including the
channel-hint observation, and the technical decision record are pending.
Raw worlds, node databases and authentication files are absent. These
receipts grant no human presentation, layout, content or pacing gate.
