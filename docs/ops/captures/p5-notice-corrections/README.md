# P5 notice correction evidence

Execution head: `c59c90f7093a10ecc7846085bc6b514f0efe3855`.
This packet records only the two requested affected captures for TR-3 and
the corrected UI 2.5 notice behavior. It grants no creative, technical or
human approval. The prior 48-screen packet remains historical reference;
none of its captures or the 48 P5 style goldens was regenerated here.

| Capture | Evidence |
|---|---|
| `wake-hall-80x24-256.txt` | Tutorial notice on the priority hint line with the escape action, absent from the world log. |
| `training-drone-80x24-16.txt` | The same notice on the right of the header during declared combat; target, hint, typed log and separator stay visible. |

The full notice remains once in local scrollback. Deterministic tests
cover the eight-second-plus-key lifetime, return from the header when
declared threats clear, prompts/channels, back/leave actions and the
unchanged legacy behavior. The supported local-palette crash correction
has operator-override render tests; shipped palette tests forbid fallback.

Transport is real NetBBS v7.45.0 Telnet to a registered native stdio door,
with `DOOR_BLACKSITE_PRESENTATION=1`, a source-matched isolated wheel and
sized attached Linux PTYs. Node/world/accounts are private; creation,
movement, targeting, firing and menus use ordinary inputs. No clock,
funding, NPC or gameplay-state mutation is used for this packet.

[Native execution run 41124990753](https://github.com/Thiesi/Blacksite/actions/runs/41124990753)
and [80x24 artifact 13009908960](https://github.com/Thiesi/Blacksite/actions/runs/41124990753/artifacts/13009908960)
hold the original full JSON style grids, ordered ANSI and console stream.
`manifest.json` names and hashes each original file and records the native
success, PTY sizes and installed-wheel receipts. Before selecting these two
texts, all six cases, 144 original hashes and 48 complete ANSI glyph/style
replays were verified, with twelve full wide-name/ASCII-handle pinned rows.

Python tree SHA-256:
`57f991279d8db3a1ed14b701ad457c87403309832550ad376270f2e3aacd17fe`.

The final evidence-only commit must match that execution in source,
tests, acceptance scripts, workflows and packaging. Current-head root
CI, full native matrix, budgets and review decisions are recorded on
[PR #110](https://github.com/Thiesi/Blacksite/pull/110). Blank final cells
and trailing spaces in `.txt` files are byte-preserved capture evidence.
S25 layout and all S27 human/presentation holds remain in force.
