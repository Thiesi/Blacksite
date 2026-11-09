# Row population cost (issue #184)

Status: fixture/method preparation; hosted results pending.
Plan: [6728923533](https://github.com/Thiesi/Blacksite/issues/184#issuecomment-6728923533).
Starting main: `5416b5d611573a91bba09d445b8503a730dafd53`.
This measurement grants no population decision or human acceptance gate.

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

Pending the first hosted execution. The raw report retains source/content
tree identity, source hashes, host/interpreter, all activity results,
per-caller CPU and counts, visibility receipts, server tick samples and
separate profile functions. No result is retained only in a temp folder.
Local fixture tests do not supply performance acceptance.

H1 and S25 layout approval remain NOT GRANTED.
