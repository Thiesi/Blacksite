"""Terminal colour roles and safe SGR emission (terminal UI §1/§8)."""

from dataclasses import dataclass
from typing import Any

Color = int | tuple[int, int, int]


def resolve_tier(depth: str, requested: str | None = None) -> str:
    tiers = ("16", "256", "truecolor")
    available = depth if depth in tiers else "256"
    if requested in tiers:
        return tiers[min(tiers.index(available), tiers.index(requested))]
    return available


@dataclass(frozen=True)
class Style:
    fg: Color = 7
    bg: Color = 0
    attrs: tuple[int, ...] = ()
    tier: str = "256"

    def sgr(self) -> bytes:
        codes = [0, *(a for a in self.attrs if a in (1, 2, 3, 4, 7))]
        for value, background in ((self.fg, False), (self.bg, True)):
            if isinstance(value, tuple):
                codes.extend((48 if background else 38, 2, *value))
            elif self.tier == "16":
                if value >= 8 and not background:
                    codes.append(1)
                codes.append((100 if value >= 8 else 40) + value % 8 if background else 30 + value % 8)
            else:
                codes.extend((48 if background else 38, 5, value))
        return ("\x1b[" + ";".join(map(str, codes)) + "m").encode("ascii")


class Palette:
    def __init__(self, data: dict[str, Any], tier: str = "256", variant: str = "default") -> None:
        self.roles = data.get("roles", {})
        self.tier = tier
        self.variant = variant if variant in ("default", "deutan", "protan") else "default"
        self.styles: dict[tuple[str, bool], Style] = {}

    def style(self, role: str = "text", *, reverse: bool = False) -> Style:
        role = {"text": "ui_text", "border": "ui_border", "title": "ui_highlight",
                "hint": "ui_highlight", "muted": "ui_dim", "warning": "hp_low"}.get(role, role)
        # Bound the cache to shipped roles plus one fallback, regardless of
        # labels in incoming log lines. Styles are immutable within a palette.
        role = role if role in self.roles else ""
        key = (role, reverse)
        if key in self.styles:
            return self.styles[key]
        raw = self.roles.get(role, {}).get(self.tier, {}).get(self.variant, 7)
        color: Color = 7
        if self.tier == "truecolor" and isinstance(raw, str) and len(raw) == 7 and raw.startswith("#"):
            try:
                color = tuple(int(raw[i:i + 2], 16) for i in (1, 3, 5))
            except ValueError:
                pass
        elif type(raw) is int and 0 <= raw <= (15 if self.tier == "16" else 255):
            color = raw
        style = Style(color, 0, (7,) if reverse else (), self.tier)
        self.styles[key] = style
        return style
