"""P5 chrome: V1 1060c9d adapted to P2 rectangles and P4 log kinds.

UI 2.1/2.4/2.5 and #106's 2026-10-30 decisions govern corrections.
No hint fitting, duplicate geometry, text classifier or clock reads.
"""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any

from blacksite.door.cells import CellBuffer, clean_text, display_width, truncate
from blacksite.door.log import wrap as word_wrap
from blacksite.layout import Layout
from blacksite.door.present.paint import Paint

LINES = {True: ('═', '║', '╔', '╗', '╚', '╟', '╢', '╤'),
         False: ('─', '│', '┌', '┐', '└', '├', '┤', '┬')}
GUTTERS = {'place': '»', 'ambient': '·', 'speech': '"', 'combat': '*',
           'danger': '‼', 'system': '+', 'reward': '√'}
COALESCE_SECONDS = 10.0  # Terminal UI 2.5.
REWARD_SECONDS = 5.0  # Terminal UI 2.5.
PROTECT_SECONDS = 10.0  # Terminal UI 2.5.
NOTICE_SECONDS = 8.0  # Terminal UI 2.5: minimum, plus a key after arrival.


def frame(buffer: CellBuffer, layout: Layout, paint: Paint, safety: str, *,
          side: bool = True, flash: bool = False) -> None:
    h, v, tl, tr, bl, lj, rj, tj = LINES[safety in ('safe', 'pocket')]
    style = paint('hp_critical' if flash else 'frame_' + safety, bold=flash)
    area = layout.frame
    buffer.put(area.x, area.y, tl + h * (area.width - 2) + tr, style)
    for y in range(area.y + 1, area.bottom - 1):
        buffer.put(area.x, y, v, style)
        buffer.put(area.right - 1, y, v, style)
    buffer.put(area.x, area.bottom - 1, bl + h * (area.width - 2), style)
    sep = layout.separator
    buffer.put(sep.x, sep.y, lj + '─' * (sep.width - 2) + rj, style)
    if side:
        divider = layout.divider
        buffer.put(divider.x, area.y, tj, style)
        for y in range(divider.y, divider.bottom):
            buffer.put(divider.x, y, '│', style)
        buffer.put(divider.x, sep.y, '┴', style)


