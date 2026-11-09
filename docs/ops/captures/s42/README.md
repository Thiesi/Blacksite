# S42 engineering evidence

Base: `aef69d989ba48658d7feb2ba5e3f3375d167c90b` (S42 filing,
PR #183). Implementation and review belong to issue #182. This packet
does not grant presentation acceptance, H1 or S25 layout approval.

## Earlier-runtime native packet

The final author audit found true names in Hit/Miss combat feedback.
The correction uses the existing per-caller presentation service,
including the controlling caller for player drones. Fresh current-source
native proof is pending; the packet below remains historical evidence.

[Manifest](native/manifest.json) and [results](native/results.json) retain
18 live captures from successful [run 42547068997](https://github.com/Thiesi/Blacksite/actions/runs/42547068997):
both 80x24 and 132x50, in 16, 256 and truecolor. Source head:
`e1a126c847b7a6f6b609a30003e70342c6eb1818`; source tree:
`3632d9db75a51cb5f365f92047ba9fdebc1bc96d`; Python tree SHA-256:
`3e25ae2e2d8c8342db06e36f923b8d903379f198c57233b233e8cef70a9a57cb`.

Each of the six size/tier combinations has three checkpoints:

- `talk-hint`: an actual regular's page shows "Move or Esc/B leaves".
- `one-press-walk-away`: one movement press closes and moves the caller.
- `shot-flee-walks-off`: actual F firing, its committed attack, and
  ordinary flee movement close the page with the captured system line.

The retained `.txt` files are direct byte copies, including terminal
padding. Raw `.ans` streams and large style snapshots remain in the six
CI artifacts linked in the manifest. `scripts/packet_s42.py` verified
every file hash, independently replayed each ANSI stream for glyphs and
styles, and checked the source-matched client against the pinned Git
tree. The packet is 123,762 bytes, within the 200 KB evidence budget.
It refuses failed/incomplete runs, source/hash/replay mismatches and an
existing destination. The source head is never relabelled as a later
packet-only head. Current-head CI and review are recorded separately
on PR #188. This packet predates the combat-feedback correction.

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
0.28125s; current-head CI must still verify the complete budget job.

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

All six earlier-runtime native cases passed, as recorded above. The
updated driver adds a fourth checkpoint: an actual shot at the covered
actor prints only "Hit: Sodium regular." or "Miss: Sodium regular."
Its declared fixture relocates that actor and delays movement for
100 ticks. Fresh native proof and presentation acceptance are pending.

## Automated review record

[Claude Sonnet 5.5 reviewed `e1a126c`](https://github.com/Thiesi/Blacksite/pull/188#issuecomment-6730270932)
and reported no actionable findings. This was static review, not a
test or playthrough. [Triage](https://github.com/Thiesi/Blacksite/pull/188#issuecomment-6730413557)
accepts the bounded boot activity grace and confirms that posed-faction
guards/no extra Warden heat are the intended owner-approved outcome.
Neither observation requested a change. The reviewer did not review
this evidence packet or Windows CI. The new packet/fixture head needs
fresh automated review and current-head CI before technical review.

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
rerun. The complete capture matrix still needs current-source CI.
