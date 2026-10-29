# P2 geometry and chrome verification

`blacksite.layout` owns the current layout tier. The door compatibility
module re-exports its types and computation. The camera crops the shared
viewport to the world and snapshot budget; it does not repeat terminal
geometry. No protocol field, world data or presentation tier is added.

The module names the frame, header, viewport, side, divider, separator,
log, hint, text area and menu overlay. It also owns existing menu list,
detail and action rectangles, cursor page distance, and server wrapping
and page policies. Page policies are distinct from drawable rectangles:
P2 preserves their existing padding and counts, including differences
between server page lengths and available text rows. Changing those
policies belongs to a later presentation slice.

Converted server sites are the camera, both Wake briefing paths, Wake
menu details, City Map text pages, contract detail pages, encounter text
and private-core logs. Additional client copies are menu list/detail
geometry, menu cursor page distance, help/scrollback sizes, view headers
and both side-panel offsets. The chrome module draws the frame, view
header/menu shell, log, hint, toast, hit flash and prompt cursor. Content
renderers receive `Layout` and draw inside its content rectangles.

The narrow-width guard requested in S25b's technical record rejects log
widths below four cells before wrapping. Two cells remain for a whole
wide glyph after the existing two-cell continuation indent. Ordinary
layout widths are at least 53, so supported output does not change.

## Checks

Run from this worktree with its `src` and repository root on `PYTHONPATH`:

```sh
pytest -q
python scripts/presentation_packet.py --output /tmp/p2-packet --strict-cp437
```

Choose a fresh packet directory. Do not use `--update-goldens`: every
glyph/style baseline and `tests/presentation/mechanics.json` must remain
byte-identical. A difference is a defect to fix.

`tests/presentation/test_geometry.py` preserves legacy boundary cases,
including the 100-column menu threshold and different page policies. Its
AST check scans every server module for arithmetic/branching on raw
terminal dimensions, following scalar aliases. It rejects a deliberately
added scratch copy. Forwarding sizes and comparing cache/version keys
remain valid. World-memory dimensions and the generic wrapper's already
resolved text width are not terminal-layout calculations.

Native acceptance uses the source-matched installed wheel through a real
NetBBS registered native stdio door, at 80x24 and 132x50 with wide names.
The full hosted native matrix and technical review remain required. No
human layout approval follows from unchanged output or engineering tests.
