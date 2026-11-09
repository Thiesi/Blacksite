# Sodium Row, round 4

Demo branch: `demo/sodium-row-round4`. Never merge this branch to main.
Built from main b1502f7 and a normal merge of round 3, plus the three
proposals accepted on #185. H1/S25 approval is NOT GRANTED.

## Start and play

Use Python 3.12+ with this checkout's test dependencies installed. In
one console, from the round 4 checkout:

```text
python scripts/demo_sodium/serve.py --install-dir .test-tmp/demo-world
```

In another VT/UTF-8 console at 80x24 or 132x50:

```text
python scripts/demo_sodium/play.py --install-dir .test-tmp/demo-world --handle Demo
```

For another caller add `--user-id 2 --handle Peer`. For charted far signs,
add `--signs` to both commands. The optional color tiers are `--color 16`,
`--color 256` and `--color truecolor`. Posted residents replace the old
`--seated` toggle. Stop the server after the session; scratch belongs in
this fixed directory, not a fresh folder per run.

The launcher selects this checkout's source and installs the explicit
round 4 data overlay under the chosen install directory. It refuses to
overwrite unrelated local overrides. Use a dedicated demo install. The
shipped content, frozen mechanics and P3 baselines remain unchanged.

## What to try

- Equip a weapon. `d` draws or holsters in either keymap. In truce, the
  first `f` draws without spending ammunition or provoking an NPC. Wait
  two seconds before firing again. The own WEAPON row shows DRAWN; other
  callers show drawn in TARGET and NEARBY, without changing their stance.
- Draw near a Sable enforcer. One keeper watches the first visible
  drawer. Another drawer gets a warning, not a second approaching guard.
  Holster, leave, or draw again; check the transfer and stand-down.
- Talk while drawn. Residents use their approved refusal lines; Vesper
  continues working. Provoked dialogue takes precedence. Try the Halo
  entrance drawn, then holstered. Other truce refusal reasons still hold.
- Walk from the Stair past the tout and haggler. The Row has 20 posted
  residents plus two enforcers and the covered Warden. Ordinary trips
  share four moving slots; the Halo's three regulars share one. Over
  several minutes watch errands and staggered swaps. Standing nonsteady
  residents shy once; seats and steady people hold. Talk reach pauses
  ordinary trips. See [EXTRAS.md](EXTRAS.md) for the complete route.
- In the Halo, listen to the runner. Marked or hunted callers get Dolf's
  hint. Try the locked back-room door: it names the Tin Halo core. Use
  the existing board jack-in route; room 3 is Back room, with the back
  door control. Flip the latch and take the existing back way before its
  ordinary reset. No routing or jack-in redesign is included.

## Evidence boundaries

Local focused checks cover the demo, both renderers at both sizes and
all three color tiers, and the unchanged mechanics/S43/interaction
fixtures. The population trace uses a manual clock; it is not CPU proof.
Hosted CI runs the full root suites on Linux and Windows. The separate
native demo workflow uses a real NetBBS registered stdio door and retains
raw ANSI, text captures and a result record at both sizes. It discloses
its character and position fixtures and verifies installed client/source
identity. See #185 for exact heads, run links and all failed outcomes.

There is no S11 gate for this demo. Automated checks and captures do not
grant human presentation, pacing, H1 or S25 acceptance. The existing
hunt-routing limitation (#187) is outside these three proposals.
