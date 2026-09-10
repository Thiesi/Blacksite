# Blacksite — Terminal UI

How the game looks and how it is driven, on every terminal NetBBS can
present: Telnet, SSH, and the web (xterm.js) transport, from 80×24 up.
The client (`blacksite.door`) implements this document; the server sends
view models (`02-architecture.md` §5.4) and never escape sequences.

---

## 1. Capability tiers

Determined at start from `door_info.json` (`color_depth`) and from the
caller's answer to a one-time on-screen check the first time they play
(stored in player settings; changeable in the settings menu).

| Tier | Colour | Glyphs | Notes |
|---|---|---|---|
| truecolor | 24-bit | Unicode box, block, shade, a small set of symbols | default when `color_depth` is `truecolor` |
| 256 | xterm-256 | same | default otherwise |
| 16 | basic ANSI, bold as bright | same | selectable; used by the colour-blind variants too |

There is no ASCII-glyph tier. UTF-8 is a platform guarantee. The set of
Unicode glyphs used is fixed (`content/glyphs.json`) and restricted to
characters that also exist in CP437, so a caller on a SyncTERM-class
Telnet client in CP437 mode, or any transcoding path, still sees the
intended shapes: box-drawing (`─│┌┐└┘├┤┬┴┼` and the double-line set),
blocks and shades (`█▓▒░▀▄`), arrows (`←↑→↓`), bullets (`•·`), card
suits (`♦♣♥♠`), and a few symbols (`§°±≡`). No emoji, no combining marks,
and a test asserts every glyph in `glyphs.json` round-trips through
CP437.

Every colour in the game is a **role** (`palette.json`): `wall`, `floor`,
`cover`, `water`, `hazard`, `player_self`, `player_crew`, `player_neutral`,
`player_hostile`, `player_marked`, `npc_*`, per-faction, `ice_*`, per
channel, `hp_ok/low/critical`, and so on. Each role has a value per tier
and per palette variant (default, deutan, protan). Content never names a
colour directly.

## 2. Layout

Computed from the terminal size at start; never hard-coded. At 80×24:

```
┌ Karst · Core Plaza · safe ─────────────────────── 21:14 · Curfew in 12m ┐  1 header
│                                                        │ TARGET          │
│                                                        │ (none)          │
│                                                        │─────────────────│
│                                                        │ NEARBY          │
│               map viewport 56 × 17                     │ Vesper    fixer │
│                                                        │ Kale_9   Sable  │
│                                                        │ Mara     crew   │
│                                                        │─────────────────│
│                                                        │ CREW            │
│                                                        │ Mara  ████░ Core│
│                                                        │ Dex   ██░░░ jack│
│                                                        │─────────────────│
│                                                        │ HP  ████████░░  │
│                                                        │ STA ██████░░░░  │
│                                                        │ SHK ██░░░░░░░░  │
│                                                        │ 1,240 ch        │
│                                                        │ Halvard +12     │
├────────────────────────────────────────────────────────┴─────────────────┤
│ [zone] Vesper: You look like you need work.                              │  3 log lines
│ [sys] Ring-fall over the second ring. Ferrymen are moving.               │
│ [crew] Mara: on my way                                                   │
│ ↑↓←→ move  Tab target  F fire  E use  J jack  I inv  C chat  ? help     │  1 hint/input
└──────────────────────────────────────────────────────────────────────────┘
```

Rules:

- **Header** (1 row): zone, safety class in its colour, clock, event
  countdown.
- **Viewport**: everything left of the side panel, everything between
  header and log. Width = columns − 24 − borders. Height = rows − 1 −
  log − 1 − borders. At 80×24 that is 56×17; at 132×50 it is 108×43.
- **Side panel** (22 columns): target, nearby, crew, vitals. Sections
  shrink from the bottom up if the height is short; vitals always show.
- **Log**: 3 rows at height 24, growing to 8 at height 40 and beyond.
  `Shift-L` opens the full scrollback as a `TextView`.
- **Hint line**: contextual keys, or the active line prompt.
- Borders use box-drawing at all tiers.

The viewport is centred on the player and scrolls in whole-tile steps
when the player is within 4 tiles of an edge. Tiles the player has seen
but cannot see now render dimmed (remembered); never-seen tiles are
blank.

## 3. The Lattice view

Same frame; the viewport renders the sector instead of a zone.

```
│      ·                 ·                    │
│    (03)────(04)      (11)                   │
│      │       \        │                     │
│    [C2]     (05)────(06)═══(07) ♦           │
│      │        │        \                    │
│    (01)────(02)       [C3]  ▒▒ you          │
│              │                              │
│            (08)·····(09)   ♦ runner         │
│              ·          ·                   │
```

- Cells are drawn as `(nn)` labels on a grid whose positions are content
  (authored once per sector, not computed at runtime). Edges are `─│/\═`
  by kind: normal, gated (double line), hidden (dotted `·`, only once
  found).
- Cores are `[Cn]` with a colour by owner faction. The runner is a
  reverse-video marker; other presences are `♦` with a relation colour.
- The side panel becomes: INTEGRITY, TRACE (with the threshold marked),
  RIG (slots with cooldown ticks), ROOM (data, controls, ICE bars).
- Inside a core, the viewport shows the core's room graph the same way,
  and the current room's contents as a short list beneath it.
- Black ICE hits flash the whole border red for one frame at every tier.

## 4. Menus and overlays

