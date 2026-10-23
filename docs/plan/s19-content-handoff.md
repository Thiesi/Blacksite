# S19 authored-content integration handoff

S19 ships the first job, six Vesper commissions, three commissions per
faction, and Cold Chain on existing maps. It also authors all 33 Season 1
contracts and the three other service orders behind authoring manifests.
The content validator must reject activation until every reference is
resolved. Pure receipt replays do not prove city navigation or pacing.

Reference: [PR #38](https://github.com/Thiesi/Blacksite/pull/38),
[issue #19](https://github.com/Thiesi/Blacksite/issues/19), and
[NetBBS issue #56](https://github.com/Thiesi/Blacksite/issues/56).

## S25 maps and sources

Bind these named anchors to deliberate, reachable map locations. Do not
replace them with aliases to unrelated vendors or temporary map stubs.
NPC scene origins resolve the named object's tile. Test each walking
escort across public exits; trams and locked exits are not escort paths.
The four willing templates need four spawn spaces and a nearby shelter
within their Old Works squat, separate from the clinic destination.

The black-core entrance is lat-sink-c13, currently a gated placeholder.
Make it the canon's discoverable hidden entrance when binding the actual
Sable core. Keep the other four survey cells reachable without additional
key gates. The local npc-oldworks-patrol template needs real patrol
waypoints and a public spawn when Old Works lands. Bind a full Exhale
spawn template before activating war-s1-4-line. Optional public NPCs must
not become somebody else's mission actors.

| Zone | Required named anchors |
|---|---|
| `chapel-nave` | `ansgar-desk`, `quell-desk` |
| `chapel-towers` | `third-listener-log` |
| `core-plaza` | `gate-east-cycle-log`, `gate-south-cycle-log`, `gate-west-cycle-log` |
| `oldworks-drop` | `strand-terminal`, `unmoored-cache` |
| `oldworks-main` | `relay-zero-hardware`, `vat-nine-shelter`, `vat-nine-shield-socket`, `vat-nine-squat` |
| `scour-landing` | `council-fire` |
| `scour-ring-2` | `convoy-depot`, `north-telemetry` |
| `scour-ring-3` | `conduit-head`, `convoy-interruption-log`, `convoy-route`, `north-recovery-cache` |
| `scour-ring-4` | `plateau-edge-1`, `plateau-edge-2`, `plateau-edge-3` |
| `sink-floor` | `sump-feed-locker`, `sump-pump-regions`, `warm-stack-1`, `warm-stack-2`, `warm-stack-3`, `warm-stack-4`, `warm-stack-5` |
| `sink-terraces` | `pale-desk`, `terrace-seven-accounts` |
| `spire-atrium` | `maartens-desk` |
| `terraces-blocks` | `block-four-nest` |
| `tramyard-depots` | `depot-manifest-locker`, `depot-surplus-latch` |
| `tramyard-gate-nine` | `ration-consignment` |
| `tramyard-wall-gate` | `convoy-muster` |
| `under-caverns` | `sled-arrival` |
| `under-drowned` | `template-canister` |
| `under-outworks` | `east-door-frame`, `east-door-hinge`, `east-door-pour-plan`, `west-line` |

Sump needs sump-fault/common/reserve geometry layouts, each with the
signed long return route, warnings and safe ejection before reflooding.
The sump-reserve-cache and depot-reserve-cache each expose the order's
two shared slv_power units. Depot needs kestrel-surplus at the actual
depot-surplus-counter, not an essential food/medical vendor. Common
allocation doubles its hourly buy-back cap without refilling spending.
Relay Zero's reserve binds only relay_open; common publishes its actual
core patrols. Bind the credential to a useful optional local shortcut
with an actual permission check. Keep S21's ordinary public relay capture
separate; a credential for an already-public control is no reward.
These effects must retain ordinary care, uplinks and outward travel.

## S27 dialogue and S26 activation

Vesper brokers generated commissions at the Tin Halo now. Story neutral
referrals remain S27 work: route the actual handler turn-in through the
broker and waive only the blocked giver-standing check. Preserve all
predecessor, settled-branch, item, grade and event requirements. Activate
the Season 1 bundle only after these referrals and all S25 targets work.

Walked-template continuation uses a paid outcome in walked-templates-s1,
not acceptance alone or the opposite exclusive template's completion.
Sablier provenance accepts either outcome; Unmoored's fresher copy also
retains its earlier mapping prerequisite. A veteran can help another
worker without another reward or a rewritten personal choice. Clinic
gives care and records tags; shield keeps consenting templates in their
squat and publishes the local NPC patrol for 20 minutes. Helpers cannot
extend that public receipt. Neither record identifies a machine voice.

The two Silt mission copies use Old Works Shallows and guaranteed visible
sources resolved by the current graph, never saved foreign coordinates.
Unmoored's sealed fragment is an explicit permanent reward for the next
job; temporary lifted payloads retire at settlement. Public core records
and their ordinary loot remain separate from each mission's copies.

The full-city human pacing gate remains mandatory after S25/S26. Re-run
escort arrival with all four followers and a clearly marked, walkable
destination. A worker stopping beside the marker can leave followers
outside its arrival radius; placement and hints must make delivery clear.
Measure actual contract, shop, surgery and detox earning routes with
complete city travel and population; fixture income is not a fun verdict.
