# Lattice traversal

Stand beside a terminal and press E or J. Every archetype can borrow its
three-slot rig with Pick and Umbrella. Ghosts have a native rig; a carried
portable rig also allows J away from a terminal. The zone's explicit
sector ID chooses the district; terminals can override it. With the vi
keymap, j moves down and Ctrl-O jacks in or out.

Arrows follow the nearest link in that direction. Traversal takes
max(0.2, 1.0 - Cortex/100) seconds, rounded up to server ticks. E uses an
uplink at the current cell. Public baseline links connect all eleven
districts even though only the ten-zone physical hub is built. A gate
names its missing credential before moving you. Hidden cells and their
edges stay absent until discovered.

Your body stays where you leave it. It cannot move, act or evade while
jacked. Other callers see its shaded stance glyph. The Lattice panel
shows body safety and HP; a real hit flashes the border and reaches the
log. Safe zones and pockets still protect the body. Elsewhere choose
shelter before connecting.

J returns immediately from a public cell. Elsewhere it starts a visible
two-second escape. Hits restart it at most three times; then the next
scheduled end completes. Moving cancels an escape. Disconnecting removes
the presence before ordinary safe logout/sleeper handling. Integrity
recovers five per second after jack-out, including offline time. Trace
stays zero in S13.

Say and emotes reach your current cell; shout reaches your sector.
Whisper, faction and crew keep their usual audiences. Street chat and
Lattice chat have separate audiences. Same-cell runners appear as a
diamond and a name in the panel.

Core entrances are visible placeholders, not working cores. Programs,
ICE, core rooms, trace and Silt arrive in S14. Its hub cores can activate
immediately; future-map hardware stays staged until S25. The canonical
sixteen relay instances use `lat-relay-<slug>`, not sector display names.
Private apartment cores are owned instances added by S18.

Operators can inspect live presences without reading the world database:

```text
blacksite admin --install-dir WORLD lattice who --json
```

For a private debugging world, reveal one cell to one character:

```text
blacksite admin --install-dir WORLD lattice reveal PLAYER SECTOR CELL
```

This authenticated, audited operator command is the only S13 discovery
path. S14/S16/S24 supply player discovery actions. It grants no items,
gate credentials, movement or discovery to another character.

Run the live acceptance from a real terminal using the NetBBS interpreter
and the Blacksite client interpreter:

```powershell
& ../NetBBS/.venv/Scripts/python.exe scripts/accept_s13_netbbs.py `
  --root C:/Temp/blacksite-s13-proof `
  --door-python .venv/Scripts/python.exe --show
```

Use a fresh private root. It registers a native stdio door and walks real
maps through NetBBS Telnet at 80x24 and 132x50. Two callers use separate
terminals, meet, see the helpless body, test a safe refusal, traverse all
eleven public sector links, refuse a gate and return. The unsafe Clinic
alley test grants grade five because S16 earning is absent and clears the
earlier refusal's heat to isolate body damage (S11 separately waits the
real ten-minute deadline). It
uses a native Ghost rig and real weapon input, with no extra money,
items or teleports. It records ANSI/screens and structured results.
This is automated terminal acceptance, not a human gameplay assessment.
