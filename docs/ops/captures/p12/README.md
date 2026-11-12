# P12 engineering evidence

Slice: [`P12-talk-and-log-fit.md`](../../../plan/slices/P12-talk-and-log-fit.md),
issue #204, PR #206. This packet does not grant presentation acceptance,
H1 or S25 layout approval.

## Native packet

[Manifest](native/manifest.json) and the four `results-*.json` files
retain 24 live captures from P12 acceptance
[run 43103576913](https://github.com/Thiesi/Karst41/actions/runs/43103576913),
at source head `dbec9c4`. The capture is NetBBS v7.45.0 over Telnet to a
registered native stdio door, run from an isolated installed wheel. The
script is `scripts/accept_p12_netbbs.py` and the workflow is
`.github/workflows/p12-acceptance.yml`.

The run covers four jobs: 80x24 and 132x50, each in the default
renderer (`legacy`) and the opt-in presentation (`present`, the
workflow's `modern`).

| Capture | Tiers | What it shows |
|---|---|---|
| `talk-halvard` | 16, 256, truecolor | Halvard's 155-character record line wrapped whole: 3 rows at 66 cells, 2 rows at 106. Under it, `c  Work board` and a single `Esc/B  Leave`. No `b Back`, no "Choice". |
| `talk-vesper` | truecolor | Vesper's line on 2 rows at 80x24, then `c Work board`, `v Trade` and `Esc/B  Leave` as the vertical list. |
| `log-after-talk` | truecolor | The log after Halvard's line and then Vesper's (see below). |
| `vendor-detail-wraps` | truecolor | The Wake Hall outfitter with the Kestrel Issue Sidearm selected. Its 86-character description wraps whole at 132x50. At 80x24 the 4-row detail rect ends row 4 with `...`, rule 3's fallback, accepted for that size by the presentation lead. |

In `log-after-talk`, Vesper's line is the newest entry and shows whole.
Halvard's older 3-row entry can't fit whole at 80x24, so it is hidden, as
rule 5 requires: no entry shows without its head. Where a shorter, older
entry fits the free row, it fills it; steps 2 and 4 say "fill whatever
is left".

The `.txt` files are byte copies of the captured screens, including
terminal padding. `scripts/accept_p12_netbbs.py` also asserts each
scenario on the live screen:

- every word of the line, in order;
- exactly one `Esc/B  Leave`;
- the line is a real shipped line;
- the description is whole or cut as stated.

The raw `.ans` streams and the JSON style snapshots stay in the four CI
artifacts named in the manifest. The SHA-256 of every `.txt`, `.ans` and
`.json` file in the results was checked against the downloaded artifact
files before copying.

## Fixtures (declared)

On main, every talker in the `s27-cast` bundle (halvard, vesper,
dispatcher and the rest) is still `"authoring"`, and none is placed. The
only active dialogue is `row-street-regular`. **None of the talkers in
these captures can be met in play today.** They are fixture-placed
copies:

- `p12-halvard` and `p12-vesper` are the shipped `halvard` and `vesper`
  dialogue, unchanged except for their ids. They sit as contact objects
  beside the caller in the Tin Halo, following S39's precedent
  (`scripts/accept_s39_netbbs.py`).
- Halvard's record line needs journal evidence `s19-hal-s1-1-recovery`
  and a prior meeting. Both are granted.
- The outfitter is the real shipped counter. The Wake training fight is
  skipped with `b` first, as the Row route already does.

The slice text asks for the 164-character dispatcher line in capture 1.
That talker sits in the Lattice. The technical lead and presentation lead
agreed on Halvard instead. Unit tests in `tests/door/test_p12_fit.py`
render the 164-character line in both renderers at both sizes.

## History

At `0f70009`, P12 acceptance
[run 43101174416](https://github.com/Thiesi/Karst41/actions/runs/43101174416)
failed in one job (132x50 presentation). The script pressed Down before
the client held the vendor page, so the cursor never moved. The other
three jobs passed. The script fix at `dbec9c4` waits for the rendered
page first. No product code changed between the two runs.
