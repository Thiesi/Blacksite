# S21 acceptance record

## Installed native validation

The local native run uses gameplay source `9034ff7`, package 0.0.18,
and NetBBS 7.31.0 checkout `d04170a`. Both callers' negotiated terminal
sizes run through real Telnet, a registered native stdio door and the
installed wheel. The Windows game-service connection uses loopback TCP.
The probe checks the isolated interpreter's package version and whole
normalized Python tree before starting; it cannot import the source
server through `PYTHONPATH` and claim that as the installed client.

This includes the review's capture-retry fix. Script-only navigation
fixes at `21a6a12` retain the same installed production package. Final
checks and written review triage are recorded in
[PR #63](https://github.com/Thiesi/Blacksite/pull/63).

| Evidence | Result |
|---|---|
| Wheel | `blacksite-0.0.18-py3-none-any.whl`, 579693 bytes |
| Wheel SHA-256 | `d0a78a42be4aae345daa33dbc2d77904053a9437ec7452d1e3f7d6b6e0a2554c` |
| Whole Python tree SHA-256 | `e4931dd51553604e2bb0d4221461022864d22d66d7854319ef980987077d7fb4` |
| 80x24 | Passed; real capture hold 182.52 seconds |
| 132x50 | Passed; real capture hold 182.67 seconds |

Command, from the isolated slice worktree, once for each size:

```powershell
$env:PYTHONPATH="$pwd/src;$pwd/scripts"
C:/Users/Thiesi/OneDrive/Dev/NetBBS/.venv/Scripts/python.exe `
  scripts/accept_s21_netbbs.py --root .test-tmp/s21-native-6/80x24 `
  --door-python .venv/Scripts/python.exe --size 80x24 --show
```

The second run uses `.test-tmp/s21-native-7/132x50` and size `132x50`.
Preserved local evidence in those roots includes `s21-results.json`,
`native-client.json`, terminal `.ans`/`.txt` captures, `progress.log` and
`console-output.json`. CI adds downloadable per-size relay proof archives.

Both sizes exercise wide-character names, actual walking to Cold Chain,
explicit hold and named runner support, competing-claim and Curfew
pauses, a real committed `relay_open` control, a full three-minute hold,
exactly two 100-XP rewards, no reward for the rival, persisted ownership
and core ownership, a usable member counter, outsider refusal, and a
visible increase of 20 influence after the settlement-time fixture.
Independent offline reads through Storage and its lease confirm each
capture fact, two +15 standings, one capture statistic per participant,
20 influence, 20 treasury and committed core ownership.

The disclosed fixtures are faction membership, an ICE-free copy of the
real tier-two Cold Chain core, a brief Curfew provider, and an injected
two-hour UTC advance **after** capture. There is no placement, funding,
grade or capture-clock fixture. The public loan terminal, network route,
core/control channel, capture duration, caller keys and storage receipts
are real. This isolates territory from already-covered ICE combat and
from S24's future event scheduler.

## Automated gates

The driver-fix head `21a6a12` passed full repository-root `pytest -q` on
Ubuntu: **1402 passed in 161.40 seconds** (Actions job `120590680137`).
Windows: **1401 passed, 1 skipped in 169.13 seconds** (job `120590679723`).
The supplemental local full-root run and final-head review/check record
are tracked in [PR #63](https://github.com/Thiesi/Blacksite/pull/63).
The three delivered Claude Sonnet 5.5 reviews cover production, content
and driver changes; their written reports do not claim independent test
execution. Worthwhile findings and rejected speculative observations are
explicitly triaged there. An automatic workflow validation skip is not
treated as a clean review.

Current focused local checks include eight width-safe relay/passage/
defence menu cases, seven relay benefit/content cases, and the committed
remote-faction loss-notice case. Failed-source injection verifies that a
loss notice is not sent before commit. Passage tests cover failed fares,
unused prepaid recovery, in-flight restart before/after arrival, immediate
gate arrival and preserving free alternatives. Full-root CI includes them.

An earlier local run used a changing worktree and is not a final gate:
its obsolete Old Works-only assertion failed after the Lattice-wide canon
fix, and its cold OneDrive startup exceeded the existing 60-second Windows
readiness deadline. The isolated CLI rerun passed in 6.49 seconds. The
final local run uses a fresh private temporary directory; no production
timeout was relaxed to accommodate that development-machine result.

The old reused test interpreter also contained a 0.0.8 client, so final
local subprocess checks use S21's installed 0.0.18 environment with its
declared pytest dependency. A diagnostic confirmed slow local Windows
client startup: no output within five seconds, then successful title,
help and exit under a 30-second readiness deadline. The Windows pipe
startup check and native harness use that startup allowance; subsequent
interaction deadlines, capture time and production limits are unchanged.

## Remaining consumers and field acceptance

Cold Chain and Block are live. Fourteen relay/core/counter definitions
remain authoring content, with Shaft additionally gated by S26's opening.
See the [consumer handoff](../plan/s21-relay-handoff.md) for every effect,
the S23 single-treasury dependency, S24 event consumers and S26 settlement.

Future districts, actual Gate Nine/cable routes and all sixteen real
anchors remain S25 work. The passage overlay and future-benefit unit
fixtures do not prove those maps. Full-city earning/clinic affordability,
unopposed relay idle time and meaningful contested decisions still require
the retained S25/S26 human play gate. This native timing proof cannot
close it. New host API/publication integration remains S31; this run
proves the named 7.31.0 native baseline and publishes no BBS capture event.
