"""P12: shared fitting rules for talk lines, menu details and the log.

Both renderers (the default door views and the opt-in presentation) use
these helpers, so P10 inherits one rule instead of two copies. Cut text
is marked with ASCII `...`, as terminal UI canon says for truncation
(03-terminal-ui.md); CP437 has no single-glyph ellipsis.
"""

from collections.abc import Callable, Sequence
from typing import Any
from dataclasses import dataclass

from karst41.door.cells import display_width, truncate
from karst41.door.log import rows as log_rows, wrap

CUT = '...'
LOG_CUT = '... Ctrl-P'
LEAVE_KEY, LEAVE_LABEL = 'Esc/B', 'Leave'
# P12 rule 4: every dialogue line fits the 80x24 talk page in this many
# rows, a row to spare over the longest shipped line.
TALK_LINE_ROWS = 4
# P12 rule 2: offer labels on the talk page are at most this wide.
TALK_LABEL_CELLS = 40


def wrap_text(text: str, width: int) -> list[str]:
    """Word-wrap each line of text, keeping blank lines as empty rows."""
    rows: list[str] = []
    for line in str(text).splitlines():
        rows.extend(wrap(line, width, continuation=0) or [''])
    return rows


def mark(row: str, width: int, marker: str = CUT) -> str:
    """End a row with marker, cutting its text so the result fits width."""
    room = max(0, width - display_width(marker))
    return truncate(row, room, ellipsis=False).rstrip(' ') + marker


def fit(rows: Sequence[str], width: int, height: int, marker: str = CUT) -> list[str]:
    """At most height rows; when rows are dropped the last kept one ends with marker."""
    if height <= 0:
        return []
    if len(rows) <= height:
        return list(rows)
    return [*rows[:height - 1], mark(rows[height - 1], width, marker)]


def fit_text(text: str, width: int, height: int) -> list[str]:
    """P12 rule 3: a menu detail wraps inside its rect, `...` past its height."""
    return fit(wrap_text(text, width), width, height)


@dataclass(frozen=True)
class TalkRow:
    """One row of a talker page: either line text or a key and its label."""
    text: str = ''
    key: str = ''
    label: str = ''


def talk_rows(line: str, actions: Sequence[dict[str, str]], width: int, height: int) -> list[TalkRow]:
    """P12 rules 1 and 2: the wrapped line, a blank row, then one action per row.

    The key column is as wide as the widest key, so `Esc/B` sets it on a
    page with no offers. One leave row closes the list.
    """
    pairs = [(str(a.get('key', '')), str(a.get('label', ''))) for a in actions]
    pairs.append((LEAVE_KEY, LEAVE_LABEL))
    column = max(display_width(key) for key, _ in pairs)
    listed = [TalkRow(key=key + ' ' * (column - display_width(key)) + '  ',
                      label=truncate(label, max(0, width - column - 2))) for key, label in pairs]
    text = wrap_text(line, width) if str(line).strip() else []
    if not text:
        return listed[-height:] if height > 0 else []
    room = max(0, height - len(listed) - 1)
    shown = [TalkRow(text=row) for row in fit(text, width, room)]
    return [*shown, TalkRow(), *listed][:max(0, height)]


# P12 rule 5 bound (technical review 6808753030): unprotected entries are
# looked for at most this many entries per log row behind the newest one.
# A 500-line ring of ordinary lines then costs at most
# LOG_LOOKBACK_PER_ROW * height + 1 wraps per render, never the whole
# ring; 1-row entries stop after `height`. Protected entries are never
# bounded by it: each one still inside PROTECT_SECONDS is considered.
LOG_LOOKBACK_PER_ROW = 2
# The presentation log digests (coalesces) this many newest lines per
# lookback entry, so a full ring never costs a full digest. A run of identical lines longer than the
# window shows a lower (xN) count in the log; Ctrl-P scrollback still has
# every line.
LOG_DIGEST_LINES_PER_ENTRY = 4
# Past that window, the presentation log reaches back for still-protected
# lines only until it holds `height` distinct ones (no more can show), and
# never more than this many extra lines. 100 is about ten seconds of heavy
# combat (10 Hz ticks, several shooters). A protected line further back
# than that, behind a flood of newer unprotected lines, can drop early.
LOG_PROTECT_EXTRA = 100


