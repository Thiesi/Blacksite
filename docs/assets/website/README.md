# Website screens

Three mockups of Blacksite at its highest fidelity: a 132x50 terminal in
truecolor with Unicode glyphs, rendered at 2112x1600 (16x32 pixels per
cell). Together they tell one evening in Sodium Row: the street, the bar
you sit down in, and the Lattice you go down into from its chair.

They are mockups of the target presentation (issue #68), not captures of
the shipped game. Each follows canon (terminal UI sections 2 and 3, the
Lattice world doc), but some of what they show is planned work.

| File | Screen | Alt text |
|---|---|---|
| `sodium-row-night-132x50-truecolor.png` | The street map | A night street in a text terminal: amber lamp pools and pink, teal and violet neon spill across wet pavement, a crowd of people drawn as glyphs, neon signs over six doorways, a side panel targeting a hostile player, and a message log. |
| `tin-halo-scene-132x50-truecolor.png` | A place's scene view | Inside a bar called the Tin Halo: a pixel-painted view under a halo of tin cans, three screens and a red back-room door, with a list of ways through the room, a minimap, and the people nearby. |
| `lattice-sodium-row-132x50-truecolor.png` | The Lattice | The city's network as amber linework on black: cells, gated and hidden links, two cores drawn as small buildings, a descent marked with an infinity sign, runners as diamonds, and a side panel with integrity, trace and seven loaded programs. |

Suggested captions:

- **Sodium Row, 23:41.** Orange lamps, wet pavement, music from six
  doorways at once. Contested ground: player fights are on here.
- **The Tin Halo.** Places you can enter open into a painted scene. Work
  in Sodium Row comes through Vesper, or it does not come.
- **Going down.** The Lattice is the grid the old engineers laid under
  the streets. Your body stays in the chair upstairs.

## What is real and what is planned

- **Sodium Row:** the map, objects, stalls, signs, floor marks and frame
  come from the engine and P6b's place content (#126). The lamp light,
  neon spill and wet pavement are the lit layer (V1, issue #68), which
  is planned. The crowd, side panel and log are placed by hand in their
  real palette roles and canon glyphs. The fixed map origin is A7 (#115).
- **The Tin Halo:** the #68 visual target, updated to the P5 chrome
  canon. The painted scene view (V3) is planned.
- **The Lattice:** hand-composed to terminal UI section 3 and the Sodium
  Row sector in the Lattice world doc. The shipped Lattice view uses the
  same layout with plainer rendering.

The soft glow around lights is a presentation effect for the website; a
terminal draws the same cells without it.

## Regenerating

Needs Pillow and a monospace font (Consolas or DejaVu Sans Mono, or set
`MOCKUP_FONT`). From the repository root:

    python scripts/presentation_mockups/website/tin_halo_final.py
    python scripts/presentation_mockups/website/lattice_mock.py

The street needs P6b's place content (#126) in the tree, because it
renders a real engine frame first:

    python scripts/presentation_mockups/website/street_frame.py 52 17 1500 tab
    python scripts/presentation_mockups/website/street_light.py
