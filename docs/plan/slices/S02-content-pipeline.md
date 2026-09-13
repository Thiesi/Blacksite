# S02 — Content formats, loaders, validator, test fixture world

**Status:** planned
**Primary model:** Opus · **Reviewer:** Sonnet (test coverage)
**Depends on:** S01 · **Milestone:** M0
**Issue:** https://github.com/Thiesi/blacksite/issues/2

## Goal

Define the on-disk content formats from `01-entities.md` §1 as typed
dataclasses with loaders, write the validator that enforces the
invariants in `01-entities.md` §5, and ship a small fixture world that
every later engine test uses. After this slice, adding a zone, item, or
ICE class is a data change that either loads or fails loudly with a
file and line.

## Spec references

- `docs/design/01-entities.md` §1 (content entities), §5 (invariants).
- `docs/design/02-architecture.md` §2.4 (install dir, `content.local/`
  override), §6.3 (loading, hot reload of empty zones).
- `docs/design/03-terminal-ui.md` §1 (glyph set, palette roles).
- `docs/design/04-assets.md` §2 (data tables), §3 (map authoring rules),
  §7 (fixture world), §8 (naming).
- `docs/world/01-gazetteer.md` sketch legend (map glyph conventions).

## Scope

- `src/blacksite/content/schema.py`: frozen dataclasses for `Zone`,
  `TileType`, `Exit`, `Spawner`, `ObjectSpec`, `Region`, `Sector`,
  `Cell`, `Core`, `Room`, `DataSpec`, `ControlSpec`, `IceTemplate`,
  `ProgramTemplate`, `ItemTemplate` (with per-class blocks), `NpcTemplate`,
  `Faction`, `ContractTemplate`, `DialogueNode`, `EventTemplate`,
  `SeasonDefinition`, `TextAsset`, `ArtAsset`, all with `schema: int`.
- `src/blacksite/content/formats.py`: the `.map` grid format (UTF-8 text,
  one row per line, glyph → tile id via `tiles.json`, trailing whitespace
  significant) and the JSON sidecar; readers for `tiles.json`,
  `glyphs.json`, `palette.json`, `keymaps.json`, `factions.json`,
  `items.json`, `programs.json`, `ice.json`, `npcs.json`,
  `contracts.json`, `events.json`, `vendors.json`, `hymns.json`,
  `seasons/<n>.json`, `sectors/<id>.json`, `cores/<id>.json`,
  `zones/<id>.map` + `.json`, `dialogue/<npc>.json`, `text/<id>.md|.txt`,
  `art/<id>.ans` + `.json`.
- `src/blacksite/content/loader.py`: `load_content(root: Path, local:
  Path | None) -> ContentTree`, applying `content.local/` overrides by
  ID, computing a content hash (SHA-256 over sorted file bytes) exposed
  as `ContentTree.hash`.
- `src/blacksite/content/validate.py`: `validate(tree) -> list[Problem]`
  where `Problem(path, line | None, message)`; enforces every invariant
  in `01-entities.md` §5 that is content-only: exits resolve to existing
  zones and passable tiles; every core control resolves to a zone object;
  every core hardware tile is a `hardware` object; every referenced text
  and art asset exists; relations defined for every faction pair and
  asymmetries match `factions.json`'s declared list; zone sizes within
  40–200 × 20–100; spawner regions non-empty; every object on a passable
  tile; every glyph in `glyphs.json`; every palette role has all three
  tiers and all three variants; item IDs unique across classes; map
  rows equal width. The Shaft Head/Shaft Foot shared-core case
  (gazetteer) is allowed only when the core declares `hardware` as a
  list of exactly two locations.
- `src/blacksite/content/ids.py`: slug validation (`^[a-z0-9]+(-[a-z0-9]+)*$`
  for content, catalog-style `^[a-z]+_[a-z0-9_]+$` accepted for item,
  program, ICE, hymn IDs as the catalog uses them).
- Shipped starter data (real, minimal): `tiles.json` with the gazetteer
  legend tiles (wall, floor, cover1–3, door, locked door, terminal,
  relay, exit, water, hazard, vendor anchor, vat, light, hardware),
  `glyphs.json` and `palette.json` per `03-terminal-ui.md` §1 (3 tiers ×
  3 variants, every role listed in that section), `keymaps.json` with
  the two keymaps from §5.1.
