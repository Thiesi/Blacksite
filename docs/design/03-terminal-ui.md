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
Unicode glyphs used is fixed (`content/glyphs.json`), and its CP437
column is restricted to characters that also exist in CP437, so a caller on a SyncTERM-class
Telnet client in CP437 mode, or any transcoding path, still sees the
intended shapes: box-drawing (`─│┌┐└┘├┤┬┴┼` and the double-line set),
blocks and shades (`█▓▒░▀▄`), arrows (`←↑→↓`), bullets (`•·`), card
suits (`♦♣♥♠`), and a few symbols (`§°±≡`). No emoji, no combining marks,
and a test asserts every glyph in the CP437 column round-trips through
CP437. The modern column follows the glyph tier rules below.

**Glyph tiers.** The game is built for a modern terminal and never
requires one. Glyphs come in two tiers, chosen independently of colour:

- **CP437 tier** (the set above): every caller can use it, and it is
  complete. Nothing needed to play exists only in the modern tier.
- **Modern tier**: a substitution, not a second renderer. Each
  `glyphs.json` entry may carry a modern glyph beside its CP437 glyph,
  which stays as the fallback. Layout, widths and the meaning of every
  cell are the same in both tiers; only the character drawn changes. In
  chrome that means, for example, eighth-block bars, diagonal arrows and
  rounded corners. Eye-level pictures use sextants in the modern tier
  and half-blocks in the CP437 tier.

Map rules hold in both tiers: one glyph per tile, no sub-tile detail,
and a map glyph means the same in both. A modern glyph may be a better
drawing of the same symbol, never a symbol only modern callers see, so
help, legends and advice between players work across tiers.

Detection: NetBBS sends only the boolean `unicode_style`, so support is
not detectable. The first-play check shows a test row for each glyph
family the modern tier uses. The modern tier is on by default when
`color_depth` is truecolor and the caller confirms the rows look right;
everyone else gets the CP437 tier. Either can be changed in settings.

The choice is stored per player but applies per connection, the way
colour is capped by `color_depth`. The modern tier is drawn only while
the connection is truecolor and `unicode_style` is true; an absent
`unicode_style` counts as false here. When a later connection's
transport or `color_depth` differs from the one the tier was confirmed
on, the check runs again before the modern tier is used. A key drawn in
CP437 glyphs always switches back to the CP437 tier, so a caller who
sees broken cells, settings menu included, can recover.

Every modern glyph is single width, has a CP437 fallback and appears in
the check; replay tests run in both tiers.

**Registry rules** (decision D6, 2026-10-28). A new glyph comes from
CP437's 0x80-0xFE range or from printable ASCII, so it never collides
with a control byte. The
map vocabulary (section 2.2) adds `τ` (drone), `≡` (closed or locked
door), `°` (a published patrol waypoint; `+` stays the door), the
Lattice shapes `∩ ∞ ╪` and the box joins `╤ ╧ ╟ ╢`, `▌` for half bars,
and the ground grain `∙ , ' \``. Letters on the map belong to signage
and paint only: no tile, thing or person is drawn as a letter. A
jacked-in body keeps its own shape, drawn dim, never a cover shade. Glyphs whose CP437 code is a control byte are kept, and S31 verifies
them on every transport that may send raw CP437. Each has a named
fallback from the safe range, used in the CP437 tier wherever S31 finds
the original unsafe:

| Glyph | Use | Fallback |
|---|---|---|
| `☺` | other callers | `ö` |
| `☻` | NPCs | `Ö` |
| `‼` | danger | `!` |
| `§` | Lattice terminal, descent console | `Σ` |
| `☼` | a rule light | `Φ` |
| `•` | bullets in text | `·` |
| `♦` | crew beacon, other runners | `σ` |

**Colour roles may set backgrounds** (decision D4). A theme gives the
ground and wall faces their background, and a few roles (hazard, the
current Lattice cell) use one. In 16 colours a background is one of
colours 0-7; bright colours are foreground only.