All menus are `MenuView`s drawn as a centred overlay (up to 70×20 at
80×24, larger on larger terminals), with a title bar, a column header,
rows, a cursor row in reverse video, a detail pane on the right when width
allows (≥ 100 columns) or below when it does not, and an action bar. They
follow the NetBBS §3.5 rule: opening a menu never asks a question; every
action is a hotkey; `Esc` or `B` closes without side effects.

Menus: inventory, equipment, rig, character sheet, skills and grade
points, contract board, active contracts, vendor, market, bounties, crew,
sitrep, settings (keymap, palette, log verbosity, sitrep visibility),
dialogue (the talker's line above, responses as rows), apartment, bank,
workshop, descent console, chronicle, help.

Overlays never stop the world. Movement keys are swallowed while a menu
is open, but the log keeps scrolling and the viewport underneath keeps
updating; a menu that has been open for 60 s in a contested or open zone
closes itself with a toast.

## 5. Input

### 5.1 Keymap

Two shipped keymaps, switchable in settings and remembered per player:

| Action | Arrows keymap | Vi keymap |
|---|---|---|
| move | ↑↓←→ (diagonals: Home/End/PgUp/PgDn) | hjkl yubn |
| sprint (hold) | Shift + move | HJKL YUBN |
| target next/prev | Tab / Shift-Tab | Tab / Shift-Tab |
| fire / attack | F | f |
| interact | E | e |
| jack in/out | J | j |
| inventory | I | i |
| character | P | p |
| rig | R | r |
| crew | G | g |
| sitrep | W | w |
| map (zone overview) | M | m |
| contracts | Q | q |
| chat (say) | C or Enter | c or Enter |
| whisper / crew / faction | ` / T / Y | same |
| use quick slot 1–5 | 1–5 | 1–5 |
| programs in rig slot 1–7 (Lattice) | 1–7 | 1–7 |
| help | ? | ? |
| log scrollback | Shift-L | Shift-L |
| redraw | Ctrl-L | Ctrl-L |
| leave door | Ctrl-X then confirm key | same |

The client sends normalised key names; the server maps names to intents
by the session's keymap. Rebinding is therefore a settings change, not a
client feature.

### 5.2 Line prompts

Chat, names, market prices, whisper targets. The hint line becomes the
prompt with a label, local echo, `Backspace`, `Ctrl-U`, `Esc` cancel,
`Enter` submit. Input is bounded (chat 200 columns, names 24). While a
line prompt is open, single-key actions are suspended; movement keys
type nothing and are ignored.

### 5.3 Key decoding

- ANSI/VT arrows (`CSI A`…), SS3 variants, Home/End/PgUp/PgDn in both
  CSI-tilde and SS3 forms, F-keys, Shift-modified arrows (`CSI 1;2 A`),
  `Esc` alone with a 50 ms timeout, `Ctrl` letters, `Enter` as CR or LF or
  CRLF, `Backspace` as DEL or BS, `Tab`, and UTF-8 text.
- Mouse sequences (`CSI M`, SGR) are recognised and discarded; the client
  never enables mouse reporting. Bracketed paste is recognised and its
  contents discarded.
- Unknown sequences are dropped whole, never leaked into a line prompt.

## 6. Rendering rules

- The client owns a cell buffer of the terminal size. Each frame:
  render the current view into the buffer, diff against the previous
  buffer, emit minimal cursor moves and colour changes, keep the cursor
  parked at the prompt position (visible only during a line prompt).
- Never write to the last column of the last row (terminal autowrap
  hazards). Never emit a wide glyph at the last column of any row.
- Display width per NetBBS's rules: East Asian wide characters take two
  cells; combining marks are not in the glyph set but may appear in
  names and are measured as zero width; control characters never reach
  the buffer.
- Names and chat are truncated with `…` to fit; the truncation is by
  display width, not code points.
- A `view` message forces a full redraw; `Ctrl-L` clears and redraws.
- Frame rate is bounded by view revisions: the client renders when a
  view or delta arrives, at most 10 times per second, and coalesces if it
  falls behind (it renders the latest state, not every intermediate one).
- On exit: reset colours, show cursor, clear the screen, print one line
  ("Karst keeps your place."), so NetBBS's menu redraws cleanly.

## 7. Screens outside play

- **Title screen**: an ANSI art block (`art/title.ans`, with 256- and
  16-colour variants) and the tagline, then the character summary or the
  Wake entry. Minimum size check happens here: below 80×24 the client
  prints the requirement and exits.
- **Wake**: a sequence of `TextView`s and one `MenuView` (archetype) with
  a name line prompt, then the zone view of the Wake Hall.
- **Dead**: a full-screen `TextView` with the decant timer and a line of
  Sablier boilerplate; any key after the timer.
- **Disconnected**: "The city is dark right now." with the reconnect
  countdown.
- **Banned**: fixed text, any key exits.

## 8. Colour-blind and low-contrast variants

- `deutan` and `protan` palette variants remap faction hues and the
  hostile/neutral/crew roles to a blue/orange/white axis and add a
  one-character relation tag after names in the nearby list (`!` hostile,
  `~` neutral, `+` crew) that is always present at every tier anyway.
- No information is conveyed by colour alone: safety class also appears
  as a word in the header, target relation as a tag, ICE class as a
  label, HP as a bar plus digits on the character sheet.

## 9. Sound

None. Terminal bell is never emitted.

## 10. Help

`?` opens a two-page `TextView` of the current context's keys (zone,
Lattice, menu) followed by the full keymap. Every menu's action bar is
its own help. The first three sessions of a new character show a
one-line hint on the hint line for the next useful key until the player
uses it; the hint system is server-driven (`hint` in the view).