- Fixture world `tests/fixtures/world/`: three zones (`fx-safe` 40×20
  safe, `fx-street` 60×24 contested with a pocket, `fx-open` 40×20
  open), one sector `fx-sector` with five cells, two cores (`fx-core-a`
  tier 1 with one control mapped to a door in `fx-street`, `fx-core-b`
  tier 2), two factions with one declared asymmetry, four items (starter
  sidearm, ammo, coverall, patch by their catalog IDs), two ICE, three
  programs, two NPC templates, one contract template, one event, one
  text asset, one art asset.
- `blacksite admin validate --content DIR` stub wired in S05; here only
  the function and a `python -m blacksite.content.validate DIR` entry.

## Out of scope

- Loading persistent state (S03).
- Hot reload behaviour at runtime (S03/S28 use the loader).
- Real zone maps beyond the fixture (S06, S08, S25).
- Item, ICE, NPC, contract, event content conversion (owning slices).

## Data and content

Everything under `src/blacksite/content/` listed above, plus the
fixture tree. Directory names and file names follow `04-assets.md` §8.

## Protocol and view models

None.

## Tests

- `tests/content/test_map_format.py::test_round_trip_grid`,
  `::test_ragged_rows_rejected`, `::test_unknown_glyph_reported_with_line`.
- `tests/content/test_loader.py::test_fixture_loads`,
  `::test_local_override_wins_by_id`, `::test_hash_stable_across_order`.
- `tests/content/test_validate.py::test_exit_to_missing_zone`,
  `::test_exit_onto_wall`, `::test_control_to_missing_object`,
  `::test_hardware_tile_must_be_hardware_object`,
  `::test_missing_text_asset`, `::test_relations_complete`,
  `::test_relations_asymmetry_must_be_declared`,
  `::test_zone_size_limits`, `::test_palette_roles_complete`,
  `::test_shared_hardware_only_when_declared`.
- `tests/content/test_ids.py::test_slug_rules`.
- `tests/content/test_shipped_tree.py::test_shipped_content_validates` —
  runs the validator over `src/blacksite/content/` and asserts zero
  problems (grows with every content slice).

## Acceptance script

1. `python -m blacksite.content.validate tests/fixtures/world` → "ok,
   3 zones, 1 sector, 2 cores, hash …".
2. Edit `fx-street.json` to point an exit at `nowhere`; rerun → one
   problem naming the file and the exit.
3. `pytest -q tests/content` green.

## Definition of done

- Roadmap §7 holds.
- `01-entities.md` §1 updated if a field had to be added or renamed, in
  the same PR.
- `04-assets.md` §7 lists the fixture world as it exists.

## Implementer notes

- Map files are UTF-8; glyphs in the map are single code points from
  `glyphs.json` and must be width 1. The validator measures with the
  same East Asian width rule the client will use (`unicodedata.
  east_asian_width in ("W", "F")` → 2); reject wide glyphs in maps.
- Content is read by the server only; the client receives view models.
  Do not import the loader from `blacksite.door`.
- Keep loaders pure (no logging, no globals) so S03 can reload zones in
  a background task.
- Windows: open files with explicit `encoding="utf-8"`, `newline=""`
  for maps.

## Lore review integration

Include entity model 2.12-2.15 and architecture 15's closed contracts:
evidence/receipts, permits, branch groups, service nodes, expedition
checkpoints, individual ballots, committed event plans and compatible
ICE variants. Validate item/program ID conventions separately from
hyphenated zone IDs. The program roster has 35 entries, no aliases.

Bundles explicitly declare active/authoring status and dependencies.
Every active reference must resolve; incomplete future content cannot
produce offers, exits or finale choices. The fixture is a complete small
bundle, not an excuse to accept dangling references in the release tree.
Add route validation across every service/event/control variant, safe
hazard rejection, unique branch/ballot keys, training-tier exception and
both required-voice lines. Numeric fixtures source main design 17/18.
