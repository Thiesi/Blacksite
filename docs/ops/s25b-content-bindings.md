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

Existing S08 objects retain their IDs, tiles, kinds and inspection names;
the generator rejects an attempt to change an existing hub object's
kind. Unavailable-zone placeholders retire only when the corresponding
exit opens. Bindings may add parameters and objects. In particular the
letting office remains a vendor, so housing binding does not turn it
into a public Lattice terminal while the new homes remain deferred.

The validator pins seven existing S08 `(zone, object)` debts as named
warnings pointing to C1 #92. Every other violation is an error, including
a new door inside an S08 hub. C1 removes each pair after repair.
A controlled Halo back door is covered; unbound decorative
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

These are ten-hub fixture receipts. The hosted matrix at `00a3f86` is
green; the local failure stays in the historical receipt. The lead
confirmed the engineering/artifact boundary in #78 comment 6494001542.
Full-city native walking and district layout acceptance stay with
S25c. New heads still require hosted acceptance and technical review.

The [live arrival scenario](s25b-arrival-captures.md) supplies the separate
TR-1 screen evidence. No additional S08-binding PR is proposed before
S25c: the existing native hub baseline is green, and commissioning the
future S25 commerce/core/service bundles piecemeal is not needed for
this engineering acceptance. District publication retains that work.

[receipt]: baselines/s25b-windows-011bf66.json
