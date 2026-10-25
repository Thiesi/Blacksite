"""Frame, header, panel rules, log and hint line (spec sections 4 and 6)."""

from datetime import datetime
from typing import Any

from blacksite.door.cells import CellBuffer, cell_width, clean_text, display_width, truncate
from blacksite.door.layout import Layout
from blacksite.door.present.paint import Paint

LINES = {True: ("═", "║", "╔", "╗", "╚", "╟", "╢", "╤", "╧"), False: ("─", "│", "┌", "┐", "└", "├", "┤", "┬", "┴")}


def frame(buffer: CellBuffer, layout: Layout, paint: Paint, safety: str, *, side: bool = True,
          flash: bool = False) -> None:
    """The outer frame says how safe your body is: line style, colour, word."""
    double = safety in ("safe", "pocket")
    h, v, tl, tr, bl, lj, rj, tj, bj = LINES[double]
    style = paint("hp_critical" if flash else "frame_" + safety if paint.has("frame_" + safety) else "ui_border", bold=flash)
    w, height = layout.width, layout.height
    buffer.put(0, 0, tl + h * (w - 2) + tr, style)
    for y in range(1, height - 1):
        buffer.put(0, y, v, style)
        buffer.put(w - 1, y, v, style)
    buffer.put(0, height - 1, bl + h * (w - 2), style)  # never the bottom-right cell
    buffer.put(0, layout.separator, lj + "─" * (w - 2) + rj, style)
    if side:
        x = layout.side.x - 1
        buffer.put(x, 0, tj, style)
        for y in range(1, layout.separator):
            buffer.put(x, y, "│", style)
        buffer.put(x, layout.separator, "┴", style)


def header(buffer: CellBuffer, layout: Layout, paint: Paint, left: list[tuple[str, str]],
           right: list[tuple[str, str]]) -> None:
    """Segments in priority order; the lowest-priority ones drop first."""
    limit = layout.width - 2
    right_text = " ".join(text for text, _ in right)
    room = limit - 2 - (display_width(right_text) + 2 if right_text else 0)
    x = 2
    for index, (text, role) in enumerate(left):
        need = display_width(text) + (1 if index else 0)
        if x + need > room:
            if index < 2:  # the zone name always shows, shortened if needed
                buffer.put(x + (1 if index else 0), 0, truncate(text, max(0, room - x - 1)), paint(role, bold=True))
            break
        x += 1 if index else 0
        buffer.put(x, 0, text, paint(role, bold=role.startswith(("head_zone", "word_"))))
        x += display_width(text)
    rx = limit - display_width(right_text)
    for text, role in right:
        if rx > x + 1:
            buffer.put(rx, 0, text, paint(role))
        rx += display_width(text) + 1


def rule(buffer: CellBuffer, layout: Layout, paint: Paint, y: int, label: str = "", role: str = "panel_label") -> None:
    x, w = layout.side.x, layout.side.width
    buffer.put(x, y, "─" * w, paint("panel_rule"))
    if label:
        buffer.put(x + 1, y, f" {label} ", paint(role, bold=role != "panel_label"))


def bar(buffer: CellBuffer, paint: Paint, x: int, y: int, label: str, value: float, maximum: float, role: str,
        digits: str, width: int = 10, tick: int | None = None) -> None:
    """`HP  ████████▌░ 87`: whole and half cells, then the number."""
    buffer.put(x, y, label.ljust(4), paint("panel_label"))
    filled = max(0.0, min(1.0, value / max(1, maximum))) * width
    for i in range(width):
        if i == tick:
            glyph, style = "│", paint("panel_strong")
        elif i < int(filled):
            glyph, style = "█", paint(role)
        elif i < filled:
            glyph, style = "▌", paint(role)
        else:
            glyph, style = "░", paint("bar_empty")
        buffer.put(x + 4 + i, y, glyph, style)
    buffer.put(x + 5 + width, y, digits, paint("panel_text"))


# --- the log ---------------------------------------------------------------