def log_window(height: int) -> int:
    """Newest log lines the presentation log digests at this log height."""
    return LOG_DIGEST_LINES_PER_ENTRY * (LOG_LOOKBACK_PER_ROW * max(0, height) + 1)


def select_lazy(count: int, rows_of: Callable[[int], Sequence[Any]],
                protected: Callable[[int], bool], height: int) -> dict[int, int]:
    """P12 rule 5 (#202): rows each shown entry gets, by index; absent hides it.

    The newest entry always gets at least one row. Protected entries then
    fill what's left, newest first and whole only; the newest takes back
    free rows; other entries fill the rest, newest first and whole only.
    A protected newest entry takes rows up to its full height first. Only
    the newest entry is ever shown in part. An entry that doesn't fit whole
    is skipped and the pass goes on to older ones, as steps 2 and 4 say:
    "fill the remaining rows", "fill whatever is left".

    Work is bounded: `rows_of` (the wrap) is called newest first, only
    for entries the passes reach, and each pass stops once the rows are
    full. The protected pass wraps only protected entries; the pass for
    other entries looks back at most LOG_LOOKBACK_PER_ROW * height
    entries. `protected` must be cheap and must not wrap.
    """
    shown: dict[int, int] = {}
    if height <= 0 or count <= 0:
        return shown
    heights: dict[int, int] = {}

    def size(index: int) -> int:
        if index not in heights:
            heights[index] = len(rows_of(index))
        return heights[index]

    newest = count - 1
    oldest = max(0, newest - LOG_LOOKBACK_PER_ROW * height)
    shown[newest] = min(size(newest), height) if protected(newest) else min(1, size(newest))
    left = height - shown[newest]

    def fill(want_protected: bool, left: int) -> int:
        for index in range(newest - 1, -1 if want_protected else oldest - 1, -1):
            if left <= 0:
                break
            if protected(index) != want_protected or size(index) > left:
                continue
            shown[index] = size(index)
            left -= size(index)
        return left

    left = fill(True, left)
    extra = min(size(newest) - shown[newest], left)
    shown[newest] += extra
    left -= extra
    fill(False, left)
    return {index: rows for index, rows in shown.items() if rows}


def select_entries(heights: Sequence[int], protected: Sequence[bool], height: int) -> list[int]:
    """select_lazy over known heights, as a list in arrival order; 0 hides."""
    shown = select_lazy(len(heights), lambda i: range(heights[i]), lambda i: protected[i], height)
    return [shown.get(index, 0) for index in range(len(heights))]


def log_cut(rows: list[str], shown: int, width: int) -> list[str]:
    """The newest entry's first rows, the last ending `... Ctrl-P` if cut."""
    if shown >= len(rows):
        return rows
    return fit(rows, width, shown, LOG_CUT)


def default_log_rows(lines: Sequence[dict[str, Any]], width: int, height: int) -> list[dict[str, str]]:
    """The default renderer's log under rule 5: whole entries, newest always shown.

    Its lines carry no arrival time, so nothing is protected here (P12
    ruling Q2, #202 6805937648); the presentation log protects. Only the
    entries select_lazy reaches are wrapped.
    """
    lines = list(lines)
    wrapped: dict[int, list[dict[str, str]]] = {}

    def rows_of(index: int) -> list[dict[str, str]]:
        if index not in wrapped:
            wrapped[index] = log_rows([lines[index]], width)
        return wrapped[index]

    shown = select_lazy(len(lines), rows_of, lambda index: False, height)
    out: list[dict[str, str]] = []
    for index in sorted(shown):
        rows, count = wrapped[index], shown[index]
        if index == len(lines) - 1 and count < len(rows):
            texts = log_cut([row['text'] for row in rows], count, width)
            rows = [{**row, 'text': text} for row, text in zip(rows, texts)]
        out.extend(rows[:count])
    return out
