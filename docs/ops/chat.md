# Chat and log (S09)

Blacksite 0.0.5 adds social play to the saved-character service. Start the
service separately and use the registered native stdio door from the
[door guide](door-client.md). The server routes every message; the client
only edits prompts and renders authorized lines.

| Action | Key or say-prompt command |
|---|---|
| Say within 20 tiles | Enter or C |
| Shout to the whole zone | `/shout text` |
| Whisper by character name or BBS handle | backtick, then `name: text` |
| Crew / faction prompt | T / Ctrl-F |
| Free-form emote | `/me waves` |
| Fixed emote, optional target | `/wave name` |
| Online characters | W; H hides/shows your location |
| Scrollback | Ctrl-P; PgUp/PgDn reads, Esc/B returns |
| Ignore / reverse ignore | `/ignore name` / `/unignore name` |
| Report | `/report name: text` |

The fixed emotes are wave, nod, shrug, salute, point, laugh, sigh, bow,
glare and spit. Their first-person and targeted forms are data in
`content/text/emotes.json`. The arrow keymap additionally accepts Y for
faction chat and Shift-L for scrollback; vi retains its sprint keys.

Say uses a 20-tile radius in the same physical zone. Shout and emotes
reach the zone; whispers reach a unique attached character anywhere.
Whispers display both character names and BBS handles. Ambiguous targets
are refused rather than guessed. Crew/faction routing cannot be selected
by naming a group in a request; server membership owns the audience.
Slash commands are interpreted only in the say prompt. Private prompts
never reroute text onto a public channel.
Joining those groups arrives in S20/S22.

Chat and emotes share four lines per five seconds. Reports use that same
budget. Excess lines show a toast. Empty prompts do nothing, and Esc
cancels. Movement keys cannot move your body while you edit a prompt.
Text is sanitized on the server and rendered through width-safe cells.
Long log lines wrap, keeping their channel colours.

Ignore suppresses that BBS identity's social messages, including after a
rename or reconnect. Reversing ignore is explicit and idempotent. Known
offline characters can be ignored or reported. A report is acknowledged
only after its database row and audit entry are written; moderation
actions remain S28 work. Operators find reports in `logs/audit.log` and
the reports table, accessed through the storage/admin layer.
Reports retain BBS identity IDs as well as character IDs, so deleting a
character cannot remove the report's attribution.

Sitrep lists attached characters, including their handle, faction, zone
and body/link state. It shows no tiles. Hiding your location also hides
every other caller's location from your own sitrep. On contested streets
the menu closes after 60 seconds; the world continues while it is open.

Client and server retain 500 log lines. A reconnect within 60 seconds,
or a view resync, replays the last 50 authorized lines. Stable line IDs
prevent duplicate display. History expires with the service process;
private chat is not written to ordinary server logs.

Acceptance uses two callers through a private NetBBS v7.31.0 Telnet node
and registered native stdio door at 80x24 and 132x50:

```powershell
NETBBS_PYTHON scripts/accept_s09_netbbs.py `
  --root .test-tmp/s09-proof --door-python .venv/Scripts/python.exe --show
```

Use a 132x50 parent terminal. The probe completes the Wake, then explicitly
places both physical bodies in the Plaza to isolate social behaviour.
It claims no walking-route test. It walks one caller 25 tiles away,
tests whispers by BBS handle, free/fixed emotes, privacy, four-of-six rate
limiting, scrollback, ignore/report and clean picker return. Result JSON
and four ANSI captures remain under the private root.

NetBBS currently restricts account usernames, and therefore door handles,
to ASCII. The live probe uses real wide-character game names. Headless
and fake-terminal tests additionally cover wide BBS handles, which the
Blacksite protocol supports. No NetBBS code change is needed here.
