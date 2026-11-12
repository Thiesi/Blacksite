# S44 engineering evidence

Slice: [`S44-row-rules.md`](../../../plan/slices/S44-row-rules.md), issue
#207, PRs #214 (parts 1–4) and #215 (parts 5–6). This packet does not
grant presentation acceptance, H1 or S25 layout approval.

## Native packet

[Manifest](native/manifest.json) and the four `results-*.json` files hold
108 live captures from S44 acceptance
[run 43189288477](https://github.com/Thiesi/Karst41/actions/runs/43189288477),
at source head `2ab65d9`. Transport: NetBBS v7.45.0 over Telnet to a
registered native stdio door, from an isolated installed wheel. Script
`scripts/accept_s44_netbbs.py`; workflow
`.github/workflows/s44-acceptance.yml`.

The run has four jobs: 80x24 and 132x50, each in the default renderer
(`legacy`) and the opt-in presentation (`present`, the workflow's
`modern`). Each job runs every scenario in all three tiers (16, 256,
truecolor), so every scenario has 12 captures.

| Capture | What it shows |
|---|---|
| `price-arrival` | First arrival on the Row. The notice "Fire: Sable comes, no Halo. At a player: Marked 15m, no work." on the hint row (presentation) or the separator (default). |
| `price-target` | TARGET on a regular shows "Truce: Sable answers". Beside it is the first-target notice "Fire here and Sable comes. No Halo." |
| `hunted-pursuit` | After a shot at the regular: "Sable is coming for you.", `HUNTED` in the header, and a guard in pursuit within ten tiles. |
| `bar-pursuit-in` | The player inside Upstairs; the guard followed through the doorway and is inside with them. |
| `bar-pursuit-out` | The player out on the street; the guard followed out. Its recorded trail passes the doorway (in the results). |
| `halo-refused` | E at the Halo's door: 'The bouncer doesn't move. "Sable's still asking about you. Try me in 5 min."' The player stays on the Row. |
| `settled` | After a death by the keeper's guards and the decant, the log reads "You wake in the vat. …" then "Sable considers it settled." |
| `enforcer-talk` | A fresh character opens a Sable enforcer's page: its line, `a  Ask about the peace` and `Esc/B  Leave`. |
| `enforcer-ask` | After `a`: the question as the caller's speech and the enforcer's answer, word for word. |

The `.txt` files are byte copies of the captured screens. The raw `.ans`
streams and JSON style snapshots stay in the four CI artifacts named in the
manifest. Every `.txt`, `.ans` and `.json` SHA-256 in the results was
checked against the downloaded artifact files before copying.

In the 256-colour and truecolor presentation captures, walls are drawn as
background-coloured blank cells (P6), so the bar's walls show as spaces in
the `.txt`. The doorway's two floor cells are visible in its bottom row,
and the colour is in the `.ans` and `.json` files. The 16-colour and
default-renderer captures draw walls as `█`.

## Fixtures (declared)

- **The bar is a test fixture.** Main's Row is open ground with no bar
  alcoves. The walls of Upstairs (x 6–20, y 4–8, doorway at (13, 8) and
  (14, 8)) are copied from `tests/npcs/fixtures/issue187-row-demo.map` (the
  #187 diagnosis map, round 3 demo geometry). They go onto the live Row as a
  geometry layer in the acceptance server only, never into shipped content
  or the wheel. The coordinates of every injected wall are in
  `fixture_walls` in each results file. The technical lead ruled on this
  (#214).
- Grade 5 for the player-vs-player rules (S38 precedent).
- **The guards hold fire until the death scene.** The keeper's guards,
  including any that spawn meanwhile, hold fire (their weapon cooldown is
  pushed out). This lets the bar, the Halo's door and the walk be filmed
  before the player dies. Fire is released for the death.
- **One pursuer in the bar scene.** The other guard leaves the world, and
  its spawner slot waits until the death scene. A guard that holds fire
  stands still while it sees you, so two inside can box the doorway.
- **The bar capture follows the #187 shape.** The player is first seen
  behind the doorway at (13, 6), then steps out of that line to (8, 6). The
  guard routes in to where it last saw them. Per canon, a guard that never
  saw you inside goes to where it lost you, then gives up after 20 s; it
  does not search.
- The death happens in sight of the guards' posts, away from the Halo's
  door, because a loot cache beside an exit takes E before the exit (S48,
  #211). The Ask is put to a guard standing at its post. A guard walking
  home leaves reach and closes the page by itself (S42).

## History

The script's earlier runs, from #215's first head `9d28bdb` to `2175981`, failed on the
script's own timing and staging, each in a later scene than the one
before. None of them was a product failure; each fix is its own commit on
#215:

- the trail was sampled after the walk;
- the death cache stood beside the door;
- the guard never saw the player inside;
- a respawned guard took up the answer mid-scene;
- the Ask page closed as the guard walked home;
- the guard moved before E.
