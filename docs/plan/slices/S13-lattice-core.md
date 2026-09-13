# S13 — Lattice: sectors, cells, jack in/out, presences, LatticeView, sector layouts

**Status:** planned
**Primary model:** Opus · **Reviewer:** Astra (spec critique of the hacking model before start, per roadmap §4)
**Depends on:** S07, S08, S12 · **Milestone:** M2
**Issue:** https://github.com/Thiesi/blacksite/issues/13

## Goal

Build the second layer of the world without its teeth: sectors as cell
graphs, jacking in at terminals or via a rig, presences that move
between cells, other runners visible in the same cell, the helpless meat
body upstairs, and the Lattice renderer. After this slice two callers
can jack in at Core terminals, meet in a cell, and jack out; ICE, cores,
and trace are S14.

## Spec references

- `docs/design/00-game-design.md` §6.1 (cells, move time 1.0 s −
  Cortex / 100 s, integrity 100, trace meter exists but does not rise
  here), §5.2 (jacked-in body helpless), §2 (session shape).
- `docs/design/01-entities.md` §1.3 (sector), §3.3 (presence), §3.6
  (session subscription: zone or sector), §5 (a player is in one zone
  instance or one sector, never both).
- `docs/design/02-architecture.md` §5.4 `LatticeView`, §6.1 (sectors
  are active only with a presence or timer).
- `docs/design/03-terminal-ui.md` §3 (Lattice view, cell glyphs, edge
  kinds, side panel), §5.1 (`J` jack, program keys 1–7 reserved).
- `docs/world/03-lattice.md` §1 (experience), §2 (sector table: cell
  counts, public/gated/hidden mix, notable cells, descent cells, uplink
  cells), §6.1 (descent exists; generation is S14).
- `docs/world/01-gazetteer.md`: terminal objects per zone.

## Scope

- `server/lattice/sectors.py`: load `content/sectors/<id>.json` for the
  11 sectors (Spire, Core, Vatside, Tramyard, Sink, Chapel Ward, Old
  Works, Terraces, Sodium Row, Undercity, Scour) with the cell counts and
  public/gated/hidden mix from `03-lattice.md` §2, each cell with a
  precomputed layout position (content, not runtime), `kind`,
  `neighbours`, `requirement` for gated cells (key item, program class
  tier, faction, standing), `label`, optional `core_id` (resolved in
  S14; the loader accepts the field and validates it against S14's core
  files when present), and one `descent` cell per sector.
- Uplink cells between sectors (gated) per §2; public Scour uplinks are
  always present; S21 adds optional ownership shortcuts.
- `server/lattice/presence.py`: `Presence` per `01-entities.md` §3.3
  with integrity 100, trace 0, rig slots from the player's rig (native
  for Ghosts; a rig implant or a carried portable rig otherwise, S16
  decides which; here: Ghost native, carried rig, or a three-slot public-terminal loan),
  cell, move timer (max(0.2, 1.0 - Cortex/100) s, tick-rounded), `visible_to`.
- Jack in: at a `terminal` object (adjacent + `E` or `J`) or anywhere
  with a rig implant (`J`). The meat actor gets stance `jacked`
  (helpless: cannot move, act, or evade; attacks on it use evasion 0;
  S10 integrates the damage path). Jack out: `J` from any public cell,
  instant; from a gated or core cell, 2 s cast (S14 adds forced
  jack-out). Integrity recovers 5 per second after jack-out.
- Movement between cells: intents `lat.move <cell>` (adjacent only),
  arrow keys move along the edge nearest that direction in the layout;
  gated cells check requirement; hidden cells are unknown until found
  (Listening check is S16's skill line; Lantern is S14; a Choir Surge is
  S24; here: hidden cells are reachable only via a debug admin command
  and never rendered until `found_cells` contains them).
- Presences in the same cell see each other (name, faction colour,
  relation); crews see each other's cell across the sector (S22 owns
  crew; until then the relation is neutral).
- Session subscription switches from zone to sector on jack-in and back
  on jack-out; the zone keeps the meat actor and other players still see
  it with the `jacked` stance glyph.
