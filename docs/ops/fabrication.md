# Salvage and fabrication

S17 implements game design 8.4. The current ten-zone hub has no live
Scour ring or ordinary workshop. Do not add a placeholder Scour map to
an installation. S25 owns real placements, routes and geography checks.

At a commissioned salvage node, E starts repeated 2-second harvests.
Movement, damage, going down, logout or Esc/B interrupts. Each completed
unit stays in inventory; incomplete units stay in the node. Node units
and inventory transfer in one SQLite transaction. Ring generation uses
persisted per-zone randomness and uptime, so downtime cannot generate a
free harvest or reroll a partly harvested node.

Buy or find a physical schematic, then use it from inventory with U.
Learning consumes that physical copy and persists its recipe in the
character journal. A duplicate stays with you. An explicitly single-use
schematic instead adds one recipe charge; current catalog recipes are
all permanent.

Existing learned journal recipes remain available after upgrading.

E opens a workshop. It shows learned recipes, carried/required salvage,
skill minimums and quality range. F starts a 3-second craft. Esc/B
leaves without starting work. Inputs, output, recipe charge (if any),
Fabrication use, XP and RNG state commit together on completion. A
failed save or interrupted craft consumes nothing. Bound service-order
salvage cannot be consumed by fabrication. Learned programs cannot be
fabricated repeatedly.

Each template declares its quality policy. Inventory and installed-item
details show the effective numeric values. A quality-1 item retains all
catalog values; only the selected magnitude changes. Permissions,
tolerance, slot counts, stack sizes and durations remain fixed. Ammo
recipes create a full pack; program recipes teach their output. Neither
rolls quality. Landing buys ordinary hull at 18 chits per unit. Intact
salvage cannot be bought or sold at NPC counters; player trade remains
an owning slice's responsibility.

For the real NetBBS engine acceptance, run `scripts/accept_s17_netbbs.py`
with the NetBBS venv interpreter, `--door-python` pointing at Blacksite's
interpreter, a fresh private `--root`, and `--show` in a real terminal.
It uses the actual NetBBS picker, Telnet and native stdio door, at 80x24
and 132x50 with wide names and 16 colours. It records ANSI/text captures
and `s17-results.json`. Its funding, node and temporary Wake-map service
objects are explicitly labelled fixtures. There is no clock shortcut.
This proof does not satisfy S25's real Scour/Landing/Old Works walks.

## Recorded S17 acceptance

The native probe passed both sizes on the local NetBBS checkout
`d04170aa998b459b9f5ca6b9bca9ea63a17f7ab9`. The labelled fixture run
recorded qualities 0.852145 at 80x24 and 0.878598 at 132x50 (samples,
not fixed balance values). Both terminal captures display the actual
quality-adjusted wrench damage. Each run harvested three hull units,
bought and learned the catalog schematic, completed a real 3-second
craft, sold one remaining hull for 18 chits, refused caller B at the
restricted workshop, and returned both callers through the real picker.
There is no clock fixture and no claim of actual future-map acceptance.
