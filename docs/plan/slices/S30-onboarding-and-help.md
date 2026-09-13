# S30 — Onboarding and help: hint system, help pages, first-run screen, session-limit UX, colour-blind palettes, settings

**Status:** planned
**Primary model:** Sonnet · **Reviewer:** Human (a first-time player pass by the user)
**Depends on:** S07, S09, S13, S19 · **Milestone:** M6
**Issue:** https://github.com/Thiesi/blacksite/issues/30

## Goal

Make the first hour self-explanatory and the hundredth hour
comfortable. Ship the server-driven hint line, the contextual help
pages, the first-run "what is this" screen, the wall-time warnings and
reconnect UX, the two colour-blind palette variants, and the settings
menu that ties keymap, palette, log verbosity, and sitrep visibility
together. Nothing here changes a rule; it explains them.

## Spec references

- `docs/design/03-terminal-ui.md` §1 (tiers, palette roles and
  variants), §5.1 (two keymaps, rebinding is a settings change), §7
  (title, Wake, dead, disconnected, banned screens), §8 (deutan and
  protan variants; no information by colour alone; relation tags), §10
  (help pages; hint system: first three sessions, next useful key until
  used).
- `docs/design/00-game-design.md` §2 (warn at five and one minutes;
  reconnect resumes), §4 (the Wake must complete in five minutes), §11
  (sitrep visibility trade), §15 (accessibility, no plain mode, refuse
  below 80×24).
- `docs/design/02-architecture.md` §2.2 (reconnect backoff up to 60 s),
  §8.2 (`BLACKSITE_SESSION_LIMIT`, reconnect within 60 s is the same
  session), §5.4 (`hint` in views; `TextView`).
- `docs/design/01-entities.md` §2.1 (`settings`).
- `docs/world/08-found-texts.md` (title tagline block, the 16-line
  first-run screen), `docs/world/07-glossary.md` (in-game glossary
  page), `docs/world/05-story-arcs.md` (Wake briefing text used by S07;
  this slice only adds hints around it).
- `docs/upstream/02-session-limits.md` and `04-door-info-enrichment.md`
  (`session_limit_seconds` if present).

## Scope

- Hint engine (`src/blacksite/server/hints.py`): an ordered list of
  hints keyed by context (zone, lattice, menu kind) and a "used"
  predicate (the player performed the action). For a character's first
  three sessions, the view's `hint` shows the first unused hint for the
  context; afterwards the static key line. Hints: move, target, fire,
  interact, chat, inventory, jack in, program slot, crew invite, sitrep,
  help, map. Stored as a bitset in `settings`.
- Help (`TextView`): `?` opens two pages: keys for the current context,
  then the full keymap; a third page "Glossary" with the glossary
  entries; a fourth "The rules in one page" (safety classes, Marked,
  death, clone debt, secured slots) written from the design doc.
- First-run screen: shown once per BBS user before the Wake, from the
  found-texts asset, any key continues; stored as a flag on the player
  row.
