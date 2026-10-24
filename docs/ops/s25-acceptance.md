# S25 acceptance record

Status: in progress. PR [#66](https://github.com/Thiesi/Blacksite/pull/66)
tracks commissioning. Shaft Foot and Far Ring still require the user's
review, as specified in the [slice](../plan/slices/S25-undercity-and-scour-content.md).
Broader S25/S26 human pacing and the S33 art gate remain open.

## Evidence and performance reference

Final-commit CI on the Linux reference server, Python 3.12 and pinned
NetBBS `v7.31.0` evaluates the unchanged three-second startup and
sub-10-ms NPC tick p99 gates at both sizes. Retain failed samples and
repeat the final head to show its distribution. Independently verify
archive digest, ZIP CRC, version, complete Python/content identity and
scenario receipts. A prior green checkpoint does not clear a new head.

Local Windows PTYs separately prove real terminal operation through
Telnet, a registered native stdio door and the installed wheel at
80x24/132x50 with wide handles. Local NetBBS source is 7.31.0 at
`d04170aa998b459b9f5ca6b9bca9ea63a17f7ab9`, rather than its exact tag.
Report local functional success and overall budget failure separately;
those processes keep their failed result. Do not label them passed or
substitute fixtures for actual geography. The reference CI result does
not replace local terminal or required human review.

The shared Windows host has produced large wall/thread CPU spreads.
One instrumented fresh start measured 15.957 s wall / 2.891 s thread CPU:
copying 324 files took 1.009 / 0.625 s, loading 12.478 / 1.203 s, and
validation 0.796 / 0.641 s. Probe overhead is included. These measurements
locate the wait in content loading; they do not establish its external
cause or justify changing gameplay or a performance threshold.

## Retained checkpoints

| Commit | Completed evidence | Remaining at that checkpoint |
|---|---|---|
| `246ac33` | Root CI: 1570 Linux; 1569 Windows plus one skip. NPC p99: 80x24 6.697/8.603 ms; 132x50 6.354/8.382 ms. Both NPC archives independently verified, including all 324 content files. | Old Exhale helper failed; final-head and human gates open. |
| `d5988e6` | Root CI green on both platforms; native 46/49. Real Sump board bound without moving its terminal. | Unequipped wide surveys died in Caverns/Ring Three. Extended 80x24 p99 failed at 20.247 ms. |
| `b7d30fc` | Canonical Warm Stack regression and root CI green. Native 51/65, including both allocations of real Cold Chain at both sizes. | Two deep surveys used a shared hardware id in the wrong zone; remaining repair failures include Key preparation and a healing-channel retry. Final proof remains pending. |

The failed `d5988e6` performance archive independently matches its source,
version, digest, CRC and all 324 content files. Late diagnostic peaks
were 51.468/7.585 ms and 22.093/6.777 ms wall/thread CPU. The wall-time
gate failed. GC and storage-flush probes now accompany tick diagnostics
to distinguish their contribution; their overhead stays inside the gate.

## Actual-city preparation and pacing

The fixture-free earned-upgrade case and original district tour remain
separate from funded hazardous surveys. Grade/funding setup proves
operation, not affordability, an income rate or a fun verdict. Keep the
one-time first job separate from repeatable earning measurements.

Public repair cases disclose grade five, funding and the S19 one-hour
service-uptime setup. UTC, NPCs and travel are not advanced. Gear,
medicine, software, movement, combat and work use actual keys. No item,
placement, ICE, reward or content fixture is supplied.

Retained attempts exposed necessary preparation: damage interrupts the
installation channel; faction membership can expose the worker to rival
guards; protected uplinks keep the body out of the repair site's fight;
and an appropriate Key must be purchased, loaded and activated. A high
program tier alone does not turn Signet's faction-specific exception
into a generic tier-two link credential. S30 help and S31 verification
retain these lessons. None warrants weakening NPCs or bypassing gates.

The corrected local 80x24 Sump/common case completed the actual public
board, supplied feed, installation, public Locksmith purchase/loading/
activation, real core control, fixed 200-chit payment and public return.
It used the installed wheel 0.0.21 with content hash
`53fcc8012799ef04a03531aff939733aa6a5c317de0c47e15e745218351bd9f9`.
Functional success is retained separately from its 3.281-second startup
failure. This prototype still needs final-head two-size validation.

Still required: complete actual service/core/relay benefits and paid
routes, repeatable earnings/acquisition and event-route pacing, final
root/native/review gates, and the explicit human reviews above. Failed
attempts remain in their local roots or linked GitHub artifacts.
