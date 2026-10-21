# S05 — Interim service runner, admin CLI skeleton, deploy templates

**Status:** done (PR #44)
**Primary model:** Sonnet · **Reviewer:** none
**Depends on:** S03 · **Milestone:** M0
**Issue:** https://github.com/Thiesi/blacksite/issues/5

## Goal

Give a SysOp a way to run the game service today, before NetBBS gains
door services (upstream 01): a foreground `blacksite serve` command,
NetBSD `rc.d` and `systemd` unit examples, and the admin CLI skeleton
with the first commands. After this slice a SysOp on NetBSD can start
the service at boot and check its status from a shell.

## Spec references

- `docs/design/02-architecture.md` §2.3 (admin CLI), §3.2 (interim
  self-hosted service), §12 (observability).
- `docs/upstream/01-door-services.md` (what replaces this later).
- `docs/design/04-assets.md` §5 (operator-facing assets).

## Scope

- `src/blacksite/admin/__main__.py`: argparse with `--install-dir`
  (default from `BLACKSITE_INSTALL_DIR`), subcommands `serve` (runs the
  server in the foreground; alias for `python -m blacksite.server`),
  `status`, `who`, `stop`, `validate` (S02's validator over
  `DIR/content` + `DIR/content.local`), `secrets rotate`, `--json` for
  machine output.
- `src/blacksite/admin/client.py`: connects with `admin.secret`, sends
  `admin.*` frames, prints results; exits 1 with a one-line message if
  the socket is absent ("service not running; start it with `blacksite
  serve` or your rc.d script").
- `deploy/rc.d/blacksite`: NetBSD `rc.subr` script with `name`,
  `rcvar`, `command` as the venv interpreter, `command_args` running
  `-m blacksite.server --install-dir ...` daemonised via
  `command_interpreter` and a pidfile at `DIR/run/blacksite.pid`
  written by the server itself (S03), `blacksite_user` defaulting to
  `netbbs`, `stop_cmd` using `blacksite admin stop` with a 10 s wait
  then `kill -TERM`. NetBSD has no `daemon(8)`; do not use it. The
  pidfile name must not collide with NetBBS's own or its backup job's.
- `deploy/systemd/blacksite.service`: `Type=simple`, `User=netbbs`,
  `ExecStart` the interpreter with `-m blacksite.server`, `ExecStop`
  `blacksite admin stop`, `TimeoutStopSec=15`, `Restart=on-failure`,
  `RestartSec=2`.
- `deploy/README.md`: install steps (venv owned by the service account,
  `pip install` the wheel, choose `DIR`, run `blacksite admin validate`,
  enable the unit), and the sentence "This is the interim path until
  NetBBS supervises door services (NetBBS issue #…)".
- Server side (small additions to S03): `admin.stop` sends `bye
  maintenance` to callers and exits; the pidfile is written on start and
  removed on stop.

## Out of scope

- Moderation, backup, restore, migrations, season commands (S28).
- The NetBBS door profile preset and SysOp guide (S31).
- Any change to NetBBS.

## Data and content

None.

## Protocol and view models

- `admin.status` reply: `uptime_s, players, active_zones, tick_p50_ms,
  tick_p99_ms, persist_lag_s, content_hash, season`.
- `admin.who` reply: list of `{handle, player_name | null, zone | null,
  connected_s}`.
- `admin.stop`: `{ok: true}` then the server stops.

## Tests

- `tests/admin/test_cli.py::test_status_json_shape` (headless harness),
  `::test_who_lists_sessions`, `::test_stop_sends_bye_then_exits`,
  `::test_missing_socket_message_exit_1`, `::test_validate_runs_validator`.
- `tests/deploy/test_units.py::test_rc_script_has_no_daemon8`,
  `::test_rc_pidfile_path_is_under_run`,
  `::test_systemd_unit_parses` (key=value sanity, `User=` present).

## Acceptance script

1. On the ReLink-style NetBSD box or a Linux host: install the wheel
   into a venv owned by the service account, copy the unit, set `DIR`.
2. Start via `service blacksite start` (or `systemctl start blacksite`);
   `blacksite admin status` prints uptime and `players: 0`.
3. Enter the door from NetBBS (S04): `blacksite admin who` lists the
   caller.
4. `service blacksite stop`: the caller sees "The city is dark right
   now."; `run/` is empty; no process remains (`ps`).
5. Reboot (or restart the unit): the service comes back.

## Definition of done

- Roadmap §7 holds; step 1–5 done on at least one real host and the
  host named in the PR.
- `deploy/README.md` cites the upstream issue number once filed.

## Implementer notes

- NetBBS's own rc.d lessons apply (recorded in its repo, PRs #321/#322):
  `rc.subr` hides a missing `$command` behind exit 0, so the script
  must check the interpreter path exists and print a clear error; use
  `${name}_flags` conventions; pidfile ownership must match the service
  user.
- The service must not run as root and must not be a child of NetBBS in
  this interim path; the unit runs it as the same service account NetBBS
  uses so the socket's 0600 mode and the install directory permissions
  line up.
- `blacksite admin stop` is preferred over signals in the units so that
  callers get `bye` before the socket disappears; the units still fall
  back to `SIGTERM`.
- Keep every deploy file ASCII; SysOps edit them on the box.

## Implementation notes

Implemented by Codex; Sonnet is the preferred primary model. Reuses the
S03 authenticated operator endpoint and maintenance shutdown. The
`blacksite` convenience command and module now expose `serve` and
`admin`; existing module/console aliases remain available. Command
options work before or after the subcommand.

Status adds the specified field names while retaining S03 status keys.
Who reports handles and connection duration; player names and zone stay
null until S06/S07 own that state. The server writes its own
`run/blacksite.pid`, removed during shutdown. Secret rotation is offline,
holds the same exclusive lease, atomically replaces each secret, and
never prints credentials. Fresh-install validation uses packaged content
plus local overrides before the server bootstraps the readable copy.

NetBSD's `command_interpreter` matches shebang processes; it does not
daemonize an executable. The template leaves it empty for the Python
binary and explicitly backgrounds the foreground server as the service
account. It checks interpreter availability and startup success, and
uses the specified bounded stop/TERM fallback. Deployment files use
ASCII and LF on every checkout.

`scripts/accept_s05_systemd.py` and the service-acceptance workflow run
the acceptance on an isolated Ubuntu systemd host with a wheel-installed
service under a non-root account and real local NetBBS native stdio.
They exercise 80x24 and 132x50 callers, status/who, maintenance shutdown,
empty run files, process exit and unit restart. Native NetBSD rc.d
execution remains a separate platform check.

## Acceptance record (2026-10-21)

- Real Ubuntu systemd host (GitHub runner), Python 3.12, installed wheel,
  non-root service account and NetBBS v7.31.0 native stdio/Telnet picker.
  Status, who, connected-caller maintenance stop, empty run files, process
  exit and enabled-unit restart pass at 80x24 and 132x50.
- The final unit result remains successful after a direct admin stop.
  Proof and ANSI captures are attached to service acceptance run
  [39585522074](https://github.com/Thiesi/Blacksite/actions/runs/39585522074).
- Full local suite before the review fixes: 416 passed, 1 skipped on
  Windows. Final focused operator/deploy checks: 9 passed. Final full CI:
  419 passed on Ubuntu; 418 passed, 1 skipped on Windows Python 3.12.
- Claude re-review reports no blockers and accepts the scenario-based
  rejections. No balance numbers or runtime dependencies changed.
- NetBSD script passes shell syntax validation; actual NetBSD execution
  is not claimed. S05's required real-host acceptance uses Linux.
