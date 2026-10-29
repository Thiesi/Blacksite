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
Run `scripts/accept_p2_netbbs.py --root /tmp/p2-native --door-python
/path/to/wheel/venv/python --show` with the NetBBS interpreter. It creates
ordinary wide-named characters and uses inventory page keys, help and
scrollback, preserving actual received ANSI/text/style captures. The
existing `scripts/accept_s04_netbbs.py` separately checks Telnet, SSH and
WebSocket at both sizes with its S04 service fixture.
The full hosted native matrix and technical review remain required. No
human layout approval follows from unchanged output or engineering tests.

## Recorded local receipt

[The evidence bundle](captures/p2-layout-geometry/README.md) records clean
head `0203051ea3f1b36cf1faf3ec5f985002325d9b4d`: root pytest 1,650 passed
and one skipped; strict packet 99/99; both wide-name native cases and all
six transport/size cases passed. All glyph/style goldens and mechanics
remain byte-identical to base `d0d2486`. An initial City Map variable
collision was fixed before this final gate; its failures are not waived.

The local node environment is observed as NetBBS 7.41.0, door API 5, from
a dirty checkout at `15f1605f80bb2235989f40accec3ab46f1cc3cae`. Its package
distribution metadata still says 3.0.0; the provenance distinguishes
that metadata from the application version. This is local compatibility
evidence. The clean hosted matrix pinned to NetBBS v7.31.0 remains the
independent minimum-version gate.
