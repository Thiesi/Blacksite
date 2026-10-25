# Presentation integration: engineering assessment and plan

**Status: proposal for the owner's decision. Nothing here is adopted.**
Issue #68. Technical lead's review, 2026-10-25, against `main` at
`d80dacd`, S25 at `a97906b` (PR #66), S27 at `3754620`, and the
presentation lead's working tree on `design/presentation-review`.

This document does not change canon, game rules, numbers or any
slice's accepted status. It does not grant or imply S25's withheld human
layout approval, which stays withheld until the owner grants it.

Canon order (`AGENTS.md` §2) is respected: where a proposal here needs a
spec change, it is listed in §9 as a decision, and the spec edit happens
top-down in its own PR after the decision.

Contents:

1. Findings in brief
2. Where the project actually stands
3. The path from authored place to terminal cell
4. Impact assessment: retain, extend, refactor, replace
5. Impact matrix
6. Slice audit, S25 to S33 and earlier slices
7. Revised implementation plan
8. Division of work
9. Decisions for the owner
10. Review and acceptance process
11. Notes for the presentation lead

Evidence labels: **[V]** read in code, content or git at the stated
commit; **[I]** inference. File paths are relative to `src/blacksite/`
unless they start with `docs/`, `tests/` or `scripts/`.

---

## 1. Findings in brief

1. **The simulation does not need to change.** Geometry, movement, sight,
   cover, memory, persistence and the disclosure filters are sound and
   already sight-correct. Every presentation channel the proposal needs
   can be added without touching rules. [V]
2. **Three real architectural obstacles stand in the way**, and none is a
   rendering problem:
   - **Layout geometry is duplicated across the protocol boundary.** The
     server computes the camera, and seven server modules wrap text,
     using private copies of the client's layout formula
     (`server/views/zone_view.py:34`, `door/layout.py:28` and others,
     §3.4). Any change to header, panel or log size, a 132x50 dashboard,
     an art strip or full-width text, silently changes the server-side
     viewport, which is a rule field.
   - **"What will E do" has no single answer.** E falls through 17
     side-effecting handlers in `server/core.py:213-247`. Nothing can ask
     what E would do without doing it, so a truthful HERE line needs a
     query refactor, not a new view field.
   - **The client has no compositor.** Zone and Lattice renderers paint
     their own header and side panel at hard-coded positions over a
     shared frame (`door/views/zone.py:41-52`, `door/views/lattice.py`).
     A new chrome means touching every renderer unless chrome is first
     split out.
3. **Everything else is "not yet used"**: background colour is already in
   `Style` and emitted at every tier; relay owners, Lattice labels and
   positions, core owners and tiers, combat state, service state and
   `facing` already exist on the server and are simply not shown. [V]
4. **Content is the larger obstacle than code.** Zone maps carry rules
   only, and S25's 24 new maps come from one generator
   (`scripts/build_city_content.py` on the S25 branch) that scales
   gazetteer sketches into walled rectangles with block grids. 179 of 310
   Lattice cells are labelled "Signal rack NN". The city has no canon
   plan-view geography, so a schematic City Map has nothing to draw
   from. [V]
5. **Eleven "done" slices have open acceptance handed to S25** (S12, S13,
   S14, S16 to S24; §6.2). Those obligations now sit behind the #68 hold
   too. Nothing else on `main` is invalidated.
6. **Verification tools give false confidence for this work.** The 33
   golden screens compare text only; colour is never compared. There is
   no golden regeneration tool, no bytes-per-frame measurement, and no
   rendered-screen CP437 check. With S25's workflow, every `src/**` PR
   starts 65 native jobs. [V]
7. **The presentation direction is implementable incrementally**, and the
   presentation lead's prototype (`door/present/`, `server/views/looks.py`)
   is a sound base. It is not committed, and it has a few engineering
   problems to resolve before it lands (§11).

## 2. Where the project actually stands

### 2.1 Slices

| Slices | State | Notes |
|---|---|---|
| S01 to S24 | merged | PRs #39 to #65. Several carry acceptance handed to S25 (§6.2). |
| S25 | draft PR #66, **human layout approval not granted** | 23 commits, 227 files, +16,166/-597. Engine fixes, content bindings and 24 generated maps interleaved. Open per `docs/ops/s25-acceptance.md`: benefit and paid-route probes, earning and pacing measurements, final-head repeats, human review. One 80x24 startup sample failed its budget (3.281 s). |
| S26 | not started | Waits on S25 and S27. Its engine part needs neither. |
| S27 | branch only, no PR | Talker engine, menus, barks, referrals; 30 focused tests; **no cast files exist**. Based on `main`, not on S25. Its slice file conflicts with the S25 branch's copy. |
| S28, S29, S31, S32 | not started | Declared dependencies wait on S26. |
| S30 | not started | All declared dependencies merged; held only by #68 (onboarding). |
| S33 | not started | Dependency S04 merged; held by #68 (art direction) and D8. |

### 2.2 Presentation work in progress

The presentation lead's work is now committed as two draft PRs:

- **#69** (`design/presentation-review`, head `01ae457`): the proposal
  (`README.md`, `spec.md`), mockups, a Sodium Row geometry candidate and
  the trial implementation. The trial touches content (`schema`,
  `validate`, `loader`, `formats`, `palette.json`, new `themes.json`,
  `looks/*.json`), server (`views/zone_view.py`, `views/looks.py`,
  `world/simulation.py`, `lattice/engine.py`, `protocol.py`) and door
  (`model.py`, `palette.py`, `terminal.py`, new `door/present/`).
- **#70** (`design/presentation-paradigms`, stacked on #69, head
  `7550c68`): three playable view paradigms (street view, scenes, Auto),
  `paradigms.md` with decisions S1 to S6, and two trial server
  affordances, `view_shape` and `walk_to`.

Both are gated by environment variables and are proposals, not adopted
inputs. Section 12 covers the owner's preference for Auto.

## 3. The path from authored place to terminal cell

### 3.1 Content

A zone is a `.map` character grid decoded through `tiles.json` into 16
tile ids (`content/formats.py:315`) plus a `.json` sidecar for exits,
objects, spawners and pockets (`content/schema.py:170-302`). The only
sub-zone rectangles are pockets (safety), spawner regions and housing
units; none has a name or a look. `ZoneMeta.district` is a free string.
There is no district entity and no geographic position. [V]

The proposal's place layer fits as a **new record type** beside the map,
as the prototype already does (`looks/<zone>.json`). The tile grid stays
the single source of rules. This avoids editing S25's sidecars.

### 3.2 Simulation

