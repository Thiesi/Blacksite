# Deployment templates

The service runs as the same non-root account as NetBBS. Set the paths
and account in these editable examples to match the host. The venv and
install directory belong to that account so socket permissions line up.

This is the interim path until NetBBS supervises door services
([NetBBS issue #466](https://github.com/Thiesi/NetBBS/issues/466)).
Blacksite's released companion-service integration remains S31's job.

## Install and inspect

Create `/opt/blacksite` and `/var/db/blacksite` owned by `netbbs`, then
run these as that account, using Python 3.12 or newer:

```sh
python3 -m venv /opt/blacksite/venv
/opt/blacksite/venv/bin/python -m pip install /path/to/blacksite.whl
/opt/blacksite/venv/bin/blacksite admin --install-dir /var/db/blacksite validate
/opt/blacksite/venv/bin/blacksite serve --install-dir /var/db/blacksite
```

Add `/opt/blacksite/venv/bin` to PATH for the shorter commands below,
or keep using their absolute paths.

Before first start, validation checks the package content plus
`DIR/content.local`. After bootstrap it checks `DIR/content` and the
overrides. Invalid content returns exit 1. Startup creates credentials,
the database and run files. Use a second shell for:

```sh
blacksite admin --install-dir /var/db/blacksite status
blacksite admin --install-dir /var/db/blacksite who --json
blacksite admin --install-dir /var/db/blacksite stop
```

`BLACKSITE_INSTALL_DIR` supplies the default directory for commands.
`blacksite-admin` and `python -m blacksite.admin` expose the same tools.
An absent service returns exit 1 and a start instruction. `--json` emits
one JSON result. Status includes uptime, callers, tick timings, content
hash and persistence lag. Who lists caller handles; character and zone
fields remain null until their engine slices land.

Stop the service before `blacksite admin --install-dir DIR secrets rotate`.
Rotation takes the service's exclusive lease and refuses while it runs.
Both HMAC credentials change; none are printed. Restart afterwards.

## NetBSD rc.d

Copy `rc.d/blacksite` to `/etc/rc.d/blacksite`, root-owned and mode 755.
Configure `/etc/rc.conf` with the host's actual paths:

```sh
blacksite=YES
blacksite_user=netbbs
blacksite_dir=/var/db/blacksite
blacksite_python=/opt/blacksite/venv/bin/python
blacksite_flags="--log-level INFO"
```

Use absolute paths without single quotes. Run `/etc/rc.d/blacksite start`,
`status`, `stop` or `restart`. The script checks the interpreter, drops
privileges, backgrounds the server, and waits for its own
`DIR/run/blacksite.pid`. Startup errors appear in `logs/service.log`.
Stop requests maintenance shutdown, waits ten seconds, then uses TERM
with another bounded wait. No daemon utility is needed.
`command_interpreter` stays empty because Python is the executable;
[rc.subr](https://man.netbsd.org/rc.subr.8) uses that field for matching
shebang interpreters rather than backgrounding commands.

## Linux systemd

Edit `systemd/blacksite.service`, copy it to
`/etc/systemd/system/blacksite.service`, then run as root:

```sh
systemctl daemon-reload
systemctl enable --now blacksite.service
systemctl status blacksite.service
```

`systemctl stop blacksite` requests maintenance shutdown; TERM is the
manager's fallback. `systemctl restart blacksite` starts a fresh process.
Inspect failures with `journalctl -u blacksite`.

## Host acceptance

On a real Linux or NetBSD host, install the wheel, start via the unit,
check status, enter through NetBBS and check who, stop while connected,
verify an empty `run/` and no process, then restart or reboot and check
status again. Static parsing and Windows subprocess checks do not prove
that service-manager acceptance passed.

## Later integration

- **S31** (NetBBS integration and release) adds
  `netbbs-door-profile.json`, the importable native stdio door profile
  (venv interpreter, argv `-m blacksite.door`), and its door-service
  variant once the upstream request lands.

Until then, `docs/design/02-architecture.md` sections 3 and 8 describe how the
pieces are meant to run.
