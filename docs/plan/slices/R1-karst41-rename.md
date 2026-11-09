# R1 — The game is called Karst 41: rename the code and its names

**Status:** in progress (draft PR #193; the owner merges)
**Primary model:** Codex · **Reviewer:** automated review, technical lead, presentation lead (title screen acceptance)
**Depends on:** the canon rename PR (creative lead, owner-approved) · **Milestone:** housekeeping
**Issue:** https://github.com/Thiesi/Karst41/issues/190

On 2026-11-09 the owner decided to rename the game from Blacksite to
**Karst 41**. The GitHub repository is now `Thiesi/Karst41`, and the
local folder has moved. This slice renames what the code calls itself.
Canon decides what the words mean: the creative lead's canon PR (game
title against place) lands first. Where this file and canon differ,
canon wins.

The owner settled three points:
- **Option A:** only the game's title changes. "The Blacksite" stays
  the in-world installation and endgame, so content ids like
  `blacksite-l1`, NPC lines and lore texts keep it.
- **The identifier is `karst41`.** The display title is **KARST 41**.
- **Old configuration names keep working until S31,** as fallbacks.

## Goal

After this slice, nothing that names the game says Blacksite: the
Python package, its entry points, the environment variables, the socket
and pid files, the temp prefixes, the CI workflows, the deploy files
and the title screen. Behaviour, rules, content and the frozen values
stay exactly as they are. It is a mechanical rename with no feature
change.

## Scope

1. **Package.** `src/blacksite` becomes `src/karst41`, together with:
   - every import;
   - `pyproject.toml`: distribution name `karst41`, package data, and
     the scripts `karst41`, `karst41-server` and `karst41-door`;
   - the `python -m karst41.{admin,bot,door,server}` entry points;
   - logger names and argparse `prog` and descriptions.

   **No `blacksite` import shim.** No operator runs the door yet:
   01-netbbs-platform says there is no installed base, and ReLink
   confirmed that no node registers it. Say on the PR if you find
   otherwise.
2. **Environment variables.** The new names are `KARST41_INSTALL_DIR`,
   `KARST41_SESSION_LIMIT`, `DOOR_KARST41_INSTALL_DIR`,
   `DOOR_KARST41_SESSION_LIMIT` and `DOOR_KARST41_PRESENTATION`.
   Include `BLACKSITE_PRESENTATION_TRIAL` and any other `BLACKSITE_*`
   name you find.
   - The old name is still read when the new one is unset. The new name
     wins when both are set.
   - Using an old name logs one deprecation line per process. It must
     not fill the log.
   - Mark every fallback `# Remove in S31.` and add the removal to the
     S31 slice file as a bullet.
   - Tests cover new only, old only, both, and neither.
3. **Runtime files.** `run/blacksite.sock` and `run/blacksite.pid`
   become `run/karst41.sock` and `run/karst41.pid`
   (`server/transport.py`). There is no fallback, because no installed
   base exists. Also update the admin tools and the deploy units:
   - `deploy/rc.d/blacksite` becomes `deploy/rc.d/karst41`;
   - the systemd unit name, the paths and `deploy/README.md`.
4. **Title screen text.** `door/screens.py` shows **KARST 41** where it
   shows `BLACKSITE` today. Replace the string comparison at
   `door/model.py:250` with a check that doesn't depend on the title
   text, such as a screen kind.
   - The tagline "a real-time door for NetBBS · Karst, Year 41" stays.
     The presentation lead may decide otherwise at acceptance.
   - Update `tests/door/golden/title_*` and the acceptance scripts that
     wait for the `BLACKSITE` text (`accept_s04_netbbs.py`,
     `accept_s05_systemd.py`).
   - Logo art is not part of this slice. It belongs to S33.
5. **Tooling and CI.**
   - The temp prefixes `blacksite-*` and `blacksite-proof/<kind>`
     become `karst41-*` and `karst41-proof/<kind>`. This covers
     `scripts/clean_scratch.py`, the scratch guard and the acceptance
     scripts.
   - The guard counts both old and new prefixes until S31, so a
     leftover old folder still warns.
   - Workflow `paths:` filters, run commands and artifact names move to
     the new names.
   - Some historical proof workflows diff against a pinned commit using
     `src/blacksite/...` paths, for example `p6-a8-proof.yml`. Map the
     old path to the new one in those workflows, or explain on the PR
     why a check no longer applies. Never weaken one silently.
6. **Docs that name identifiers:**
   - AGENTS.md, README and CLAUDE.md paths and commands;
   - the install guide, the architecture's install section and the S31
     register step.

   Only identifiers and repo URLs change here. Where the text means the
   game, the canon PR has already changed the wording. Update
   `github.com/Thiesi/Blacksite` links to `Thiesi/Karst41` in living
   docs. GitHub redirects the old URLs, so this is tidiness, not
   breakage.

## Not in scope

- **Historical evidence** under `docs/ops/captures` and older evidence
  notes: it's a record, and its hashes must stay valid. The same goes
  for old commit messages and closed issues.
- **In-world uses of "the Blacksite":** content ids, NPC lines, lore,
  and places such as "Blacksite Outworks".
- **The website** (netbbs.org, handled by the NetBBS session) and the
  banner art (presentation lead). Both come after this slice.
- **Any behaviour, rule, content or layout change.**

## Checks the PR must report

- **Frozen values.** The P3 interaction digest (`05213f38…`, 10,704
  cases), the mechanics fingerprint and every other frozen value stay
  unchanged. If any of them hashes a module path or the package name,
  stop and list every changed case for the owner. A fingerprint move
  needs the owner's approval, as always. Don't rebaseline.
- **Persisted data.** Search a real `world.db` produced by the
  acceptance runs for stored module paths or names: pickles, JSON type
  tags, schema keys. If you find any, add a migration with a test.
  Report the result either way.
- **Leftovers.** Run `git grep -n -i blacksite` after the change. Give
  each remaining hit a reason, grouped as: place (canon), historical
  evidence, S31 fallback, or redirecting URL.
- **Evidence.**
  - Full suite on Linux and Windows.
  - Acceptance S04, S05 (systemd), S10, S11 and S24 at both sizes.
  - Native captures of the title screen at 80x24 and 132x50 in all
    three tiers, from a wheel built from this head.
  - An install from a clean venv with `pip install` of the built wheel,
    then `python -m karst41.door` starts.

## Merge

The PR edits the plan and docs, so the owner merges (§7.1 condition 3).
Presentation acceptance of the title screen comes from the presentation
lead. Open branches catch up by merging main after R1 lands, never by
rebase-and-force.

H1 and S25 layout approval are not affected and stay withheld.
