# S33 — ANSI art pack: title, sigils, vignettes, the Ring, Wake Hall, dead screen, transitions

**Status:** planned
**Primary model:** Opus (composition and `.ans` authoring) · Sonnet (sidecars, loader, fallbacks) · **Reviewer:** Human (view every piece on a real terminal at three tiers)
**Depends on:** S04 · **Milestone:** M6
**Issue:** (filled in when filed)

## Goal

Ship the game's visual identity as ANSI art blocks the client can show
at every tier, with a loader that measures them, a sidecar that
declares their variants, and a text fallback for every piece so a
missing or over-wide file never breaks a screen. Agents are poor at
art; the process here assumes a human pass on the four most visible
pieces and treats everything else as optional polish.

## Spec references

- `docs/design/04-assets.md` §4 (the piece list with sizes and tiers,
  the recommended process, human review, image-to-ANSI alternative),
  §8 (naming: `art-<name>`, `-256`, `-16`, `-w132`).
- `docs/design/01-entities.md` §1.15 (art asset: `.ans` plus sidecar
  `width, height, min_tier, palette variants`).
- `docs/design/03-terminal-ui.md` §1 (fixed glyph set from
  `glyphs.json`; no emoji or combining marks), §6 (never the last
  column of the last row; wide glyphs never at a row's last column;
  full redraw rules), §7 (title screen; Wake; dead screen; Lattice
  jack-in transition frames), §3 (black ICE border flash is not art).
