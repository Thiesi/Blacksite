# Blacksite — guidance for development agents

Blacksite is a real-time multiplayer cyberpunk door game for NetBBS,
developed as a **third-party native door**: this repository has no commit
access to NetBBS and no say in its release cycle. Read this file before
doing anything; it is the canonical guidance for every agent and every
model that works here. `CLAUDE.md` only points at this file.

## 1. What this repository is

- The game's design, world, and build plan (`docs/`), and, as slices
  land, its code (`src/blacksite/`), content (`src/blacksite/content/`),
  tests (`tests/`), and deployment templates (`deploy/`).
- Python 3.12+, standard library only at runtime (asyncio, sqlite3,
  json). Test dependency: pytest. Nothing else without a design change.
- License: BSD-2-Clause, same as NetBBS.

## 2. The canon hierarchy

When documents disagree, the higher one wins and the lower one is a bug:

1. `docs/world/00-bible.md` — the setting. Canon.
2. `docs/design/00-game-design.md` — the rules and numbers.
3. `docs/design/01-entities.md`, `02-architecture.md`, `03-terminal-ui.md`,
   `04-assets.md` — the technical contracts.
4. `docs/world/01-*` to `08-*` — expansions of the bible (gazetteer,
   factions, Lattice, people, story, catalog, glossary, found texts).
5. `docs/plan/00-roadmap.md` and `docs/plan/slices/*.md` — the build plan.
6. `docs/upstream/*.md` — requests to NetBBS.

Change canon at the top and propagate down, in the same PR. Never fix a
contradiction by editing only the lower document.

## 3. How work is organised

- The unit of work is a **slice**: one file in `docs/plan/slices/`, one
  GitHub issue in this repository, one PR. The slice file is the spec;
  the issue links it. Do not start a slice whose dependencies (listed in
  the file and in the roadmap) are not merged.
- Each slice names a **primary model** (Fable, Opus, Sonnet, Astra,
  Gemini, Human; see the roadmap §3). If you are a different model, you
  may still do the work, but say so in the PR and expect a review by the
  named one.
- Branch names: `slice/S07-characters`. One slice per branch. Commit
  messages: imperative, first line ≤ 72 columns, body says what and why.
- Work in a **git worktree**, never directly in a checkout another agent
  may be using.
- Open the PR against `main` with: the slice ID in the title, a summary
  of what changed, the acceptance script's result (what you ran, on what
  terminal size, through which NetBBS transport), and any design doc
  numbers changed and why.
- A slice is done when everything in the roadmap's "definition of done"
  holds. Mark the slice file `Status: done (PR #n)` in the same PR.

## 4. Coding rules

- **Server-authoritative.** The client never decides game state. If you
  find yourself computing a rule in `blacksite.door`, stop.
- **The simulation never touches sockets, files, or wall clocks
  directly.** It receives ticks, inputs, and a clock; it returns state
  changes and messages. That is what makes it testable and, later,
  federatable.
- **Width-safe rendering, always.** Every string that reaches the
  terminal goes through the client's cell buffer, which measures display
  width with East Asian width rules and never writes the last column of
  the last row. Handles and chat may contain anything; assume they do.
  This mirrors NetBBS's own rule and is not negotiable.
- **No shell, no paths across the protocol.** The server and client
  exchange JSON frames as specified in the architecture document; the
  admin CLI is the only thing that names files.
- **Content is data.** Zones, items, ICE, factions, contracts, events,
  seasons, dialogue, and text are files under `content/`, validated at
  load and by tests. Adding content never means adding an `if` to the
  engine.
- **Numbers live in the design doc.** Constants in code are named,
  sourced from `00-game-design.md` with a comment, and asserted by a
  test. A balance change edits the doc and the test in the same PR.
- **Determinism.** Every zone and sector instance has its own seeded
  RNG. Tests step ticks and assert; no sleeps, no wall-clock reads in
  logic.
- **Menus never gate on questions.** Follow NetBBS's design doc §3.5: a
  screen shows content first, actions are hotkeys, `Esc`/`B` always
  leaves without side effects, and a yes/no is only ever the last
  keystroke behind a hotkey the player chose.
