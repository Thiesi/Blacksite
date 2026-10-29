# S25b authoring and review

The generator ports the content bindings from #66 at
`1224c3007069391a8fa341e01b08bcc0b8a7b752` onto the current canon and
S25a engine. Its scope is the 24 commissioned zones and ten S08 hubs.
The four planned Warmwater zones and the S26 finale remain outside it.

Generate a review tree from the repository root:

```sh
python scripts/build_city_content.py --output .test-tmp/s25b-city
python -m blacksite.content.validate .test-tmp/s25b-city
pytest -q tests/content/test_commissioned_city.py
```

Use a new output directory for each receipt. The S25b authoring workflow
also uploads this tree as `s25b-authored-content`. It is a proposed city,
not shipped content or a layout approval. This engineering PR leaves
the ten shipped hubs in place. District publication stays with S25c and
the owner's H2/H3 gates; C1 owns protected S08 geometry under D-T3.

Route-bearing doors use the technical lead's cheap deterministic check:
two impassable neighbours on one axis, two passable sides on the other.
The generator protects their frames during later connectivity passes.
If existing machinery occupies a frame, a non-exit door moves to the
nearest available floor that admits a frame. Exit doors keep their
route tile. Spawn tiles, arrival tiles, objects and patrol points remain
protected. This does not establish location identity or room design.

The validator reports seven existing S08 route-door violations as named
warnings pointing to C1 #92. The same failures in every other zone are
errors. A controlled Halo back door is covered; unbound decorative
doors are excluded by behaviour. These are visible migration debts,
not evidence that the existing hub doors already guard useful routes.

The retained Citadel probe closes the actual Atrium-to-Mezzanine exit,
checks the independent exit remains usable, restores the machinery and
rechecks that restoration grants no admission credential.

The restored Landing-to-Wall Gate link uses Gate Nine's existing gate
travel policy. Its outbound control binds both the Landing and Ring 1
exits. Outworks retains the base core's tier 5 without a balance change.
The three added vendors are the Depots surplus counter, Caverns
way-station and Gate Market salvage buyer, matching their gazetteer
sites. New rooms, additional vendors and balance changes need separate
decisions.

The existing S08 apartment doors and 36-cell Terraces sector stay in
place. C1/S25c owns the 24 homes, their 48-cell sector expansion and the
deferred S23 Terraces-home field receipt, per #78 comment 6491941496.
The corresponding #66 housing probes are deferred with that content;
the authoring tests instead assert preservation of the existing doors
and register. The corrected Shaft Foot console is at its southern
gazetteer site, away from the old incidental telemetry adjacency.

TR-9 sends the complete first arrival paragraph through the existing
cell-width-safe log and local scrollback. This is a player-visible change
in every shipped zone, independent of the held city proposal. Like any
zone log line, it uses one of the 500 retained entries and may occupy one
of the 50 reconnect replay slots. The client deduplicates replay by ID.
Discovery emits the first paragraph as the arrival summary; later
paragraphs remain in the asset and are not emitted by discovery. The
previous toast emitted only its first line. This is the explicit S25b
TR-9 change, not an interaction-dispatch or renderer change.
The fake-terminal checks cover 80x24 and 132x50;
native receipts and hosted checks must be reported separately.
TR-8 measures the hub validator's CPU time inside the three-second
startup envelope, excluding shared-runner scheduling pauses. The full
native startup wall-time gate remains three seconds.

## Local engineering receipt

Implementation `011bf66cdc53780288af13f485e6ab78d8403437` passes the full
repository suite: 1,675 passed and one skipped. The clean-head strict
packet passes all 99 cases with zero authored CP437 failures, 419,766
checked authored cells and 714 separately counted caller observations.
Only the two Wake Hall log rows and their six colour snapshots change,
for the explicitly retained arrival paragraph.

The [Windows receipt][receipt] also retains the failed native budgets.
Both sizes complete the S25a fixture scenario through NetBBS Telnet and
registered native stdio, but startup takes 9.328 seconds. The measured
load call accounts for 7.233 seconds of wall time and 1.125 CPU seconds;
validation takes 0.143 wall seconds. These measurements do not identify
the cause of the wall-time gap. NPC p99 is 9.596 ms at 80x24 and 13.582 ms
at 132x50. The native command therefore fails its existing startup and
NPC gates. The installed wheel's Python tree matches the implementation.

These are ten-hub fixture receipts. Full-city native walking, hosted
native acceptance, the publication-boundary answer on #78, technical
review and the district layout gates remain separate obligations.

[receipt]: baselines/s25b-windows-011bf66.json
