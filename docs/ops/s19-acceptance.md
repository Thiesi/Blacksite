# S19 acceptance record

Implementation and final-head proof:
[PR #62](https://github.com/Thiesi/Blacksite/pull/62).
This record distinguishes observed interactions from future geography
and human pacing. It does not certify enjoyment from automated runs.

## Test suite

Windows, Python 3.12.10, from the repository root:

```
pytest -q --basetemp=.test-tmp/s19-full-root-5 --junitxml=.test-tmp/s19-full-root-5.xml
```

Result: **1344 passed, one skipped**, 671.94 seconds. The final escort
custody changes also passed 165 contract/NPC tests. The waiting regression
uses the actual wandering mission template and fails with only its wait
guard removed in memory. The withdrawal regression failed before its fix
and passes with another original worker taking over.

## Actual NetBBS terminal acceptance

Local NetBBS 7.33.0, Telnet to a registered native stdio door, installed
Blacksite 0.0.17, actual ANSI terminal output, 16 colours and wide names.
Every driver verifies the installed client's version and normalized
whole Python tree against its game service before opening a caller.

| Driver | Cases observed | Boundary |
|---|---|---|
| `accept_s19_netbbs.py` | Manual and public-loan first job at 80x24 and 132x50; 200 chits, 100 XP, explicit eight-faction +5, evidence and ordinary exit | Shipped hub; no gameplay fixtures |
| `accept_s19_crews.py` | Both sizes; consent, four targets become six, 250/275 chit payments, 250 XP each, late third member receives zero | Mission drones use one HP and delayed attacks/movement; combat pacing is not measured |
| `accept_s19_services.py` | Four services, both allocations at both sizes; both walked-template outcomes and ration choices; repair reconnect and acknowledged-payment server restart | Three future service bindings and fork geography use a labelled local bay; Cold Chain retains its shipped clinic/core; uptime setup exposes faults |

The final service/fork wheel has SHA256
`86de84bf1189db3d74d6296ecf3890a38a2051c23eaadac797dbcb09bbdc3ba5`.
Its Python tree is
`0af07f80f70b25c6a3d9e31e4dd917e7963b88b480e4d9094ba56601cc70745f`.
All four result files, their client fingerprints, worker payments and
restart assertions were independently checked against the source tree.
Individual hub/crew runs retain their own fingerprints; PR #62 records
the final-head results and durable CI artifacts for the complete matrix.

Run each driver with the NetBBS interpreter and
`--door-python <installed-Blacksite-python> --root <proof-directory>`.
Use `--show` in a real terminal. The service driver defaults to `all`;
its optional `--stage forks` isolates fork diagnostics. CI uses `all`.
Proof directories retain JSON results, client fingerprints, ANSI streams,
text snapshots and progress/failure logs. Failed intermediate runs are
not substituted for these successful cases.

## Remaining consumer acceptance

The [content handoff](../plan/s19-content-handoff.md) names every S25
binding and S27/S26 activation requirement. Three services and all 33
Season 1 contracts remain authoring content until those dependencies land.
No future map, neutral referral or story source is supplied by an alias.

The [earnings report](s19-earnings.md) observes actual receipts and quotes
but assumes activity cadence. S25/S26 still require complete-city human
pacing, the real commerce/clinic routes, useful optional credentials and
natural group-escort arrival. Pure fact-sequence chain replays and native
fixtures establish mechanics, not full-city navigation or entertainment.
