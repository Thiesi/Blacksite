"""Cell-width wrapping for the log panel and paged local scrollback."""

from typing import Any

from blacksite.layout import MIN_LOG_WIDTH
from blacksite.door.cells import clean_text, cell_width

PREFIXES = {"system":"sys", "faction":"fac"}


def rows(lines: list[dict[str, Any]], width: int) -> list[dict[str, str]]:
    # Two continuation cells plus a whole two-cell glyph (terminal UI 6).
    if width < MIN_LOG_WIDTH:
        raise ValueError("log width must leave room for an indented wide glyph")
    result = []
    for line in lines:
        prefix = "[" + PREFIXES.get(line.get("channel", "system"), line.get("channel", "system")) + "] "
        text = clean_text(prefix + str(line.get("text", "")))
        indent = ""
        while text:
            used, end = len(indent), 0
            for char in text:
                size = cell_width(char)
                if used + size > width:
                    break
                used += size
                end += 1
            if end == len(text):
                result.append({"text": indent + text, "role": line.get("role", "text")})
                break
            # A space just beyond the fitting prefix is also a valid break.
            # Only an overlong word is split, always between whole glyphs.
            boundary = text.rfind(" ", 0, end + 1)
            if 0 < boundary < end:
                word_width = 0
                for char in text[boundary + 1:]:
                    if char == " ":
                        break
                    word_width += cell_width(char)
                    if word_width > width - 2:
                        boundary = -1
                        break
            if boundary > 0:
                current, text = text[:boundary].rstrip(" "), text[boundary + 1:].lstrip(" ")
            else:
                current, text = text[:end], text[end:]
            result.append({"text": indent + current, "role": line.get("role", "text")})
            indent = "  "
    return result