`server/world/zone.py` (passability, opacity, doors, geometry overlays,
`geometry_revision`), `sight.py` (radius, Bresenham line of sight,
cached `visible_tiles`, stealth and private filters) and `movement.py`
are rule code with tests. Remembered terrain is per character,
`Perception.remembered[zone][tile] = tile_id`, persisted compressed in
`player.progress["memory"]` (`server/players.py:16`). Objects and door
states are never remembered. [V]

**Retain unchanged.** No presentation change needs to touch this layer.

### 3.3 View model and protocol

`server/views/zone_view.py:build` emits `viewport`, `tiles` (legend
indices; -1 never seen, -2 remembered), `remembered`, a global sorted
`legend`, `actors` (glyph, role, stance; name only for self), `objects`
(id, xy, kind, state, glyph, role always `text` or `muted`), `me`,
`hazards`, `escape`. Deltas are JSON-pointer ops, sent only when smaller
than the full view (`server/views/delta.py:41-56`). The protocol checks
the envelope only, so additive body fields are free
(`server/protocol.py:225-232`). [V]

The disclosure boundary is enforced in the builder: tiles and objects by
sight plus scouting, actors by `sees_actor` and private/training
filters, hazards and escapes by visibility. Two existing leaks, outside
the proposal: `world/city.py` lists every zone name in the district,
visited or not; `npc-plainclothes-warden` (Sodium Row) is identified by
its template name and its `npc_wardens` colour. [V]

### 3.4 Layout geometry (obstacle)

The client's `layout.compute` (`door/layout.py:25`) and the server's
`camera` (`server/views/zone_view.py:31`) share the same formula by
copy. Further copies wrap or page text at widths derived from it:
`server/wake.py:41,63,81` (briefing at `width-29`, the map area),
`world/simulation.py:301-306` (City Map pages),
`contracts/panels.py:303-306`, `lattice/encounters.py:1426`,
`private_cores.py:239`, and the client menu page size
(`door/model.py:230`). [V]

### 3.5 Interaction (obstacle)

E is consumed by the first of: events, market, contracts, factions,
crews, relays, apartments, progression, lattice, interlock, combat,
fabrication, commerce, npcs, chat, lattice terminal, then
`simulation.interact`, which picks adjacent exits first and then objects
by `(not underfoot, id)` (`server/core.py:213-247`,
`server/world/simulation.py:112`). Each handler tests its own adjacency
and acts at once. The tutorial terminal opening the outfitter is the id
ordering at work. [V; root cause I]

### 3.6 Door client

`Display.render` (`door/model.py:255-300`) builds a fresh `CellBuffer`,
draws the shared frame (`door/views/__init__.py:79`), dispatches a
renderer per view kind (text, dead, menu, zone, lattice), overlays toast
and hit flash, and diffs. Every `view` frame repaints in full; every
style run emits a full SGR reset. `cells.py` enforces display width and
the last-cell rule and is tested by an independent replay
(`tests/fake_terminal.py`). [V]

Every server panel (inventory, character sheet, contracts, market,
events, relays, crews, City Map list, talker) is a generic `menu` body
from `server/wake.py:menu`, drawn by one `render_menu`. A global
restyle is therefore client-only. Semantic emphasis inside panels would
need an additive row/span role later. [V]

### 3.7 Log and voice

`LogLine` is `{id, channel, text, role, at}`; no kind. About 178 helper
calls route through `sim.log`, which stamps everything `zone`/`chan_zone`
(`world/simulation.py:78`), so `zone` currently means place, system,
danger and speech alike. Zone atmosphere is an 8-second toast of one
lore line on first visit. Each zone has one seeded `zone.rng`, shared by
spawns, wander, combat, clinics, encounters and, on the S27 branch,
barks. [V]

### 3.8 Lattice

`LatticeView` already sends every known cell's position, kind, access,
label, core id and flags, plus edges by kind and presences. Showing
names for every cell is a client choice. Missing: per-cell owner and
tier, sector theme, link labels. 179 of 310 labels are placeholders. [V]

### 3.9 City Map

`M` opens a list of visited zones in the current district
(`world/city.py:9-23`), paged into a text overlay. Content has no
district positions and no plan-view geography; the gazetteer gives
per-zone sketches and exit sides, and the bible's geography is vertical
and relational. A schematic map needs a canon decision first. [V]

## 4. Impact assessment

### Retain unchanged

| Component | Why |
|---|---|
| `server/world/` (zone, sight, movement, safety, exits, registry) | Rules are correct and tested; presentation never needs them changed. |
| Character memory and its persistence | Already the "known space" data. Charted terrain can be synthesised per view without writing memory. |
| Deltas and `ViewStore` | Additive fields cost nothing in deltas; static looks only change when the camera moves, which already forces a full view. |
| Protocol envelope and framing | Additive body fields need no version change. |
| `door/cells.py`, `terminal.py`, `keys.py`, `connection.py`, `client.py`, `screens.py` | Width safety, input and transport are independent of the look. |
| Server-composed menu bodies | One generic renderer; a restyle needs no builder edits. |
| Headless harness and fake terminal | Sufficient base for every new test proposed here. |

### Extend

| Component | Extension |
|---|---|
| Content schema and validator | A place record type (themes, regions, signs, marks, glints, charted, names), validated against tile *classes*, not hard-coded tile ids, so S25 tiles (`convoy-road`, `gantry-hazard`) are covered. |
| `palette.json`, `door/palette.py` | Background roles, theme roles, light-ground variants, frame and log roles, deutan and protan values; a dimming function per tier (needs an xterm-256 RGB table); 16-tier backgrounds clamped to 0-7. |
| `glyphs.json` | `actor-drone`; jacked body as a flag, not the cover-2 shape; Lattice glyphs (D6). |
| `ZoneView` | Sight-masked `looks`; object role by kind; actor class; `me.district`, PvP eligibility; `focus` once §4 Refactor 2 lands. |
| `NpcTemplate` | Optional presented class (civilian, warden, security, hostile, drone, vendor) with an explicit override for disguised NPCs; current faction-derived role as fallback. |
| `LogLine` | Optional `kind`, `speaker`, `speaker_role`; one emit entry point that requires a kind. |
| `LatticeView` | Owner and tier per core cell (private cores read "private"), sector theme id, link labels; black ICE marking from the player's survey state, never from the template. |
| Relay objects | Owner-coloured role from data already present (`relay_views.py:187-217`). |
| `door/log.py` | Display-side coalescing and XP merge; scrollback keeps raw lines. |
| `render_menu`, `render_text` | New chrome; full-width text area. |
| Player settings | A write path for the settings the UI spec already lists (S30) plus art mode (D8) and log verbosity. |
| Test tooling | Style-aware goldens, regeneration flag, fingerprint, size budgets, CP437 check on rendered cells, review packets. |