S30/S31 platform admission follows architecture 8.4: respect NetBBS's
boolean `unicode_style`, returning a clear graphic-terminal requirement
when false instead of silently overriding an ASCII preference. CP437
callers keep the same glyphs through NetBBS's UTF-8-to-CP437 transcoding;
the subprocess still emits UTF-8. This adds no plain-text display tier.

Commerce objects use the registered `$` for counters/banks and `*` for
dropped-item caches. These are object overlays, so an anchor remains
visible even when its underlying terrain is ordinary floor.

Apartment storage uses `*`, the protected safe uses `$`, and the bed
uses `b`. Interact on the bed to inspect rent, locks and core status,
read the intrusion log, surrender, leave or log out. Visitor views never
include the resident's body or drone in the private room. An apartment
key's inventory detail shows its lock tier and labels expired keys.

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
│               map viewport 55 × 17                     │ Vesper    fixer │
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

- **Header** (1 row): district (dim), zone (bright), the safety word, then
  live facts (heat, Marked, `PvP G5+` on contested ground, event
  summary); the clock at the right. Lower-priority segments drop first.
  The frame around it shows safety by line style (2.1); the sketch draws
  single lines throughout.
- **Viewport**: width = columns - 2 outer borders - 1 divider - 22
  side-panel columns. Height = rows - 2 outer border/header rows - 1
  separator - log rows - 1 hint row. Thus 55x17 at 80x24 and 107x38 at
  132x50. The sketch above is schematic; geometry follows this formula.
- **Side panel** (22 columns): the sections of 2.4, in that order.
  Sections shrink from the bottom up if the height is short; vitals
  always show.
  With a live crew, the small layout keeps one other member's health and
  location visible; `G` opens the full leader-first roster. Hazard,
  objective and service warnings take priority over optional crew rows.
  Jacked members show integrity against their actual maximum. Private
  interiors and remote Silt rooms are redacted. A crew beacon is drawn
  above the marked member's body glyph; Marked names remain red with a
  crew plus tag.
- **Log**: 3 rows at height 24, growing to 8 at height 40 and beyond,
  in the kinds of 2.5. `Ctrl-P` opens the full scrollback as a
  `TextView`.
- **Hint line**: contextual keys, or the active line prompt.
- Borders use box-drawing at all tiers.

The viewport is centred on the player and scrolls in whole-tile steps
when the player is within 4 tiles of an edge.

