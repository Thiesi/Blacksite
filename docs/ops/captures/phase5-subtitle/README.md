# Phase 5 subtitle: native title captures

These are text captures of the title screen as a real caller saw it, with
the new subtitle `a real-time door for NetBBS . the year of the Exhale` at
80x24 and 132x50.

- **Source:** CI artifact `s05-linux-service-proof` (id 13691550319), from
  run [42647932148](https://github.com/Thiesi/Karst41/actions/runs/42647932148)
  at head `188f598` on PR #198. The runtime code is the same as at
  `a7f23cf`; the only later change is a test file.
- **Transport:** real NetBBS v7.45.0 Telnet into the installed wheel,
  through the S04 caller flow (`accept_s04_netbbs.Caller.play`) that S05
  reuses. In the full native run the S04 subset job is skipped, so S05 is
  where that flow runs.
- **Method:** the raw `.ans` streams were replayed from the alternate-screen
  start through `tests/fake_terminal.FakeTerminal`, stopping at the first
  complete frame that has `KARST 41` on row 1 and the new subtitle.

| File | Raw stream | sha256 |
|---|---|---|
| `title-80x24.txt` | `netbbs-80x24.ans` | `76ca8825dde8a58ccff3f14dbeca2a54ee5bee60b1afbd1d8c4ccb1de0948ca6` |
| `title-132x50.txt` | `netbbs-132x50.ans` | `72f73f2ada3be0b1de2eb5fda2c3bddda76175fbc37aa3e24f05493cab556d75` |

At 80x24 the 52-character subtitle fits the title column, which holds 53
cells. At 132x50 it is untruncated.
