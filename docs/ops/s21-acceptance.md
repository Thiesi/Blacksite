# S21 acceptance record

## Installed native proof

The local native run uses gameplay source `0b3ffaef`, package 0.0.18,
and NetBBS 7.31.0 checkout `d04170a`. Both callers' negotiated terminal
sizes run through real Telnet, a registered native stdio door and the
installed wheel. The Windows game-service connection uses loopback TCP.
The probe checks the isolated interpreter's package version and whole
normalized Python tree before starting; it cannot import the source
server through `PYTHONPATH` and claim that as the installed client.

| Evidence | Result |
|---|---|
| Wheel | `blacksite-0.0.18-py3-none-any.whl`, 579534 bytes |
| Wheel SHA-256 | `5ddd7c090980d99eb7302de92e251d30b9201e8a12c861581b5fb3429782b0b2` |
| Whole Python tree SHA-256 | `8344f8cd6975c01444d2da9b9e0ea0719b37e9cc82862f9a9413201aa3f64db3` |
| 80x24 | Passed; real capture hold 182.3 seconds |
| 132x50 | Passed; real capture hold 182.4 seconds |

Command, from the isolated slice worktree, once for each size:

```powershell
$env:PYTHONPATH="$pwd/src;$pwd/scripts"
C:/Users/Thiesi/OneDrive/Dev/NetBBS/.venv/Scripts/python.exe `
  scripts/accept_s21_netbbs.py --root .test-tmp/s21-native-4/80x24 `
  --door-python .venv/Scripts/python.exe --size 80x24 --show
```

The second run substitutes `132x50` in both arguments. Preserved local
evidence is under `.test-tmp/s21-native-4/<size>/`: `s21-results.json`,
`native-client.json`, terminal `.ans`/`.txt` captures, `progress.log` and
`console-output.json`. CI adds downloadable per-size relay proof archives.

Both sizes exercise wide-character names, actual walking to Cold Chain,
explicit hold and named runner support, competing-claim and Curfew
pauses, a real committed `relay_open` control, a full three-minute hold,
exactly two 100-XP rewards, no reward for the rival, persisted ownership
and core ownership, a usable member counter, outsider refusal, and a
visible increase of 20 influence after the settlement-time fixture.

The disclosed fixtures are faction membership, an ICE-free copy of the
real tier-two Cold Chain core, a brief Curfew provider, and an injected
two-hour UTC advance **after** capture. There is no placement, funding,
grade or capture-clock fixture. The public loan terminal, network route,
core/control channel, capture duration, caller keys and storage receipts
are real. This isolates territory from already-covered ICE combat and
from S24's future event scheduler.

## Automated gates

The exact gameplay head passed the full repository-root `pytest -q` on
Ubuntu: **1400 passed in 170.47 seconds** (Actions job `120537411164`).
Windows: **1399 passed, 1 skipped in 367.31 seconds** (job `120537410859`).
The supplemental local full-root run and final-head review/check record
are tracked in [PR #63](https://github.com/Thiesi/Blacksite/pull/63).

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