- Session-limit UX (`blacksite.door`): read `BLACKSITE_SESSION_LIMIT`
  (default 3600) or `session_limit_seconds` from `door_info.json` if
  present; `toast` at T−300 s and T−60 s ("The line drops in five
  minutes. Karst keeps your place."); at T−5 s the client sends `bye
  {reason: session_limit}` and exits cleanly so NetBBS's watchdog never
  fires. Server marks the session `resumable` for 60 s.
- Disconnected screen: reconnect countdown with backoff (1, 2, 4, 8…
  up to 60 s total), then "The city is dark right now." and exit 0.
- Palettes: `content/palette.json` gains `deutan` and `protan`
  variants for every role at all three tiers; the nearby list and
  target block show the relation tag (`!`, `~`, `+`) at every tier and
  variant.
- Settings menu (`MenuView`): keymap (arrows/vi), palette (default/
  deutan/protan), tier override (auto/truecolor/256/16), log verbosity
  (all/combat off/chat only), sitrep visibility (visible/hidden),
  reset hints. Changes apply immediately (client re-renders on the
  palette or tier change; a full `view` follows).
- Minimum-size refusal text and the "leave door" confirmation key
  (`Ctrl-X` then `Y`).
- Title screen composition with the tagline block (art itself is S33;
  the text fallback is here).

## Out of scope

- The Wake's own steps and briefing (S07). Chat channels (S09). Art
  (S33). Colour role assignment for new subsystems (each owning slice).
- Platform forwarding of the real limit (upstream 02/04).

## Data and content

- `content/hints.json`: `id, context, text, used_when` (closed set of
  intent names).
- `content/text/help-*.md`, `text-first-run`, `text-rules-one-page`.
- `palette.json` variants; a validator rule that every role exists in
  every tier and variant.

## Protocol and view models

- `hint` field already in `ZoneView`/`LatticeView`/`MenuView`; this
  slice populates it from the engine.
- Intents: `settings.open`, `settings.set {key, value}`, `help.open
  {page}`, `first_run.ack`.
- `welcome.palette` carries the chosen variant; `toast` for limit
  warnings.

## Tests

- `test_hint_engine_shows_first_unused_for_context`
- `test_hints_stop_after_three_sessions`
- `test_hint_marked_used_on_matching_intent`
- `test_help_pages_render_within_80x24_text_view`
- `test_first_run_shown_once_per_user`
- `test_session_limit_toasts_at_300_and_60_seconds` (fake clock)
- `test_client_sends_bye_and_exits_before_limit`
- `test_server_resumes_session_within_60_seconds_without_sleeper_penalty`
- `test_reconnect_backoff_sequence_caps_at_60_total`
- `test_palette_variants_cover_every_role_and_tier`
- `test_relation_tags_present_in_nearby_and_target_at_all_tiers`
- `test_settings_change_triggers_full_view`
- `test_min_size_refusal_message_and_exit_0`
- `test_leave_door_requires_confirmation_key`

## Acceptance script

1. Register a new BBS user, enter the door at 80×24: the first-run
   screen appears once; after the Wake, the hint line says "↑↓←→ move"
   until you move, then "Tab target" and so on.
2. Press `?` in the zone, in the Lattice, and in the inventory: the
   first page differs each time; page 3 is the glossary.
3. Open settings, choose the deutan palette: hostile and crew colours
   change and the `!`/`+` tags remain; switch to 16 colours: the screen
   redraws fully and stays readable.
4. Register the door with `BLACKSITE_SESSION_LIMIT=420` in the profile
   environment: at 2 minutes and at 6 minutes the toasts appear; at 7
   minutes the client leaves cleanly to the door picker; re-enter within
   a minute and you are exactly where you were.
5. Stop the game service while playing: the disconnected screen counts
   down; start it within 30 s: play resumes; stop it for two minutes:
   "The city is dark right now." and the door exits.
6. The user plays as a first-time player for thirty minutes and lists
   every moment they did not know what to press; each becomes a hint or
   a help line in the PR.

## Definition of done

- Tests green; validator covers hints, palette variants, help assets.
- The user's first-time pass recorded and addressed.
- Slice file marked done with PR number.

## Implementer notes

- NetBBS's wall-time watchdog terminates the door at the cap; leaving
  five seconds early avoids the caller seeing a killed process and keeps
  the session record's exit code 0.
- The `session_limit_seconds` field does not exist until upstream 04
  lands; the environment variable is the source of truth meanwhile and
  the SysOp guide must say the two must agree.
- Palette changes must re-render through the cell buffer, not by
  re-emitting the last frame with new colours.
- Keep help text under 76 columns in the source; the client wraps by
  display width anyway but golden screens are easier to read.

## Lore review integration

Use the revised first-run text and terminal UI 11. Teach the lease/grade
distinction, secured recovery and debt, physical-body risk while jacked,
public loan rig, journal provenance, work-order allocation and personal
finale choice. Finish Vesper's job with optional prose closed at 80x24;
repeat at 132x50 and all palette tiers with a wide handle. Each confusion
observed in the human run becomes a concrete UI/content fix, not a claim
that automated tests establish fun or balance.
