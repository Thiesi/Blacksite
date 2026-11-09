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
        self.styles: dict[tuple[str, bool] | tuple[str, bool, str], Style] = {}

    def style(self, role: str = "text", *, reverse: bool = False, bg: str | None = None) -> Style:
        role = {"text": "ui_text", "border": "ui_border", "title": "ui_highlight",
                "hint": "ui_highlight", "muted": "ui_dim", "warning": "hp_low"}.get(role, role)
        # Bound the cache to shipped roles plus one fallback, regardless of
        # labels in incoming log lines. Styles are immutable within a palette.
        role = role if role in self.roles else ""
        bg = bg if bg in self.roles else None
        key = (role, reverse) if bg is None else (role, reverse, bg)
        if key in self.styles:
            return self.styles[key]
        color = self.colour(role, 7)
        back = self.colour(bg, 0) if bg else 0
        # Terminal UI 1: backgrounds at 16 colours are restricted to 0-7.
        if self.tier == '16' and isinstance(back, int) and back > 7:
            back = 0
        style = Style(color, back, (7,) if reverse else (), self.tier)
        self.styles[key] = style
        return style

    def colour(self, role: str, fallback: int) -> Color:
        """The one palette lookup for foreground and background roles."""
        raw = self.roles.get(role, {}).get(self.tier, {}).get(self.variant, fallback)
        if self.tier == "truecolor" and isinstance(raw, str) and len(raw) == 7 and raw.startswith("#"):
            try:
                return tuple(int(raw[i:i + 2], 16) for i in (1, 3, 5))
            except ValueError:
                return fallback
        elif type(raw) is int and 0 <= raw <= (15 if self.tier == "16" else 255):
            return raw
        return fallback
