# Door client development and acceptance (S04)

Install the package in its own venv and start the service independently
as described in [the server smoke test](server-core.md). The client
never starts a service.

Register a native **stdio** door in a local NetBBS checkout:

| Field | Value |
|---|---|
| Executable | absolute path to this checkout's venv interpreter |
| Arguments | `-m blacksite.door` |
| Encoding | `utf-8` |
| Environment | `DOOR_BLACKSITE_INSTALL_DIR` = absolute service directory |
| Sessions | 16; multi-node certification enabled |
| Width/height | leave zero to use the negotiated terminal size |
| Resize signal | optional, on Unix when the host supports it |

Current NetBBS profile dimensions pin the door's dimensions as well as
checking the caller's minimum. Leaving them zero permits 132×50 callers
to use their full terminal; Blacksite enforces its own 80×24 minimum.
Current profiles accept custom environment keys under `DOOR_*` only.
`BLACKSITE_INSTALL_DIR` and `BLACKSITE_SESSION_LIMIT` remain accepted for
standalone development; profiles use `DOOR_BLACKSITE_INSTALL_DIR` and
`DOOR_BLACKSITE_SESSION_LIMIT`. The effective limit in the drop-file can
reduce either configured limit.

On a Windows development console, use `--local` to select console key
input. A NetBBS stdio door omits that flag and reads its binary pipe.
The entry point restores a missing Windows `SystemRoot` from the OS
before importing asyncio: Python's Winsock loader needs it even in a
sanitized native-door environment. This does not forward parent BBS
environment variables or outbound capabilities to the game.

The title uses its text fallback until S33 supplies the optional art
view. It never blocks input. `?` opens the local keymap help fallback;
PgUp/PgDn page it and Esc/B returns. `I` on the title opens the first-run
information. S07 owns character creation and persistent first-run state.
Ctrl-X opens the leave confirmation and Y is the final keystroke.

All text, including names, chat, prompts and exit text, goes through the
cell buffer. The last cell remains unwritten; wide glyphs never start
in the last column. No mouse reporting or terminal bell is enabled.
The display renders at most ten times per second and remains idle when
nothing changes. Menus send cursor and selection intents to the server.

Two reproducible acceptance tools live under `scripts/`:

```powershell
# Run with the NetBBS checkout's venv, including its SSH/web extras.
NETBBS_PYTHON scripts/accept_s04_netbbs.py `
  --root .test-tmp/netbbs-acceptance `
  --door-python .venv/Scripts/python.exe

# Run with Blacksite's venv. This takes ten real minutes.
python scripts/measure_s04_idle.py --root .test-tmp/idle --seconds 600
```

The first script creates an isolated NetBBS database, registers the
actual door profile and runs NetBBS's production picker, subprocess
runtime and Telnet/SSH/web listeners on loopback ports. It tests both
80×24 and 132×50, help paging, Esc, leave confirmation and the real
picker redraw. Its final web session stops the service and verifies the
full 60-second reconnect countdown before returning to the picker.
It does not change an existing node or the NetBBS repository. Saved ANSI
captures and a result file are written under the supplied root.

The CPU tool drives the real module over native stdio pipes, visiting
help each minute. On Windows it measures the interpreter directly,
because the venv redirector's CPU counter excludes its Python child.
Its source path points at the same checkout; runtime dependencies stay
standard-library only. This CPU probe is separate from transport proof.

The test suite replays emitted ANSI into an independent fake terminal.
Run it with a repository-local temporary directory:

```powershell
New-Item -ItemType Directory -Force .test-tmp | Out-Null
python -m pytest -q --basetemp=.test-tmp/suite
```
