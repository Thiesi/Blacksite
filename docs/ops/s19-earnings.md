# S19 earning receipts and affordability scenarios

The production transaction paths pay the amounts below. Activity cadence
is assumed; this is not a measurement of human travel, combat or fun.
No fixture cash is added and no starting equipment is sold. NPC defeats
are completed-outcome fixtures. Public NPC scheduling, ICE and positions
are isolated as listed in the accompanying JSON.

Reproduce from the repository root with the development environment:

```
python -m scripts.report_s19_economy --output docs/ops/s19-earnings.json
```

The machine-readable [report](s19-earnings.json) includes the shipped
content hash, input cadence, quotes, source receipts and explicit limits.
This extends the S16 XP schedule without claiming its assumed activities
are measured play. PR #38 requires the complete city's human earning and
source checks after S25/S26 integration.

## Observed receipt amounts

| Source | Result |
|---|---|
| Solo Warden commission | 4 mission drones; 200 chits and 200 contract XP |
| Two-person commission | 6 drones; Ghost 250 chits, Operator 275 chits; 250 contract XP each |
| Repeated turn-in | zero extra credit |
| Twenty enforcer defeat outcomes | 80 dropped 9 mm rounds; 16 chits actually sold; the same amount spent from the vendor budget |
| Civic ledger credit | 80 chits through a completed source lift |

The enforcer sample is one deterministic loot sample, not every street
NPC or a measured kill rate. Core cash and corpse loot go to their
recipient. A crew support worker receives no automatic duplicate of
that cash. Mission-defeat XP is omitted from the XP schedules below, so
it cannot be counted again as a second contract award.

## Assumed sessions and gross cash

Four completed jobs/hour uses fewer than a board's ten fresh offers/hour.
Mixed play assumes six successful lifts across replenished core sources
and eight additional street defeats/hour. Street-only assumes twenty
defeats/hour. Source access and success rates are unmeasured assumptions.

| Profile | Gross chits/hour |
|---|---:|
| street | 16 |
| solo jobs | 800 |
| crew jobs ghost | 1000 |
| crew jobs operator | 1100 |
| mixed solo | 1286.4 |
| mixed crew lifter | 1486.4 |
| mixed crew support | 1100 |

These are gross forecasts. Ammo, healing, rent, failures, recovery and
other expenses reduce spendable income. The crew lifter/support rows
keep the real distribution of personal source cash; they assume no bank
transfer or equal split. Each goal below starts independently with the
original 200 chits and observes discrete 15-minute job payouts.

| Independent goal | Ordinary quote | Solo jobs, minutes | Crew Ghost jobs, minutes | Mixed solo, minutes |
|---|---:|---:|---:|---:|
| HV-7 carbine | 340 | 15 | 15 | 15 |
| Reflex Arm plus white-clinic installation | 2640 | 195 | 150 | 120 |
| Installation only, Arm already owned | 440 | 30 | 15 | 15 |
| Jury Rig plus white-clinic installation | 1440 | 105 | 75 | 60 |
| Clinical Rig plus white-clinic installation | 4320 | 315 | 255 | 195 |
| Detox | 400 | 15 | 15 | 15 |
| Each fixed Tin Halo program | 1600 | 105 | 90 | 75 |

Quotes do not create missing shop placements. The HV-7's actual depot
purchase, the Spire Arm purchase/installation and the Sink black clinic
remain S25 field gates. A black clinic quotes the Arm at 1,320 chits with
15% failure risk, compared with 2,640 and 2% at the ordinary clinic. Those
are single-attempt quotes, not guaranteed successful-installation costs.
Cold Chain changes only eligible installation service fees; item price,
removal, detox and risk remain unchanged.

The four 1,600-chit programs are fixed at Vesper. Blackout is an optional
identity-scoped Reach image, not a cash purchase or a required rare drop.
Actual acquisition and shared guards are covered by the source tests.

## S16 progression schedule extended with contract receipts

The schedule adds four observed contract-XP grants/hour to S16's mixed
activity assumptions, with the sampled grade-one street opponents. Run
XP is paid once per core/identity/day; later lifts retain their source
cash but add no repeated run XP. Initial discoveries are one-time grants.

| Profile | Grade 5, assumed minute | Grade 10, assumed minute | XP after six hours |
|---|---:|---:|---:|
| street | 276 | not reached | 1834 |
| mixed solo | 50 | 328 | 6119 |
| mixed crew | 44 | 269 | 7294 |

These scenarios give jobs and varied runs a useful earning role; they
do not establish that continuous low-risk fighting is the best loop.
They do not justify changing canonical rewards on their own. Measure
the actual complete-world routes, spending, losses, group roles and
player interest before accepting the 45-90 minute / 4-6 hour targets.
The S25/S26 human pacing gate remains open.
