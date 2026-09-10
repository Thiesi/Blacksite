# S04 — Door client core: door_info, connect, terminal, key decoder, cell-buffer renderer, tiers, reconnect

**Status:** planned
**Primary model:** Opus · **Reviewer:** Astra (renderer and key decoding critique before start)
**Depends on:** S01 · **Milestone:** M0
**Issue:** (filled in when filed)

## Goal

Build the thin door client NetBBS launches per caller: read
`door_info.json`, connect to the service, own the terminal (capability
tier, layout, cell buffer, diff renderer, key decoder), render the
generic view kinds (`text`, `menu`, log, prompt, toast), and reconnect
or exit cleanly. After this slice a caller entering the door from a
real NetBBS node sees the title screen, the MOTD, a help `TextView`,
and can leave with `Ctrl-X`.

## Spec references

- `docs/design/02-architecture.md` §1 (platform facts), §2.2 (client),
  §4 (hello HMAC), §5 (protocol), §7 (rendering and input), §8.2
  (wall-time UX), §11 (client budget).
- `docs/design/03-terminal-ui.md` all sections; §2 layout, §4 menus,
  §5 input, §6 rendering rules, §7 screens outside play, §8 palettes.
- `docs/design/04-assets.md` §4 (art fallback), §7 (fake terminal).
- `docs/world/08-found-texts.md` (title tagline block, first-run screen).

## Scope

- `src/blacksite/door/doorinfo.py`: read `NETBBS_DOOR_INFO`; fields
  `handle`, `user_id`, `terminal_width`, `terminal_height`,
  `color_depth`, `node_name`; every upstream-04 field optional
  (`unicode_style`, `timezone`, `transport`, `node_id`, `door_api`,
  `session_limit_seconds`); `BLACKSITE_INSTALL_DIR` and
  `BLACKSITE_SESSION_LIMIT` from the environment; re-read on `SIGUSR1`
  where available (upstream 03).
- `src/blacksite/door/connection.py`: connect to `DIR/run/blacksite.sock`
  (or the TCP port file), send `hello` with HMAC from `DIR/secrets/
  door.secret`, receive `welcome`, keep `ping` every 10 s, reconnect
  with backoff 1, 2, 4, 8, 16, 30 s up to 60 s total, then the
  "The city is dark right now." screen and exit 0.
- `src/blacksite/door/terminal.py`: raw byte I/O over stdin/stdout
  (binary, unbuffered), enter/leave sequences (alternate screen, hide
  cursor, reset attributes; on exit reset colours, show cursor, clear,
  print "Karst keeps your place."), never enables mouse reporting,
  never emits the bell, refuses below 80×24 with the requirement text.
- `src/blacksite/door/keys.py`: decoder for everything in
  `03-terminal-ui.md` §5.3 (CSI/SS3 arrows, Home/End/PgUp/PgDn in both
  forms, F1–F12, `CSI 1;2 A` shift-arrows, lone `Esc` with 50 ms
  timeout, Ctrl letters, CR/LF/CRLF as Enter, DEL/BS as Backspace, Tab,
  UTF-8 text, mouse and bracketed paste recognised and discarded,
  unknown CSI dropped whole). Output: normalised key names as the
  protocol's `key.k` values (document the name table in the module).
- `src/blacksite/door/cells.py`: `CellBuffer(width, height)` of
  `(glyph, fg, bg, attrs)`; `put(x, y, text, style)` measuring East
  Asian width, refusing wide glyphs at the last column, clipping by
  display width, never writing the last cell of the last row;
  `diff(prev) -> bytes` with cursor-move minimisation and SGR change
  minimisation; `full() -> bytes`.
- `src/blacksite/door/palette.py`: tier resolution (`truecolor`, `256`,
  `16`) from `color_depth` and player settings; palette roles from
  `welcome.palette`; SGR emitters for each tier; the `deutan`/`protan`
  variants.
- `src/blacksite/door/layout.py`: computes header, viewport, side panel,
  log rows, hint row from the terminal size per §2 (56×17 viewport at
  80×24; log rows 3 at height 24 growing to 8 at ≥40).
- `src/blacksite/door/views/`: renderers for `TextView` (title, lines,
  paging), `MenuView` (overlay up to 70×20, cursor row reverse, detail
  pane right at ≥100 columns else below, action bar), log panel, hint
  line, line prompt (local echo, Backspace, Ctrl-U, Esc, Enter, bounded
  200 columns), toast. `ZoneView`/`LatticeView` renderers are S06/S13;
  this slice defines the renderer interface they implement.
- `src/blacksite/door/screens.py`: title screen (art with text fallback
  if `art/title.ans` is missing or too wide), first-run "what is this"
  text, disconnected, banned, session-limit toasts at 5 and 1 minutes
  before `BLACKSITE_SESSION_LIMIT` (default 3600).
- `src/blacksite/door/client.py`: the two pumps (stdin → keys →
  frames; frames → views → render), frame-rate bound of 10 renders/s
  with coalescing, `ack` after each render, `Ctrl-L` full redraw,
  `Ctrl-X` + confirm key to leave, `?` opens help `TextView` from the
  server (or a local fallback page listing the keymap).
