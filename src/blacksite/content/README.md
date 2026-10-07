# Shipped content tree

Everything the game knows about Karst that is not engine code lives
here as data files. The server loads and validates this tree at start,
then the operator's `content.local/` tree, which wins on ID collision
(`docs/design/02-architecture.md` §2.4, §6.3). Adding content never
means adding an `if` to the engine.

This directory is installed as package data. On first start the
service runner (S05) copies it into the install directory so an
operator can read and override it.

Check a tree with:

```
python -m blacksite.content.validate DIR [--local DIR]
```

The record shapes are `docs/design/01-entities.md` §1 and
`schema.py`. The layout:

| Path | Entity | Arrives in |
|---|---|---|
| `tiles.json` | Tile types (map char, glyph, colour role, passable, cover, hazard) | S02 (shipped) |
| `glyphs.json`, `palette.json`, `keymaps.json` | Glyph registry, palettes, keymaps | S02 (shipped) |
| `zones/<id>.map` + `zones/<id>.json` | Zone grid and sidecar (exits, spawners, objects, pockets) | S06, S08, S25 |
| `sectors/<id>.json` | Lattice sectors and cells | S13 |
| `cores/<id>.json` | Cores, rooms, data, controls | S13, S15 |
| `ice.json`, `programs.json` | ICE and program templates | S14 |
| `items.json` | Item templates with per-class blocks | S12, S16, S17 |
| `vendors.json` | Vendor inventories | S12 |
| `hymns.json` | Cantor abilities | S10 |
| `npcs.json` | NPC templates | S11 |
| `factions.json` | Factions, relations, declared asymmetries, ranks | S20 |
| `contracts.json`, `evidence.json` | Contract templates, story chains, evidence records | S19 |
| `services.json` | Public service nodes and their allocations | S19 |
| `dialogue/<id>.json` | Talkers: lines, offers, barks | S27 |
| `events.json`, `routes.json` | World event templates and routes | S24 |
| `seasons/<n>.json` | Season definitions | S26 |
| `bundles/<id>.json` | Bundle manifests (active or authoring) | S19, S26 |
| `text/<id>.md` or `.txt` | Found texts, briefings, MOTDs | as needed |
| `art/<id>.ans` + `.json` sidecar | ANSI art blocks | S33 |

## Map legend

A `.map` is a UTF-8 grid, one row per line, every row the same width.
Trailing spaces are cells, not padding. Each character is a tile's
`char` from `tiles.json`:

```
#  wall              .  floor            ;  cover 1 (low)
%  cover 2           &  cover 3 (high)   +  door
=  locked door       T  Lattice terminal R  relay terminal
>  exit              ~  water            !  hazard
$  vendor anchor     V  clone vat        L  light
H  core hardware
```

Every file carries `"schema": 1` (`blacksite.version.CONTENT_SCHEMA`).
Text files must use LF line endings (`.gitattributes` enforces it); the
content hash covers every byte.
