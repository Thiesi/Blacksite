# Server core development smoke test (S03)

The interim runner and deployment units arrive in S05. For now, start
the foreground service from an installed checkout:

```powershell
python -m blacksite.server --install-dir .test-tmp/world --tcp
```

On Unix, omit `--tcp` for the private Unix socket. The TCP listener
binds only `127.0.0.1` and writes its selected port to `run/port`.
The install directory belongs to the service account. Unix `run/` and
`secrets/` are private; secrets and the socket are mode 0600. Windows
inherits the install directory's ACL, so use a private directory.

In a second terminal:

```powershell
python -m blacksite.bot --install-dir .test-tmp/world --watch
```

The bot prints one pong latency and waits for the maintenance bye.
Without `--watch` it exits after one ping. `--width 132 --height 50`
sets the advertised terminal capabilities for the larger smoke pass.
This is a protocol probe; there is no game screen until S04/S06.

Starting another server against the same directory must fail with the
`world.db.sessions lease` message. Stop the first server with Ctrl-C
(Windows or Unix), Ctrl-Break (Windows), SIGTERM (Unix), or an
authenticated `admin.stop`.
The watching bot prints `bye maintenance`, the server exits zero,
and `run/` becomes empty. The advisory-lock sidecar remains on disk;
its existence does not mean a server is running. Never delete it to
force a start while another process holds the lease.

The server copies shipped content on first start and on package version
change. Put overrides in `content.local/`; the server preserves that
tree. Validation failures stop startup and release the lease. A crash
during a content upgrade may leave `content.next` or `content.previous`;
inspect these with the server stopped before retrying. Do not discard
an operator's changes without comparing them first.

Inspect `logs/server.log` for JSON `world open`, content hash and season.
Operator actions go to both the database audit table and the append-only
`logs/audit.log`. Authentication credentials are never logged.

Run tests from the repository root with a writable temp parent:

```powershell
New-Item -ItemType Directory -Force .test-tmp | Out-Null
python -m pytest -q --basetemp=.test-tmp/suite
```

Multiplayer tests use `tests/harness.py`, manual ticks and the production
protocol core without sockets. Lifecycle tests use local sockets only.
