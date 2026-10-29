# S25b live arrival captures

`scripts/accept_s25b_arrivals.py` supplies PR #97's TR-1 evidence. It
plays through a real NetBBS node, its registered native stdio door and
the installed Blacksite wheel. Captures are received ANSI transcripts,
terminal text and semantic glyph/style snapshots, not composed frames.

The matrix has twelve arrival screens: Wake Hall and generated Service
Level, at 80x24 and 132x50, in 16, 256 and truecolor. Additional live
Ctrl-P scrollback screens show recovery when the full paragraph has
already scrolled above the visible log.

## Reproduce

Use a NetBBS interpreter with its SSH/web extras and a fresh installed
Blacksite wheel. The probe checks that the wheel's Python tree matches
the server source. Use a fresh output root for each run. On Windows,
put capture worlds in system temp rather than a OneDrive directory;
the latter blocked a generated-world bootstrap directory rename during
the first local attempt.

```sh
python scripts/accept_s25b_arrivals.py \
  --root /tmp/s25b-arrivals-16 \
  --door-python /path/to/installed/blacksite/python --tier 16
```

Repeat with fresh roots and `--tier 256` and `--tier truecolor`.
`--show` forwards the 16-colour caller's actual ANSI to the terminal.
The `S25b live arrival captures` workflow runs all tiers with NetBBS
v7.31.0 and a wheel built at the checked-out head.

## Playable sequence and fixture boundary

1. Start a fresh registered caller, choose Blacksite in the node's
   picker and create the default archetype using normal keys. Enter the
   wide-character name, skip the briefing and leave the recruiter cards.
   Wake Hall appears with the arrival paragraph in the log.
2. Capture that first screen at both sizes. This case uses the shipped
   ten-zone world without a content overlay.
3. For Service Level, start another private world using the generated
   34-zone `content.local` tree. Its only additional geography fixtures
   are two marked street exits on existing passable tiles, connecting
   Wake Hall and `under-service`. NPCs and game rules remain enabled.
4. Create a caller normally. Walk to the training corridor at (21, 14)
   and press B to skip that fight. Walk onto the private shortcut at
   (32, 16). Ordinary exit travel enters Service Level; there is no
   player placement, explicit discovery call or clock fixture.
5. Capture the first destination screen. Check the paragraph's order,
   visible log rows and retained text. If it has scrolled up, press
   Ctrl-P and, if needed, Page Down. Capture the recovered paragraph in
   the real local scrollback. Escape leaves without changing game state.
6. Walk back through the private return exit and leave through Ctrl-X's
   normal confirmation.

This is arrival-message proof, not full-city walking, human pacing or
layout approval. The generated world is a labelled acceptance fixture;
none of its maps or content files publish with #97. Performance gates
remain in the separate full native matrix.

## Read the captures

Each `arrival-<scenario>-<size>-<tier>` has:

| File | Source |
|---|---|
| `.ans` | Actual received transcript, including the real node picker |
| `.txt` | Terminal replay at the capture point |
| `.json` | Live observations and the P1 glyph/style snapshot |

`result.json` records the head, clean/dirty state, negotiated colour
tier, served content hash, source-matched native Python hash and every
fixture. Archive only clean-head receipts. A clipped arrival screen
stays in the evidence; its `-scrollback` companion does not replace it.

The interim role is `chan_zone`. P4 adds `kind: place`; P5 can then style
it separately. At 80x24, subsequent arrival and XP notices can push the
first line of Service Level's paragraph above the three visible log
rows. The text remains in scrollback. The existing log also wraps by
cell width: a word can split at 132x50. These are recorded observations
for P4/P5, not hidden by this capture scenario or fixed as a renderer
change in S25b.
