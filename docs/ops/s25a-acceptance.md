# S25a acceptance record

Implemented by Codex (GPT-6), rather than the preferred Opus. This
record covers the engine split from S25 at `1224c30`, based on current
`main` at `68dd3e8`. No S25 map or hub geometry is included. S25's human
layout approval remains **not granted**. S25a remains in progress until
the required reviews and acceptance pass; only the owner merges.

## Scope and canon

The owner's decisions in plan §14.2 are the authority. Game design
§5.2 now specifies sight by zone: Service 5, Drowned 4, Caverns 3,
Outworks 6, Shaft Foot 10; the existing light-effect floor, Lowlight
Eyes and Flare Stick calculation remains intact. Tests exercise all
five values on fixtures; their maps arrive in S25b.

Game §§5.2, 5.5, 5.6, 6.4, 7.5, 7.7, 8.4 and 8.7 record the ported
rules and fixes. Gate Nine's 60/120-second schedule, the city NPC stat
table (XP 20, respawn 60 s), and gantry damage 5 dps are provisional,
tuned at the pacing gate. Water's destination movement cost is 2.
Entities §§1.1, 1.2, 1.6 and 1.17 and architecture §§6.1 and 15 describe
their contracts. The gazetteer retains its original sight values and
describes unmarked hidden passages. The Lattice records the conditional
48-cell Terraces target while retaining the current 36-cell baseline.

Relay Zero's staged reserve credential names only `worker_return`;
its inactive core declares that control without new hardware or map
placement. The ordinary `relay_open` stays public. S25b owns the real
gate, walls, shortcut measurement and lockdown proof. The new NPC
profiles, 24 homes, vendors and ordinary core activation also remain
with S25b/S25c. There is no mechanics fingerprint yet (P1 owns it), and
no golden rebaseline or rendering change is included.

## Deterministic checks

Run pytest from the worktree root with its `src` on `PYTHONPATH` and
a private `--basetemp` under `.test-tmp`.

| Check | Local result |
|---|---|
| Route credentials, saved journeys, water, Gate Nine, lifecycle | 36 passed, 1 Windows skip |
| Corrected catalog, validator and service-effect suite | 144 passed |
| Sector baseline, E/J, sight, recovery, salvage, homes, crews | 48 passed |
| Initial content/service/crew run | 293 passed, 1 stale starter-tile assertion failed; corrected and covered above |
| Initial local full suite | Interrupted after catalog correction; no full local pass claimed |
| First full root CI, `28136c0` | Linux 1570 passed, 1 failed: Terraces baseline/target mismatch; corrected at `f342e3b` |

Full Linux and Windows root CI, automated review and technical review
at the PR head remain separate gates. Their current results belong in
the PR, not inferred from these focused checks.

## Native functional evidence

Command, using the local NetBBS interpreter and a freshly installed
Blacksite wheel:

```text
python scripts/accept_s25a_netbbs.py --root .test-tmp/native-quiet
  --door-python .test-tmp/native-venv/Scripts/python.exe
```

This runs real registered native stdio doors through a local NetBBS
Telnet node. It uses 16 colours at 80x24 and 132x50 and a name containing
`界`. The server and isolated installed door have matching Python trees.
The local NetBBS checkout is at
`15f1605f80bb2235989f40accec3ab46f1cc3cae`, rather than the CI release pin.
The wheel SHA256 is
`3838b28f0776250fb602d374d4475dc61cf13641f079e2ae3f4a677112f6d69a`.

The explicit private Wake fixture adds one water tile and an adjacent
terminal. It excludes wandering Wake NPCs to isolate fallback E; the
other nine shipped zones retain their ordinary population. Runtime
fixture props exercise light, camera, salvage marker and season console.
No character funds, gear, placement or route authorization is granted.

Playable sequence from the ordinary Wake spawn:

1. Walk across the water tile to the fixture terminal. The destination
   step consumes twice ordinary movement time.
2. Stand on each passive marker and press E. The Lattice opens. Press
   J and wait for the actual street view before the next case.
3. Stand on the console and press E. Its sealed-door message appears;
   no Lattice presence is created. Press J to jack in explicitly.
4. Jack out, activate the shipped zones for the strict NPC sample, then
   leave through the normal door exit back to the BBS.

Both sizes completed those functional checks. The proof directory
contains live `.ans`/`.txt` captures by scenario, `native-client.json`,
`startup-profile.json`, NPC profiles and `result.json`. These are
automated functional captures, not a human layout pass. SSH, web,
truecolor and 256-colour captures were not run locally for this split.

## Performance stays failed locally

The final quiet-fixture Windows run reports `functional_passed: true`
and `passed: false`, exiting with failure:

| Sample | Measured | Budget | Result |
|---|---:|---:|---|
| Startup | 6.531 s | ≤3 s | fail |
| NPC p99, 80x24 | 30.852 ms | <10 ms | fail |
| NPC p99, 132x50 | 153.266 ms | <10 ms | fail |

Earlier local startup samples of 16.235, 11.172 and 9.109 seconds and
failed NPC samples are retained under `.test-tmp/native-*`. A capture
attempt with a wandering orderly also failed before the fixture was
isolated. No failed run is represented as a pass.

The dedicated S25a workflow repeats the native fixture on Linux against
NetBBS `v7.31.0`, with startup copy/load/validate and NPC wall/thread CPU,
GC and storage-flush diagnostics. It keeps the same budgets, including
probe overhead. The ordinary native matrix still checks the unchanged
shipped population and the broader subsystem scenarios. Neither this
record nor a CI pass grants any human gate or commissions S25's maps.
