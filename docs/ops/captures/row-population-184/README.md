# Row population cost (issue #184)

Status: initial grid measured; matched controls requested on PR #186.
Plan: [6728923533](https://github.com/Thiesi/Blacksite/issues/184#issuecomment-6728923533).
Starting main: `5416b5d611573a91bba09d445b8503a730dafd53`.
This measurement grants no population decision or human acceptance gate.

Technical record
[6729363372](https://github.com/Thiesi/Blacksite/pull/186#issuecomment-6729363372)
accepts within-runner marginals but requires matched controls before using
absolute figures. The predeclared plan is
[6729408184](https://github.com/Thiesi/Blacksite/pull/186#issuecomment-6729408184),
with the exact-snapshot amendment in the following comment. Original grid
data below stays intact. No second favorable-sample grid run is planned.

## Method

The equivalent pinned workflow `row-population-proof.yml` checks out its
exact event head on hosted Linux/Python 3.12. Each caller/tier group
measures all twelve population cells on the same runner, then four
fully-known corners. The 72 ordinary-state cells are required; the 24
known corners are additional. The historical A8 workflow stays unchanged.

The script calls the existing `budget.activity` for each twelve-second
P1 activity, retaining its MIX, ten-Hz shared ticks and five-Hz walking.
Every caller uses the unchanged `budget.Caller` Display methods and
Meter. A group adapter advances one shared server tick, then drains and
draws all callers. It never creates four independent simulation worlds.
The original Display boundary excludes server, setup, codecs and I/O.

Report mean, maximum and total caller CPU s/h. A grid cell is within 108
only if every caller is within that target. Marginals are adjacent finite
differences in aggregate caller CPU, divided by added NPCs and callers;
they retain negative values and do not assume linearity. Comparisons
across caller/tier groups use different hosted runners, so host variation
limits causal attribution.

Shared server CPU meters `HeadlessServer.step`, including simulation and
session view production. It excludes memory receipt commits and all real
storage, network and native terminal processes. Separately labelled
200-tick CPU profiles use standing callers at four population corners;
they do not contribute acceptance CPU samples or represent the P1 mix.

## Declared fixtures

No shipped content, engine or renderer changes. Both Sable posts and the
Warden retain their authored counts, templates, regions and behaviour.
Only ordinary regular count/region changes in the in-memory fixture:
4/8/12 regulars use their ordinary wander behaviour in region (45,8,11,5).
This keeps actual moving figures visible and away from four caller lanes.

Stationary extras copy the regular template, replacing wander with an
anchored talker behaviour. They still pass through ordinary NPC evaluation
and views: no training exemption or engine bypass. A deterministic nested
layout spreads them over the visible bar-3 frontage and street. All
0/20/40/80 counts are prefixes of one layout, outside caller lanes, moving
region, authored post regions, reserved tiles and hazards. Actual actor
counts, positions, view membership and movement are retained and checked.

The four distinct caller starts are (46,14), (46,15), (46,16), (46,17).
They perform the same eight-right/eight-left P1 route in parallel. Extra
tiles are visible from every step of every lane under the shipped radius
13 and ordinary line of sight. No fog, radius, actor disclosure or geometry
rule changes. Fully-known corners affect terrain memory only.

The bar-frontage layout is a local visible sample, not the entire Row's
population or an interior geography/playtest claim. Fixed post and Warden
cost remain part of the baseline. Moving counts mean ordinary wandering
actors, which retain their normal pauses; actual position changes are
reported. The provisional hourly activity mix is not measured player
behaviour. Results here must not be cited as whole native-process CPU.

## Evidence

The first hosted execution completed without a retry. The raw reports retain source/content
tree identity, source hashes, host/interpreter, all activity results,
per-caller CPU and counts, visibility receipts, server tick samples and
separate profile functions. No result is retained only in a temp folder.
Local fixture tests do not supply performance acceptance.

H1 and S25 layout approval remain NOT GRANTED.


## Results from the first hosted execution

Measurement head: `1ee8bbe25961f6677f8ce402f0b0d15c8a87506e`.
[Run 42538074504](https://github.com/Thiesi/Blacksite/actions/runs/42538074504)
completed all six jobs: **72 ordinary cells and 24 fully-known corners**.
Every activity has 120 ticks; walking activities execute all 59 requested
steps per caller, with no cadence slip. All actor visibility/count and
stationary-position assertions pass. Independent arithmetic from the raw
CPU seconds/elapsed durations reproduces every weighted total and target
flag. All six ZIP hashes match GitHub, and report heads/content/runtime
identities match. The raw reports, including all misses, are artifacts;
`manifest.json` gives exact member, report and archive hashes.
`summary.json` retains every cell, 102 adjacent marginals and profiles.

**Stationary extras are cheaper than wanderers in these samples, but are
not free.** Adjacent stationary increments range from -0.075207 to
1.118932 door CPU s/h per extra per caller; moving increments range from
2.403788 to 8.616775. Negative sample differences are retained as noise,
not converted to zero or interpreted as a saving. Adding 80 stationary
extras costs **21.060020 to 55.498915 door CPU s/h per caller**, and
**93.733321 to 369.708180 shared server CPU s/h**, in matched ordinary
cells. These are measured finite differences, not a universal unit price.

Only **5/72 ordinary cells** keep every caller within 108:

- four callers, 16 colours: 0 or 20 extras, four wanderers;
- four callers, truecolor: 0, 20 or 40 extras, four wanderers.

No one-caller cell meets 108. Neither eight nor twelve wanderers meets it
in any ordinary cell. Two of the 24 known corners pass: four callers,
zero extras/four wanderers, in 16 colours and truecolor. This is a target
comparison, not an acceptance waiver or a population recommendation.

**Interpretation limit:** all one-caller zero-extra baselines already
miss 108, and results differ across caller/tier hosts. Do not interpret
the four-caller passing cells as proof that adding callers reduces CPU.
Only within-group population differences share a runner. The current
runtime and deliberate visible/collision-free placements differ from
historical A8; its 73.7/79.5/140.5 figures are context, not a matched
before/after control. No regression cause is inferred from that comparison.

### Every grid cell

CPU s/h; mean/max are per caller, server is the shared tick meter.
The 108 flag compares the unrounded maximum, not the displayed mean.
Known rows are optional corners. No row is omitted because it misses.

| Knowledge | Callers | Tier | Still | Wander | Door mean | Door max | Server | <=108 |
|---|---:|---|---:|---:|---:|---:|---:|---|
| ordinary | 1 | 16 | 0 | 4 | 143.565 | 143.565 | 186.842 | no |
| ordinary | 1 | 16 | 0 | 8 | 164.557 | 164.557 | 203.678 | no |
| ordinary | 1 | 16 | 0 | 12 | 188.764 | 188.764 | 218.220 | no |
| ordinary | 1 | 16 | 20 | 4 | 162.024 | 162.024 | 216.796 | no |
| ordinary | 1 | 16 | 20 | 8 | 181.297 | 181.297 | 236.612 | no |
| ordinary | 1 | 16 | 20 | 12 | 208.416 | 208.416 | 254.731 | no |
| ordinary | 1 | 16 | 40 | 4 | 170.272 | 170.272 | 243.678 | no |
| ordinary | 1 | 16 | 40 | 8 | 193.033 | 193.033 | 270.356 | no |
| ordinary | 1 | 16 | 40 | 12 | 220.265 | 220.265 | 298.442 | no |
| ordinary | 1 | 16 | 80 | 4 | 188.923 | 188.923 | 314.499 | no |
| ordinary | 1 | 16 | 80 | 8 | 216.419 | 216.419 | 340.881 | no |
| ordinary | 1 | 16 | 80 | 12 | 243.528 | 243.528 | 372.151 | no |
| ordinary | 1 | 256 | 0 | 4 | 156.716 | 156.716 | 210.289 | no |
| ordinary | 1 | 256 | 0 | 8 | 182.134 | 182.134 | 232.285 | no |
| ordinary | 1 | 256 | 0 | 12 | 205.011 | 205.011 | 248.529 | no |
| ordinary | 1 | 256 | 20 | 4 | 175.810 | 175.810 | 238.885 | no |
| ordinary | 1 | 256 | 20 | 8 | 194.752 | 194.752 | 260.245 | no |
| ordinary | 1 | 256 | 20 | 12 | 224.213 | 224.213 | 281.421 | no |
| ordinary | 1 | 256 | 40 | 4 | 176.637 | 176.637 | 268.680 | no |
| ordinary | 1 | 256 | 40 | 8 | 211.104 | 211.104 | 292.535 | no |
| ordinary | 1 | 256 | 40 | 12 | 222.822 | 222.822 | 314.334 | no |
| ordinary | 1 | 256 | 80 | 4 | 194.177 | 194.177 | 332.829 | no |
| ordinary | 1 | 256 | 80 | 8 | 224.498 | 224.498 | 370.754 | no |
| ordinary | 1 | 256 | 80 | 12 | 255.156 | 255.156 | 393.435 | no |
| ordinary | 1 | truecolor | 0 | 4 | 126.696 | 126.696 | 159.152 | no |
| ordinary | 1 | truecolor | 0 | 8 | 144.546 | 144.546 | 172.632 | no |
| ordinary | 1 | truecolor | 0 | 12 | 165.440 | 165.440 | 185.311 | no |
| ordinary | 1 | truecolor | 20 | 4 | 140.656 | 140.656 | 185.797 | no |
| ordinary | 1 | truecolor | 20 | 8 | 161.037 | 161.037 | 199.913 | no |
| ordinary | 1 | truecolor | 20 | 12 | 180.522 | 180.522 | 214.613 | no |
| ordinary | 1 | truecolor | 40 | 4 | 147.895 | 147.895 | 202.376 | no |
| ordinary | 1 | truecolor | 40 | 8 | 165.412 | 165.412 | 219.159 | no |
| ordinary | 1 | truecolor | 40 | 12 | 188.876 | 188.876 | 240.172 | no |
| ordinary | 1 | truecolor | 80 | 4 | 157.835 | 157.835 | 252.885 | no |
| ordinary | 1 | truecolor | 80 | 8 | 182.701 | 182.701 | 277.555 | no |
| ordinary | 1 | truecolor | 80 | 12 | 199.534 | 199.534 | 300.377 | no |
| ordinary | 4 | 16 | 0 | 4 | 88.854 | 94.862 | 421.835 | yes |
| ordinary | 4 | 16 | 0 | 8 | 105.613 | 112.765 | 472.036 | no |
| ordinary | 4 | 16 | 0 | 12 | 115.776 | 122.219 | 520.323 | no |
| ordinary | 4 | 16 | 20 | 4 | 100.246 | 102.930 | 485.705 | yes |
| ordinary | 4 | 16 | 20 | 8 | 115.674 | 120.417 | 541.573 | no |
| ordinary | 4 | 16 | 20 | 12 | 130.642 | 136.465 | 579.936 | no |
| ordinary | 4 | 16 | 40 | 4 | 106.443 | 110.154 | 534.692 | no |
| ordinary | 4 | 16 | 40 | 8 | 122.290 | 126.963 | 593.914 | no |
| ordinary | 4 | 16 | 40 | 12 | 136.873 | 140.943 | 647.295 | no |
| ordinary | 4 | 16 | 80 | 4 | 115.918 | 117.107 | 647.557 | no |
| ordinary | 4 | 16 | 80 | 8 | 135.068 | 142.785 | 715.742 | no |
| ordinary | 4 | 16 | 80 | 12 | 148.002 | 156.905 | 774.441 | no |
| ordinary | 4 | 256 | 0 | 4 | 132.727 | 140.573 | 621.200 | no |
| ordinary | 4 | 256 | 0 | 8 | 157.416 | 169.733 | 686.573 | no |
| ordinary | 4 | 256 | 0 | 12 | 176.450 | 188.697 | 743.682 | no |
| ordinary | 4 | 256 | 20 | 4 | 151.035 | 163.172 | 706.142 | no |
| ordinary | 4 | 256 | 20 | 8 | 174.821 | 187.282 | 776.202 | no |
| ordinary | 4 | 256 | 20 | 12 | 198.829 | 212.258 | 840.742 | no |
| ordinary | 4 | 256 | 40 | 4 | 160.132 | 171.170 | 789.952 | no |
| ordinary | 4 | 256 | 40 | 8 | 187.917 | 205.857 | 857.708 | no |
| ordinary | 4 | 256 | 40 | 12 | 203.353 | 215.058 | 926.683 | no |
| ordinary | 4 | 256 | 80 | 4 | 177.533 | 190.424 | 936.802 | no |
| ordinary | 4 | 256 | 80 | 8 | 205.734 | 216.424 | 1027.580 | no |
| ordinary | 4 | 256 | 80 | 12 | 231.949 | 247.749 | 1113.390 | no |
| ordinary | 4 | truecolor | 0 | 4 | 84.618 | 91.752 | 384.367 | yes |
| ordinary | 4 | truecolor | 0 | 8 | 99.696 | 109.728 | 436.462 | no |
| ordinary | 4 | truecolor | 0 | 12 | 115.249 | 126.618 | 466.374 | no |
| ordinary | 4 | truecolor | 20 | 4 | 97.914 | 102.835 | 433.068 | yes |
| ordinary | 4 | truecolor | 20 | 8 | 108.957 | 117.285 | 458.686 | no |
| ordinary | 4 | truecolor | 20 | 12 | 118.572 | 129.019 | 493.804 | no |
| ordinary | 4 | truecolor | 40 | 4 | 96.409 | 102.813 | 457.954 | yes |
| ordinary | 4 | truecolor | 40 | 8 | 114.009 | 122.087 | 501.875 | no |
| ordinary | 4 | truecolor | 40 | 12 | 126.724 | 139.419 | 549.289 | no |
| ordinary | 4 | truecolor | 80 | 4 | 105.678 | 116.563 | 549.020 | no |
| ordinary | 4 | truecolor | 80 | 8 | 126.777 | 134.220 | 623.262 | no |
| ordinary | 4 | truecolor | 80 | 12 | 137.282 | 142.087 | 672.841 | no |
| known | 1 | 16 | 0 | 4 | 140.712 | 140.712 | 193.210 | no |
| known | 1 | 16 | 0 | 12 | 190.257 | 190.257 | 229.269 | no |
| known | 1 | 16 | 80 | 4 | 188.252 | 188.252 | 318.149 | no |
| known | 1 | 16 | 80 | 12 | 244.144 | 244.144 | 379.549 | no |
| known | 1 | 256 | 0 | 4 | 160.755 | 160.755 | 217.555 | no |
| known | 1 | 256 | 0 | 12 | 203.882 | 203.882 | 260.023 | no |
| known | 1 | 256 | 80 | 4 | 183.872 | 183.872 | 341.086 | no |
| known | 1 | 256 | 80 | 12 | 244.695 | 244.695 | 399.306 | no |
| known | 1 | truecolor | 0 | 4 | 123.607 | 123.607 | 166.867 | no |
| known | 1 | truecolor | 0 | 12 | 163.430 | 163.430 | 194.478 | no |
| known | 1 | truecolor | 80 | 4 | 157.564 | 157.564 | 261.913 | no |
| known | 1 | truecolor | 80 | 12 | 201.909 | 201.909 | 308.105 | no |
| known | 4 | 16 | 0 | 4 | 89.664 | 92.074 | 447.139 | yes |
| known | 4 | 16 | 0 | 12 | 118.277 | 126.731 | 533.952 | no |
| known | 4 | 16 | 80 | 4 | 117.443 | 125.341 | 663.861 | no |
| known | 4 | 16 | 80 | 12 | 149.663 | 152.305 | 790.606 | no |
| known | 4 | 256 | 0 | 4 | 136.134 | 147.541 | 678.212 | no |
| known | 4 | 256 | 0 | 12 | 181.193 | 202.250 | 783.470 | no |
| known | 4 | 256 | 80 | 4 | 182.791 | 194.203 | 980.391 | no |
| known | 4 | 256 | 80 | 12 | 231.249 | 249.958 | 1158.880 | no |
| known | 4 | truecolor | 0 | 4 | 88.681 | 93.184 | 399.170 | yes |
| known | 4 | truecolor | 0 | 12 | 112.660 | 121.234 | 469.372 | no |
| known | 4 | truecolor | 80 | 4 | 110.371 | 114.988 | 605.574 | no |
| known | 4 | truecolor | 80 | 12 | 141.497 | 156.767 | 709.539 | no |

### Adjacent marginal cost, per caller

Door CPU s/h per added NPC per caller. Each row's min/median/max spans
only the other population axis within the same caller/tier runner.
`summary.json` retains all 102 individual differences and the separate
shared-server marginal; no linear fit or cross-host normalization is used.

| Callers | Tier | Added type | Interval | Min | Median | Max |
|---:|---|---|---|---:|---:|---:|
| 1 | 16 | stationary | 0 to 20 | 0.837037 | 0.922923 | 0.982592 |
| 1 | 16 | stationary | 20 to 40 | 0.412430 | 0.586786 | 0.592430 |
| 1 | 16 | stationary | 40 to 80 | 0.466268 | 0.581569 | 0.584646 |
| 1 | 16 | moving | 4 to 8 | 4.818348 | 5.468954 | 6.873907 |
| 1 | 16 | moving | 8 to 12 | 6.051952 | 6.778454 | 6.807949 |
| 1 | 256 | stationary | 0 to 20 | 0.630904 | 0.954693 | 0.960117 |
| 1 | 256 | stationary | 20 to 40 | -0.069559 | 0.041354 | 0.817633 |
| 1 | 256 | stationary | 40 to 80 | 0.334850 | 0.438501 | 0.808336 |
| 1 | 256 | moving | 4 to 8 | 4.735381 | 6.967293 | 8.616775 |
| 1 | 256 | moving | 8 to 12 | 2.929453 | 6.542381 | 7.664319 |
| 1 | truecolor | stationary | 0 to 20 | 0.698001 | 0.754088 | 0.824584 |
| 1 | truecolor | stationary | 20 to 40 | 0.218743 | 0.361930 | 0.417713 |
| 1 | truecolor | stationary | 40 to 80 | 0.248502 | 0.266437 | 0.432216 |
| 1 | truecolor | moving | 4 to 8 | 4.379306 | 4.778783 | 6.216449 |
| 1 | truecolor | moving | 8 to 12 | 4.208182 | 5.047362 | 5.865973 |
| 4 | 16 | stationary | 0 to 20 | 0.503065 | 0.569608 | 0.743301 |
| 4 | 16 | stationary | 20 to 40 | 0.309834 | 0.311539 | 0.330774 |
| 4 | 16 | stationary | 40 to 80 | 0.236872 | 0.278234 | 0.319461 |
| 4 | 16 | moving | 4 to 8 | 3.857078 | 4.075785 | 4.787665 |
| 4 | 16 | moving | 8 to 12 | 2.540730 | 3.439604 | 3.741911 |
| 4 | 256 | stationary | 0 to 20 | 0.870227 | 0.915396 | 1.118932 |
| 4 | 256 | stationary | 20 to 40 | 0.226219 | 0.454852 | 0.654800 |
| 4 | 256 | stationary | 40 to 80 | 0.435028 | 0.445435 | 0.714897 |
| 4 | 256 | moving | 4 to 8 | 5.946525 | 6.559317 | 7.050337 |
| 4 | 256 | moving | 8 to 12 | 3.859035 | 5.380178 | 6.553660 |
| 4 | truecolor | stationary | 0 to 20 | 0.166163 | 0.463047 | 0.664781 |
| 4 | truecolor | stationary | 20 to 40 | -0.075207 | 0.252588 | 0.407599 |
| 4 | truecolor | stationary | 40 to 80 | 0.231714 | 0.263944 | 0.319204 |
| 4 | truecolor | moving | 4 to 8 | 2.760941 | 4.084763 | 5.274823 |
| 4 | truecolor | moving | 8 to 12 | 2.403788 | 2.902544 | 3.888208 |

### Shared server profile: the quadratic scan is visible

These are separate process-CPU profiles over 200 ticks with standing
callers, ordinary knowledge, truecolor. Profiling adds overhead; do not
substitute its times or proportions for the unprofiled P1 hourly samples.
The actual implementation is named `Npcs.evaluate` (the issue calls it
`NpcEngine.evaluate`). It still evaluates anchored extras normally and
scans zone actors every five ticks. No idle/training exemption is added.

At 80 extras evaluation grows to 3,480 or 3,800 calls, versus 280 or 600
without extras. Cumulative evaluation CPU grows from 0.039-0.153 s to
2.565-3.794 s in these profiles. This exposes the all-NPC/all-actor scan;
it does not prove the entire tick follows a pure quadratic law. View
production also grows: four-caller `zone_view.build` rises from
1.197/2.052 s to 7.470/8.487 s at the two moving-count corners.
Stationary actors therefore have both evaluation and per-caller view
cost, beyond the door's incremental drawing. No optimization is proposed.

| Callers | Still | Wander | Profile total s | Evaluate calls | Evaluate cumulative s | zone_view.build cumulative s |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 4 | 2.556018 | 280 | 0.038863 | 0.303602 |
| 1 | 80 | 4 | 9.293159 | 3480 | 2.718420 | 2.130027 |
| 1 | 0 | 12 | 3.386798 | 600 | 0.132739 | 0.555964 |
| 1 | 80 | 12 | 11.467617 | 3800 | 3.793946 | 2.404292 |
| 4 | 0 | 4 | 6.952715 | 280 | 0.049312 | 1.196548 |
| 4 | 80 | 4 | 21.220014 | 3480 | 2.564723 | 7.469641 |
| 4 | 0 | 12 | 9.070987 | 600 | 0.152553 | 2.052040 |
| 4 | 80 | 12 | 25.195747 | 3800 | 3.565045 | 8.487091 |

### Validation and review ledger

Before opening PR #186, hosted Linux root pytest passed **2430 tests in
304.52 s**. Windows then passed **2429 tests, one skipped, in 693.11 s**:
[push CI 42538074437](https://github.com/Thiesi/Blacksite/actions/runs/42538074437).
Local fixture/accounting tests passed eight cases in 6.35 s, including
one complete sleep-free four-caller walk with 80 extras/12 wanderers.
No local performance sampling or full-suite run was made.

Automated review at the measurement head: Claude Sonnet 5.5, initialized
as `claude-sonnet-5-5`, [6729181469](https://github.com/Thiesi/Blacksite/pull/186#issuecomment-6729181469),
no actionable findings. Its cadence warning is checked against all raw
activities: every one has 120 ticks, and every walking key succeeds.
Its quiet-wanderer warning does not occur: every activity observes actual
wanderer position changes. These checks do not waive a future failure.

The final evidence/done-mark push changes only documentation. Its exact
head, checks, automated-review triage and technical request are on #186.
The hosted measurement source remains pinned to 1ee8bbe; artifacts are
not relabelled as another execution. No population, human-layout or
performance threshold decision is granted. H1/S25 remain NOT GRANTED.
