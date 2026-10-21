# Shared-zone development preview (S06)

Install Blacksite 0.0.2 or newer in the door's own venv. Follow the
[door registration guide](door-client.md), including its negotiated
dimensions and multi-session profile. Start the service separately:

```powershell
blacksite serve --install-dir .test-tmp/world --tcp `
  --spawn-zone vatside-wake-hall
```

Unix uses the local socket by default; `--tcp` selects the loopback
development fallback. `vatside-clinics` is also available for preview.
The server maps arrows/diagonals and Shift movement, enforces movement
cooldowns and stamina, and sends only authorized terrain and presences.
`?` opens help; Ctrl-X then Y leaves through NetBBS's normal picker.

Without `--spawn-zone`, S07 starts saved characters and the Wake. Preview bodies use the
handle and temporary HP/STA pools. Position and terrain memory survive
a reconnect within 60 seconds, but not a service restart or grace expiry.
Character creation and persistence arrive in S07. Travel arrives in S08;
NPCs, terminals, vendors and faction services are inert map anchors here.
The authoring bundle is not an activated city release. Validation still
rejects activation while its future references are absent.

Version 0.0.2 refreshes the package-owned content copy on startup using
the existing validated staging procedure. Keep local overrides under
`content.local`; do not edit the package-owned copy.

Run acceptance with the NetBBS checkout's interpreter, including SSH/web
extras, and Blacksite's installed door interpreter:

```powershell
NETBBS_PYTHON scripts/accept_s06_netbbs.py `
  --root .test-tmp/s06-proof --door-python .venv/Scripts/python.exe --show
```

The probe creates a private node and world, registers the native stdio
door and drives NetBBS's real picker over Telnet and SSH. It checks two
callers at 80x24, then Telnet at 132x50 with SSH at 80x24, movement speed,
sprint STA, wall occlusion, dim terrain memory and clean return. It idles
both callers for 60 seconds and checks the admin tick p99 below 5 ms.
It starts a fresh timing window after reporting the movement phase so
the idle measurement covers those 60 seconds.
`--show` displays actual caller ANSI in the running terminal. Captures
and `result.json` stay under the supplied root. Use a new root each run.
The Linux service acceptance job repeats this against an installed wheel.

For a disposable automated mover, use `blacksite.bot --help` and its
`--walk N --seed N` options with that world's credential. It acknowledges
views and sends seeded random movement intents; no simulation rule runs
in the bot or door client.