- `src/blacksite/door/__main__.py`: wires it all; exit codes 0 for
  every user-facing end, 2 only for a configuration error before the
  terminal is entered (printed as one plain line).
- Fake terminal `tests/fake_terminal.py`: records emitted bytes,
  replays them into a screen model, exposes `screen_text()` and
  `cell(x, y)`.

## Out of scope

- Zone and Lattice renderers (S06, S13).
- Wake screens (S07), dead screen (S10).
- Settings menu persistence (S30); this slice reads settings from
  `welcome` only.

## Data and content

- Uses `palette.json`, `glyphs.json`, `keymaps.json` as delivered in
  `welcome`; ships nothing of its own except the local help fallback.

## Protocol and view models

- Consumes `welcome`, `view` (kinds `text`, `menu`), `delta` (applies
  JSON-patch-like ops; on `base` mismatch sends `intent
  {name: "resync"}`), `log`, `prompt`, `toast`, `bye`, `pong`.
- Produces `hello` (with `caps {width, height, tier, unicode: true}`),
  `key`, `intent` (menu cursor moves, resync, leave), `line`, `ack`,
  `ping`, `bye`.

## Tests

- `tests/door/test_keys.py::test_csi_arrows`, `::test_ss3_arrows`,
  `::test_home_end_both_forms`, `::test_shift_arrows`,
  `::test_lone_escape_timeout`, `::test_enter_variants`,
  `::test_backspace_variants`, `::test_utf8_text`,
  `::test_mouse_discarded`, `::test_bracketed_paste_discarded`,
  `::test_unknown_csi_dropped_whole`.
- `tests/door/test_cells.py::test_wide_glyph_two_cells`,
  `::test_wide_glyph_refused_at_last_column`,
  `::test_never_writes_last_cell`, `::test_clip_by_display_width`,
  `::test_diff_minimal_moves`, `::test_combining_mark_zero_width`.
- `tests/door/test_layout.py::test_80x24`, `::test_132x50`,
  `::test_log_rows_scale`.
- `tests/door/test_palette.py::test_roles_every_tier`,
  `::test_16_colour_bold_bright`, `::test_variants_swap_hues`.
- `tests/door/test_views.py::test_menu_detail_right_at_100_cols`,
  `::test_menu_detail_below_at_80`, `::test_text_paging`,
  `::test_prompt_local_echo_and_cancel`,
  `::test_wide_handle_in_header_truncated_with_ellipsis`.
- `tests/door/test_client.py::test_render_rate_bound_and_coalesce`,
  `::test_delta_base_mismatch_resync`, `::test_reconnect_backoff_then_dark`,
  `::test_session_limit_toasts`, `::test_exit_sequence_bytes`,
  `::test_refuse_below_80x24`.
- Golden screens: `tests/door/golden/title_80x24.txt`, `title_132x50.txt`,
  `menu_80x24.txt`.

## Acceptance script

1. Register the door on a local NetBBS node (native stdio, executable =
   venv python, args `-m blacksite.door`, environment
   `BLACKSITE_INSTALL_DIR`, `max_sessions` 16, `encoding` utf-8).
   Start the server from S03.
2. Enter the door over Telnet at 80×24: title screen, MOTD line, hint
   row. Press `?`: help text pages with PgDn. `Esc` returns.
3. Repeat over SSH and over the web transport; arrows and `Esc` behave
   identically.
4. Resize to 132×50 *before* entering: layout uses the full size.
5. Stop the server: "The city is dark right now." with a countdown;
   after 60 s the door exits to the NetBBS door picker with a clean
   screen.
6. `Ctrl-X`, confirm: clean exit, NetBBS menu redraws correctly.

## Definition of done

- Roadmap §7 holds, including the three transports in step 2–3.
- Client CPU over a 10-minute idle-plus-help session measured under
  20 s (`time` on the door process) and recorded in the PR.

## Implementer notes

- NetBBS relays stdio bytes unmodified and byte by byte; do not rely on
  line buffering. Set stdin/stdout to binary and unbuffered.
- No resize is forwarded today; read the size once and lay out. If
  `SIGUSR1` arrives (upstream 03), re-read `door_info.json` and redo the
  layout with a full redraw.
- `RLIMIT_CPU` is 300 s per door process; rendering must stay lazy
  (render only on new revisions, coalesce). The wall cap is 3600 s
  unless the profile says otherwise; `BLACKSITE_SESSION_LIMIT` is how
  the SysOp tells the client.
- Telnet clients may send CR NUL or CR LF for Enter; the web transport
  (xterm.js) sends CR; SSH sends CR. Handle all three as one Enter.
- The process is reaped unconditionally by NetBBS on any exit path; the
  exit sequence must be sent *before* the client returns from `main()`,
  and flushed.
- Never spawn the server from the client (`AGENTS.md` §8).
- Windows development: use `msvcrt` for raw stdin only under a
  `--local` development flag; the NetBBS path is POSIX stdio.
