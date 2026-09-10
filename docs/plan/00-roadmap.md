# Blacksite — Build Roadmap

The implementation plan: milestones, slices, dependencies, and which
model each slice is written for. Every slice has its own file in
`docs/plan/slices/` with the full specification and is filed as a GitHub
issue in this repository; the issue links the file and the file is the
source of truth. Platform work Blacksite needs from NetBBS is in
`docs/upstream/` and filed in the NetBBS repository, never here.

---

## 1. Principles

- **Vertical first.** M1 ends with two players walking around one zone,
  shooting a drone, and seeing each other do it, through a real NetBBS
  door. Everything after that widens the world; nothing after that
  changes the architecture.
- **A slice is one PR.** It has a spec, a test list, an acceptance
  script (what a human does to see it work), and a definition of done.
  It should be doable by the named model in one focused session.
- **Content is data.** Slices that add content add files under
  `content/` and a validator test; they do not add branches to the
  engine.
- **Numbers live in the design doc.** A slice that needs to change a
  number changes `docs/design/00-game-design.md` in the same PR.
- **No slice depends on an upstream NetBBS change.** Where a request is
  open, the slice builds the interim path.

## 2. Milestones

| Milestone | Outcome | Slices |
|---|---|---|
| M0 Foundation | Package, content pipeline, server and client skeletons, protocol, interim service runner | S01–S05 |
| M1 Meatspace vertical | Two callers in one zone: movement, sight, chat, combat, death, NPCs, items, vendors | S06–S12 |
| M2 The Lattice | Jack in, sectors, cores, ICE, programs, interlock | S13–S15 |
| M3 Progression and economy | XP, skills, implants, drugs, salvage, fabrication, apartments, contracts | S16–S19 |
| M4 Factions and conflict | Factions, standing, Marked, relays, crews, market and bounties | S20–S23 |
| M5 World depth | Events, Undercity and Scour content, seasons and the Blacksite, named NPCs and dialogue | S24–S27 |
| M6 Ship | Admin tooling, load test, onboarding and help, NetBBS integration, federation audit, art | S28–S33 |

After M1 the game is demonstrable on a NetBBS node. After M2 it is the
game. After M4 it is worth a public release as 0.x. M5 and M6 make it
1.0.

## 3. Model labels

| Label | Meaning |
|---|---|
| **Fable** | Claude Fable 5.1. Design-heavy or ambiguous; cross-cutting judgement; anything that changes the design doc's shape. |
| **Opus** | Claude Opus 5. Systems work with real design freedom inside a fixed spec: server subsystems, the renderer, the simulation. |
| **Sonnet** | Claude Sonnet. Mechanical, well-specified work: data conversion, loaders, CLIs, tests from a list, content from a sketch. |
| **Astra** | ChatGPT Astra 6. Independent second opinion: protocol and security review, balance review, spec critique before a slice is started. Not for writing slices that touch the design doc. |
| **Gemini** | Gemini via Antigravity. Bulk content generation with a long context (many zone maps or dialogue files from the gazetteer and personae docs), where the whole world bible fits in the prompt. Output goes through the validator and a Sonnet review. |
| **Human** | The user or an artist. ANSI art passes, playtests, the final call on balance. |

A slice names one primary model and may name a reviewer.

## 4. Slice index

