# S28 — Operator tooling: full admin CLI, moderation, backup/restore, migrations, audit, SysOp guide

**Status:** planned
**Primary model:** Sonnet · **Reviewer:** Opus (backup/restore and migrations)
**Depends on:** S05, S16, S23, S26 · **Milestone:** M6
**Issue:** https://github.com/Thiesi/blacksite/issues/28

S18 hands off lazy rent reconciliation via
`Apartments.ensure_rent(player_id)`. After an authorized operator clock
advance, reconcile and drain the bounded commerce queue before reporting
success. Preserve frozen invoice amounts, the original unpaid deadline,
instance quality and the physical apartment's rolling theft watermark.
One paid week plus two weeks lapsed requires 21 days; acceptance uses 22
days with no remaining rent funds. S18's native jump is explicitly an
injected housing-clock fixture, not production admin tooling. Backups
include `interlock_state` tenancy, key, safe and impound records in the
same SQLite snapshot as items and players. See game design 8.7, entity
2.3 and accepted [PR #38](https://github.com/Thiesi/Blacksite/pull/38).

## Goal

Give the SysOp everything they need to run a world without reading
code: the complete `blacksite admin` command set over the server's
socket, an offline mode for backup, restore, and migrations, moderation
that keys on the BBS user id, an audit log of every operator action, and
a SysOp guide that walks from install to a season rollover. Every
command already has a server-side implementation in an earlier slice or
gets one here; this slice makes them one coherent tool.

## Spec references

- `docs/design/02-architecture.md` §2.3 (command list: status, who,
  kick, mute, ban, unban, teleport, refund, event force, event cancel,
  season status, season advance, reload zones, backup, restore check,
  chronicle append, export leaderboard; `--offline`), §2.4 (directory
  layout: `secrets/`, `logs/`, `backups/`), §3.3–3.4 (start/stop, lease
  file), §4 (admin secret), §6.2 (online backup API, manifest with
  content hash and schema version; numbered migrations), §12
  (`status` fields, audit log), §13 (bans by `bbs_user_id`).
- `docs/design/00-game-design.md` §14 (mute, kick, ban, teleport,
  refund; one character per BBS user, SysOp may raise), §11 (reports).
- `docs/design/01-entities.md` §2.10 (bans, mutes, audit, reports),
  §2.11 (schema version).
- `docs/design/04-assets.md` §5 (SysOp guide, admin reference).
- NetBBS precedent: War Dialer's `war_dialer_admin.py` and
  `netbbs.backup` handling of door worlds (`docs/NetBBS-door-guide.md`
  "Backup, ownership and restore") for the manifest and lock-sidecar
  conventions a SysOp already knows.

## Scope

- `src/blacksite/admin/cli.py`: argparse tree, `--install-dir`,
  `--offline`, `--json` output for every read command, exit codes
  (0 ok, 1 refused, 2 usage, 3 cannot connect).
- Online commands (socket, `operator` role): `status`, `who` (players,
  zone, faction, jacked, session age, handle), `kick <user> [reason]`,
  `mute <user> <minutes> [reason]`, `unmute`, `ban <user> [--until]
  [reason]`, `unban`, `teleport <user> <zone> [x y]`, `refund <user>
  <chits> [reason]`, `give <user> <item template> [n]` (audit-logged,
  for recovery), `event list|force|cancel`, `season status|advance
  --confirm|set-depth`, `market list|cancel`, `bounty list|refund`,
  `reload zones`, `chronicle append <file>`, `export leaderboard
  [--season n]`, `export chronicle`, `reports list|resolve`, `stop
  [--grace s]`, `characters allow <user> <n>` (raise the one-character
  cap).
- Offline commands (no server, exclusive lease taken): `backup` (online
  backup API into `backups/<UTC timestamp>/world.db` with
  `manifest.json`: schema, content hash, package version, sha256),
  `backup` is also allowed online (the server performs it);
  `restore check <dir>` (verifies manifest, sha256, schema not newer,
  reports differences), `restore apply <dir> --confirm` (offline only,
  moves the current DB aside as `world.db.replaced-<ts>`), `migrate`
  (apply pending numbered migrations; also what the server does at
  start), `migrate --dry-run`, `verify` (runs the entity §5 invariants
  over persistent rows), `secrets rotate door|admin`.
- Moderation semantics: a banned user's next `hello` is answered with
  `bye {reason: banned}` and the fixed text; an active session is
  kicked at ban time. Mute silences all chat channels except `system`
  and shows the muted player a toast. Kick applies the logout rule from
  a safe zone (no sleeper penalty) and returns to NetBBS.
- Audit: every operator command appends to `logs/audit.log` (JSON per
  line: at, operator name from `USER`/`USERNAME` capped at 80 chars, as
  War Dialer does, command, target, reason, result). `status` reports
  audit line count and last entry.
- Player reports (`/report` from S09) listed and resolved here.
- `docs/ops/sysop-guide.md`: install (venv, wheel, install dir),
  register the door in NetBBS (points at S31's preset), start the
  service (released supervisor with NetBBS >= 7.31.0, or S05's explicit
  rc.d/systemd alternative with the service block removed), first start and
  secrets, daily operation (`status`, `who`), moderation, events,
  seasons and the Chronicle, backup and restore with the manifest
  explained, upgrades and migrations, troubleshooting (cannot connect,
  lease held, schema newer, content invalid), and what is deliberately
  not automated.
- `docs/ops/admin-reference.md`: one entry per command with synopsis,
  effect, audit line, and exit codes.

## Out of scope

- The NetBBS door profile preset and packaging (S31). The interim
  service units themselves (S05; this slice documents them).
- Any NetBBS SysOp screen (upstream 01).
- Telemetry beyond `status`.

## Data and content

- `bans`, `mutes`, `audit` (file, not table), `reports` per entities
  §2.10; `character_cap` per user in world meta.
- Migration module naming: `src/blacksite/server/storage/migrations/
  m0001_initial.py` … with `up(conn)` only (no downgrades; restore is
  the downgrade).

## Protocol and view models

- Operator frames over the same protocol: `admin {cmd, args}` →
  `result {ok, data | error}`; the session role gates them (architecture
  §4).
- Player-facing: `toast` on mute/kick/teleport/refund; `bye` on ban.

## Tests

- `test_cli_refuses_without_admin_secret`
- `test_status_json_shape`
- `test_who_lists_handle_and_zone`
- `test_kick_applies_safe_logout_and_bye`
- `test_ban_disconnects_and_blocks_next_hello`
- `test_unban_allows_hello`
- `test_mute_silences_chat_except_system`
- `test_teleport_moves_player_and_toasts`
- `test_refund_credits_bank_and_audits`
- `test_backup_manifest_has_schema_content_hash_sha256`
- `test_restore_check_rejects_newer_schema_and_bad_sha`
- `test_restore_apply_requires_offline_and_confirm`
- `test_migrate_applies_in_order_once`
- `test_server_refuses_newer_schema`
- `test_verify_reports_invariant_breaks`
- `test_audit_line_per_command_with_operator_capped_80`
- `test_characters_allow_raises_cap`
- `test_exit_codes`

## Acceptance script

1. With the service running and one caller online, run `blacksite
   admin --install-dir DIR status` and `who`: the caller appears with
   handle and zone.
2. `mute <user> 5 "test"`: the caller sees the toast and cannot say;
   `unmute` restores it.
3. `ban <user> "test"`: the caller is dropped to the NetBBS door picker;
   re-entering the door shows the banned text and returns; `unban` and
   re-enter works.
4. `backup`: a timestamped directory with `world.db` and `manifest.json`
   appears; `restore check` on it reports "ok".
5. Stop the service, `restore apply` without `--confirm` refuses; with
   it, restores; start the service; the world matches the backup.
6. `tail logs/audit.log` shows one line per command above with your
   OS username.
7. Read `docs/ops/sysop-guide.md` from a clean machine's point of view
   and follow it to a running door; note every step that needed
   knowledge the guide did not give, and fix the guide in the PR.

## Definition of done

- Tests green; both ops documents complete; slice file marked done with
  PR number.
- The user has followed the guide once on a real node.

## Implementer notes

Issue #56: follow `docs/plan/01-netbbs-platform.md` and architecture 6.2.
NetBBS's installation-directory backup is node-wide opt-in, unquiesced
and not restored automatically. Retain Blacksite's SQLite backup API
snapshot and manifest. Verify online backup during writes, integrity and
service-stopped/exclusive-lease restoration; a raw copy of world.db/WAL
must not be presented as recovery proof. Document both stop grace budgets,
the service breaker and manual node-copy recovery. Optional outbound
cannot be advertised as working under the registered-only default gate.

- Never open `world.db` directly while the lease sidecar is held by a
  running server; `--offline` must fail fast with exit 3 and the holder's
  pid.
- The backup must be the SQLite online backup API, not a file copy: WAL
  mode makes a plain copy inconsistent.
- Reasons and operator names are user text: cap lengths as War Dialer
  does (reason 240) and strip control characters before they hit the
  audit log or a player's toast.
- `stop` must honour architecture §3.4's 10-second hard limit; do not
  wait for a slow persistence flush forever.

### S22 crew integration handoff

S22 [PR #61](https://github.com/Thiesi/Blacksite/pull/61) crews dissolve
on restart and remove deleted/disconnected members immediately; there
is no crew table to back up. Existing frozen loot entitlements persist
with their owning source. Preserve consistent SQLite backup semantics.

<!-- s19-services:start -->
### S19 source and service handoff

Reference: [S19 PR #62](https://github.com/Thiesi/Blacksite/pull/62),
[acceptance record](../../ops/s19-acceptance.md) and
[PR #38](https://github.com/Thiesi/Blacksite/pull/38).

S19 supplies the implemented source interfaces, 68 authored contracts
and four service nodes. Full root pytest passed 1344 tests with one
skip. Installed native acceptance covers both sizes and allocations,
forks, repair reconnect and paid restart. Consume the merged PR;
S25/S27/S26 still own real geography, referrals and activation.

Include contracts_state and vendor_budget_state meta in consistent
backups/restores and audit inspection. Budget spent/limit details join the
existing SQL rows atomically; no S19 schema-version migration is required.
Test restore after allocation expiry and a durable reward write before
acknowledgement.
<!-- s19-services:end -->

### S23 market handoff

Consume architecture 15.2 and S23, retaining the accepted
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) product boundaries.
Schema 4 adds market listings, bid history and bounties, with market
serials in meta and private financial audit. Include all in backups.
`admin.market.list` and `admin.bounty.list` take optional positive `page`
(default 1), return at most 100 records and expose `page/pages/total`.
Market pages include current held bids for their selected listings.
Expose pagination in the CLI; do not assume one response is the world.
Cancellation/refund replies follow the durable atomic source commit.

<!-- s24-handoff:start -->
### S24 event integration and acceptance handoff

Reference: [S24 #24](https://github.com/Thiesi/Blacksite/issues/24),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

Retain authenticated, audited `event list [--page N]`, `event force ID
[--where SCOPE]`, and `event cancel PLAN` (also under `admin event`).
List pages hold at most 100 plans. Force obeys capacity, cooldown,
scope conflicts and at least five seconds of public warning. Inspect
committed revisions/source receipts; a failed save publishes nothing.
Document `meta.events_state` as additive world-schema-4 state, backed up
with the world. An incompatible event definition is cancelled with a
correction at restart, never silently redirected. Do not spawn a server
from the door or edit a running database.

Inspect active plans before a content deploy. Incompatible definitions
cancel unfinished event work, including Convoy jobs; completed jobs keep
their one-hour turn-in window. Prefer deployment between active windows.
Expected unavailable-source failures log structured diagnostics and
consume only their roll or committed cancellation, without stopping
the service. Include those records in operator troubleshooting.
<!-- s24-handoff:end -->