### Refactor (each with its reason)

1. **One layout geometry, used by both sides.** Move the formula into a
   pure module imported by `door/layout.py`, the server camera and every
   server text-wrap site; give `Layout` named rectangles (header,
   viewport, side, log, hint, text area, overlay) and a layout tier.
   *Reason:* today a client layout change silently changes the
   server-side viewport, a rule field, and breaks wrap widths; a
   dashboard tier and full-width text are impossible to do coherently
   without this. A shared module is preferred over sending the viewport
   in `caps` because client and server ship from one package and the
   native acceptance already checks source identity; it needs no
   protocol change. Output must be byte-identical.
2. **An interaction-focus resolver.** Each E-handling subsystem exposes a
   pure query (`what would E do for this session now`, returning a
   target id, label and verb, or nothing) beside its existing `input`;
   `core.py` composes them in the current order; E dispatch and the view
   both use the composed result. *Reason:* a HERE line computed by a
   parallel heuristic would drift from what E does, which is worse than
   no HERE line. This is the only change in the plan that touches many
   subsystems, so it is bounded: behaviour of E stays identical,
   enforced by a test that the predicted handler is the one dispatched
   over a matrix of positions in the fixture world and shipped hubs.
   Any ordering change (the terminal/outfitter case) is a separate,
   explicitly approved change.
3. **Chrome out of the renderers.** One chrome module draws frame,
   header, side panel shell, log and hint from `Layout`; view renderers
   draw only their content rectangles. *Reason:* without it every
   renderer reimplements the header and panel and the frame-by-safety,
   header segments and panel sections diverge per view, the "partially
   converted game" the owner wants to avoid. Byte-identical output for
   the existing look first.
4. **Hit flash and toast** move into chrome: the flash recolours the
   frame instead of overwriting the header with `-` and `|`; the
   first-entry place line becomes a log line. *Reason:* both currently
   destroy information (header text, separator) for the length of the
   effect.

### Replace

1. **The zone renderer** (`door/views/zone.py`), by the layered renderer
   (ground, structure, things, people) that the prototype's
   `door/present/zone.py` starts. *Reason:* the luminance ladder, dimming
   and per-cell backgrounds are a different drawing model; patching the
   current one would carry two models in one function. It sits behind
   the renderer switch until cutover.
2. **The Lattice renderer** (`door/views/lattice.py`), by the linework
   renderer of D7. *Reason:* `(nn)` tokens on a scaled grid share
   nothing with lit cells, named links and 3x3 core boxes. The server
   view needs only additions.
3. **The City Map list overlay**, by a schematic map view, after the
   canon geography decision. *Reason:* a list cannot carry geography;
   #68 names this directly.

Nothing else is replaced. In particular, the zone format, the view
model, the menu system and the simulation are extended, not rewritten.

## 5. Impact matrix

Priority: **1** now, independent of decisions; **2** after the spec
decisions; **3** after representative-location approval.

| Concern | Files and callsites | Contract change | Gameplay effect | Migration and compatibility | Tests and acceptance | Needs presentation lead | Priority, owner |
|---|---|---|---|---|---|---|---|
| Verification baseline | `tests/door/golden/*`, `tests/fake_terminal.py`, `tests/harness.py`, `.github/workflows/service-acceptance.yml` | none | none | goldens gain a style layer; native subset for door-only PRs, full matrix before merge | fingerprint, style goldens, size budgets, CP437 cell check | no | 1, Codex (P1) |
| Layout geometry | `door/layout.py:25`, `server/views/zone_view.py:31`, `server/wake.py`, `world/simulation.py:301`, `contracts/panels.py:303`, `lattice/encounters.py:1426`, `private_cores.py:239`, `door/model.py:230` | `02-architecture.md` names one geometry source | none (byte-identical) | none | goldens and fingerprint unchanged | no | 1, Codex (P2) |
| Chrome split | `door/views/__init__.py:79`, `door/views/zone.py:41-52`, `door/views/lattice.py`, `door/model.py:255-300` | renderer signature takes `Layout` | none | none | byte-identical goldens | no | 1, Codex (P2) |
| E focus | `server/core.py:213-247`, 17 `input` handlers, `world/simulation.py:112` | `ZoneView.focus`, J target | none; ordering fix only if approved | additive field | predictor-equals-dispatcher matrix test; Wake Hall native script | HERE wording; hidden-exit rule (D-T4) | 1, Opus (P3) |
| View semantics | `server/views/zone_view.py:87-116`, `content/schema.py:917`, `glyphs.json`, `relay_views.py`, `lattice/engine.py:485-526` | additive fields; NPC presented class | none; fixes drone `@` and jacked `▒` | old client ignores fields | role and glyph tests updated; disclosure tests for class override and private cores | class taxonomy, glyphs (D6) | 2, Codex (P4) |
| Log kinds and voice | `server/protocol.py:103`, `world/simulation.py:78`, ~178 helper calls, `crew_engine.py:66`, `combat/engine.py:272`, `progression_engine.py:273` | `kind`, `speaker` on log lines | none | default kind from channel keeps old lines valid | lint test: every emitter passes a kind; new-Wake script | kinds and rules (D5) | 2, Codex (P4) |
| Palette and style | `door/palette.py:17-60`, `palette.json` | new roles; bg roles | none | additive roles; existing roles unchanged | contrast-floor test per theme and tier; variant completeness | values (D4) | 2, Codex (P5) |
| Zone renderer | `door/views/zone.py` replaced by `door/present/zone.py` | none | none | behind switch until cutover | style goldens 2 sizes x 3 tiers x wide handle; frame budgets | yes | 2, Codex (P5) |
| Place layer | new `looks/*.json`, `themes.json`, `content/schema.py`, `validate.py`, `server/views/looks.py`, `zone_view.py` | `01-entities.md` place record; `04-assets.md` §3 | none, except charted terrain shows layout (D1) | absent record means no dressing | validator rules; sight-mask test; charted masking of hidden-exit corridors and private interiors | yes (D1 to D3) | 2, Codex engine, presentation lead content (P6) |
| Spawner spread | zone sidecars (Plaza civilians held in x5-22, y3-8 by `wander` clamp, `npcs/engine.py:360`) | none | NPCs occupy more of the space | content only | existing spawner validator | placement intent | 3, content (P6, C1) |
| Lattice | `door/views/lattice.py`, `lattice/engine.py`, `content/sectors/*.json` (179 placeholder labels) | additive LatticeView fields | none | labels change, ids and topology unchanged | Lattice goldens regenerated; no `(nn)` remains | yes (D7), label voice | 2, Codex renderer, Sonnet labels (P7) |
| Ambient and barks | prototype `ZoneSimulation.ambient`; S27 `BarkScheduler` | one emitter, per-caller budget | none | — | derived RNG test: ambient leaves `zone.rng` sequence untouched; rate test | ambient content | 2, Codex with S27 (P8) |
| City Map | `world/city.py`, `world/simulation.py:228-306` | new map view kind; district geography content | none | list remains until replaced | disclosure test (visited only) | geography (D-T7) | 3, after canon (P9) |
| Map geometry | S25 `scripts/build_city_content.py`, 24 S25 maps, S08 hub maps | none in format | movement and sight change where geometry changes | fingerprint rebaselined per approved zone; S25 coordinate-bound receipts re-run | BFS walkability, size, gates; human layout gate | yes, geometry direction | 3, S25 owner under human gate |
| Settings | `server/players.py:66`, `chat.py:276` | settings write intents | none | defaults preserve current behaviour | persistence tests | settings list | 2, S30a |
| Performance | none measured today | budgets in slice files | none | — | bytes per full redraw and delta at 132x50 truecolor; render time | no | 1 baseline (P1), 2 enforce (P5) |
| Transport glyphs | `glyphs.json` (`•` 0x07, `←` 0x1B in CP437) | registry rule | none | — | rendered-cell CP437 check; S31 real-transport run | yes (D6) | 1 check (P1), S31 human |