- **Type hints everywhere, dataclasses for entities, no global mutable
  state, asyncio only in the server's I/O layer and the client's two
  pumps.**
- **Logging** is structured (one JSON object per line) in the server;
  the client logs nothing to the terminal except the game.

## 5. Testing rules

- `pytest` from the repository root must be green before a PR opens.
- Every rule from the design doc has a unit test with the doc's number
  in it.
- Every content file loads under the validator in tests; the shipped
  tree and the fixture tree both.
- Multi-session behaviour is tested with the headless harness (several
  sessions, deterministic ticks), not with sockets.
- The client is tested against the fake terminal at 80×24 and 132×50,
  with at least one wide-character handle.
- No test leaves the machine. No test needs a running NetBBS.
- Windows development is supported for tests and the client; the server's
  Unix socket has a `127.0.0.1` TCP fallback for that case only.

## 6. Working with NetBBS

- **Never commit to NetBBS from here.** Anything the platform needs is
  written up in `docs/upstream/` and filed as an issue in `Thiesi/NetBBS`.
  Keep this repository limited to what is implemented entirely in
  Blacksite's own code.
- Test caller-facing changes through a real NetBBS node: a local checkout
  of NetBBS, a registered native stdio door pointing at this repo's venv
  interpreter with argv `-m blacksite.door`, and the game service started
  with `blacksite serve`. The SysOp guide (once S28/S31 land) has the
  exact steps; until then `docs/design/02-architecture.md` §8.
- Track the NetBBS door guide and `netbbs.doors.runtime` for changes to
  the door API; the architecture document §1 records the facts we build
  on and their source. If NetBBS changes them, update §1 first.
- When an upstream request is accepted and released, the slice that
  consumes it (usually S31) removes the interim path only if the SysOp
  guide keeps a clear "requires NetBBS ≥ x.y" line.

## 7. Writing rules for docs and in-game text

- The bible's §2 style guide governs all in-game text: second person,
  present tense, short sentences, concrete nouns, no "cyberpunk", no
  "hacker", no "cyberspace".
- Every new proper noun goes into `docs/world/07-glossary.md`.
- Docs are Markdown, wrapped at about 76 columns, tables for anything
  tabular, no em-dashes in in-game text (the terminal glyph set does not
  include them).
- Do not resolve the Custodian/Tenant question anywhere, ever.

## 8. Things not to do

- Do not add a runtime dependency.
- Do not add a plain-text or ASCII-only display tier; the floor is ANSI
  colour plus cursor addressing at 80×24 with UTF-8.
- Do not add a ninth joinable faction, magic, or a way out of Karst.
- Do not widen a slice. If the spec is wrong, say so in the issue and
  stop; if it is merely incomplete, do the spec and note the gap.
- Do not spawn the game server from the door client.
- Do not read or write `world.db` from anything but the server's storage
  layer and the admin CLI's offline mode.
- Do not use real people, companies, or other fictions' names.

## 9. Repository layout (target)

```
AGENTS.md  CLAUDE.md  README.md  LICENSE  pyproject.toml
docs/
  world/     00-bible … 08-found-texts
  design/    00-game-design … 04-assets
  plan/      00-roadmap, slices/S01 … S33
  upstream/  README, 01 … 06
  ops/       sysop-guide (from S28/S31)
src/blacksite/
  server/    simulation, storage, protocol, sessions, events, admin endpoint
  door/      terminal, keys, renderer, views, client loop
  admin/     CLI
  bot/       load-test client
  content/   zones, sectors, cores, tables, text, art
deploy/      netbbs-door-profile.json, rc.d, systemd
tests/
```

## 10. Model-specific notes

- **Fable / Opus**: you may propose design changes; make them in the
  design doc first, in the same PR, with the reason.
- **Sonnet**: do exactly the slice. If the slice file is ambiguous, pick
  the reading that changes the least and note it in the PR.
- **Astra / Gemini**: your output is reviewed by a Claude model before
  merge; write for a reviewer. Gemini content batches go through the
  validator before anyone reads them.
- **Everyone**: the acceptance script in the slice file is not optional.
  Run it on a real terminal.
