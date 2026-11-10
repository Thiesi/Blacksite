# P12 — Talk lines and log entries are never cut

**Status:** proposed (owner finding, round 4 demo, 2026-11-10; spec in
#185 comment 6755448631; technical lead agreed to a separate P-slice)
**Primary model:** Codex · **Reviewer:** automated review, technical lead, presentation lead (presentation acceptance)
**Depends on:** P5 (merged) · **Lands before:** the talk content in the Row rules slice (V Trade, Ask about…) · **Milestone:** presentation track

Canon: terminal UI 2.5 (the log) and the talk page as S42 left it. Where
this file and canon differ, canon wins.

## Goal

A line someone says to you can always be read in full, on the page where
it was said. The talk page has room for more actions, because Talk now
always offers something (owner decision, 2026-11-10).

## What's wrong today

| Surface | 80x24 | 132x50 |
|---|---|---|
| Talk page line (`menu()` detail) | One row, cut at 66 cells, though the detail rect has 4 rows | One row, cut at 53 cells, in a narrow column with an empty listing beside it |
| Talk actions | One row, cut at 66. It says both `b Back` and `Esc/B back` | Same, at 106 |
| Log | Wraps, but it picks the newest **rows**, not entries. With 3 rows an older entry loses its head first, and protected danger/combat rows can cut out its middle | 8 rows, same rule |

255 of the 405 shipped and round 4 dialogue lines are cut on the 80x24
talk page, and 338 at 132x50. The longest is 164 characters. At 66 cells,
every one of them wraps to 3 rows or fewer. Ctrl-P scrollback already
works on every screen, the talk page included, and holds the full text,
but nothing points to it.

Both renderers have the bug. The default door still uses the old one
(`views/__init__.py` `render_menu`, `chrome.render_frame` with
`log.rows`), and the new presentation (`present/screen.py` `menu()`,
`present/chrome.py` `_select`) is opt-in until P10. **This slice fixes
both.** The old renderer gets the same rules through shared helpers, so P10
inherits them.

## Scope

**1. The talk line wraps and uses the whole page.** For `kind ==
'talker'` (no rows), the line starts at the top of the listing area and
takes the full inner width: 66 cells and 13 rows at 80x24, 106 cells at
132x50. It word-wraps, with no quotes and no brackets. If a line ever
needs more rows than it has, the last row ends with `…`, and the full line
is still in the log. Rule 4 keeps shipped content from reaching that
fallback.

**2. Talk actions are a vertical list under the line,** one per row,
after one blank row, with a single leave row last:

```
┌─ Dolf - Tin Halo ────────────────────────────────────────────────┐
│                                                                  │
│ Back room's on Vesper's system. Jack in from the board if you    │
│ want out the quiet way.                                          │
│                                                                  │
│ v  Trade                                                         │
│ a  Ask about the back room                                       │
│ Esc/B  Leave                                                     │
```

- **Key column:** the key in `key_text`, two spaces, then the label in
  panel text. Key and label are aligned across rows. The key column is
  as wide as the widest key, so `Esc/B` sets it on a page with no offers.
- **One leave row,** `Esc/B  Leave`. The client drops its
  `  Esc/B back` suffix on the talk page.
- **The one server-side change:** `server/dialogue_runtime.py`
  `publish()` stops appending `{'key': 'b', 'label': 'Back'}` to talker
  actions. `b` and `Esc` still close the page through the client's
  existing menu routing. A walk-away page still leaves on a move. No
  other server code changes in this slice.
- **Labels:** at most 40 cells. Validated in rule 4.
- **Keys:** offer hotkeys stay page-local, and an offer key still wins
  over a move binding, as today. Shipped recruiters use `j`, which is
  vi's move down, so on those pages vi's `j` takes the offer and every
  other move key still walks. New offers use `v` Trade and `a` Ask about.
  No offer may use `b` (the leave key) or repeat another offer's key on the
  same talker. Validated in rule 4.
- **Other menus** (vendors, contracts, Wake) keep their one-row actions
  bar. Only the talker page changes.

**3. Every menu's detail wraps.** Both `menu()` functions word-wrap each
detail line inside the detail rect instead of cutting it. Rows past the
rect's height follow rule 1's `…` fallback. Vendors, contracts and the
Wake get this for free. Their goldens change where a detail used to be
cut.

**4. A content fit check in the validator.**
- Every dialogue `text` wraps to **4 rows or fewer at 66 cells**, using
  the client's own wrap. That's the 80x24 talk width, with a row to spare
  over today's longest line.
- Every offer label is at most 40 cells.
- No offer hotkey is `b`, and no talker has two offers on the same key.
  The validator already checks both (`content/validate.py`, case
  insensitive). Keep that check; only the row and label checks are new.

The validator reports the talker, the line id and the row count, so the
creative lead's new answers fail at authoring time, not in play.

**5. The log shows whole entries.** Both renderers select **entries**,
not rows. An entry is shown complete or not at all.
- **The newest entry always shows,** at least its first row. A line just
  said is never pushed off the page. Selection runs in this order:
  1. Reserve one row for the newest entry.
  2. Protected danger and combat entries (within `PROTECT_SECONDS`, as
     `_select` judges now) fill the remaining rows, newest first, whole
     only.
  3. The newest entry takes back any rows still free, up to its full
     height.
  4. Other entries fill whatever is left, newest first, whole only.
- **Cut newest entry:** if the newest entry gets fewer rows than it needs,
  its first rows show and the last of them ends with `… Ctrl-P`. This is
  the only entry that is ever shown in part.
- Rows display in arrival order, newest at the bottom.
- If the newest entry is itself protected, it's still handled in step 1.
- Continuation rows keep today's look: no gutter, indented to the text.
- Coalescing (`(x2)`) and the XP merge are unchanged.

**6. The way to the full text.** Ctrl-P already works everywhere. The
`… Ctrl-P` marker from rule 5 points to it where it's needed. The help
page keeps its row. The hint line doesn't change; it's already full at
80x24.

## Out of scope

- New dialogue content: the V Trade and Ask about… lines and offers are
  the Row rules slice's. That slice lays its actions out on this page.
- The long tutorial objective cut with "..." in the header and hint row.
  It's a separate item in the presentation queue.
- Sidebar truncation (names, the WEAPON section). That has its own
  P-slice.
- Scrollback layout. Ctrl-P is unchanged.

## Tests

- **Talk page, both renderers, 80x24 and 132x50:** the longest shipped
  line (164 characters) with 0, 1 and 3 actions. No cell of the line is
  cut, there's exactly one leave row, and no `b Back`.
- **Fallback:** a synthetic 20-row line ends its last visible row with
  `…`.
- **Server:** `publish()` sends no `b` action for talkers. Update
  fixtures that still carry it, such as `tests/door/test_dialogue_render.py`. `b` and `Esc`
  still close the page. A move still walks away, and an offer key still
  wins over a move binding.
- **Menu detail wrap:** a vendor or contract detail longer than one row
  wraps inside its rect at both sizes.
- **Validator:** it rejects a 5-row line, a 41-cell label, an offer on
  `b` and a repeated key on one talker, and it passes every shipped
  dialogue file.
- **vi `j` on a recruiter page:** it takes the offer. `k` still walks
  away.
- **Log, both renderers, 80x24:**
  - A 2-row speech entry followed by a 2-row ambient entry shows only
    the newer one whole, and no headless rows.
  - With a protected danger line plus two speech entries, every entry
    shown is complete.
  - A newest entry taller than the log shows its head and `… Ctrl-P`.
  - **Three 1-row combat lines, all protected, then a 1-row speech
    line:** the speech line shows on the bottom row, with the two newest
    combat lines above it. The same case with a 2-row speech line shows
    the speech's first row ending `… Ctrl-P`, plus the two newest combat
    lines.
- **Goldens:** regenerated where a detail or log screen changes. The PR
  lists them.

## Captures I'll accept

Native, through NetBBS Telnet to native stdio, at **80x24 and 132x50**,
in the new presentation and the default renderer, as TXT plus raw ANSI:

1. **Halo runner bark on the talk page:** "Back room's on Vesper's
   system. Jack in from the board if you want out the quiet way." whole,
   with no `b Back` (the owner's case). On main without the round 4 overlay,
   use the longest shipped line instead (the dispatcher, 164 characters).
2. **Vesper's talk page** with her offers as the vertical list and one
   `Esc/B  Leave`.
3. **The log at 80x24** right after that talk line plus a following
   line, showing no headless entry.
4. **A vendor page** whose detail wraps.

At 132x50 the talk line should span the full width, not the old 53-cell
column. I'll judge the look from these captures. A 16-colour capture of
1 is enough for that tier.

## Definition of done

Roadmap §7: the tests above, automated review triage, the technical
lead's record and the presentation lead's acceptance from the captures.
The PR says which renderer each capture used. H1 and S25 layout approval
are not part of this slice and aren't granted by it.