- `docs/world/08-found-texts.md` (title tagline block; the fallback
  text for the title), `docs/world/02-factions.md` (colours per faction
  with 256- and 16-colour fallbacks; uniform and visual tells for the
  sigils), `docs/world/01-gazetteer.md` (district atmospheres for the
  vignettes), `docs/world/00-bible.md` §2 (tone: noir, the Ring as the
  antagonist's clock).
- NetBBS `AGENTS.md` (trusted preformatted art rows must still be
  width-measured; NetBBS's `write_preformatted_line` precedent).

## Scope

Pieces (from the asset manifest), each as `content/art/<id>.ans` in
UTF-8 with SGR sequences only (no cursor movement, no clear-screen), one
row per line, plus `<id>.json` sidecar:

| Piece | Base size | Variants | Fallback |
|---|---|---|---|
| `art-title` | 80×20 | `-256`, `-16`, `-w132` (132×30) | the tagline block from the found texts |
| `art-sigil-<faction>` × 8 | 22×6 | `-256`, `-16` | faction short name in its colour, centred |
| `art-vignette-<district>` × 7 | 56×12 | `-256`, `-16` | the zone atmosphere text's first two lines |
| `art-ring` | 80×8 | `-256`, `-16` | one line: "The Ring is up." |
| `art-wake-hall` | 40×14 | `-256`, `-16` | none (Wake shows text only) |
| `art-dead` | 56×10 | `-256`, `-16` | the decant timer line only |
| `art-jack-in-1..3` | 56×17 | `-256`, `-16` | no transition (cut) |
| `art-blacksite-l1` | 80×20 | `-256`, `-16` | the level's first log line |

- Sidecar: `{"id", "width", "height", "min_tier": "16|256|truecolor",
  "variants": {"256": file, "16": file, "w132": file}, "fallback":
  text asset id or null, "glyphs_used": [...]}`.
- Loader (`src/blacksite/door/art.py`): reads a piece for the session's
  tier and width (prefers `-w132` when the viewport is ≥ 132 columns),
  measures every row by display width, rejects a piece whose rows
  exceed the target area or use glyphs outside `glyphs.json`, and
  returns the fallback instead; renders into the cell buffer through
  the normal path (no raw writes).
- A `scripts/art-check.py` tool: validates every `.ans` against its
  sidecar (size, glyph set, SGR-only), renders each variant to a PNG-
  free text preview for review, and reports the widest row.
- Screen wiring: title (S30's composition), faction screens' side
  panel (sigils), first entry to a district (vignette overlay for 3 s
  or any key), Scour zone header (the Ring, top of the viewport when
  height ≥ 40), Wake, dead, jack-in transition (three frames at 150 ms,
  skippable), Blacksite Level 1 entry.
- Human pass: title, the Ring, Wake Hall, dead screen are reviewed by
  the user on a real terminal (SyncTERM-class over Telnet, an SSH
  client, and the web transport) at truecolor, 256, and 16 colours;
  feedback applied before merge.
- Image-to-ANSI path (optional): `scripts/img2ans.py` converting a PNG
  to the fixed palette with the block-glyph set, for vignettes produced
  by an image model; output goes through `art-check.py` like any other
  piece.

## Out of scope

- Palette roles and tiers (S04/S30). District first-entry logic beyond
  the overlay hook (S08). The title screen's non-art composition (S30).

## Data and content

- 8 + 7 + 6 + 3 + 1 = 25 pieces in up to three variants each; `glyphs.
  json` unchanged (any new glyph is a design change in `03-terminal-
  ui.md` §1 first).

## Protocol and view models

- None. Art is client-side; the server only sends a `view` of kind
  `text` or the existing screen kinds with an `art` hint field naming
  the piece (`ZoneView.hint` is not reused; add `art: id | null` to
  `TextView` and the zone-entry `toast`).

## Tests

- `test_every_sidecar_has_files_for_declared_variants`
- `test_rows_fit_declared_size_by_display_width`
- `test_only_sgr_sequences_no_cursor_movement`
- `test_only_glyphs_from_glyphs_json`
- `test_wide_glyph_never_at_last_column`
- `test_loader_picks_w132_variant_at_132_columns`
- `test_loader_returns_fallback_when_file_missing`
- `test_loader_returns_fallback_when_piece_too_wide_for_terminal`
- `test_render_at_16_colours_uses_16_variant`
- `test_jack_in_transition_skippable_by_any_key`
- `test_art_check_script_flags_bad_piece`

## Acceptance script

For each of the 25 pieces, at 80×24 and 132×50, at truecolor, 256, and
16 colours, through Telnet (SyncTERM or similar), SSH (a Unix terminal),
and the NetBBS web transport:

1. Enter the door: the title renders without wrapping or stray
   characters; at 132 columns the wide variant appears.
2. Start a fresh character: the Wake Hall piece shows; die in the Wake
   corridor deliberately: the dead piece shows above the timer.
3. Walk into each district for the first time: the vignette overlays
   and any key dismisses it.
4. Open a faction screen: the sigil sits in the side panel at its
   size.
5. Walk into `scour-ring-1` at 132×50: the Ring sits above the
   viewport; at 80×24 it does not appear and the layout is unchanged.
6. Jack in: three frames, then the Lattice; press a key during the
   frames: it cuts.
7. Delete `art-title.ans` and re-enter: the tagline text appears
   instead, no error.
8. The user signs off the four human-review pieces.

## Definition of done

- All pieces present in all declared variants and passing `art-check`;
  tests green; human sign-off recorded in the PR; slice file marked
  done with PR number.

## Implementer notes

- Compose in the block and shade glyphs (`█▓▒░▀▄`) with box-drawing for
  frames; avoid half-block colour tricks that need truecolor for the
  256 and 16 variants, or produce the lower variants separately.
- 16-colour terminals render "bright" via bold on some clients; keep
  contrast from glyph density, not brightness alone.
- SyncTERM-class clients may be CP437-native: NetBBS transcodes, so
  glyphs outside CP437's repertoire (some shades map fine, `◊` does not)
  may show as `?`; stay inside the intersection of CP437 and the glyph
  set for art, which `glyphs.json` already respects.
- Never emit a piece with raw writes; every row goes through the cell
  buffer so the last-column rule holds automatically.
