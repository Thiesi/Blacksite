# S42 engineering evidence

Base: `aef69d989ba48658d7feb2ba5e3f3375d167c90b` (S42 filing,
PR #183). Implementation and review belong to issue #182. This packet
does not grant presentation acceptance, H1 or S25 layout approval.

## Current-runtime native packet

The final author audit found true names in Hit/Miss combat feedback.
The correction uses the existing per-caller presentation service,
including the controlling caller for player drones. The new packet
includes an actual covered-actor shot at every size and colour tier.

[Manifest](native/manifest.json) and [results](native/results.json) retain
24 live captures from successful [run 42554076114](https://github.com/Thiesi/Blacksite/actions/runs/42554076114):
both 80x24 and 132x50, in 16, 256 and truecolor. Source head:
`1f80fefab79153b0fe2301a5f32c32c2419f0289`; source tree:
`c31b7cd892440449e3c834232c8670fc76a3087e`; Python tree SHA-256:
`c5b58d97b60536562be354cbde46cfdd54580540728f90ace91e45ff77b09974`.

Each of the six size/tier combinations has four checkpoints:

- `talk-hint`: an actual regular's page shows "Move or Esc/B leaves".
- `one-press-walk-away`: one movement press closes and moves the caller.
- `shot-flee-walks-off`: actual F firing, its committed attack, and
  ordinary flee movement close the page with the captured system line.
- `covered-shot-label`: actual F firing at the covered actor logs its
  cover name, with no true name or caller reveal.

The retained `.txt` files are direct byte copies, including terminal
padding. Raw `.ans` streams and large style snapshots remain in the six
CI artifacts linked in the manifest. `scripts/packet_s42.py` verified
every file hash, independently replayed each ANSI stream for glyphs and
styles, and checked the source-matched client against the pinned Git
tree. The packet is 165,216 bytes, within the 200 KB evidence budget.
It refuses failed/incomplete runs, source/hash/replay mismatches and an
existing destination. The source head is never relabelled as a later
packet-only head. Current-head CI and review are recorded separately
on PR #188. The earlier 18-capture packet remains available at
[e2e4fcd](https://github.com/Thiesi/Blacksite/tree/e2e4fcdfff002b07fc7affbe9bef734c51f053c9/docs/ops/captures/s42/native),
pinned to its original runtime, before the combat-feedback correction.

The full S42 evidence directory is about 274 KB because it also preserves
the first local native proof and the original failed focused-test logs.
Those historical records explain failures and setup limits; neither is
relabeled as current-runtime proof. The large new ANSI/style streams
remain CI artifacts rather than being added to the repository.

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
6. Corrected legacy-content and manually constructed talk-menu fixtures:
   **36 passed** in 17.63 seconds across their two modules.
7. Ruled TARGET/NEARBY/Tab parity, armed-cover control, existing truce,
   view-semantics and world/session tests: **119 passed** in 54.96 seconds.
   The two actual-shot parity cases then passed with a farther hostile
   keeper, which would outrank a cover wrongly left in the neutral bucket.
8. Actual-shot feedback for either crowd member, both revealed/covered
   drone cases, and existing combat/drone ownership modules:
   **80 passed** in 34.09 seconds.

Full branch CI history (the root suite, not a local full suite):

| Head | Run | Linux | Windows |
| --- | --- | --- | --- |
| `f485335` | [42543547211](https://github.com/Thiesi/Blacksite/actions/runs/42543547211) | 3 failed, 2502 passed | 3 failed, 2501 passed, 1 skipped |
| `43225d0` | [42544238313](https://github.com/Thiesi/Blacksite/actions/runs/42544238313) | 3 failed, 2503 passed | 3 failed, 2502 passed, 1 skipped |
| `e1a126c` | [42545805798](https://github.com/Thiesi/Blacksite/actions/runs/42545805798) | 2509 passed | 2508 passed, 1 skipped |
| `e2e4fcd` | [42548574546](https://github.com/Thiesi/Blacksite/actions/runs/42548574546) | 2509 passed | 2508 passed, 1 skipped |
| `1f80fef` | [42554070213](https://github.com/Thiesi/Blacksite/actions/runs/42554070213) | 2511 passed | 2510 passed, 1 skipped |

Both runs found the same three fixture adaptations: the legacy NPC test
removed the cover but retained its new `poses_as` binding, and the two
size variants of a view test constructed `TalkerMenu` without the new
caller pose/hit fields. The fixtures now provide the matching state;
their original disclosure assertions remain. The second head was pushed
for the crowd timeout correction before the first CI finished. Neither
failed head was rerun unchanged.

The first PR's [P6 charted-budget job](https://github.com/Thiesi/Blacksite/actions/runs/42547068957/job/128934251671)
also failed. The historical Row metadata lacked S42's required
`poses_as`; there was one final validation error, with max CPU 0.312s
below the unchanged 3s limit. `presentation_p6_validation.py` now supplies
only that declared link in memory for its two pinned-data cases and
records the adaptation. Pinned JSON/map bytes, their hashes, geometry,
all three validator phases and all assertions remain unchanged. The
shipped case gets no adaptation. The full local comparison then passed
all three datasets/phases, with zero final errors and max final CPU
0.28125s. The complete P6 workflow passed at `e2e4fcd`
([42548574496](https://github.com/Thiesi/Blacksite/actions/runs/42548574496));
fresh current-head acceptance is recorded on the PR.

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

The real-shot view comparison exposed another tell: the regular's
TARGET relation became `hostile`, while the fleeing covered NPC stayed
`neutral`. The [technical lead's ruling](https://github.com/Thiesi/Blacksite/issues/182#issuecomment-6729956315)
includes that correction in S42. Only a still-covered, unarmed actor
with a declared crowd gets its public provocation relation in TARGET,
NEARBY and Tab ordering. Real-shot tests compare both actors' complete
TARGET and NEARBY records, excluding actor identity, after shooting
either member. Equal-range/high-HP fixtures remove ordinary range and
displayed damage differences. Actual Tab inputs select both in the
same public hostility/distance order without revealing either. An armed
covered fixture retains its mask until it hunts.

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

All six current-runtime native cases passed, as recorded above. The
driver adds a fourth checkpoint: an actual shot at the covered
actor prints only "Hit: Sodium regular." or "Miss: Sodium regular."
Its declared fixture relocates that actor and delays movement for
100 ticks. Presentation acceptance is pending.

## Automated review record

[Claude Sonnet 5.5 reviewed `e1a126c`](https://github.com/Thiesi/Blacksite/pull/188#issuecomment-6730270932)
and reported no actionable findings. This was static review, not a
test or playthrough. [Triage](https://github.com/Thiesi/Blacksite/pull/188#issuecomment-6730413557)
accepts the bounded boot activity grace and confirms that posed-faction
guards/no extra Warden heat are the intended owner-approved outcome.
Neither observation requested a change. The reviewer did not review
this evidence packet or Windows CI.

All three delivered reviews at `e2e4fcd` were triaged on the PR with no
actionable findings. Claude Sonnet 5.5 then reviewed `1f80fef` twice:
[full diff](https://github.com/Thiesi/Blacksite/pull/188#issuecomment-6731226440)
and [requested incremental pass](https://github.com/Thiesi/Blacksite/pull/188#issuecomment-6731245654).
Both report no actionable findings and were static reads, with no tests
or capture verification. Their dispositions are recorded
[here](https://github.com/Thiesi/Blacksite/pull/188#issuecomment-6731235000)
and [here](https://github.com/Thiesi/Blacksite/pull/188#issuecomment-6731288535).

The incremental review suggested checking other combat-name logs. Exact
current source confirms that warning/damage lines name the attacker
after its reveal, while these unarmed NPCs flee without attacking.
Pickup is a player/crew path. NPC death emits no victim-name message;
both shipped crowd templates have XP 0 and identical ration loot, so
the eligible-kill standing/reward branch does not distinguish them.
This is a source audit, not a native death-scenario claim. The graph
server was unavailable for this final check; exact source was used.

### Passing local proof at an earlier head

The [local manifest](local-80x24-16/manifest.json) pins three passing
80x24/16-colour captures to head
`43225d06505dbb871e4c2f1ca321d789ee2a9862`, before the ruled view-parity
correction. They show the [hint](local-80x24-16/s42-talk-hint-80x24-16.txt),
[one-press move](local-80x24-16/s42-one-press-walk-away-80x24-16.txt) and
[real-shot flee close](local-80x24-16/s42-shot-flee-walks-off-80x24-16.txt).
All three raw ANSI prefixes were replayed independently against the
retained text and style snapshots. Their common cumulative ANSI stream
is retained losslessly as gzip; the manifest records each prefix length
and hash, the compressed hash and the source-matched Python tree hash.

This was actual local NetBBS Telnet/native stdio output, forwarded with
`--show` to exec output. PTY creation was unavailable, so it is not a
physical-terminal or human-acceptance claim. Local setup first lacked a
build backend; an isolated wheel build succeeded. Attempts to execute
the NetBBS interpreter or read its dependencies inside the sandbox were
denied before acceptance started; the authorized non-PTY execution
completed on its first actual native run. No failing native gate was
rerun. The new complete capture matrix is recorded separately above.