## 6. Slice audit

### 6.1 S25 to S33

| Slice | Can continue | Classification | Recommended action |
|---|---|---|---|
| S25 | partly | **subdivide; acceptance revised** | Split into S25a engine fixes and canon corrections, S25b content bindings (vendors, banks, cores, relays, services, NPC profiles) validated on current maps, S25c geometry and place records per district under the human gate. Replace acceptance step 5 (list `M` overview) until P9 exists. Widen the human gate from two named zones to the §10.3 criteria per district. Approval stays withheld. Splitting needs the owner's consent (D-T2). |
| S26 | engine yes | **subdivide** | S26a seasons engine (contribution, rosters, ballots, settlement, Chronicle) against fixture maps; depends on S19, S21, S22, S24 only. S26b Season 1 bundle and Blacksite level 1 map; depends on S25c, S27, P6 and a human layout gate. |
| S27 | backend and cast yes | **add presentation requirements; placement waits** | Finish engine, referrals and all cast files now. Add: speech lines carry `kind` and structured `speaker`; barks go through the single ambient emitter (P8) with a derived RNG. Native steps 1 and 3, speaker placement and ambient emission wait for P4, P8 and S25c anchors. Rebase its slice-file edit onto the S25 branch copy. |
| S28 | mostly | **continue; relax dependency** | Core tooling depends on S05, S16, S23; season commands follow S26a. Add: `reload zones` and resync must carry place records. |
| S29 | instrumentation yes | **subdivide; wait for view contract** | S29a bot, instrumentation, tick profiling now. S29b delta and render budget verdict, compaction covering `looks`, client render CPU on the new renderer, after P5 to P7 and S25c. Add S25 as a direct dependency (the hour run uses S25 maps). |
| S30 | plumbing yes | **subdivide; presentation requirements** | S30a now: session-limit UX, reconnect, `unicode_style` refusal, hint engine, settings persistence and intents, help plumbing, S25 repair help. S30b after P5 to P8: deutan and protan for the final role set, art mode and log verbosity settings, legend help, first-run and Wake layout, human first-time pass. |
| S31 | no | **add dependencies and acceptance** | Depends on P10 and the final human gate H4. Its step 7 includes the CP437 control-code check and every D6 glyph. Keep full presentation sign-off out of the release slice: H4 is its own gate issue that S31 depends on. |
| S32 | yes | **continue; one note** | Design-only. Add the additive view fields (`looks`, `focus`, log `kind`) to the protocol reservations it audits. |
| S33 | tooling yes | **subdivide; wait for D4, D6, D8** | S33a loader, sidecars, `art-check`, fallbacks, tests now. S33b composition, sizes and screen wiring after the D8 playtest; vignette count and sizes revisited against district themes; sigil fit re-checked against the new side panel. |

### 6.2 Earlier slices

| Slice | Effect | Action |
|---|---|---|
| S04, S06, S07, S10, S12, S13, S16 | Text goldens pin today's rendering. | Valid regression fixtures until cutover; regenerated by P5 to P7. They never were design approval. |
| S06 | Acceptance step 3 ("seen tiles stay dimmed") changes meaning under D1 and D2. | Mechanics evidence stands; canon line in `03-terminal-ui.md` §2 changes with D1. |
| S08 | Hub maps are the open rectangles #68 cites; step 4 is the rejected list overview. | Hub place records in C1. Hub *geometry* changes need D-T3: the S25 spec forbids redesigning hub graphs. |
| S13 | Step 2 expects `(nn)` cells. | Superseded by P7; mechanics evidence stands. |
| S12, S13, S14, S16 to S24 | Acceptance handed to S25 (Tramyard rifle, Spire and Sink clinics, district cores and relays, real fields and workshops, Terraces homes, service targets, faction sites, crowded crews, Sink Rim bounty, events). | These stay owned by S25b and S25c and stay open. They are not re-opened on the original slices. |
| S16, S22 | Drone glyph, jacked marker and crew beacon glyphs change in P4. | Render tests updated in P4; beacon preservation re-checked. |

### 6.3 Evidence

**Preserved** (engineering facts, unaffected by presentation):
all S01 to S24 mechanics, persistence and security results; S25 at
`1224c30`: root CI 1573 Linux and 1572 Windows plus one skip, native
65/65, NPC p99 and startup samples including the recorded failures,
archive and content identity, functional receipts (purchases, repairs,
Locksmith Key, worker allocations); the measured pacing facts behind the
S25 canon corrections; S27's focused tests.

**Not acceptance of presentation, and never claimed as such:**
the rejected S25 approval packet, "reviewer walked each zone", BFS and
navigation passes, golden screens, S08 step 4 and S25 step 5 overview
evidence, and every capture so far used as layout evidence.

**Will go stale when geometry changes** (re-run, never assumed): S25
receipts bound to coordinates or step counts, for example the workers
passage "saves at least eight steps", the Shaft Head aisle, spawn-escape
regressions, Ring-fall footprints and the Terraces register wing.

### 6.4 Dependency changes

- New presentation slices P1 to P10 and content slice C1 (§7).
- S25 → S25a, S25b, S25c; S26 → S26a, S26b; S29 → S29a, S29b;
  S30 → S30a, S30b; S33 → S33a, S33b.
