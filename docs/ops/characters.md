# Characters and the Wake (S07)

Install Blacksite 0.0.3 or newer in the door's own venv and start the
ordinary service. Registration follows the [door guide](door-client.md).
The door connects to the service; it never starts one.

```powershell
blacksite serve --install-dir .test-tmp/world --tcp
```

New callers choose an archetype, enter a name (Enter keeps the displayed
BBS default), read or skip the resumable briefing, and take a recruiter
card or none. Names use 2-24 display columns, are unique without regard to
case, and allow letters, digits, spaces, hyphens, underscores and
apostrophes. Esc returns from the name screen; Esc/B leaves the briefing
without creating a character. On the card rack Esc/B takes no card.

After a durable commit the character arrives in the Hall with the
catalog's starter kit, 200 chits, Pick and Umbrella. A card gives +10
standing, not membership. `P` opens attributes, derived values, skills,
grade, XP and unspent points. Move the menu cursor to scroll all rows.
`D` opens deletion; only typing the exact character name deletes it.
Esc cancels. Deletion retains the identity's lease clock, personhood,
receipts and carried clone debt.

Safe/pocket logout is immediate. A contested/open body remains a sleeper
for 60 seconds; reconnect within that interval reclaims it. On expiry it
moves to the nearest authored safe/pocket zone, with the Hall as the
incomplete-city fallback. Restart reconciles real elapsed offline time.
There is no combat in S07, so it adds no combat penalty. Travel is S08;
character item use, equipment rules and vendors follow in S12/S16.

One character per BBS identity is the default. To raise the world cap,
stop the service and use the offline command, which takes the same lease:

```powershell
blacksite admin --install-dir .test-tmp/world character-cap 2
```

Returning callers then choose among their characters or a free slot.
Lowering the cap does not erase existing characters. BBS handles may
change; identity is the origin and BBS user ID. The character name and
BBS handle remain separate on the screen. Lease days and the grade-five
XP target are also separate; personhood does not remove grade protection.

The package upgrades world schema 1 to 2 transactionally. Ordinary player
and terrain-memory changes flush every five seconds, logout immediately.
The installed package-owned content copy refreshes to 0.0.3; local
overrides remain under `content.local`. Back up the install directory
before a normal package upgrade.

Run the acceptance probe with NetBBS's interpreter and extras:

```powershell
NETBBS_PYTHON scripts/accept_s07_netbbs.py `
  --root .test-tmp/s07-proof --door-python .venv/Scripts/python.exe --show
```

It uses a private registered native stdio door and NetBBS's real Telnet
picker at 80x24 and 132x50. It records Wake timing, Ghost numbers, Unmoored
standing, starter grants, same-tile return, restart and a real 120-second
offline interval. Since S08 travel is absent, contested logout uses
explicit server-side scenario placement; the probe claims no exit
behavior. Actual ANSI and `result.json` remain under its private root.
CI repeats the sequence on Linux against an installed wheel.
