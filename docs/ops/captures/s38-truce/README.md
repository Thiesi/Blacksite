# S38 truce acceptance

PR #159 implements issue #142 on owner-merged A8, base
`8db772ce550c810d007890400320c53a7c2b69c1`. This packet records
engineering evidence; it grants no human or presentation acceptance.

## Playable scenario

Use an isolated NetBBS node with a registered native stdio Blacksite
door and an isolated Blacksite service. Never use a production world.
The automated script is `scripts/accept_s38_netbbs.py`.

1. Create two callers on separate accounts. Finish or skip the wake-hall
   exercise, then travel through Vatside Clinics and Core Plaza to
   Sodium Row. The header reads `CONTESTED─TRUCE─PvP G5+`. First arrival
   logs `Nobody draws on Sodium Row. Sable makes sure of it.`
2. For this PvP exercise only, the script supplies grade-five players
   through the owning server and queues their saves. The current script
   also supplies Sable/Warden factions and loans an owned Sentry. These
   are explicit fixtures, not grade, membership or item acquisition
   evidence. Bring both
   callers into sight near (12, 5) and (14, 5); target the other caller
   with the normal target keys. TARGET says `Firing marks you`.
   Open DRONES with O, select the loaned Sentry, and deploy with U.
   Its order detail says `order marks you for 15 minutes` even though
   the target belongs to a hostile faction. Capture the menu, recall
   with R and leave with Esc before firing. No drone attack is ordered.
3. Fire through the ordinary warning interval. The attacker becomes
   Marked. The log says `You break Sodium Row's truce. You are Marked
   for 15 min.` before `Sable is coming for you.` The header shows the
   Mark in the modern presentation. Further hits refresh guard
   provocation without repeating that keeper announcement while the
   response remains active.
4. Log both callers out. Create another caller, travel to the Row, and
   approach a shipped Sodium regular. Select that NPC using the normal
   target keys. TARGET says `Truce: Sable answers`.
5. Fire through the warning interval. Sable's shipped enforcers target
   the attacker and the danger log says `Sable is coming for you.` The
   attacker is not Marked for shooting this NPC. Log out normally.

The native workflow repeats this sequence for both presentations at
80x24 and 132x50, in 16 colours, 256 colours and truecolor. Every
caller's negotiated colour tier is asserted. Linux `script` attaches
the primary proof to a PTY; the transport is Telnet into NetBBS and its
registered native stdio subprocess. The script does not bypass fire,
travel, targeting or logout. It does not claim SSH, web, CP437, earned
progression, human pacing, presentation sign-off or H1/S25 acceptance.

## Rule and compatibility evidence

`tests/npcs/test_truce.py` covers faction and explicit-hostility
suppression, retained Warden heat/Marked behaviour, attacks on all
three kinds of Row resident, defense against Marked/hunting targets,
grade and crew protection, valid owned-drone attribution, rejected
out-of-zone drone control, a defending drone whose owner is elsewhere,
remote source bodies, actual Lattice burn
completion, target-zone marking, renewed provocation and announcement
deduplication. The shipped enforcer/covered-Warden regression runs 300
deterministic ticks without faction-driven targeting, harm or reveal.

`tests/door/test_truce_render.py` supplies 24 glyph/style contracts at
both sizes, both presentations and all three colour tiers, including
the longest keeper name and a wide-character caller handle. These
constructed golden contracts supplement the native captures.

The mechanics digest changes from
`09562f9cd4777467352032839849456af7a6b5b5c270593c765595276ca159f2`
to
`b145e1d13f146c6ad1a47879a2325e3e93bb4f0951caea17628feb92896e6f8b`.
The projection changes only `zones.sodium-row.truce`, from absent to
`sable`; geometry, population and the deterministic walk do not move.
This flag/rule move is covered by the owner's approval of S38. No
other fingerprint move is claimed. The frozen pre-P3 E/J interaction
digest stays
`05213f386e4ca644479f8ff80d43ca4e27ebd0acd0013e644b2072a9b9c59185`:
its log projection excludes only the separately tested new first-arrival
place line. Existing handler outcomes and root golden requirements are
unchanged.

## Retained attempts and review

