# P4 acceptance evidence

Source head: `d447fcd0fe08ddc57a0f7094c569f8f21e3d6df6`.
Base: `92b7315053f4e81b64168084955d75c459bb2066` (owner-merged P2, including S25b).

[Hosted run](https://github.com/Thiesi/Blacksite/actions/runs/40933190108) passes six
native cases: 80x24 and 132x50, each in 16, 256 and truecolor, with
wide caller names. These 24 text captures come from received door output.

| Capture | Ordinary playable scenario |
|---|---|
| `wake-*` | Create a character in Wake Hall; full arrival paragraph in history. |
| `place-history-*` | Ctrl-P shows that complete paragraph, tagged place. |
| `lattice-*` | Walk, skip training, reach terminal and jack in. |
| `sodium-cover-*` | Walk through Clinics/Plaza to Sodium Row and target the actual shipped Warden: Sodium regular, Civilian. |

The caller returns to Core Plaza and leaves cleanly. No placement,
funds, rules or clock fixtures are used. The independent local run
passes the same six cases through a real NetBBS native stdio node;
16-colour received ANSI is forwarded to the terminal. The local node
is NetBBS 7.41.0 / API 5 at the dirty checkout recorded in its small
environment receipt; hosted acceptance uses clean NetBBS v7.31.0.

GitHub executes synthetic merge `62a7da5321d3313ae13bad0bfa2c7ddc11361c0b`.
Its complete tree `491c552b6cfd43f07643da4fdd4c51d619e957e0` equals the source tree.
The manifest retains both SHAs and hashes the text and raw counterparts.
Large raw ANSI/style JSON remain in the exact linked CI artifacts.
Text retains every cell, including the reserved final corner.

Pre-P2 local root at `6911c832f05dae4b5de82603c436e653bc4aa826`:
**1709 passed / 1 skipped**.
The current combined head passes full root CI on Windows and Linux;
`root-ci.json` records each exact count and job URL. This distinguishes
the earlier independent local run from current-head hosted execution.
Focused disclosure/replay/arrival/geometry/City Map checks: **81 passed**.
Strict packet: **99/99**, zero authored CP437 failures.
Every glyph/style golden and mechanics file matches S25b byte for byte.
The earlier pre-S25b packet is superseded; its bytes remain in Git history.
The repeated combat-name finding was withdrawn after tracing the real
retaliation callback. `shipped-retaliation.json` records caller-first hit
and miss against the unmodified shipped Warden. The production-hook
regression remains; `review-triage.json` links the written re-check.

These receipts grant no human layout, content, pacing or performance
approval. Raw worlds, node databases and authentication files are absent.