GUTTERS = {"place": "∙", "ambient": "∙", "speech": '"', "combat": "*", "danger": "‼", "system": "+", "lattice": "∙"}
CHAT = {"say", "whisper", "crew", "faction", "lat"}


def kind(line: dict[str, Any]) -> str:
    """The log channel a line belongs to (spec 6.3). Servers may say so
    with `kind`; older lines are classified by channel and role."""
    if line.get("kind") in GUTTERS:
        return str(line["kind"])
    channel, role, text = line.get("channel", "system"), line.get("role", ""), str(line.get("text", ""))
    if role in ("warning", "hp_low", "hp_critical", "player_hostile"):
        return "danger"
    if channel in CHAT and channel != "lat":
        return "speech"
    if channel == "lat":
        return "lattice"
    if channel == "system" or (text.startswith("You gain ") and " XP" in text):
        return "system"
    return "combat"


def _seconds(line: dict[str, Any]) -> float | None:
    try:
        return datetime.fromisoformat(str(line.get("at", ""))).timestamp()
    except ValueError:
        return None


def digest(lines: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """(kind, text): identical lines within 10 s coalesce, XP within 5 s merges."""
    out: list[list[Any]] = []  # kind, text, count, at, xp
    for line in lines:
        k, text, at = kind(line), clean_text(str(line.get("text", ""))), _seconds(line)
        xp = None
        if text.startswith("You gain ") and " XP" in text:
            try:
                xp = int(text.split(" ")[2])
            except (IndexError, ValueError):
                xp = None
        prev = out[-1] if out else None
        near = prev is not None and at is not None and prev[3] is not None
        if prev and prev[1] == text and (not near or at - prev[3] <= 10):
            prev[2] += 1
            prev[3] = at
            continue
        if prev and xp is not None and prev[4] is not None and (not near or at - prev[3] <= 5):
            prev[4] += xp
            prev[1] = f"{prev[4]} XP"
            prev[3] = at
            continue
        out.append([k, f"{xp} XP" if xp is not None else text, 1, at, xp])
    return [(k, text + (f" (x{count})" if count > 1 else "")) for k, text, count, _, _ in out]


def log(buffer: CellBuffer, layout: Layout, paint: Paint, lines: list[dict[str, Any]], tint: str | None = None) -> None:
    rows: list[tuple[str, str, bool]] = []
    width = layout.log.width - 2
    for k, text in digest(lines[-40:]):
        current, used, first = "", 0, True
        for char in text:
            size = cell_width(char)
            if used + size > width:
                rows.append((k, current, first))
                current, used, first = "", 0, False
            current += char
            used += size
        rows.append((k, current, first))
    for index, (k, text, first) in enumerate(rows[-layout.log.height:]):
        y = layout.log.y + index
        role = "log_lattice" if k == "lattice" and tint is None else "log_" + k
        if first:
            buffer.put(layout.log.x, y, GUTTERS.get(k, " "), paint(role if k != "system" else "log_system"))
        if k == "speech" and ": " in text and first:
            who, said = text.split(": ", 1)
            buffer.put(layout.log.x + 2, y, who + ":", paint("log_speaker"))
            buffer.put(layout.log.x + 4 + display_width(who), y, said, paint(role))
        else:
            buffer.put(layout.log.x + 2, y, text, paint(role, bold=k == "danger"))


def hints(buffer: CellBuffer, layout: Layout, paint: Paint, hint: str) -> None:
    """Key caps bright, labels quiet: `E interact  M map  ? help`."""
    x, limit = 1, layout.width - 2
    for chunk in [c for c in hint.replace(": ", " ").split("  ") if c.strip()]:
        key, _, label = chunk.strip().partition(" ")
        need = display_width(chunk.strip()) + 2
        if x + need > limit:
            break
        if len(key) <= 6 and label:
            buffer.put(x, layout.hint, key, paint("key_cap", bold=True))
            buffer.put(x + display_width(key) + 1, layout.hint, label, paint("key_text"))
        else:
            buffer.put(x, layout.hint, chunk.strip(), paint("key_text"))
        x += need
