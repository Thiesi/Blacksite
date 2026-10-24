# S23 acceptance record

S23 adds local listings, bank escrow, protected delivery and bounties.
[PR #64](https://github.com/Thiesi/Blacksite/pull/64) records review triage
and the final merge-head checks. Production Python source is unchanged
from reviewed `8467ea4`; `773dfdc` completes the native driver and S29
handoff. Later completion-document commits do not change that source.

## Installed native validation

Both local runs use Blacksite 0.0.19 installed from the wheel, actual
NetBBS 7.31.0 checkout `d04170aa998b459b9f5ca6b9bca9ea63a17f7ab9`,
Telnet into a registered native stdio door, and Windows loopback TCP to
the service. All four caller names contain a wide character. `--show`
forwards the ANSI stream through the ordered console writer. Both runs
drained that writer at teardown.

| Evidence | Result |
|---|---|
| Wheel | `blacksite-0.0.19-py3-none-any.whl`, 596146 bytes |
| Wheel SHA-256 | `9a702b9175b726aafc6cd70533c2d828cb98dbf3aa03588d18750df27cbf084f` |
| Normalized Python tree SHA-256 | `826c471d76e06126be18b498277c18cd372790fd3997e2c52fd5c0edde8eb9cc` |
| 80x24 | Passed, `.test-tmp/s23-native-9/80x24` |
| 132x50 | Passed, `.test-tmp/s23-native-10/132x50` |

The driver verifies the isolated interpreter's version and complete
Python tree before starting NetBBS. The client cannot silently import
the source checkout and pass as the installed package.

Run from the isolated slice worktree, once for each size:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONIOENCODING='utf-8'
C:/Users/Thiesi/OneDrive/Dev/NetBBS/.venv/Scripts/python.exe `
  scripts/accept_s23_netbbs.py --root .test-tmp/s23-native-9/80x24 `
  --door-python .test-tmp/s23-native-venv/Scripts/python.exe `
  --show --size 80x24
```

The second run uses the 132x50 root and size in the table. Preserved
evidence includes `s23-results.json`, `native-client.json`, terminal
`.ans`/`.txt` captures, input traces, `progress.log`, storage and
`console-output.json`.

Each size exercises real walking and keys: Core public services via F9,
listing an unequipped/unsecured starter pistol at 50/100 chits for 24
hours, visible seller net 47/95 before Y, a 60-chit bid, refused seller
cancellation, and a buyout requiring only 40 extra chits. Settlement
pays the seller 95 and Kestrel treasury 5 without adding influence. The
buyer walks to the actual bank counter and collects the exact instance
for no fee. Street E still opens the normal board/jack interaction.

The poster escrows a 200-chit bounty; actual targeted F combat kills
the target and pays the hunter. The original pistol remains in the
victim's cache with victim and killer rights. A grade-2 target is
refused without a debit. All callers return to the node. The hunter
first buys four ammo packs with carried chits at the real Wake
outfitter; combat consumes carried ammo normally.

Independent offline reads through Storage and its lease confirm sold
listing 100, released own bid 60, claimed bounty 200, exact item identity
and state apart from its new owner, banks 895/0/1200, treasury 5 and
influence 0. This verifies persistence separately from driver assertions.

## Automated checks and downloadable evidence

At `773dfdc`, full repository-root `pytest -q` passed on Ubuntu:
**1455 passed in 301.42 seconds**, job `120717263109`; Windows:
**1454 passed, 1 skipped in 179.22 seconds**, job `120717262993`.
These are CI results. Local focused market/engine/protocol/UI checks
passed 53 tests; the final UI wording check passed 14 overlapping tests.
No final local full-root result is claimed for S23.

The focused checks cover real Display key dispatch at both widths,
empty-board actions, net-zero disclosure, instance and quality
preservation, escrow releases, restart and migration, effective carry
after collection, queued bounty posting behind death, failed source
publication and injected SQLite rollback after partial writes.

Fifteen downloadable archives from
[run 40042719582](https://github.com/Thiesi/Blacksite/actions/runs/40042719582)
were independently checked against GitHub's SHA-256 digest, ZIP CRC,
version 0.0.19, the whole Python tree above, terminal captures and the
meaningful scenario receipts. No failure trace was accepted as proof.

| Archives | Independently checked receipts |
|---|---|
| S23 market, both sizes | 60 escrow, 40 extra buyout, 95/5 settlement, exact free collection, paid ammunition, actual bounty death/cache rights, grade refusal |
| S21 relay, both sizes | Actual >=180-second capture, XP 100/100/0, contested/Curfew pauses, named control, member/outsider access, influence +20 |
| S19 contracts, five scenarios at both sizes | Manual/network, crew/common/reserve allocations and committed source outcomes with disclosed fixtures |
| S14 encounters, one combined archive | Solo and duo gates at both sizes, shared reward 120 and one consumed source generation |

The verification receipt is preserved locally at
`.test-tmp/s23-final-archives-verified.json`; archive IDs and final-head
checks are recorded in PR #64. CI builds have independent wheel ZIP
metadata; source identity is established by the full Python tree.

At `773dfdc`, the 80-column NPC job passed its gameplay checks including
actual ten-minute heat expiry, but failed the final 10-ms tick p99 gate
at 16.36 ms. It remains a failed attempt. Completion requires the
unchanged gate to pass on the final head; PR #64 records that result.

## Review and remaining acceptance boundaries

Three written Claude Sonnet 5.5 reviews cover production and the final
driver delta, at `a50ebd8`, `8467ea4` and `773dfdc`. The model was checked
in job initialization logs. Reviewers did not claim independent test
or native execution. Accepted findings fixed retained-history cost,
seller net disclosure and queued-death coverage. Unsupported expiry
exceptions, a new bounty tax and future-only effect composition were
rejected with practical-impact rationale in the PR.

The driver fixtures set grade/full pools and banked funds. There is no
item, placement, reward, clock or future-map fixture. The bounty kill
uses existing Vatside contested geography. Actual Sink routes and
normal earning, commerce, clinic affordability and human pacing remain
S25/S26 obligations carried from PR #38. This acceptance does not prove
those experiences or long-term economy balance.

S29 must measure retained history, large carried/stored/impounded/cached
item tables and realistic interlock state under active simulation and
queued persistence before release. Synthetic timings are diagnostic,
not that load gate. S32 must preserve immutable closed financial rows
and rebuild the derived held-bid index from authoritative state.
