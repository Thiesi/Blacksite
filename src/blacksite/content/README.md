# Shipped content tree

Everything the game knows about Karst that is not engine code lives
here as data files. The server loads and validates this tree at start,
then the operator's `content.local/` tree, which wins on ID collision
(`docs/design/02-architecture.md` §2.4, §6.3). Adding content never
means adding an `if` to the engine.

This directory is installed as package data. On first start the
service runner (S05) copies it into the install directory so an
operator can read and override it.

The intended layout, from `docs/design/01-entities.md` §1 and
`docs/design/04-assets.md` §2:

| Path | Entity | Arrives in |
|---|---|---|
| `zones/<id>.map` + `zones/<id>.json` | Zone grid and sidecar (exits, spawners, objects, pockets) | S02 fixtures, S06, S08, S25 |
| `tiles.json` | Tile types (glyph, colour, passable, cover, hazard) | S02, S06 |
| `glyphs.json`, `palette.json`, `keymaps.json` | Terminal glyphs, palettes, keymaps | S04 |
| `sectors/<id>.json` | Lattice sectors and cells | S13 |
| `cores/<id>.json` | Cores, rooms, data, controls | S13, S15 |
| `ice.json`, `programs.json` | ICE and program templates | S14 |
| `items.json` | Item templates with per-class blocks | S12, S16, S17 |
| `vendors.json` | Vendor inventories | S12 |
| `hymns.json` | Cantor abilities | S10 |
| `npcs.json` | NPC templates | S11 |
| `factions.json` | Factions, relations, ranks | S20 |
| `contracts.json` | Contract templates and story chains | S19 |
| `dialogue/<npc>.json` | Dialogue lines and offers | S27 |
| `events.json`, `routes.json` | World event templates and routes | S24 |
| `seasons/<n>.json` | Season definitions | S26 |
| `text/<id>.md` or `.txt` | Found texts, briefings, MOTDs, descriptions | as needed |
| `art/<id>.ans` + `.json` sidecar | ANSI art blocks | S33 |

Every file carries a `schema` integer (`blacksite.version.CONTENT_SCHEMA`).
Formats, loaders, and the validator are S02's job; until then this
directory holds only this file and the package marker.