- `door/views/lattice.py`: render `LatticeView` per `03-terminal-ui.md`
  §3: `(nn)` cells at layout positions scaled to the viewport, edges by
  kind (`─│/\`, double for gated, dotted for found-hidden), `[Cn]`
  placeholders for core entrances (coloured by owner in S14), reverse-
  video self marker, `♦` other presences with relation colour, side
  panel INTEGRITY / TRACE / RIG / ROOM (ROOM empty until S14).
- Jack-in and jack-out transition frames (3 frames, from `art/` when
  present, text fallback otherwise).
- Admin: `blacksite admin lattice who` lists presences by sector and
  cell.

## Out of scope

- Cores, rooms, ICE, programs, trace rise, forced jack-out, black ICE,
  Silt generation: S14.
- Controls and hardware, cut-power: S15.
- Relay-dependent uplink cells: S21.
- Listening skill, rig implants and tolerance: S16.
- Hidden-cell reveal by Choir Surge: S24.

## Data and content

- `content/sectors/*.json` for all 11 sectors with hand-placed layout
  positions (an author tool `scripts/layout_sector.py` that produces a
  first spring layout is allowed, but positions are committed as data).
- Fixture world gains one 6-cell sector with one gated and one hidden
  cell and two terminals in its zone.
- `content/text/lattice-jackin.md` (the §1 ritual text, shown on first
  jack-in per character).

## Protocol and view models

- `LatticeView.body`: `cells [{id, x, y, kind, label, known, core?}]`,
  `edges [{a, b, kind}]`, `presences [{id, cell, name?, role}]`, `me
  {cell, integrity, trace, rig [{slot, program?, cd}]}`, `room null`,
  `hint`.
- Intents: `lat.jack_in`, `lat.jack_out`, `lat.move`.
- Log lines: enter sector, cell entered (label), another runner arrives
  or leaves the cell, jack out.

## Tests

- `tests/test_sectors_content.py::test_eleven_sectors_load_with_counts_from_doc`
- `tests/test_sectors_content.py::test_exactly_one_descent_cell_per_sector`
- `tests/test_sectors_content.py::test_every_neighbour_symmetric`
- `tests/test_sectors_content.py::test_layout_positions_unique_and_in_bounds`
- `tests/test_presence.py::test_move_time_1s_minus_cortex_over_100`
- `tests/test_presence.py::test_gated_cell_requires_requirement`
- `tests/test_presence.py::test_hidden_cell_not_in_view_until_found`
- `tests/test_presence.py::test_jack_out_public_instant_gated_2s`
- `tests/test_presence.py::test_integrity_recovers_5_per_s_after_jack_out`
- `tests/test_presence.py::test_ghost_native_rig_three_slots`
- `tests/test_presence.py::test_non_ghost_needs_rig_item_secured_or_terminal`
- `tests/test_sim_multi.py::test_two_presences_same_cell_see_each_other`
- `tests/test_sim_multi.py::test_jacked_body_visible_helpless_in_zone`
- `tests/test_sim_multi.py::test_player_in_sector_not_in_zone_view_actors_list_as_mover`
- `tests/test_sim_multi.py::test_session_subscription_switches_on_jack`
- `tests/test_door_lattice.py::test_lattice_view_80x24_golden`
- `tests/test_door_lattice.py::test_lattice_view_132x50_golden`
- `tests/test_door_lattice.py::test_arrow_key_picks_nearest_edge`

## Acceptance script

1. Two callers on one NetBBS node at 80×24 stand in `core-plaza`.
2. Caller A presses `E` at a public terminal: the transition frames
   play, the Lattice view shows the Core sector with `(nn)` cells and A's
   marker at Plaza Exchange; the side panel shows INTEGRITY 100, TRACE 0,
   RIG with the shared starter programs Pick and Umbrella.
3. Caller B sees A's glyph change to the jacked stance in the zone and
   sees body safety. In this safe zone every attack is refused; repeat in
   an unsafe fixture to observe the helpless body's evasion of zero.
4. Caller B jacks in at the second terminal; both walk to the same cell
   and see each other's `♦` and name in the side panel.
5. A tries a gated cell without the key: a log line names the
   requirement; nothing else happens.
6. Both press `J`: instant jack-out from a public cell; zone view
   returns, integrity unchanged.

## Definition of done

Roadmap §7, plus: all 11 sectors render without overlap at 80×24 and
132×50, and the multi-session tests pass with deterministic ticks.

## Implementer notes

- The sector layout positions must be committed content; do not compute
  a spring layout at runtime, it will differ across restarts and break
  golden tests.
- `03-lattice.md` uses zone slugs that differ from the gazetteer in a
  few places (`spire-lobby`/`spire-upper` vs `spire-atrium`/
  `spire-shaft-head`, `tramyard-gates` vs `tramyard-wall-gate`,
  `sink-terrace-3` vs `sink-terraces`). The gazetteer is canonical for
  IDs; a reconciliation pass on the world docs is pending. Validate
  terminal-to-sector mappings against the gazetteer.
- The `jacked` stance must be a first-class stance in S06's actor model
  so S10 can treat it as evasion 0 without special-casing.
- Keep the presence's move timer on the sector's tick, not wall time.

## Lore review integration

Enforce exactly one physical body plus at most one Lattice presence.
Jacking never teleports the body. Every archetype can use public loan
terminals and later descend; native/portable rigs are advantages, not
story access gates. Required routes have visible alternatives. One Silt
entrance per sector is baseline; the Listening Post has its authored
extra route. S14 adds explicit survey/sample actions, not random repeated
Listening rolls. Public jack-out is immediate; other escape channels
have design 6.1's bounded interruption, always shown in the view.
