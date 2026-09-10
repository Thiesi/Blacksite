# S31 — NetBBS integration and release: door profile preset, install guide, packaging, first tagged release; door-service profile once upstream 01 lands

**Status:** planned
**Primary model:** Sonnet · **Reviewer:** Human (install on the ReLink test node)
**Depends on:** S28, S30 · **Milestone:** M6
**Issue:** (filled in when filed)

## Goal

Turn the repository into something a SysOp installs: a wheel with the
content inside it, a door profile preset they import on NetBBS's
Compatibility screen, an install guide that goes from a bare service
account to a playing caller, a release checklist, and the first tagged
release. Also prepare, behind a version gate, the door-service profile
that NetBBS will accept once upstream request 01 ships.

## Spec references

- `docs/design/02-architecture.md` §2 (components, install directory
  layout, content copied out on first start), §3 (target and interim
  lifecycle), §8 (registration: native stdio, `max_sessions` 16,
  `multinode_certified` true, `time_limit` at platform maximum,
  `memory_mb` 128, `BLACKSITE_INSTALL_DIR`; wall-time cap; presence), §14
  (packaging: single package, entry points, content as package data,
  Python 3.12+, no runtime deps, semantic versioning, independent
  protocol major).
- `docs/upstream/01-door-services.md` (the `service` profile block),
  `02-session-limits.md`, `04-door-info-enrichment.md` (`door_api`),
  `06-third-party-door-install.md` (the preset shape NetBBS may adopt).
- `docs/design/04-assets.md` §5 (operator-facing assets), §6 (player-
  facing README section).
- NetBBS `docs/NetBBS-door-guide.md`: "Register and test inside NetBBS"
  (import of a repository JSON on the Compatibility screen, argv
  substitutions `{install_dir}` and friends, `max_sessions`, **Check
  setup**, **Test as SysOp**), "Native doors" (interpreter doors),
  "Trust and filesystem layout" (install directory ownership).
- `AGENTS.md` §6 (working with NetBBS), §9 (repository layout).

## Scope

- `pyproject.toml`: package `blacksite`, `requires-python >= 3.12`, no
  dependencies, `[project.scripts]` `blacksite = blacksite.cli:main`
  (dispatching `serve`, `door`, `admin`, `bot`), `[tool.setuptools.
  package-data]` including `content/**` and `deploy/**`, version from
  `blacksite/__init__.py`.
- `python -m blacksite.door`, `python -m blacksite.server`, `python -m
  blacksite.admin`, `python -m blacksite.bot` all work as module
  invocations (NetBBS profiles use `-m`).
- `deploy/netbbs-door-profile.json`: the importable profile with
  `executable_path` placeholder `/path/to/blacksite-venv/bin/python`,
  `args` `["-m", "blacksite.door"]`, `profile` `{version: 1, adapter:
  native, endpoint: stdio, encoding: utf-8, width: 0, height: 0,
  time_limit: 3600, memory_mb: 128, max_sessions: 16,
  multinode_certified: true, environment: {BLACKSITE_INSTALL_DIR:
  "/var/games/netbbs/blacksite", BLACKSITE_SESSION_LIMIT: "3600"}}`,
  plus a `description` string for the door registration.
- `deploy/netbbs-door-profile.service.json`: the same plus the
  `service` block from upstream 01, shipped with a header comment file
  (`deploy/README.md`) stating it requires NetBBS ≥ the release that
  ships door services, and is otherwise rejected by **Check setup**.
- Content bootstrap: first server start copies `content/` out of the
  package into `DIR/content/` and records the package version; a
  version change re-syncs and never touches `content.local/`
  (architecture §2.4) — implement here if S03/S05 left it as a stub.
- `docs/ops/install.md` (or the install chapter of the SysOp guide):
  create the service-account-owned venv and install dir per the NetBBS
  guide's ownership rules; `pip install blacksite-x.y.z-py3-none-any.whl`;
  first `blacksite serve --install-dir DIR` to create secrets and
  content; register the door (SysOp → Doors, minimum play level 255
  first), import the preset, set the interpreter path, **Check setup**,
  **Test as SysOp**, then lower the level; the interim service under
  rc.d/systemd; the door-service variant; upgrade procedure (stop,
  pip install, `blacksite admin migrate --dry-run`, start); backups.
