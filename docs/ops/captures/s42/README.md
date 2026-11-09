# S42 engineering evidence

Base: `aef69d989ba48658d7feb2ba5e3f3375d167c90b` (S42 filing,
PR #183). Implementation and review belong to issue #182. This packet
does not grant presentation acceptance, H1 or S25 layout approval.

## Frozen values

[`frozen-values.json`](frozen-values.json) records an unchanged mechanics
fingerprint and the unchanged original P3 matrix: 10,704 cases, SHA-256
`05213f386e4ca644479f8ff80d43ca4e27ebd0acd0013e644b2072a9b9c59185`.
No case changed, so there is no rebaseline or changed-case exception.
The driver is `tests.presentation.interaction_matrix.run_matrix`; the
fingerprint is `tests.presentation.mechanics.fingerprint`, compared with
the existing committed baselines. Both ran against this worktree with
`PYTHONPATH=src;.`.

## Focused validation history

All pytest commands use `PYTHONPATH=src` and
`--basetemp=.test-tmp/pytest`. No full local suite has run.

1. Dialogue runtime, NPC engine and truce modules: **110 passed,
   9 failed**. [Original output](validation/focused-1.log). The nine
   assertions expected the old covered Warden Marked/heat hostility.
   S42 intentionally removes it. Tests now retain real-Warden controls;
   the hostile-but-covered Tab scenario uses an armed undercover fixture
   and retains its ordering and no-targeting-reveal assertions.
2. Initial new S42 tests plus truce and door dialogue tests:
   **102 passed, 8 failed**. [Original output](validation/focused-2.log).
   These were fixture errors: PgUp/PgDn protocol names are `pgup`/`pgdn`,
   a guard occupied a control spawn tile, the vi welcome settings were
   nested incorrectly, and the offer fixture lacked its nearby board.
3. Corrected fixtures, all new S42 tests, truce, door dialogue and S39
   exit tests: **165 passed**. No failed gate was rerun unchanged.
4. Expanded reach, covered-name, real-shot, secret-faction guard,
   first-meeting and overlay cases, plus existing dialogue runtime,
   NPC engine/truce, door dialogue and S39 modules: **243 passed**
   in 66.02 seconds. The command named those seven test modules.
5. NPC reach/engine/truce after adding a shared lost-sight close across
   evaluation phases: **137 passed** in 59.76 seconds. The extra
   `poses_as` validator cases then passed separately (**1 passed**).

The initial standalone frozen-value helper also exited after completing
the matrix because it named `mechanics-baseline.json`; the existing file
is `mechanics.json`. The corrected helper produced the retained result.
An initial pytest command could not redirect output before the scratch
directory existed; pytest did not start.

## Runtime boundaries and reveal audit

The reach filter applies only to ordinary wandering. It preserves all
adjacent eligible callers, following game design 5.5's singular rule
that a wander step never leaves a player beside it behind. The slice's
lower-level "every" wording was corrected to "any" to match canon.
No extra zone RNG draw is introduced. Patrol, hunt, flee, event motion
and A9's return-home route retain their movement paths.
Declared crowd members share the latest ordinary observation of their
current attacker. Their existing 20-second lost-sight interval ends on
one tick, after every member's observation phase, rather than exposing
the cover through different five-tick evaluation phases. Their common
provocation deadline also ends the reaction on one tick.

Every production `Combat.reveal` call was inspected in current source:

| Caller | Why it reveals |
| --- | --- |
| `Combat.warn` | Raising a weapon to act against that caller |
| `Combat.shot` | An actual attack |
| `Combat.hurt` | Actual damage |
| `Npcs.keep_truce` | Keeper guards begin hunting |
| `Npcs.provoked` target/group | Only a hunting response; fleeing keeps cover |
| `Npcs.provoked` local guards | Recruited guards begin hunting |
| `Npcs.evaluate` | Hunt, after deciding the action state |

`Combat.select` and `Combat.target_view` do not reveal. The graph's
static callers missed dynamic `self.combat.reveal` sites, so the audit
also searched and read every current server source match. Unrelated
Lattice and event methods named `reveal` do not call `Combat.reveal`.
Covered, unarmed actors are also excluded from secret-faction guard
recruitment: they enforce nothing until a separately specified action
can make them act against a caller.

## Native capture route

`scripts/accept_s42_netbbs.py` runs real NetBBS Telnet to the registered
native stdio door, with an isolated source-matched wheel. Its workflow
runs both sizes and all three colour tiers. Captures cover the physical
talk hint, one movement press closing and moving, and a real shot causing
ordinary flee movement to close the page with "Sodium regular walks
off." The script declares its relocated regular, ambient pause and
initial 25-tick movement cooldown. It injects no shot, flee step, player
movement, page close or log line. Shipped NPC positions and counts do
not change.

Native results and the presentation lead's acceptance are pending.