def header(buffer: CellBuffer, layout: Layout, paint: Paint, left: list[tuple[str, str]],
           right: list[tuple[str, str]], *, notice: tuple[str, str, float] | None = None) -> None:
    """Drop low-priority whole segments before shortening the zone."""
    area = layout.header
    if notice:
        # Use the existing right segment ahead of clock/handle. Preserve
        # safety/threat words and room for the zone ellipsis; the normal
        # drop order below removes district/service, then shortens the zone.
        fixed = [clean_text(text) for text, role in left[1:] if text
                 and role != 'head_district' and not (role == 'head_info' and text != 'PvP G5+')]
        # Share scarce width when both names are long; otherwise keep the
        # full zone and give the notice every remaining cell at the right.
        notice_room = min(display_width(clean_text(notice[0])), area.width // 2)
        available = max(0, area.width - display_width(' '.join(fixed)) - bool(fixed) - notice_room - 2)
        zone_room = min(display_width(clean_text(left[0][0])), available) if left else 0
        reserve = display_width(' '.join(fixed)) + zone_room + bool(fixed and zone_room)
        text = truncate(clean_text(notice[0]), max(0, area.width - reserve - 2))
        right = [(text, notice[1])] if text else []
    right_text = ' '.join(clean_text(text) for text, _ in right)
    room = area.width - (display_width(right_text) + 2 if right_text else 0)
    shown = [(clean_text(text), role) for text, role in left if text]
    while display_width(' '.join(text for text, _ in shown)) > room:
        optional = [i for i, (text, role) in enumerate(shown)
                    if role == 'head_district' or role == 'head_info' and text != 'PvP G5+']
        if not optional:
            break
        shown.pop(optional[-1])
    if len(shown) >= 2 and display_width(' '.join(text for text, _ in shown)) > room:
        fixed = display_width(' '.join(text for text, _ in shown[1:])) + 1
        shown[0] = (truncate(shown[0][0], max(0, room - fixed)), shown[0][1])
    shown = [entry for entry in shown if entry[1] == 'head_district'] + [entry for entry in shown if entry[1] != 'head_district']
    x = area.x
    for text, role in shown:
        buffer.put(x, area.y, text, paint(role, bold=role.startswith(('head_zone', 'word_'))))
        x += display_width(text) + 1
    x = area.right - display_width(right_text)
    for text, role in right:
        buffer.put(x, area.y, text, paint(role))
        x += display_width(text) + 1


def rule(buffer: CellBuffer, layout: Layout, paint: Paint, y: int,
         label: str = '', role: str = 'panel_label') -> None:
    area = layout.side
    buffer.put(area.x, y, '─' * area.width, paint('panel_rule'))
    if label:
        buffer.put(area.x + 1, y, f' {label} ', paint(role, bold=role != 'panel_label'))


def bar(buffer: CellBuffer, paint: Paint, x: int, y: int, label: str, value: float,
        maximum: float, role: str, digits: str, width: int = 10) -> None:
    """UI 2.4: ten full/half/empty cells and a number."""
    buffer.put(x, y, label.ljust(4), paint('panel_label'))
    filled = max(0.0, min(1.0, value / max(1, maximum))) * width
    for i in range(width):
        glyph = '█' if i < int(filled) else '▌' if i < filled else '░'
        buffer.put(x + 4 + i, y, glyph, paint(role if i < filled else 'bar_empty'))
    buffer.put(x + 5 + width, y, digits, paint('panel_text'))


@dataclass
class LogEntry:
    kind: str
    text: str
    at: float | None
    arrived: float
    speaker: str = ''
    speaker_role: str = 'log_speaker'
    count: int = 1
    xp: int | None = None

    @property
    def shown(self) -> str:
        return self.text + (f' (x{self.count})' if self.count > 1 else '')


def seconds(line: dict[str, Any]) -> float | None:
    try:
        return datetime.fromisoformat(str(line.get('at', ''))).timestamp()
    except ValueError:
        return None


def digest(lines: list[dict[str, Any]]) -> list[LogEntry]:
    """Declared kinds only; XP formatting never determines a line's kind."""
    out: list[LogEntry] = []
    for line in lines:
        kind = line.get('kind')
        if kind == 'notice':
            continue  # P4 owns notices on the existing toast surface.
        if kind not in GUTTERS:
            kind = 'system'
        text, at = clean_text(str(line.get('text', ''))), seconds(line)
        who, role = str(line.get('speaker', '')), str(line.get('speaker_role', 'log_speaker'))
        arrived = float(line.get('_arrived', -1e30))
        same = next((entry for entry in reversed(out)
                     if at is not None and entry.at is not None and 0 <= at - entry.at <= COALESCE_SECONDS
                     and (entry.kind, entry.text, entry.speaker, entry.speaker_role) == (kind, text, who, role)), None)
        if same:
            same.count += 1
            same.at, same.arrived = at, arrived
            continue
        match = re.fullmatch(r'You gain (\d+) XP\.?', text) if kind == 'reward' else None
        xp = int(match[1]) if match else None
        prev = out[-1] if out else None
        if prev and kind == prev.kind == 'reward' and at is not None and prev.at is not None and 0 <= at - prev.at <= REWARD_SECONDS:
            if xp is not None and prev.xp is not None:
                prev.xp = prev.xp * prev.count + xp
                prev.text = f'{prev.xp} XP'
            else:
                prev.text = prev.shown + '; ' + text
            prev.count = 1
            prev.at, prev.arrived = at, arrived
            continue
        out.append(LogEntry(str(kind), text, at, arrived, who, role, xp=xp))
    return out


def _rows(lines: list[dict[str, Any]], width: int) -> list[tuple[LogEntry, str, bool]]:
    rows = []
    for entry in digest(lines):
        text = entry.shown
        if entry.kind == 'speech' and entry.speaker and not text.startswith(entry.speaker + ': '):
            text = entry.speaker + ': ' + text
        rows.extend((entry, line, index == 0)
                    for index, line in enumerate(word_wrap(text, width - 2, continuation=0)))
    return rows


def _select(rows: list[tuple[LogEntry, str, bool]], height: int,
            now: float) -> list[tuple[LogEntry, str, bool]]:
    if height <= 0:
        return []
    protected = [i for i, (entry, _, _) in enumerate(rows)
                 if entry.kind in ('danger', 'combat') and 0 <= now - entry.arrived < PROTECT_SECONDS]
    selected = set(protected[-height:])
    for index in range(len(rows) - 1, -1, -1):
        if len(selected) >= height:
            break
        selected.add(index)
    return [rows[i] for i in sorted(selected)]


def visible_rows(lines: list[dict[str, Any]], width: int, height: int,
                 now: float) -> list[tuple[LogEntry, str, bool]]:
    return _select(_rows(lines, width), height, now)


def log(buffer: CellBuffer, layout: Layout, paint: Paint, lines: list[dict[str, Any]], now: float) -> None:
    area = layout.log
    for index, (entry, text, first) in enumerate(visible_rows(lines, area.width, area.height, now)):
        y, role = area.y + index, 'log_' + entry.kind
        if first:
            buffer.put(area.x, y, GUTTERS[entry.kind], paint(role, bold=entry.kind == 'danger'))
        if first and entry.kind == 'speech' and entry.speaker:
            speaker = clean_text(entry.speaker)
            if text.startswith(speaker + ': '):
                text = text[len(speaker) + 2:]
            name = truncate(speaker, max(1, area.width - 6))
            buffer.put(area.x + 2, y, name + ': ', paint(entry.speaker_role if paint.has(entry.speaker_role) else 'log_speaker'))
            x = area.x + 4 + display_width(name)
            buffer.put(x, y, truncate(text, area.right - x), paint('log_speech'))
        else:
            buffer.put(area.x + 2, y, text, paint(role, bold=entry.kind == 'danger'))


def hints(buffer: CellBuffer, layout: Layout, paint: Paint, hint: str, role: str = 'key_text') -> None:
    """Host the exact P3 fitter output, including prompts and channels."""
    buffer.put(layout.hint.x, layout.hint.y, truncate(hint, layout.hint.width), paint(role))
