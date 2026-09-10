# S09 — Chat and log: channels, prompts, emotes, sitrep, ignore/report

**Status:** planned
**Primary model:** Sonnet · **Reviewer:** none
**Depends on:** S06 · **Milestone:** M1
**Issue:** (filled in when filed)

## Goal

Let players talk: zone say and shout, whisper, the system channel,
emotes, the sitrep list, ignore and report, and the log panel with
scrollback that carries all of it. Faction and crew channels get their
plumbing here and their gating in S20/S22. After this slice two
players in Meridian Plaza can hold a conversation and see who else is
in the city.

## Spec references

- `docs/design/00-game-design.md` §11 (social layer), §14 (chat rate
  limit 4 per 5 s; report to admin log).
- `docs/design/02-architecture.md` §5.3 (`log` frame), §13 (chat
  sanitised, ANSI stripped).
- `docs/design/03-terminal-ui.md` §2 (log rows), §5.1 (chat keys), §5.2
  (line prompts, 200 columns), §6 (truncation by display width).
- `docs/design/01-entities.md` §2.10 (reports), §3.6 (session).

## Scope

- `src/blacksite/server/chat.py`: channels `say` (20-tile radius in the
  zone), `shout` (whole zone), `whisper` (player anywhere by character
  name or BBS handle), `faction` and `crew` (routed to members; S20/S22
  set membership), `system` (server), `zone` (ambient and object lines,
  e.g. S08's tram and S15's "The gate cycles open."); each line has
  `channel, text, role, at`; server-side sanitisation: strip C0/C1 and
  ANSI escapes, normalise NFC, cap 200 display columns; rate limit 4
  lines per 5 s per session with a toast on excess.
- Emotes: fixed list (`wave, nod, shrug, point, salute, sit, laugh,
  glare, bow, spit`) with optional target; rendered on `zone`
  ("Kale_9 waves at you.").
- Sitrep (`W`): `MenuView` of online characters: name, handle, faction
  (or Freelance), zone (or "hidden"), jacked-in flag (S13 sets it);
  players who set `sitrep_hidden` in settings show "hidden" and see
  only "hidden" for others.
- Ignore (`intent ignore {name}`): the ignoring player receives nothing
  from the target on say/shout/whisper/emote; persisted in player
  settings. Report (`intent report {name, text}`): writes a `reports`
  row and a line to `audit.log`; toast "Reported."
- Server-side per-session log ring (500 lines) so a `view` resync or a
  reconnect within 60 s replays the last 50 lines.
- Client: log panel renders the last N lines with channel prefixes
  (`[zone] [say] [sys] [crew] [fac] [whisper]`) in their role colours,
  wrapping long lines by display width; `Shift-L` opens the scrollback
  `TextView` (500 lines, paged); `C`/`Enter` opens the say prompt,
  `` ` `` whisper (prompts for a name then text, or `name: text`),
  `T` crew, `Y` faction; `/me <emote>` and `/<emote> [target]` in the
  say prompt.
- `ZoneView.nearby` becomes real: visible players within sight with
  `role` and `relation` (neutral until S20).

## Out of scope

- Faction membership gating (S20), crew membership (S22).
- Moderation actions on reports: mute/kick/ban (S28).
- Cross-node anything.

## Data and content

- `text/emotes.json` (id, first-person, third-person, targeted forms).

## Protocol and view models

- `intent {name: "chat", args: {channel, text, target?}}`,
  `{name: "emote", args: {id, target?}}`, `{name: "ignore"}`,
  `{name: "report"}`, `{name: "sitrep"}`, `{name: "settings", args:
  {sitrep_hidden}}`.
- `log {lines: [...]}` per §5.3; `prompt {id, kind: "line", label,
  max_len: 200}`.

## Tests

- `tests/server/test_chat.py::test_say_radius_20`,
  `::test_shout_whole_zone`, `::test_whisper_by_handle_or_name`,
  `::test_rate_limit_4_per_5s_toast`, `::test_ansi_stripped`,
  `::test_control_chars_stripped`, `::test_200_columns_cap_display_width`,
  `::test_ignore_blocks_all_channels`, `::test_report_writes_row_and_audit`,
  `::test_ring_replays_50_on_reconnect`.
- `tests/server/test_sitrep.py::test_lists_online_with_zone`,
  `::test_hidden_symmetric`.
- `tests/door/test_log_panel.py::test_wrap_by_display_width`,
  `::test_channel_prefix_colours`, `::test_scrollback_paging`,
  `::test_prompt_swallows_movement_keys`.

## Acceptance script

1. Two callers in Meridian Plaza. A presses `Enter`, types "hello",
   `Enter`: both logs show `[say] A: hello`.
2. B walks 25 tiles away; A's say no longer reaches B; A's shout does.
3. A whispers B by handle; B replies with `` ` ``.
4. `/me waves` and `/wave B` render as third-person lines.
5. `W` lists both with zones; B hides in settings; A sees "hidden".
6. A types six lines quickly: the fifth and sixth are refused with a
   toast.
7. A wide-character handle in a whisper renders without breaking the
   panel at 80×24.

## Definition of done

- Roadmap §7 holds.
- Design doc §11 channel list matches the implementation exactly.

## Implementer notes

- Chat text is untrusted input that will be rendered by every other
  client: sanitise on the server, and still route it through the cell
  buffer's width-safe path on the client (`AGENTS.md` §4).
- Telnet callers may send CR LF or CR NUL for Enter inside a line
  prompt; the key decoder (S04) already normalises this; do not
  re-parse bytes here.
- While a line prompt is open the client must not send movement `key`
  frames (`03-terminal-ui.md` §5.2).
- Keep the log ring per session, not per player, so two sessions of
  the same user within the reconnect window do not double-replay.