Every slice is filed as an issue in this repository whose number equals
the slice number (S07 is issue #7). The tracking epic is issue #34.

Dependencies are hard: a slice cannot start until its dependencies are
merged. "Content" slices can run in parallel with engine slices once
S02's formats exist.

| ID | Title | Model | Depends on |
|---|---|---|---|
| S01 | Repository skeleton, package layout, CI, test harness conventions | Sonnet | — |
| S02 | Content formats, loaders, validator, test fixture world | Opus | S01 |
| S03 | Server core: socket, framing, hello/auth, sessions, tick loop, event bus, persistence layer | Opus | S01 |
| S04 | Door client core: door_info, connect, terminal, key decoder, cell-buffer renderer, tiers, reconnect | Opus | S01 |
| S05 | Interim service runner, admin CLI skeleton, deploy templates | Sonnet | S03 |
| S06 | Zones: map loading, movement, sight, multi-player presence, ZoneView | Opus | S02, S03, S04 |
| S07 | Characters: the Wake, archetypes, attributes, skills, persistence | Opus | S06 |
| S08 | City graph: exits, transitions, safety classes, pockets, the Core and Vatside and Sodium Row maps | Sonnet | S06 |
| S09 | Chat and log: channels, prompts, emotes, sitrep, ignore/report | Sonnet | S06 |
| S10 | Combat v1: targeting, weapons, cooldowns, cover, damage, shock, down/dead, clone vats, corpse caches, hymns | Opus | S07 |
| S11 | NPCs v1: templates, spawners, behaviours, aggro by relations, Wardens | Opus | S10 |
| S12 | Items, inventory, equipment, vendors, bank, currency | Sonnet | S07 |
| S13 | Lattice: sectors, cells, jack in/out, presences, LatticeView, sector layouts | Opus | S06 |
| S14 | ICE and programs: cores, rooms, encounters, trace, black ICE, the Silt generator | Opus | S13 |
| S15 | Interlock: controls, hardware, cut-power, private cores, core ownership | Opus | S14, S11 |
| S16 | Progression: XP, grades, grade points, skill-by-use, implants and surgery, drugs and dependencies | Opus | S10, S12 |
| S17 | Salvage and fabrication, Ring-fall salvage nodes, schematics, workshops | Sonnet | S12 |
| S18 | Apartments: rent, storage, safe, private core tier, eviction, impound | Sonnet | S12, S15 |
| S19 | Contracts: template engine, six types, boards, crew scaling, story chains, Vesper | Opus | S11, S14 |
| S20 | Factions: membership, standing, relations, Marked, Warden heat, ranks and perks, faction chat | Opus | S11 |
| S21 | Relays and territory: capture rules, influence, buffs, relay vendors, season tally | Opus | S20, S15 |
| S22 | Crews: invite/leave/kick, crew chat and panel, beacon, loot modes, shared XP | Sonnet | S09, S10 |
| S23 | Market and bounties: listings, bids, fees, bounty rules | Sonnet | S12, S20 |
| S24 | World events engine and the five events | Opus | S11, S13, S17 |
| S25 | Undercity and Scour content: all remaining zone maps, spawners, salvage rings | Gemini or Sonnet, Sonnet review | S08, S11, S17 |
| S26 | Seasons: Depth meter, descent consoles, leaderboards, the Chronicle, Blacksite level 1 (instanced zone and sector) | Opus, Fable for the level design review | S21, S19, S24 |
| S27 | Dialogue and named NPCs: dialogue engine, all major and minor NPC files, ambient logs | Sonnet engine, Gemini or Sonnet content | S19 |
| S28 | Operator tooling: full admin CLI, moderation, backup/restore, migrations, audit, SysOp guide | Sonnet | S05, S16 |
| S29 | Load and latency: bot client, 16-bot hour, profiling, delta compaction if needed | Opus | S15, S22 |
| S30 | Onboarding and help: hint system, help pages, first-run screen, session-limit UX, colour-blind palettes, settings | Sonnet | S07, S09 |
| S31 | NetBBS integration and release: door profile preset, install guide, packaging, first tagged release; door-service profile once upstream 01 lands | Sonnet | S28, S30 |
| S32 | Federation readiness audit (design only): origin/authority invariants, protocol reservations, a written bridge design against NetBBS #168 | Fable, Astra review | S21, S26 |
| S33 | ANSI art pack: title, sigils, vignettes, the Ring, Wake Hall, dead screen, transitions | Opus composition, Human pass | S04 |

Reviews: before S03, S04, and S14 start, an **Astra** critique pass over
the relevant spec sections is recommended (protocol, renderer, hacking
model). Before S10 and S16 land, an **Astra** or **Fable** balance read
of the numbers against the catalog.

## 5. Suggested order for one developer at a time

S01 → S03 → S04 → S02 → S05 → S06 → S07 → S09 → S10 → S12 → S11 → S08
→ S13 → S14 → S15 → S16 → S20 → S22 → S17 → S18 → S19 → S21 → S23 →
S24 → S25 → S27 → S26 → S28 → S30 → S29 → S31 → S33 → S32.

## 6. Parallel tracks for several agents

- **Engine track** (Opus): S03 → S06 → S07 → S10 → S11 → S13 → S14 →
  S15 → S16 → S20 → S21 → S24 → S26 → S29.
- **Client track** (Opus then Sonnet): S04 → S09 → S30 → S33.
- **Data track** (Sonnet): S02 → S12 → S17 → S18 → S22 → S23 → S28.
- **Content track** (Gemini or Sonnet, after S02): S08 → S25 → S27 →
  S19's content half.
- **Integration track** (Sonnet): S01 → S05 → S31.

## 7. Definition of done for any slice

- The slice file's acceptance script passes on a real terminal at 80×24
  and at one larger size, through a NetBBS node for anything caller-
  facing (a local NetBBS checkout is fine).
- `pytest` green, including the content validator.
- Design doc numbers unchanged, or changed in the same PR with the
  reason in the PR description.
- Docs updated: `AGENTS.md` if a convention changed, the SysOp guide if
  an operator-facing behaviour changed, the slice file marked done with
  the PR number.
- No new runtime dependency.