The committed text samples and `manifest.json` come from the first
attached-PTY run, at
`8c6c1d634d54e7c80ac1e6b6c97c7affa0d7fa64`:
[run 42141227625](https://github.com/Thiesi/Blacksite/actions/runs/42141227625).
All four size/presentation jobs passed, with all three colour tiers in
each. The manifest identifies all 48 raw captures and their hashes;
24 representative text samples are committed, keeping this packet
below 200 KB. Each sample includes the header and its named scenario.
The remaining text files and raw streams stay in the named artifacts.
Replay of all 48 game streams matches their text captures and rejects
autowrap-corner writes. The manifest's `terminal_offset` skips the
Telnet negotiation and node picker before the game's alternate-screen
entry; the raw-stream hash covers the entire unchanged file.

P4 also passed both sizes at that same head:
[run 42141227469](https://github.com/Thiesi/Blacksite/actions/runs/42141227469).
These are explicitly earlier-head results. The later announcement fix
does not change the first-attack frames shown here. Current-head native
results and any failures are linked in the PR handoff; this packet
does not relabel earlier captures as current-head captures.

The initial local native attempt at
`3fb3554065cdfe015087a0da7df243ffde4ba203` reached the player-mark
capture and then failed in the harness: `NativeProbe.leave` lacked its
required capture label. Commit
`280499ae2e642109c6ac8d896adf54527a27adfb` fixes those calls. The
original capture archive is retained in the fixed local scratch path
`%TEMP%/blacksite-s38/native-local-first-failure.zip`, SHA-256
`da4dfed12b6a4d17527345e7c82babbdaa95f01aa4393f891750694c547a37e5`.
It is a failed attempt, not completed acceptance. Its small failure
manifest is retained beside this document.

The subsequent local run at
`d82602197128f92e3e4113034601643e473ffcf9` passed the modern 80x24
scenario in all three colour tiers on released NetBBS v7.45.0,
commit `614725882b12749c2e90b40e0d051484d7f0ee47`. Windows did not
supply an attached PTY, so this run is supplementary functional
evidence. Its source-matched wheel SHA-256 was
`280ff931d0bfdf944b2ccb2e21ef74a06fbe714c5843141075d9cb92bc3d866b`.

The full local suite at d826021 passed 2270 tests with one skip.
After the announcement fix and real-burn regression tests, the full
suite at `d68236a5cf12c0b3e2fbfeb7289a396b15b7cb9d` passed
2273 tests with one skip in 408.61 seconds.
The first automated review, Claude Sonnet 5.5 at
`8c6c1d634d54e7c80ac1e6b6c97c7affa0d7fa64`, identified repeated
keeper announcements during player combat. This is credible small-log
clutter. The fix gates only the announcement on an active keeper
provocation; every hit still refreshes the response. New tests cover
multiple guards sharing a spawner, repeated hits and an expired
response. Final validation and current-head review are recorded on
the PR.

The b52c67a review confirmed that fix and found a defending-drone zone
mismatch. A held drone can remain behind after its controller leaves:
`controller_body(acting=False)` intentionally retains its owner's
protection, whereas an attacking drone needs current control authority.
The keeper selection and response now use that same defending owner
body as marking does, consistent with game design 5.3/7.3. Tests cover
both directions: a drone on the Row with its owner elsewhere retains
ordinary non-truce marking; a drone elsewhere with its owner on the
Row invokes the Row's truce and waiting guards. Hostile-faction and
neutral targets are covered without relaxing grade or safety.
The same arrangements run through direct fire, `mark_indirect`, and
two committed machinery hits in `PhysicalEffects.flush_hits`. The
fixtures deploy a real owned drone and issue its normal hold command
before its owner leaves. Remote marking resolves that defending body
before both the Mark text and keeper-hook zone check. Repeated remote
hits produce one waiting announcement while refreshing provocation.

The review's zone-wide alert question is answered by S38's explicit
requirement to provoke every keeper guard in the zone. No new sight or
distance limit is imposed. If there are no keeper guards, the attack
still Marks as required but does not announce a nonexistent chase.
Speculative unrelated-provocation suppression and import-order notes
do not change behaviour; repeated indirect and direct responses share
the tested announcement gate.

## Open presentation boundary

The current presentations have no place-card consumer. The public view
supplies the keeper and `Sable keeps the peace here.`; the existing
header, TARGET warning and arrival/log surfaces render their approved
text. The required place-card label `CONTESTED · TRUCE` and keeper
sentence are not claimed as rendered. The author requested a spec
clarification on issue #142, comment 6673216233, rather than inventing
a new timed/dismissible card in this rules slice. This remains an open
requirement until explicitly disposed of by the owner. The technical
lead confirmed in review 6675920960 (TR-5) that S38 has no card consumer
to extend and requested that owner decision. The public `truce_text`
stays. The remote `<Keeper> is waiting for you on <zone>.` wording also
awaits explicit presentation-lead sign-off (TR-6).

Presentation wording/header sign-off, technical review, and any owner
gates remain separate. H1 and S25 human layout approval remain withheld.

## Technical-review corrections

The review at f9eab8a (comment 6675920960) identified three caller
failures, a related warning mismatch and a missing compatibility test:

- TR-1: keeper warnings now depend on a live provocation or an actual
  hunt, not intrinsic Warden hostility. Marked and heated callers see
  the same warning on a covered Warden and a regular until they
  provoke it. Tests assert both cover-safe warning and keeper response,
  and that only live provocation entries suppress the warning.
- TR-2: remote provocation records the response without replacing a
  guard's current local target, state or last-seen position. A test
  keeps an out-of-sight local chase alive after another player's remote
  attack and subsequent NPC evaluation.
- TR-3: the DRONES order detail uses `would_mark(..., indirect=True)`.
  Tests cover hostile targets on and off the Row and neutral targets
  outside. The updated native acceptance captures that actual menu in
  each size/presentation/colour-tier combination with declared fixtures.
- TR-4: TARGET uses the indirect both-body rule for drone targets. An
  open-area shooter targeting gear whose owner remains in contested
  ground gets the warning that matches the eventual Mark.
- TR-7: direct and indirect attacks on players outside a truce zone
  explicitly assert no NPC provocation, while normal marking remains.

The pre-existing Tab-order tell stays with issue #125. No new card,
balance, population, geometry or ownership-rule change is introduced.
The corrected head's full suite, automated review and fresh P4/S11/S38
runs are recorded on the PR; older evidence retains its original SHA.

The first expanded native run at 19963d5 failed all four jobs while
waiting for `15 minutes` on one rendered line. The saved screens show
the correct warning, wrapped across two rows for longer handles. At
132 columns the choice list occupies the adjacent column, so joining
the entire screen would also mix unrelated list text into the detail.
The harness now reads the existing shared menu-detail rectangle and
joins its rows before matching the complete unchanged sentence. Both
renderers use that rectangle. The timeout and all gameplay checks stay
unchanged. Replaying each of the four failed captures proves the new
reader recognizes the warning; changing `order` in the rendered detail
makes each negative control fail as required. The failed run, artifact
IDs, original archive hashes and capture hashes are retained in
`technical-native-first-failure.json`. All four original ZIPs remain
in `%TEMP%/blacksite-s38/technical-first-failure/` and on GitHub.
