# City travel (S08)

Blacksite 0.0.4 supplies the ten-zone M1 hub. Start the service separately
and register the native stdio door as in [the door guide](door-client.md).
New callers complete the Wake; returning callers resume their character.

Walk onto `>` street exits, or press E on or beside an exit. The Wake
door opens onto Clinic Row. Sablier Boulevard leads to Meridian Plaza;
the Neon Stair leads to Sodium Row and the Tin Halo. The header reports
the body's current safety, including protected clinic counters. Cold
Chain's capture hardware remains in the contested street.

At a tram platform press E. Departures occur on fixed 90-second UTC
boundaries, followed by a real ten-second ride. The wait stays on the
platform; the ride removes the body from both zones. Esc opens the log
without cancelling the ride. Ctrl-X leaves normally. A reconnect during
a ride retains its arrival deadline; offline arrivals use the destination's
normal logout protection or sleeper recovery. No new combat penalty exists.
Before departure, movement or Esc/B cancels boarding and returns to the
street. An accidental platform interaction never requires logging out.

Press M for the district overview and its visited-zone list with safety
classes. Up/Down selects a visited zone. Enter opens its atmosphere and
public connections in a paged TextView. PgUp/PgDn reads; Esc/B returns to
the street. This does not fast travel. Memory and first-visit flags persist
separately for each zone.

The hub bundle is active and has no dangling exits. S25 routes are visible
construction boundaries. Apartment interiors await S18. NPCs, vendors,
terminals and relays are placed anchors; their actions arrive in their own
slices. Faction lean remains lore until S20 provides faction records.
S15 receives bounded tram holds and exit-lock state hooks; this slice has
no Curfew or control producer.

Startup refreshes the package-owned content copy by package version. Keep
operator overrides in `content.local`. No world schema migration is needed.

Acceptance walks real paths through an isolated local NetBBS Telnet node,
using the registered native stdio door, at 80x24 and 132x50. It also walks
a second caller to the Plaza and checks shared arrival, waits on real
tram clocks, opens the log in flight, and reads the map overview:

```powershell
NETBBS_PYTHON scripts/accept_s08_netbbs.py `
  --root .test-tmp/s08-proof --door-python .venv/Scripts/python.exe --show
```

Use a 132x50 parent terminal for `--show`. The probe writes `result.json`
and ANSI captures. It never edits an existing NetBBS node or teleports a
caller. Budget several minutes for walking and two scheduled departures.
