# Items and banking (S12)

Press I in a zone to see inventory. Q/Enter equips in the default slot;
F lets you choose a compatible slot. E lists equipped slots; Enter there
unequips. S toggles a secured slot, D drops the selected stack, X splits
a stack, and U uses a consumable or learns a physical schematic. Esc/B
closes a menu without a transfer. See [fabrication](fabrication.md) for
learned recipes, workshops and per-template item quality.
Installed implants remain installed; surgery belongs to S16.

Walk next to a counter and press E. Enter buys one listed pack or sells
the selected carried stack. T switches buy/sell. Prices and gates come
from the server. Counters carry ammo for their weapons. Each counter has
its own 2 000-chit hourly resale budget; that budget never limits buying
essential supplies. Faction membership is supplied by S20, not claimed
by a client. Freelance pays list price regardless of recruiter standing.

The Wake Outfitter is in Wake Hall. Public clinic, showroom, precinct
and Tin Halo counters occupy their existing canonical hub zones. Their
menus label equipment whose combat, surgery, drone or other behaviour
is not implemented yet. Such a label does not promise that behaviour.

At a bank, choose deposit/withdraw and type a whole number. Esc cancels
the amount prompt. Banked chits stay separate from hand chits. Purchases,
sales, equipment changes, drops, pickups and bank transfers commit before
the caller sees success. A failed write leaves goods and balances intact.

Dropped goods form a public cache for five minutes, including across
service restart. Walk next to it and press E to pick up an item. Two
callers cannot obtain the same item. Bound supplies and story items
cannot be dropped or sold. The default three secured slots protect
items from S10's future corpse-cache rule; unsecure goods before a
voluntary drop or sale. Learned programs/schematics are journal state.

Med patches heal 25; rations restore 20 stamina; stims fill stamina and
add 10 shock. Consumable cooldowns are ten seconds per class. Trauma kits
channel for two seconds; moving, taking a hit or cancelling interrupts
the use. A cell charger refills a carried depleted cell, up to three
uses; neutralisers remove chemical effects; flare sticks provide sight
radius eight for three minutes in dark areas. S16 owns drug effects.
Unsupported tools state that they are not yet usable and remain carried.

Package 0.0.6 migrates world schema 2 to 3 without replacing players,
identities or items. Protocol major 1 and content schema 1 stay unchanged.
Keep the usual offline database backup before upgrading a live service.

## S25 handoff

The current world intentionally remains S08's ten-zone hub. Full catalog
data is present; future-zone vendors are in the authoring bundle
`s25-commerce`. They do not open remote or relocated counters. S25 must
activate their definitions, place their real objects and faction-hall
banks, and run the deferred Tramyard rifle-purchase acceptance at both
terminal sizes. The S25 spec, roadmap and issue #25 record this decision.
The content handoff test fails if a future zone ships without its vendor
activation/anchors or its required bank.

## Acceptance

Run with NetBBS v7.31.0's Python environment and the installed Blacksite
door interpreter, in a real terminal:

```powershell
NETBBS_PYTHON scripts/accept_s12_netbbs.py `
  --root .test-tmp/s12-proof --door-python .venv/Scripts/python.exe --show
```

The private world uses real walking and four new accounts, two per size
(80x24 and 132x50), with wide game names. It supplies no extra chits or
teleports. Each caller sells and replaces the starter sidearm, buys ammo,
equips, sells the baton, exchanges a dropped patch, walks to the tram-hub
bank, deposits 100 and cancels a withdrawal. The final hand balance is
19 and the bank balance is 100. It checks durable state and clean picker
return; result JSON and four ANSI captures remain under the private root.
