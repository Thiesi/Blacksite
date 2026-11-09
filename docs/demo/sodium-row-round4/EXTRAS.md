# Round 4 extras and Halo back way

Demo component by the second engineer (Codex), based on `f299672`, with
t4's `b678fee` merged normally. This branch never merges to main. The
creative build list is #185 comment 6749988072; placement is 6750084395;
swap and budget decisions are 6750293749, 6750405790 and 6750417314.
H1/S25 approval remains NOT GRANTED.

## Cast and movement

| Zone | Cast | Ordinary moving budget |
|---|---|---:|
| Row | 20 posted residents, plus two enforcers and the Warden | 4 |
| Halo | Bouncer, Vesper, Dolf, three regulars | 1 |

Crowds use one slot each. A swap is the explicit two-slot exception:
both slots reserve atomically, including the waiting doorway person.
Homes exchange at the start. The drinker steps out and aside, then the
doorway person walks in; neither person spawns or disappears. Interrupted
swaps retain their exchanged homes. Paused trips keep their slots.
Arriving actors keep their movement counted through the end of that
tick. Watch/hunt/flee remain separate from the ordinary budget.

Home holds are 60–180 s for seats and 120–300 s for street/doorway posts.
Errands use counter 50, doorway 30, table 20 where those posts exist.
A swap and a free doorway errand share the doorway's weight, rather
than doubling it. Errands return home next. Fixed extras do no scheduling
or RNG work while at home. Active callers pause ordinary trips in talk
reach. The drawer itself cannot pin a shy reaction by talk reach.

The Warden shares the regulars' post list, holds, weights and crowd slot.
The cover validator checks those numbers and t4's steady flag. Post
validation excludes objects, exits, spawn and hazards. Spawn and respawn
respect home ownership while residents are away.

The tout stands at (4,11), the haggler at (5,11). The old look-at tout is
removed. Both names fit 14 cells and use the existing civilian treatment.
The Spare Parts terminal errand uses (84,3): (83,2) and (85,2) are walls.
Every authored home-to-post route was checked reachable on the demo map.

## Play checks for the integrated build

1. Arrive from the Stair. Read the sign with the tout and haggler below
   it. Talk to both; neither sells anything in this demo.
2. Walk past the four doorway knots and into Upstairs. Six bar drinkers
   hold seats initially. Over several minutes, watch counter/table trips
   and a swap. The first person clears the door before the second enters.
3. Approach a moving regular and talk. They pause in reach; after you
   leave, their trip resumes. Repeat beside a street regular's cover.
4. Draw near a standing, nonsteady resident. They step back once and
   hold. Seats and steady people stay put. A resident on an errand heads
   home. The shared limit still applies when several people react.
5. In the Halo, listen to the runner. With a hunted or Marked character,
   talk to Dolf: he points to the house system and the board.
6. Try the closed back-room door at (30,4). It says
   "Locked. The latch runs off the Tin Halo core."
7. Use the existing jack-in path to enter the Tin Halo core. Room 3 reads
   "Back room" and its control remains "back door". Flip it and use the
   back route before the ordinary 300 s reset.

New in round 4: all ordinary tout/haggler lines and barks; three regular
barks, two enforcer barks and two doorstep barks from extras §9; the
Halo-only runner hint and Dolf's back-way hint. The Halo copies reuse
existing street-free barks as their greeting; they do not give Row
directions indoors. t4 owns the drawn/provoked overlays for the new sets.

## Verification and integration limits

With `PYTHONPATH=src;.` and the root venv interpreter:

```text
python -m pytest tests/demo -q --basetemp=.test-tmp/pytest -p no:cacheprovider
118 passed in 43.25s
python scripts/demo_sodium/check_round4_posts.py --ticks 6000 \
  --output docs/demo/sodium-row-round4/extras-trace.json
```

The retained trace is a functional ManualClock run, not native or CPU
proof. It records 593 Row steps, 256 Halo steps and five swaps; population
stays 23/6, maximum reservations are 3/4 and 1/1, and home ownership stays
unique. Synthetic tests exercise all four Row slots, including shying and
paused trips. The generator was rerun with byte-identical output.
The launcher help exposes `--signs`; posts replace `--seated`.

Failed intermediate checks are retained on #185 (6750385029, 6750512090,
6750757548). Swap tests caught doorway staging and a second shy step after
a return home. Demo test updates replace retired seated expectations,
the old bark count and the old locked line. One updated fixture first
counted the two card players as bar drinkers; that assertion was fixed.

Four canonical NPC checks fail against the common demo base: three use
main's former coordinates, and one exposes two public/charted regions
that don't match the demo geometry. The two validator messages reproduce
on untouched `f299672` content. No new post route needs that disconnected
ground. t4 owns the explicit content-overlay integration, restoring
main's shipped content and correcting the overlay's public declarations.
No canonical test, golden, mechanics or P3 baseline was changed here.

The three coordinate cases have explicit demo equivalents in
`tests/demo/test_round4_coordinates.py`, so the content-layer integration
can keep main's original cases and also check the demo:

| Original main case | Demo coordinates and check |
|---|---|
| `test_design_5_5_shipped_halo_post_fills_beside_arriving_caller` | Bouncer (9,9), beside the Halo arrival; exactly one spawns |
| `test_design_5_5_shipped_row_wanderers_keep_plaza_and_halo_exits_clear`, regular | Start (3,12), next to Stair exit (2,12); a post trip moves away without occupying the exit |
| Same test, Warden | Start (89,12), next to Halo exit (90,12); the same post rule keeps the exit clear |

The three demo cases pass separately on the extras component. At overlay
integration, use `scripts.demo_sodium.content.load_demo_content` in their
content import, as the other demo tests do. The plain content loader is
used on this pre-overlay component branch.

The head still needs t4's new-set reaction overlays, final content layer,
hosted full-suite checks, native captures and lead review. No full local
suite, S11, native acceptance or presentation acceptance is claimed by
this component packet.
