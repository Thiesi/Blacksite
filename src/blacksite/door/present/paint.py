"""Styles for the proposal 68 renderers: roles, backgrounds, known light."""

from blacksite.door.palette import Color, Palette, Style

KNOWN_FG, KNOWN_BG = 0.55, 0.62  # Known space: the same hues, about 55-60 per cent light.


def _xterm() -> list[tuple[int, int, int]]:
    base = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128), (0, 128, 128),
            (192, 192, 192), (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255),
            (255, 0, 255), (0, 255, 255), (255, 255, 255)]
    steps = [0, 95, 135, 175, 215, 255]
    cube = [(steps[i // 36], steps[i // 6 % 6], steps[i % 6]) for i in range(216)]
    return base + cube + [(8 + 10 * i,) * 3 for i in range(24)]


XTERM = _xterm()
_NEAREST: dict[tuple[int, int, int], int] = {}


def _hue(rgb: tuple[int, int, int]) -> float | None:
    import colorsys
    h, l, sat = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    return h * 360 if sat > 0.15 and max(rgb) - min(rgb) > 12 else None


def nearest(rgb: tuple[int, int, int]) -> int:
    """The 256-colour index for a dimmed colour. The cube has no dark steps
    between 0 and 95, so a plain RGB match turns dim amber olive. Keep the
    hue if the palette can at no more light; otherwise use grey of the same
    lightness, as the 16-colour tier does."""
    if rgb not in _NEAREST:
        light, hue = sum(rgb) / 3, _hue(rgb)
        choice = None
        if hue is not None:
            fits = [i for i in range(16, 232) if (h := _hue(XTERM[i])) is not None
                    and min(abs(h - hue), 360 - abs(h - hue)) <= 20 and sum(XTERM[i]) / 3 <= light * 1.25]
            if fits:
                choice = min(fits, key=lambda i: abs(sum(XTERM[i]) / 3 - light))
        if choice is None:
            choice = min(range(232, 256), key=lambda i: abs(XTERM[i][0] - light))
            if light < 6:
                choice = 16
        _NEAREST[rgb] = choice
    return _NEAREST[rgb]


class Paint:
    """A palette plus the two things the shipped one does not do: bold and
    the dimmed light of known-but-unseen space."""

    def __init__(self, palette: Palette, glyphs: str = "cp437") -> None:
        self.palette = palette
        self.tier = palette.tier
        self.glyphs = glyphs
        """"modern" lets eye-level art use sextants (V0 spike); "cp437" does not."""
        self.dims: dict[Style, Style] = {}

    def __call__(self, role: str, bg: str | None = None, *, bold: bool = False, reverse: bool = False) -> Style:
        style = self.palette.style(role, reverse=reverse, bg=bg)
        if bold and self.tier != "16" and 1 not in style.attrs:
            style = Style(style.fg, style.bg, (*style.attrs, 1), style.tier)
        return style

    def has(self, role: str | None) -> bool:
        return bool(role) and role in self.palette.roles

    def known(self, style: Style) -> Style:
        """Terrain you know but cannot see now. 16 colours cannot dim, so
        known space there is dark grey on black."""
        if style not in self.dims:
            if self.tier == "16":
                dimmed = Style(8 if style.fg != 0 else 0, 0, (), "16")
            else:
                dimmed = Style(self.scale(style.fg, KNOWN_FG), self.scale(style.bg, KNOWN_BG), (), self.tier)
            self.dims[style] = dimmed
        return self.dims[style]

    def scale(self, value: Color, factor: float) -> Color:
        rgb = value if isinstance(value, tuple) else XTERM[value]
        dimmed = tuple(int(c * factor) for c in rgb)
        return dimmed if self.tier == "truecolor" else nearest(dimmed)  # type: ignore[return-value]
