# P8 engineering evidence

Slice: [`P8-voice-and-ambience.md`](../../../plan/slices/P8-voice-and-ambience.md),
issue #209, PR #230. This packet does not grant presentation acceptance,
H1 or S25 layout approval.

## Native packet

[Manifest](native/manifest.json) and the four `results-*.json` files hold
36 live captures from P8 acceptance
[run 43340009052](https://github.com/Thiesi/Karst41/actions/runs/43340009052),
at source head `3cf8514`. Transport: NetBBS v7.45.0 over Telnet to a
registered native stdio door, from an isolated installed wheel. Script
`scripts/accept_p8_netbbs.py`; workflow
`.github/workflows/p8-acceptance.yml`.

The run has four jobs: 80x24 and 132x50, each in the default renderer
(`legacy`) and the opt-in presentation (`present`, the workflow's
`modern`). Each job runs every scenario in all three tiers (16, 256,
truecolor), so every scenario has 12 captures.

| Capture | What it shows |
|---|---|
| `bark` | On Sodium Row, a regular within six tiles barks: "Sodium regular: A tram goes over somewhere above the roofs. The puddles shiver." It's a `speech` line under the regular's presented name. At 80x24 it wraps onto a second log row, whole. |
| `ambience` | A Row ambience line (`ambient`, no speaker) arrives, from `looks/sodium-row.json`. Which line it is comes from the Row's own random stream. |
| `combat-quiet` | After a real F at the regular, the combat line ("You raise your weapon. …") is in the log. For the next 8 s the bark and the ambience are forced due every half second, and none is delivered (`delivered_in_window: []` in the results). That's the suppression and the 10 s hold. |

The `.txt` files are byte copies of the captured screens. The raw `.ans`
streams and JSON style snapshots stay in the four CI artifacts named in the
manifest. Every `.txt`, `.ans` and `.json` SHA-256 in the results was
checked against the downloaded artifact files before copying.

A capture's screen check compares each whole log entry, joining a wrapped
line's rows, so a cut or half-drawn line would fail the run.

## Cost

[`native/p8-cost.json`](native/p8-cost.json) is the `p8-cost` job of the same run
(`scripts/measure_p8_cost.py`, ubuntu-latest). It puts one, then three,
callers on the shipped Row for 10 simulated minutes:

| callers | emitter per tick | its 1 Hz tick: mean / p99 / max | emitter's share of loop | lines heard per caller |
|---|---|---|---|---|
| 1 | 4.9 µs | 40 / 77 / 109 µs | 0.43% | 8 |
| 3 | 6.0 µs | 49 / 103 / 147 µs | 0.21% | 12, 9, 11 |

## Fixtures (declared)

- One Sodium regular is relocated beside the caller and holds still, so it
  is inside the bark radius when filmed.
- Its bark is made due, and the Row's ambience is made due once the
  caller's 20 s budget has reopened. This saves waiting the 90 s interval
  and the 60–90 s cadence. While the ambience is filmed, other barks wait,
  so a regular firing in the same second can't spend the budget first.
- The keeper's guards hold fire (S44 precedent), so the shot doesn't end
  in a death. During the quiet window the bark and the ambience are forced
  due every 0.5 s, to show suppression, not silence, keeps the log clear.

## History

Earlier runs on #230 failed on the script's own checks, each fixed in its
own commit. None was a product failure.
- It matched another zone's ambience heard on the trip to the Row.
- An 80x24 wrap defeated a whole-text match.
- A second bark took the budget as the ambience was made due.