- S28 depends on S05, S16, S23 (season commands after S26a).
- S29b depends on S25c and P5 to P7. S27 completion depends on P4, P8
  and S25c (placement).
- S31 depends on P10 and H4.

## 7. Revised implementation plan

### 7.1 Principles

1. **Rules never move silently.** A mechanics fingerprint (P1) guards
   every presentation PR. It moves only through an explicit rebaseline:
   the PR names the zones, says why (D1 charted, or human-approved
   geometry), and carries the technical lead's approval.
2. **Foundations before looks.** The three obstacles (geometry, focus,
   chrome) are removed with byte-identical output before any visual
   change, so each visual PR is small and reviewable.
3. **One switch, one cutover.** The new presentation is a single client
   switch covering every view kind. Players keep the shipped
   presentation until cutover (P10) flips the default for all screens at
   once and removes the old renderers. Reviewers and playtests use the
   switch. There is never a shipped state where some screens use one
   grammar and some the other.
4. **Additive server changes.** Every server field is optional and
   ignored by the old renderer, so any server PR reverts on its own.
5. **Prove on representative places, then migrate.** Three hub zones and
   one sector go through a human gate before any further content work.
6. **Disclosure is reviewed, not assumed.** Every new field states what
   it could reveal (unseen geometry, hidden exits, private interiors,
   disguises, standing, unvisited zones) and has a test.

### 7.2 Sequence

```
now, in parallel ────────────────────────────────────────────────────────
 P0 spec decisions (presentation lead drafts, owner decides)
 P1 verification foundation          #67 fixes        S27 backend + cast
 S25a engine split (if D-T2)         S26a  S29a  S30a  S33a  S32  S28 core
after P1 ────────────────────────────────────────────────────────────────
 P2 layout geometry + chrome split   P3 interaction focus
after P0 + P1 ───────────────────────────────────────────────────────────
 P4 view semantics (additive)
after P2 + P4 (P3 for HERE) ─────────────────────────────────────────────
 P5 client foundations (behind switch)
after P5 ────────────────────────────────────────────────────────────────
 P6 place layer + 3 representative zones   P7 Lattice   P8 voice (+S27)
 ── H1 human gate: representative locations ──     PT1 D8 playtest
after H1 ────────────────────────────────────────────────────────────────
 C1 remaining hub place records       S25c geometry pilots: Shaft Foot,
 P9 City Map (after canon geography)    Far Ring ── H2 human gate ──
 S25c remaining districts, each ── H3 human gate per district ──
then ────────────────────────────────────────────────────────────────────
 P10 cutover    S26b  S27 completion  S29b  S30b  S33b
 ── H4 final human gate (all §10.3 criteria, real transports) ──  S31
```

Critical path: P1 → P2 → P5 → P6 → H1 → S25c → P10 → H4 → S31. P3, P4,
P7, P8 and P9 run beside it.

### 7.3 Slices

Each slice gets a file in `docs/plan/slices/` and an issue when this plan
is adopted. Every slice: `pytest` green, fingerprint unchanged unless
the slice says otherwise, the automated review, and the gates in §10.

**P0 Presentation spec decisions.** *Purpose:* make D1 to D7 canon,
top-down. *Scope:* edits to `03-terminal-ui.md` §1, 2, 3, 8, 10;
`04-assets.md` §3, 9; `01-entities.md` zone and NPC records;
`02-architecture.md` §5.4 view fields plus the engineering contracts
from this plan (one layout geometry; focus contract; log `kind` and
`speaker`; disclosure rules for looks, charted, focus, presented class).
*Excludes:* D8, City Map geography, any code. *Depends:* owner decisions.
*Owner:* presentation lead drafts the design sections; technical lead
drafts the engineering contract sections and reviews consistency.
*Gate:* owner approval.

**P1 Verification foundation.** *Purpose:* make presentation changes
measurable before any is made. *Scope:* golden regeneration flag;
style-aware goldens (glyph plus normalised style grid) for every
existing golden, per tier; mechanics fingerprint (rule projection in
world coordinates: tile ids, passable, opaque, cover, hazard, exits,
object tiles per zone and sector; plus a scripted walk's rule fields,
with harness seeds keyed by zone id and NPCs isolated); baseline bytes
per full redraw and per delta at 80x24 and 132x50 for three tiers;
CP437 round-trip check on every rendered golden cell; headless review
packet builder (per-frame `.ans`, `.txt`, context JSON; optional PNG
from a script outside the test path, since tests may only use pytest);
a door-path native subset for PRs touching only `door/` or content
presentation, with the full matrix kept for ready-for-review and merge.
*Excludes:* any rendering change. *Depends:* none. *Owner:* Codex.
*Tests:* the tools test themselves; one deliberate rule change in a
scratch fixture must fail the fingerprint. *Gate:* automated review,
technical lead.

**P2 Layout geometry and chrome.** *Purpose:* remove obstacles 1 and 3.
*Scope:* §4 Refactors 1 and 3; `Layout` with named rectangles and a
tier field (only the current tier defined). *Excludes:* new tiers, any
visible change. *Depends:* P1. *Owner:* Codex. *Tests:* all goldens and
style goldens byte-identical; fingerprint identical; a test that no
server module computes layout outside the shared module. *Gate:*
automated review, technical lead.