The presentation rules below are the owner's decisions D1 to D7 of
2026-10-28 (issue #68). The principle behind them: **shape is the rule,
light and colour are the place.** A tile's glyph says what it does; its
colour, its ground and the words on its walls say where you are. Nothing
decorative ever changes what a tile does, and nothing needed to play
exists only in decoration.

### 2.1 Frame and safety

Safety is shown three ways at once: the frame's line style, its colour
and a word in the header.

| Class | Frame lines | Frame colour | Header word |
|---|---|---|---|
| safe | double `═ ║` | Warden blue | SAFE |
| pocket | double | teal | POCKET |
| contested | single `─ │` | amber | CONTESTED, and `PvP G5+` |
| open | single | red | OPEN |

Safe ground is Warden blue, not green (D4). Safe and pocket ground both
use double lines; the header word tells them apart, so colour is never
the only difference. In the Lattice the frame shows the body's safety,
never the sector's (section 3). A hit recolours
the frame for one frame; it never draws over cells.

### 2.2 Map vocabulary

Four bands of light, darkest to brightest. Each band stands out from the
one below in every theme and tier, by at least a minimum lightness step
that the first contrast test fixes (proposed: 8 per cent in 256 colours
and truecolor).

| Band | Contents | Treatment |
|---|---|---|
| Ground | floor, paving, paint, roof | the theme's background; sparse, low-contrast grain |
| Structure | wall faces, signage | the facade's background; lettering lit on it |
| Things | interactables, cover, hazards, exits | a bold fixed shape in its kind's colour on the ground |
| People | you, callers, NPCs, drones | brightest; you are reverse video |

Terrain:

| Element | Shape | 256 colours and truecolor | 16 colours |
|---|---|---|---|
| Floor | theme grain (`· ∙ , ' \``), or bare away from walls | theme background, dim grain | `·` grey on black |
| Wall face (a wall beside open ground) | blank | facade background | `█` grey |
| Roof (a wall with no open neighbour) | blank | near black | blank |
| Sign | letters on wall faces | lit lettering on the facade | letter colour on black |
| Paint | `─ │` and letters | dim paint colour on the ground | dark grey |
| Cover 1-3 | `░ ▒ ▓` | cover colour; named in HERE | same |
| Water | `≈` | water background; glints change colour, never shape | blue |
| Hazard, warned tiles | the tile's shape, `‼` in the log | amber on dark red | bright yellow, reverse |

Things:

| Kind | Shape | Colour family |
|---|---|---|
| Lattice terminal, descent console, relay | `§` / `Ω` | cyan |
| Vendor, bank | `$` | gold |
| Hardware | `■` | violet |
| Door / closed or locked door | `+` / `≡` | brass |
| Exit | `»` | white, with a painted or signed destination; a hidden exit is not drawn as one (below) |
| Light source (a rule light) | `☼` | warm white |
| Clone vat | `Θ` | vat green |
| Dropped cache | `*` | gold |
| Crew beacon | `♦` | crew colour |
| Published patrol waypoint | `°` | amber |

A pool of lamplight drawn by a theme is not a light source: only `☼`
objects change sight, and only they are drawn as `☼`.

**Walkable and blocked ground differ by shape.** A wall face is a blank
cell on the facade's background, so a floor tile beside a wall face
always carries grain, even in a theme whose ground is otherwise bare: a
blank cell is never walkable where a wall is near. In 16 colours wall
faces are `█`. A render test checks that no bare floor cell borders a
wall face.

**A hidden exit is always drawn as the ground around it:** no `»`, no
paint, no sign naming a destination. HERE names it only while you stand
on it (architecture 5.5.2). A later rule may show exits a caller has
found; none does yet.

People:

| Who | Shape | Colour and attribute |
|---|---|---|
| You | `@` | reverse video, always |
| Other callers | `☺` | by relation: crew, neutral, hostile, Marked |
| NPCs | `☻` | by presented class (D-T8): what you can know of them, never a hidden allegiance |
| Drones | `τ` | by relation |
| Anyone hostile to you | their shape | reverse video in their colour, never colour alone |
| A jacked-in body | its shape | dim (in 16 colours, dark grey), never reverse video; NEARBY and CREW say `jacked` |
| Your target | its shape | underlined, and named in TARGET |

Reverse video means two things only: you, and hostility. A disguised
NPC presents its cover (D-T8) until it acts against you: then you see
its true class, because it has just shown it.

On light grounds (clinic interiors) roles use their `_light` variant, so
people stay readable on white. Nothing decorative is drawn over a
person, a thing, a warned tile or your target.

### 2.3 Seen, known and charted ground

- **Seen now:** full light.
- **Known** (seen before, or charted): the same place at about 55 to 60
  per cent of its light (D2). In 256 colours the hue is kept where the
  palette can, otherwise grey at the same lightness; in 16 colours, dark
  grey with every third floor dot. Known ground never shows people,
  objects' live state or warned tiles.
- **Unknown:** blank.
- **Charted ground** (D1): a zone (or pocket) flagged `charted` in its
  zone data shows its public ground as known on arrival: the layout of safe hubs and small
  public interiors, so you know where you are before you have walked it.
  Sight still decides people and live state. Charted ground covers only
  the zone's declared public region; it never shows a hidden passage or
  a private interior, and it never becomes part of what your character
  remembers. Its disclosure terms are architecture 5.5.5.

### 2.4 The side panel

Top to bottom; a section shows only when it has something to say, except
TARGET and the pinned vitals.

1. **DANGER** (when warned): time to the hazard, the ways out.
2. **NOW** (when present): event plans and the objective's next action.
3. **HERE** (when something is in reach): what is within one step, as
   the focus contract of architecture 5.5.2 discloses it.
4. **TARGET**: name in its role colour, HP bar, range, cover in words,
   relation, warnings (Protected, Firing marks you), the weapon you would
   use. Empty: `none   Tab picks`.
5. **NEARBY**: shape in colour (reverse when hostile), then name and
   relation tag; it shrinks first.
6. **CREW** (with a crew): beacon `♦`, leader `+`, health, zone.
7. **Pinned to the bottom**: name (and handle at 132x50 if it differs),
   grade, HP, STA and SHK bars, chits, lease days; discharge at 132x50.

Sections are introduced by a dim rule with a label (`─ TARGET ───`); no
brackets anywhere. Bars are ten cells of `█ ▌ ░` with the digits after;
shock has a bar.

### 2.5 The log

Every line has a kind, shown by a gutter mark and a colour (D5):

| Kind | Gutter | Colour |
|---|---|---|
| place | `»` | warm |
| ambient | `·` | dim grey |
| speech | `"` | speaker lit, words white |
| combat | `*` | white |
| danger | `‼` | amber, bold |
| system | `+` | dark grey |
| reward | `√` | dim |

The kinds are architecture 5.5.3's; a line in the Lattice keeps its kind
and takes the sector's colour. Each kind has its own gutter mark, so no
kind is told apart by colour alone.

- **Place lines** name where you have arrived, once, on first entry.
- **Ambient lines** are a place's own voice: at most one every 60 to 120
  seconds per caller, never in combat or travel, and they can be muted
  in settings.
- Identical lines within 10 seconds coalesce (`(x13)`); reward lines
  within 5 seconds merge into one.
- Danger lines never coalesce with other kinds, and no other line pushes
  a danger or combat line out of the visible log within 10 seconds.
- **Notices** (kind `notice`: restarts, maintenance, news from the node)
  are not world-log lines. A notice takes the hint line over key help
  and stays there until a key is pressed and at least 8 seconds have
  passed. It never hides a prompt or escape keys: while a prompt is open,
  or while you are threatened (a DANGER state, combat, a hazard), it
  shows in the header's right end instead, and returns to the hint line
  afterwards. Each notice also keeps
  one line in scrollback (`Ctrl-P`) and stays in help (section 10). A
  new Wake sees none in its world log in the first five minutes.

### 2.6 The place card

On first sight of a zone the map area shows the place card: district and
zone in letter-spaced capitals, the safety word and the zone's text, lit
by the place's own ground colour. It is the default way a place presents
itself (the owner's default under D8; other art modes and a larger
dashboard wait for a playtest). 16-colour callers get a drawn 16-colour
card where the place has one (assets 4), otherwise the text card.

- It lasts up to 8 seconds. **Any key closes it, and that key still
  acts**: a move on the card is a move.
- It never opens while anything threatens you (a hazard, a target, a
  hostile nearby, combat, heat), and closes the moment one appears or
  you are hit.
- It can be shown again on request; whether it opens on entry is a
  setting.

### 2.7 Atmosphere: allowed and not

Allowed: static themes and regions, light pools, signage (including dead
letters), paint, water glints, place lines, ambient lines and the place
card, within the rules above.

Not allowed: animation or flicker on a timer; anything that looks like a
threat (red flashes, `‼`, reverse video) used as decoration; meaning by
colour alone; dressing over a rule tile; anything that delays input; art
that covers a timed hazard or an escape action (assets 9).

## 3. The Lattice view

Same frame; the viewport renders the sector instead of a zone. The
Lattice is drawn as linework on black (decision D7, 2026-10-28): the
grid the old engineers laid out (Lattice 1), not a map of ground.

```
│ ·     ·     ·     ·     ·     ·     ·     · │
│       ■─────■           ■                   │
│       │      \          │                   │
│     ╔═╗      ■══════════╪═════■ ♦           │
│     ║V║──────█           \                  │
│     ╚═╝      │           ▐S▌                │
│              ■ · · · · ∙                    │
│ Signal rack 11, Vatside                      │
│ ← Core uplink  → Sablier Clinical  ↓ Rack 9  │
```

- No background fills. A faint field of dots shows the grid. Cell
  positions are content (authored once per sector, not computed at
  runtime).
- Cells are `■` in the sector's light. Links are `─│/\` by kind: gated
  cells are `╪` with double-line links `═ ║`; hidden cells `∙` with
  dotted links, shown only once found; the uplink `∩`; a descent `∞`.
- Cores are buildings: `╔═╗ ║V║ ╚═╝` with the core's initial, or `▐V▌`
  when rows are tight, in the owner's colour. Initial and colour come
  from the owner the Lattice view discloses; a private core shows as
  private, never as the person or faction behind it.
- You are the reverse-video cell (`█` in the sketch). Other runners are
  `♦` beside their cell, in their relation colour.
- Below the field, a caption: where you are, then every link from your
  cell as an arrow and a name. Cells carry no `(nn)` numbers.
- The frame shows the safety of your body, never the sector's (2.1):
  that is what is at risk while you are down.
- Tab/Shift-Tab cycle defenders and runners in the same cell or room and
  instance. A selected runner shows integrity percent or PROTECTED; body
  permissions and Burn legality come from the server, never the client.
- The side panel becomes: RUNNER (integrity, trace with its threshold
  marked), BODY (the body's zone, safety word, HP, black ICE risk),
  TARGET, NOW, NEAR, RIG (slots with cooldown ticks), and inside a core
  ROOM (data, controls, ICE bars).
- Inside a core, the viewport shows the core's room graph the same way,
  and the current room's contents as a short list beneath it.
- Black ICE hits flash the whole border red for one frame at every tier.

Core graphs use at most 8x4 authored positions; the current room's
contents sit beneath the graph rather than below seven rig slots in the
side panel. Silt bands use a compact 5x4 graph with orthogonal visible
links. A riser and sink have explicit UP/DOWN markers. Persistent danger,
body safety, cast/escape progress and the next trace consequence take
priority over optional descriptions. Every ICE shows its phase and a
counter; Liar's suspect labels never replace authoritative controls.

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
dialogue (the talker's line as detail, offers as hotkeys, no response
rows), apartment, bank,
workshop, descent console, chronicle, territory, help.

F8 at a physical terminal or relay opens the public territory list. E at
a relay opens its current claims, owner and influence rate. H explicitly
starts a hold; S supports the selected named claim; V opens the current
owner's member counter; X withdraws. Esc/B closes a card without starting
or withdrawing a claim. Outside the card, B leaves an active hold.
Claim cards show whole seconds so their choices do not churn at tick
frequency; the server's hold clock remains precise. Contested and Curfew
states visibly pause the timer. The ordinary hostile-zone menu timeout
still applies, and closing a card never pauses the world.

F9 beside a public terminal opens services, including terminals that also
host a contract board. E retains the existing board or jack interaction.
In services, M opens the market, O bounties, J the jack and C delivery
collection.
Outside menus, M remains the map, O drone commands and C chat. The market
uses D to bid, U to buy out, L to list, M for own listings, C to collect,
K to cancel, F to filter class and S to sort. Esc/B leaves every screen
without a transfer; Y is the last step of a chosen financial action.
Listing confirmation shows the seller's net proceeds at the asking price
and optional buyout, including zero net for a one-chit sale. The 5% fee
rounds up to whole chits; it does not introduce a minimum listing price.
Bank menus also expose C for market delivery collection.

Market menus send at most 12 rows per page. Up/down and PgUp/PgDn move
the authoritative cursor across pages; the selected row and detail pane
stay together. Listing history remains stored without growing each view
frame beyond the protocol limit. The page count includes retained own
listings, so sellers can inspect earlier outcomes.

  A workshop lists learned schematics with carried/required salvage,
  Fabrication minimum and quality range (game design 8.4). F starts a
  craft; Esc/B returns without side effects. Physical harvesting and
  crafting expose `me.channel {label, remaining}` on the hint line,
  preserving the existing cell-buffer width rules. Inventory and
  installed-item details show quality-adjusted values from the same
  per-template selector as equipment resolution.

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
| jack in/out | J | Ctrl-O |
| inventory | I | i |
| drone commands | O | o |
| character | P | p |
| rig | R | r |
| crew | G | g |
| sitrep | W | w |
| map (zone overview) | M | m |
| contracts | Q | q |
| chat (say) | C or Enter | c or Enter |
| whisper / crew / faction | ` / T / Ctrl-F | same |
| use quick slot 1–5 | 1–5 | 1–5 |
| programs in rig slot 1–7 (Lattice) | 1–7 | 1–7 |
| help | ? | ? |

The drone panel lists packed and deployed units with their current health
and mode. `U` deploys, `R` recalls, `F` follows, `H` holds, and `T` assigns
the current target. Using a packed drone from inventory also deploys it.
An idle mode toggle grants no skill. `Esc`/`B` closes the panel.
| log scrollback | Ctrl-P | Ctrl-P |
| redraw | Ctrl-L | Ctrl-L |
| leave door | Ctrl-X then confirm key | same |

S09 also accepts Y for faction chat and Shift-L for scrollback with the
arrow keymap. The vi keymap retains Y/L as sprint movement; Ctrl-F and
Ctrl-P work in both keymaps. Sitrep's H action hides or shows your zone;
hidden callers see only hidden locations for others. The selected row's
detail pane keeps name, handle, faction, location and link state readable
when the full row does not fit at 80 columns.

The client sends normalised key names; the server maps names to intents
by the session's keymap. Rebinding is therefore a settings change, not a
client feature.

S10 adds X to cycle equipped weapons, V for abilities, and Z for Ghost
stealth in both keymaps. In abilities, 1-5 binds the selected action;
Enter uses it. A selected target shows name, faction, HP percent, range,
cover and relation. A hit changes the border for one rendered frame at
every tier. Down/decant views retain the log and cannot dismiss the timer.

### 5.2 Line prompts

Chat, names, market prices, whisper targets. The hint line becomes the
prompt with a label, local echo, `Backspace`, `Ctrl-U`, `Esc` cancel,
`Enter` submit. Input is bounded (chat 200 columns, names 24). While a
line prompt is open, single-key actions are suspended; printable vi movement letters
are ordinary text. Arrow navigation cannot move the character.

### 5.3 Key decoding

- ANSI/VT arrows (`CSI A`…), SS3 variants, Home/End/PgUp/PgDn in both
  CSI-tilde and SS3 forms, F-keys, Shift-modified arrows (`CSI 1;2 A`),
  `Esc` alone with a 200 ms timeout, `Ctrl` letters, `Enter` as CR or LF or
  CRLF, `Backspace` as DEL or BS, `Tab`, and UTF-8 text.
- Drain ready input before expiring a lone `Esc`. Rendering or pipe
  backpressure can delay the timer and reader together; queued arrow
  bytes must take precedence over the elapsed framing grace.
  Preserve a successful read that finishes in the timeout's loop turn;
  consuming bytes and then losing that result cannot type a chat hotkey.
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
- Names and chat are truncated with `...` to fit; the truncation is by
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
  as a word in the header and as the frame's line style, hostility as
  reverse video and a relation tag, danger as `‼` and the DANGER
  heading, seen and known ground as light and the absence of people,
  crew as `♦` and `+`, ICE class as a label, HP as a bar plus digits on
  the character sheet.
- Every role added by the presentation rules (section 2) has deutan and
  protan values; red-green pairs (the open frame, the HP bar, hostile on
  a light ground) shift to magenta, blue and orange.
- The 16-colour tier uses backgrounds 0-7 only (section 1), reverse video
  for emphasis, and keeps the floor dot so walkable ground stays
  readable on black.
- People are readable on every ground, white interiors included (2.2).

## 9. Sound

None. Terminal bell is never emitted.

## 10. Help

`?` opens a two-page `TextView` of the current context's keys (zone,
Lattice, menu) followed by the full keymap. Every menu's action bar is
its own help. The first three sessions of a new character show a
one-line hint on the hint line for the next useful key until the player
uses it; the hint system is server-driven (`hint` in the view).

Help also keeps the node's operator notices (restarts, maintenance,
news), newest first. They are shown on the hint line when they arrive
(2.5) and never enter the world log.

## 11. Playable information, journals and decisions

The default play screen answers four questions without scrollback:
what is dangerous now, what action advances the job, what it costs,
and how to leave. Vitals and safety remain visible when an objective or
hazard compresses the nearby list. Warning timers use a word and digits,
not colour or a one-frame flash alone. Menus do not pause the world;
show body safety and provide the current escape action while jacked in.

`Q`/`q` opens contracts and its journal tab. The journal separates
**Observed**, **Source says**, **Open question**, and **Next action**.
A record is acquired by inspection, not by reading every prose page.
Inspection shows operational controls before optional source text; a
player can execute the whole job using labels, target markers and
progress bars. No parser, quiz or correct conversation answer exists.

At 80 columns the contract menu shows one selected list row and expands
the operational card below it. Up/down selects another record;
`[`/`]` pages long detail. At 132 columns the list and detail sit beside
each other. A confirmation remains bound to its chosen card even if new
proposals arrive. A private/public turn-in shows its actual reward,
publication audience, scoped effect and duration before the final `Y`.
At 80 columns the objective and its current action cost use the bottom
hint line; service state uses the header. Vitals, current danger and
escape keep their normal positions. The Q panel separates active jobs,
completed jobs and acquired records. A published patrol adds a visible
journal entry only while its local telemetry permission is active.

The hint row keeps this priority: an active prompt or notice, then a
channel line by itself, then the active objective and its current cost,
then E/J context, then remaining whole key-help groups. Help comes first
among those remaining groups when it fits. This applies at both widths.
When E and J select the same target with the same verb, show one `E/J`
group (`E/Ctrl-O` in vi). Distinct targets or verbs keep separate groups.
Do not append a generic `E act` group; Q keeps its job-panel help.
Shorten E/J labels first, keeping at least the first word of each name
and never cutting a key or verb. If that cannot fit, drop J, then E.
Only then shorten the objective's target text; keep `Next:`, its verb
and the current cost. This uses the existing hint row, not a new panel.

Work-order panels show reservation owner, stage, supplied item, target,
public/worker allocation, recipients and expiry. The reserving player's
choice is visible before others join. Expired or stale choices refresh
the panel and consume nothing. Route changes appear in the map and
header; costs appear before the player commits the action.

The Silt panel labels the repeating signal and sampling window, counts
the channel, marks a known riser and shows Sweeper warning/escape. A
Chorister may speak during this procedure; its prose is optional.

The finale has a safe decision room. Each participant receives their
own options, standing deltas, name-publication scope, ballot status and
settlement explanation. A leader cannot select another player's choice.
The name field edits only the choosing player's displayed name and only
where that choice calls for it. The Chronicle labels expedition report,
personal choice and settled public result separately, including dissent.

Human acceptance: finish the first job, a pump repair, a Silt survey and
a solo finale at 80x24 using the compact labels without opening a lore
page; then read the records and check that they deepen the same events.
Repeat with a wide handle and all colour tiers. These remain required
playtests, not a claim that the design has already been played.


### S20 faction presentation

Recruitment shows all eight standings and titles before actions (nine once the Lamp Compact is built, planned, #90). Join
and leave require a final chosen confirmation; Esc/B cancels. At 80x24
membership requirements, card distinction and cooldown remain visible.
Attending's visited vat choices use their own list with one select action.

Faction colour roles style member glyphs, target/nearby names and faction
chat. Marked overrides member colour with the existing red
`player_hostile` role; the `!` relation tag preserves meaning without
colour. Sitrep retains the existing Name/Handle/Faction/Zone/Link cells,
then adds Rank and a server-authored Marked/Heat countdown. Selected-row
detail keeps status and rank readable at 80 columns. Inspector telemetry
reveals only an actively Marked body's current zone, never coordinates;
existing scoped Hound reports retain their separate exact-location rule.
