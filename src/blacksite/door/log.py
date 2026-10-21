"""Cell-width wrapping for the log panel and paged local scrollback."""

from typing import Any

from blacksite.door.cells import clean_text, cell_width

PREFIXES = {"system":"sys", "faction":"fac"}


def rows(lines: list[dict[str, Any]], width: int) -> list[dict[str, str]]:
    result = []
    for line in lines:
        prefix = "[" + PREFIXES.get(line.get("channel", "system"), line.get("channel", "system")) + "] "
        text = clean_text(prefix + str(line.get("text", "")))
        current, used = "", 0
        for char in text:
            size = cell_width(char)
            if used + size > width:
                result.append({"text": current, "role": line.get("role", "text")})
                current, used = "  ", 2
            current += char
            used += size
        result.append({"text": current, "role": line.get("role", "text")})
    return result