**P3 Interaction focus.** *Purpose:* remove obstacle 2. *Scope:* §4
Refactor 2; `ZoneView.focus` and the J target. *Excludes:* any change to
what E does, unless D-T4 approves an ordering rule, which is then its
own commit and its own test. *Depends:* P1. *Owner:* Claude Opus (the
roadmap's label for cross-subsystem systems work), Codex review.
*Tests:* predicted handler equals dispatched handler over every
interactable tile in the fixture world and the ten hubs, in physical
and jacked states; focus never names an object outside sight or a
hidden exit before D-T4's rule allows. *Real terminal:* Wake Hall
script, 80x24 and 132x50: the hint line names what E opens before it
is pressed. *Gate:* automated review, technical lead, presentation lead
for wording.

**P4 View semantics.** *Purpose:* send the place facts the server
already knows. *Scope:* object role by kind; NPC presented class with
disguise override; actor class; drone glyph; jacked flag; `me.district`
and PvP eligibility; relay owner role; log `kind` and `speaker` through
one emit entry point; first-entry place line as a log line (toast kept
for the old renderer); crew restart notice moved off the world log;
LatticeView owner, tier, sector theme, link labels. *Excludes:*
rendering; ambient emission. *Depends:* P0 (D5, D6), P1. *Owner:* Codex.
*Tests:* field presence; disclosure (plainclothes Warden presents as
its override, private cores read "private", black ICE only after
survey); every emitter passes a kind; fingerprint unchanged apart from
new fields. *Gate:* automated review, technical lead.

**P5 Client foundations.** *Purpose:* one coherent new chrome for every
view kind, behind the switch. *Scope:* palette background roles and
dimming; frame by safety; header segments with drop order; side panel
sections and bars; log gutters, coalescing and XP merge; hit flash on
the frame; 16-tier reverse; full-width text views; new chrome for menu,
text, dead, Wake and title screens; the zone renderer replacement
(without place records it draws the rule layer only). Built from the
presentation lead's `door/present/` once committed. *Excludes:* place
records, Lattice drawing, ambient. *Depends:* P0, P2, P4 (P3 for HERE).
*Owner:* Codex. *Tests:* style goldens per view kind at 80x24 and
132x50, three tiers, wide handle, old and new switch states; frame byte
budgets set from the P1 baseline in this slice's file; contrast floors.
*Real terminal:* NetBBS Telnet at both sizes, 256 and 16 colours: walk
the Wake, the Wake Hall and Meridian Plaza, fight the training drone,
open inventory, contracts and help. *Presentation criteria:* §10.3
items 2 (partly), 4 and 8 on hub zones without place records. *Gate:*
automated review, technical lead, presentation lead.

**P6 Place layer and representative locations.** *Purpose:* prove the
direction in live play. *Scope:* place record format and validator
(tile classes, not ids; signs on walls, marks on floor, reserved shapes
forbidden; 16-colour backgrounds 0 to 7; contrast floors); themes;
sight-masked `looks`; charted zones if D1 (masking hidden-exit corridors
and private interiors, never writing memory); place records and spawner
spread for Meridian Plaza, Clinic Row and Sodium Row. *Excludes:*
geometry; other zones. *Depends:* P0 (D1 to D3), P4, P5. *Owner:* Codex
engine, presentation lead content. *Tests:* validator rules; looks
appear only where tiles are visible or known; charted fingerprint move
limited to the three zones' `tiles` and `remembered` and approved in the
PR; budgets. *Real terminal:* the proposal's §8 walk reproduced through
NetBBS, live, at both sizes and two tiers. *Gate:* **H1**.

**P7 Lattice presentation.** *Purpose:* make going down look like the
city going quiet. *Scope:* D7 renderer; sector themes; real labels for
the 179 placeholder cells (ids and topology unchanged). *Depends:* P0
(D7), P4, P5. *Owner:* Codex renderer; Sonnet or Gemini labels from
`03-lattice.md`, reviewed by the presentation lead. *Tests:* Lattice
style goldens for all sectors; no placeholder label remains; private
core and survey disclosure. *Real terminal:* jack in at Clinic Row,
cross the Vatside sector, enter and leave a core, at both sizes.
*Presentation criteria:* §10.3 item 7. *Gate:* H1 (Vatside sector).

**P8 Voice and ambience.** *Purpose:* the place speaks without drowning
danger. *Scope:* one ambient emitter for zone ambience and S27 barks,
with a per-caller budget, its own RNG derived per zone instance (never
`zone.rng`), suppression in combat and travel, and the verbosity
setting. *Depends:* P4, S27 engine, S30a settings path. *Owner:* Codex
with S27. *Tests:* ambient never draws from `zone.rng`; rate limits;
danger and combat lines never coalesced or pushed out by ambient within
ten seconds. *Presentation criteria:* §10.3 item 8. *Gate:* automated
review, technical lead, presentation lead.

**P9 City Map.** *Purpose:* geography instead of lists. *Scope:* district
and zone positions as content, tram topology, a map view kind,
visited-only disclosure (fixing the current unvisited-name leak).
*Depends:* canon geography decision (D-T7), P5. *Owner:* presentation
lead for the canon proposal; Codex for the view. *Gate:* human review
of the map at both sizes.

**P10 Cutover.** *Purpose:* one grammar everywhere. *Scope:* switch
default on; old zone and Lattice renderers and old chrome removed;
goldens regenerated; every shipped zone has a place record (validator
becomes strict). *Depends:* P5 to P8, C1, S25c complete. *Owner:* Codex.
*Gate:* technical lead, presentation lead, owner.

**C1 Hub place records.** The seven remaining S08 hubs, by the
presentation lead or Sonnet against P6's format. Geometry changes only
if D-T3 allows. *Gate:* H3 per hub.

**S25c geometry.** Geometry revision runs through the generator so the
fix is systematic, not 24 hand edits: the presentation lead supplies the
architectural vocabulary (alcoves, alleys, terraces, platforms) per
district from the gazetteer, the S25 owner implements it in
`build_city_content.py`, and each district is reviewed live. Pilots are
Shaft Foot and the Far Ring, the owner's named cases. *Gate:* H2 for
pilots, H3 per district; S25 approval only by the owner.

**PT1 D8 art-prominence playtest.** Art modes as a client setting
(none, collapsing strip, fixed strip) on the same scripted routes at
both sizes. *Depends:* P5, P6, S33a. *Owner:* presentation lead designs,
Codex builds, owner plays. Feeds S33b and S30b.

### 7.4 Containment and rollback

| Risk | Containment |
|---|---|
| New renderer regresses play | Single client switch, default off until P10; old renderers untouched until P10; P10 is one revertable PR. |
| Server field leaks hidden state | Additive fields reviewed against the §10.2 disclosure list; each field has a disclosure test; reverting a field breaks nothing. |
| Presentation PR moves a rule | Fingerprint fails; only an explicit, approved rebaseline passes. |
| Bigger frames hurt slow links | P1 baseline, P5 budgets, S29b verdict; place looks static per zone so deltas stay small. |
| Shared chrome change breaks every screen | P2 lands chrome with byte-identical output first; visual chrome changes land in P5 under style goldens for every view kind. |
| Geometry rework invalidates S25 evidence | Coordinate-bound receipts are re-run per district, never carried over. |
| CI cost of 65 native jobs per push | Door-path subset per push, full matrix before merge (P1). |

## 8. Division of work

| Party | Owns |
|---|---|
| **Presentation lead** | Experience and interaction design: D1 to D8 drafts; themes, palette values, glyph choices; place records for representative zones; geometry vocabulary per district; Lattice label voice; City Map geography proposal; the perceptual acceptance scenarios; the D8 playtest design; creative sign-off on every player-visible PR. |
| **Technical lead (this role)** | Architecture and integration: this plan and the slice files; engineering contract sections of P0; P3 interface (and implementation, unless the owner prefers Codex); dependency graph and status; review of every PR for cross-subsystem effect, disclosure and canon consistency; rebaseline approvals; keeping docs, roadmap and decisions consistent; surfacing decisions to the owner. |
| **Codex** | Implementation: P1, P2, P4 to P8, P10, P9 view, S25a/b, S26a, S27 backend, S28, S29a, S30a, S33a, #67; S25c generator work under the human gate. |
| **Sonnet or Gemini** | Content batches: Lattice labels, C1 records, S27 cast files, through the validator and a review. |
| **Automated Claude review** | Independent code review on every PR, unchanged. |
| **Owner** | Product decisions (§9), human gates H1 to H4 and PT1, S25 layout approval, merges. |

## 9. Decisions for the owner

The presentation lead's D1 to D8 are theirs to put to the owner; the
engineering consequences of each are noted. The D-T items are this
plan's own.

| ID | Decision | Recommendation | Why it matters |
|---|---|---|---|
| D-T1 | Adopt this plan: P1 to P10, C1, the slice splits and the gates H1 to H4 | Adopt | Without it, presentation and feature work proceed on incompatible assumptions. |
| D-T2 | May S25's engine fixes and canon corrections land as S25a, ahead of layout approval? | Yes, as a separate PR with its own review; S25 layout approval stays withheld | #68 lists such work as independent, but the hold says S25 cannot merge around its gate, so this needs your explicit consent. It removes merge pressure from geometry work and keeps 16k lines from going stale. |
| D-T3 | May S08 hub geometry change (Clinic Row's missing alleys), amending the S25 rule that forbids redesigning hub graphs? | Yes, under the same per-zone human gate and fingerprint rebaseline | The gazetteer architecture is missing in hubs too; place records cannot add alleys. |
| D-T4 | When you stand on a hidden passage, may HERE name it? | Yes, only when standing on its tile (where E already uses it, S25 rule), never from adjacency | Otherwise HERE either lies or reveals passages from a distance. |
| D-T5 | Cutover policy: one global switch and one cutover, versus adopting screens one at a time | One global cutover | Prevents a shipped game with two visual grammars. The cost is a longer interval before players see improvements. |
| D-T6 | Sequencing: presentation foundations ahead of S26b, S30b, S33b, S29b and S31, while backend work continues in parallel | Yes | Those slices' acceptance depends on the new presentation; finishing them first would be re-done. |
| D-T7 | Commission a canon city plan (district positions, tram lines) at gazetteer level for the City Map | Yes, presentation lead proposes, you approve | No plan-view geography exists in canon; a map cannot be drawn without it. |
| D-T8 | Disguised NPCs: give the plainclothes Warden a presented class distinct from its true faction | Yes, and fix it in P4 | Today its name and colour disclose it, which contradicts the gazetteer's intent. |
| D1 | Charted public geography | Engineering: feasible; masks hidden-exit corridors and private interiors; moves the fingerprint for flagged zones only | Changes `03-terminal-ui.md` §2. |
| D2 | Known space dimmed per tier | Engineering: client-only | Changes `03-terminal-ui.md` §2. |
| D3 | Place layer in content | Engineering: as a separate record type, validated by tile class | `04-assets.md`, `01-entities.md`. |
| D4 | Backgrounds, frame by safety, safe colour Warden blue | Engineering: client-only; see §11 note on walls | `03-terminal-ui.md` §1, 2, 8. |
| D5 | Log kinds, place lines, ambient rules | Engineering: needs one emitter and a derived RNG (P4, P8) | `03-terminal-ui.md`, S27. |
| D6 | Glyph additions | Engineering: rendered-cell CP437 check before adoption | `glyphs.json`. |
| D7 | Lattice linework | Engineering: renderer replaced, view extended, 179 labels | `03-terminal-ui.md` §3. |
| D8 | Layout tiers and art prominence, by playtest | Engineering: needs P2's layout tiers; PT1 | S33, S30. |

## 10. Review and acceptance process

### 10.1 PR classes and gates

| Class | Examples | Required before merge |
|---|---|---|
| A. Rule or engine | S25a, S26a, S27 backend | pytest; slice acceptance script; automated review; technical lead for cross-subsystem effects; owner merge |
| B. View contract | P3, P4 | A, plus the disclosure checklist; fingerprint unchanged except named additions |
| C. Player-visible presentation | P5 to P8, C1 | B, plus style goldens, frame budgets, real-terminal script at both sizes and two tiers, presentation lead creative sign-off, the named human gate if any |
| D. Geometry | S25c, hub geometry | C, plus approved fingerprint rebaseline, re-run coordinate-bound receipts, per-zone human gate |
| E. Canon and spec | P0, decisions | Owner approval; propagated top-down in the same PR |

### 10.2 Checklist for every PR

1. **Spec currency.** Cites the current authoritative sections; no
   requirement taken from a superseded document or an agent's memory.
2. **Canon.** No rule, number or canon changed unless the PR changes the
   top document first.
3. **Fingerprint.** Unchanged, or the rebaseline names zones, reason and
   approval.
4. **Disclosure.** For every new or changed view field: can it reveal
   unseen geometry, hidden exits, private interiors, disguised identity,
   standing, unvisited zones or another player's state? Tested.
5. **One mechanism.** No second copy of layout geometry, focus
   resolution, log emission, palette lookup or ambient scheduling.
6. **Determinism.** No new draw on `zone.rng` for presentation; seeds
   derived; no wall-clock reads in logic.
7. **Budgets.** Frame and delta sizes within the slice's budget.
8. **Width safety.** Every new string through the cell buffer; wide
   handle in tests.
9. **Both renderers** (until P10): old renderer unaffected; new renderer
   consistent across every view kind it touches.
10. **Evidence honesty.** The PR says which acceptance it claims and
    which it does not; engineering results are never presented as
    visual approval.

### 10.3 Human acceptance

The proposal's §11 criteria are the basis, run through a real NetBBS
node at 80x24 and 132x50, in 256 and 16 colours, with a wide-character
handle, by a reviewer who has not read the design. H1 applies criteria
1 to 7 to Meridian Plaza, Clinic Row, Sodium Row and the Vatside sector.
H2 and H3 add, per district: the reviewer names the district from an
uncaptioned frame, finds the landmarks the gazetteer names, and walks
from arrival to each exit without opening a menu. H4 applies all ten
criteria to the whole city, including the deutan, protan and transport
checks. Each gate records the reviewer, date, commit, terminal and
transport. No automated result substitutes for a gate.

## 11. Notes for the presentation lead

Coordination through committed documents, not conversation. These are
engineering observations on the proposal and the trial code, for
discussion; none overrides a design decision.

1. **Committed.** Resolved by #69 and #70. The trial code should still
   land through P2 to P6 in reviewed pieces rather than by merging the
   design PRs.
2. **Walls as blank background cells** (256 and truecolor tiers) express
   opacity by colour alone. That conflicts with "shape is the rule" and
   with `03-terminal-ui.md` §8. A shaped wall with signage letters
   overriding only signed cells would keep both.
3. **F9 trial key** collides with UI spec §4 (F9 opens services at a
   public terminal). F5 and F6 are free today.
4. **Ambient emitter** in the trial runs inside the simulation tick and
   is seeded from the session id. Under P8 it would be one emitter shared
   with S27 barks, seeded per zone instance, with session state removed
   on detach. The trial's `Toast.full` field is undeclared.
5. **Fingerprint and charted terrain** cannot both be absolute: D1 moves
   `tiles` and `remembered` for charted zones. P1 provides the explicit
   rebaseline path; the proposal's "hashes never move" rule should say
   so.
6. **Mockup provenance.** `build.py` places the character with a teleport
   in places, and sets the local handle to `Kale_9` while the server-side
   hello keeps `Wide界`. P6's acceptance reproduces the frames from live
   play through NetBBS.
7. **Charted disclosure.** Charted terrain must exclude the corridors
   behind S25's three hidden exits and housing interiors; the trial
   already excludes hidden-exit tiles but not the space behind them.
8. **Tile classes.** The trial validator names `wall`, `floor` and
   `water`; S25 adds `convoy-road` and `gantry-hazard`. Validating by
   class (opaque, passable, water, hazard) keeps the place layer correct
   as tiles are added.
9. **`walk_to` and charted ground.** `next_step` treats every in-bounds
   template tile of a charted zone as known, so a walk can route through
   space the player has never seen, including any passable tile behind a
   hidden exit. A walk also steps through `interact(street=True)` on
   every tile, so a path crossing an exit tile could start travel. Route
   over the same disclosed set the view sends, and refuse exit tiles
   other than the goal. *Fixed in #70 `136051c`* for hidden-exit tiles
   and exit tiles. Corridors behind hidden exits remain charted until
   note 7 is resolved.
10. **Session state.** `walks` and `deep_views` are never cleared when a
    session leaves (the same issue as the ambient state in note 4), and
    `view_shape` is handled before the caller-role check, so a watcher
    can change it. *Fixed in #70 `136051c`.*
11. **Deep camera.** It passes `old=None`, which turns off camera
    hysteresis, so the viewport recentres on every step and deltas grow.
    It also adds a third branch to the camera formula that the door must
    mirror (obstacle 3.4); under P2 it becomes a named layout shape.
    *Deferred to P2 by agreement.*
12. **The decider is an information channel.** Auto switches to
    TACTICAL on `nearby.relation == "!"`, hazards and targets. If the
    server ever marks a disguised NPC as hostile before the player could
    know, the view switch discloses it. The threat signal should be one
    server-declared field covered by a disclosure test (P4), not a
    door-side inference. *Agreed; deferred to P4.*

## 12. Planning for the Auto direction

After playing the prototypes on 2026-10-25, the owner prefers Auto
(#70, prototype C) as the player-experience direction. It is a direction
for planning, not acceptance. The interaction rules and their timings
remain open, so this plan prepares for Auto without freezing it.

### 12.1 Principles the presentation lead is building into #70

`paradigms.md` §5 now states them as A1 to A6 (#70 `136051c`). The main
refinement: the movement mode decides the view (arrow steps → map,
choosing a way → scene), and ground only sets where a zone starts.

1. Danger switches to the tactical map immediately.
2. No oscillation: escalate fast, calm down slowly.
3. Intent is read from what the player does, not from geography alone.
4. An escape hatch that never fights the player.
5. Keys keep one meaning in every view: arrows always step, and choosing
   a destination uses only keys the scene owns.
6. In development, the decider's reasoning is inspectable (overlay and
   trace file).

### 12.2 What changes in this plan

Auto strengthens the foundations rather than replacing them. Every Auto
view still draws inside one layout, through shared chrome, with a truthful
E prompt, so P1 to P5 stay in place and in order.

| Slice | Change |
|---|---|
| P1 | Adds a decider trace format and a replay test: a recorded view sequence must produce the same view choices. Principle 6 becomes verifiable rather than a debug aid. Starting point: #70's JSONL trace (`BLACKSITE_AUTO_TRACE`, one record per change: `at, t, from, to, view, looking, rule, why, zone, pos, inputs`). |
| P2 | The layout module gains named view shapes (map, scene, look). The deep camera becomes one of them, and the server and door read the same definition. |
| P3 | Extends from the E focus resolver to the key contract. Principle 5 is tested: across every view, each movement key maps to the same intent. #70's current proposal: arrows step, Enter talks, and `,` `.` Space choose ways. |
| P4 | Adds a server-declared `threat` state and reason, with a disclosure test. The decider reads only that field, never door-side inference (§11 note 12). It also adds `places`, `here` and known exits, routed over the disclosed set (§11 note 9). |
| P5 | Adds the context decider as a pure door module (`door/present/context.py` today), driven by view bodies and a clock, behind the single client switch. |
| new W1 | Server travel over known ground (`walk_to`), only if the owner accepts S1. It covers the routing set, exit tiles, cooldown parity, cancel on any input, and session cleanup. Owner: Codex; review: technical lead. |
| new V1 | Street-view looks as an optional view. They must meet P1's frame budgets at 132x50 and degrade at 16 colours under S2. |
| C1, S25c, S27, S33 | Places become content per zone (S5). Whether place names are gazetteer canon or presentation decides which slice writes them and which review applies. |
| PT1 | The D8 playtest also tunes Auto: hold time, look duration and boundary behaviour. |

None of these slices is filed or started before D-T1.

### 12.3 What stays open

- S1 to S6 in `paradigms.md` are the presentation lead's to put to the
  owner. Engineering consequences:
  - **S1 `walk_to`:** a new server-driven mechanic and a scripting
    surface, so it needs its own slice (W1) and a rule in game design.
  - **S2 deep camera:** within `MAX_VIEW_CELLS`, but it moves the budget
    test baseline and the UI §2 camera rule.
  - **S4 server facing:** a rule change, and a fingerprint rebaseline if
    adopted.
  - **S6 key meaning:** principle 5 already answers it; the canon update
    is UI §5.
- Collision with S25: #69 and #70 touch `zone_view.py`, `schema.py`,
  `validate.py`, `loader.py` and `palette.json`, which S25 also changes.
  Neither design PR should merge. Their code lands through P-slices,
  rebased after S25a (D-T2).
- Canon: Auto changes `03-terminal-ui.md` §2 (camera), §4 (view kinds)
  and §5 (keys). That canon edit belongs in P0 once the owner accepts the
  direction, top-down and in the same PR as the first slice that depends
  on it.