- Release checklist `docs/ops/release.md`: version bump, changelog
  entry (`CHANGELOG.md`, new), protocol major unchanged or bumped with
  a note, `pytest`, content validator, `perf_hour_run` smoke (10
  minutes), build sdist and wheel, install into a clean venv and run the
  acceptance script of this slice, tag `vX.Y.Z`, GitHub release with the
  wheel attached, README status line updated.
- README: replace the "Design complete" status with install pointers
  and a player section (what to expect, minimum terminal).
- The first release: `v0.1.0` after M4 is merged, or whatever the
  roadmap says at the time; this slice performs the first one.
- `door_api` handling: the client reads `door_api` from
  `door_info.json` if present and refuses a major it does not know with
  a clear line (upstream 04).

## Out of scope

- The SysOp guide's operational chapters (S28). The rc.d/systemd units
  (S05). Any NetBBS-side change (upstream).
- Publishing to PyPI (a GitHub release with the wheel is the
  distribution channel).

## Data and content

- `CHANGELOG.md`, `deploy/README.md`, the two preset JSONs, version
  constant, `docs/ops/install.md`, `docs/ops/release.md`.

## Protocol and view models

- None new. The client asserts the protocol major at `hello` (already
  in S03/S04); this slice adds the package version to `welcome` for the
  settings/help "About" line.

## Tests

- `test_wheel_contains_content_and_deploy_trees` (build in tmp,
  inspect)
- `test_module_entry_points_run_help` (subprocess `-m` for the four
  modules)
- `test_preset_json_validates_against_netbbs_profile_fields` (the field
  set in `netbbs.doors.profiles.DoorProfile` as documented in
  architecture §1; keep a copy of the field list in the test with the
  NetBBS version it was taken from)
- `test_service_preset_differs_only_by_service_block`
- `test_content_bootstrap_copies_once_and_resyncs_on_version_change`
- `test_content_local_never_touched_by_resync`
- `test_client_refuses_unknown_door_api_major`
- `test_version_constant_matches_pyproject`

## Acceptance script

1. On the ReLink test node (NetBSD), as the service account: create the
   venv and install dir per `docs/ops/install.md`, install the wheel,
   run the first `blacksite serve`; secrets and content appear.
2. In NetBBS as SysOp: register "Blacksite", import
   `deploy/netbbs-door-profile.json`, set the interpreter path, **Check
   setup** reports no problems, **Test as SysOp** shows the title screen
   at your terminal size; leave; lower the play level.
3. Two callers over SSH and one over the web transport enter the door
   at once; all three see each other in `core-plaza`; `max_sessions`
   permits it.
4. Stop the game service; a caller entering the door sees "The city is
   dark right now." and returns to the picker within a minute.
5. Upgrade path: install a rebuilt wheel with a bumped version, restart;
   `DIR/content/` is re-synced and a file placed in `content.local/`
   survives.
6. Tag and publish the release; download the wheel from the GitHub
   release into a clean venv on the Windows dev box; `python -m
   blacksite.door` prints the minimum-terminal message when run without
   `NETBBS_DOOR_INFO`.

## Definition of done

- Tests green; the release exists on GitHub with the wheel attached;
  the ReLink node runs it; README updated.
- Slice file marked done with PR number.

## Implementer notes

- NetBBS launches doors with a minimal environment (never the full
  parent environment): everything the client needs must come from the
  profile's `environment` map or `door_info.json`.
- `time_limit` above 3600 is capped by NetBBS until upstream 02; the
  preset says 3600 and the guide explains.
- NetBBS is built and run on NetBSD; test the wheel there, not only on
  Linux or Windows. A NetBSD `pkgsrc` Python 3.12 is the reference.
- Do not put the interpreter path in the preset as anything but a
  placeholder: the SysOp edits it on the Compatibility screen.
- Keep the `service` preset separate so **Check setup** on an older
  NetBBS never sees an unknown field.
