# Deployment templates

The service runs as the same non-root account as NetBBS. Set the paths
and account in these editable examples to match the host. The venv and
install directory belong to that account so socket permissions line up.

This is the interim path until NetBBS supervises door services
([NetBBS issue #466](https://github.com/Thiesi/NetBBS/issues/466)).
Karst 41's released companion-service integration remains S31's job.

## Install and inspect

Create `/opt/karst41` and `/var/db/karst41` owned by `netbbs`, then
run these as that account, using Python 3.12 or newer:

```sh
python3 -m venv /opt/karst41/venv
/opt/karst41/venv/bin/python -m pip install /path/to/karst41.whl
/opt/karst41/venv/bin/karst41 admin --install-dir /var/db/karst41 validate
/opt/karst41/venv/bin/karst41 serve --install-dir /var/db/karst41
```

Add `/opt/karst41/venv/bin` to PATH for the shorter commands below,
or keep using their absolute paths.

Before first start, validation checks the package content plus
`DIR/content.local`. After bootstrap it checks `DIR/content` and the
overrides. Invalid content returns exit 1. Startup creates credentials,
the database and run files. Use a second shell for:

```sh
karst41 admin --install-dir /var/db/karst41 status
karst41 admin --install-dir /var/db/karst41 who --json
karst41 admin --install-dir /var/db/karst41 stop
```

`KARST41_INSTALL_DIR` supplies the default directory for commands.
`karst41-admin` and `python -m karst41.admin` expose the same tools.

Until S31, old `BLACKSITE_*`/`DOOR_BLACKSITE_*` environment names remain
fallbacks. Every new spelling wins over every old spelling; within each
generation, `DOOR_*` takes precedence over the standalone name. Explicit
CLI arguments still win. Empty new values are set, not missing. Using
an old name emits one deprecation warning per process through Python's
`karst41.environment` logger. Operator CLI use shows it on stderr; the
door suppresses default terminal logging and retains the record for
host-configured diagnostics.
The socket, pid and installed Python package have no legacy alias.

R1 has no installed production base. For a local development setup, stop
the old process before replacing it. Keep the existing world directory
and pass that same absolute `--install-dir` to the new command; do not
start on an empty default directory by accident. Replace the local
service/unit names and NetBBS registration argv with those shown here.
There is no runtime-file, rc.conf or old-package compatibility service.
An absent service returns exit 1 and a start instruction. `--json` emits
one JSON result. Status includes uptime, callers, tick timings, content
hash and persistence lag. Who lists caller handles; character and zone
fields remain null until their engine slices land.

Stop the service before `karst41 admin --install-dir DIR secrets rotate`.
Rotation takes the service's exclusive lease and refuses while it runs.
Both HMAC credentials change; none are printed. Restart afterwards.
Each door connection reads its credential from `DIR/secrets/door.secret`.

## NetBSD rc.d

Copy `rc.d/karst41` to `/etc/rc.d/karst41`, root-owned and mode 755.
Configure `/etc/rc.conf` with the host's actual paths:

```sh
karst41=YES
karst41_user=netbbs
karst41_dir=/var/db/karst41
karst41_python=/opt/karst41/venv/bin/python
karst41_flags="--log-level INFO"
```

Use absolute paths without single quotes. Run `/etc/rc.d/karst41 start`,
`status`, `stop` or `restart`. The script checks the interpreter, drops
privileges, backgrounds the server, and waits for its own
`DIR/run/karst41.pid`. Startup errors appear in `logs/service.log`.
Stop requests maintenance shutdown, waits ten seconds, then uses TERM
with another bounded wait. No daemon utility is needed.
`command_interpreter` stays empty because Python is the executable;
[rc.subr](https://man.netbsd.org/rc.subr.8) uses that field for matching
shebang interpreters rather than backgrounding commands.

## Linux systemd

Edit `systemd/karst41.service`, copy it to
`/etc/systemd/system/karst41.service`, then run as root:

```sh
systemctl daemon-reload
systemctl enable --now karst41.service
systemctl status karst41.service
```

`systemctl stop karst41` requests maintenance shutdown; TERM is the
manager's fallback. The stop RPC is best effort, so an earlier successful
`karst41 admin stop` does not leave the unit marked failed when systemd
repeats that RPC after the socket disappears.
`systemctl restart karst41` starts a fresh process.
Inspect failures with `journalctl -u karst41`.

## Host acceptance

On a real Linux or NetBSD host, install the wheel, start via the unit,
check status, enter through NetBBS and check who, stop while connected,
verify an empty `run/` and no process, then restart or reboot and check
status again. Static parsing and Windows subprocess checks do not prove
that service-manager acceptance passed.

## Later integration

- **S31** (NetBBS integration and release) adds
  `netbbs-door-profile.json`, the importable native stdio door profile
  (venv interpreter, argv `-m karst41.door`), and its door-service
  variant once the upstream request lands.

Until then, `docs/design/02-architecture.md` sections 3 and 8 describe how the
pieces are meant to run.
