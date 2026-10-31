"""P5/P6 styles, from presentation-v1 1060c9d: UI 1, 2.2 and 2.3.

Palette remains the sole role lookup. Dimming is cached per Paint, not
in shared mutable state. P6 caches person lifts against actual region ground.
"""

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, radians, sin

from blacksite.door.palette import Color, Palette, Style
from blacksite.place import Theme

KNOWN_FG, KNOWN_BG = 0.55, 0.62  # Known space: the same hues, about 55-60 per cent light.
BAND_STEP = 8.0  # UI 2.2 / presentation decision, PR #110 comment 6528855270.
HUE_TOLERANCE = 10.0  # Same decision; degrees in CIE LCh.
JACKED_16, HALVARD_16 = 8, 7
PEOPLE_16 = (7, 9, 10, 11, 12, 13, 14, 15, 7, 9, 10, 11, 12, 13, 14, 15)


def theme_roles(theme: Theme, tier: str) -> tuple[str, str, bool]:
    """UI 2.2's actual mapped ground, structure and light-role policy."""
    if tier == '16':
        return 'ground_black', theme.wall_fg or 'wall', False
    return theme.ground_bg or 'ground_black', theme.wall_bg or 'wall_face', theme.luma == 'light'


def _xterm() -> tuple[tuple[int, int, int], ...]:
    base = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128), (0, 128, 128),
            (192, 192, 192), (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255),
            (255, 0, 255), (0, 255, 255), (255, 255, 255)]
    steps = [0, 95, 135, 175, 215, 255]
    cube = [(steps[i // 36], steps[i // 6 % 6], steps[i % 6]) for i in range(216)]
    return tuple(base + cube + [(8 + 10 * i,) * 3 for i in range(24)])


XTERM = _xterm()

# sRGB transfer/XYZ and CIE Lab equations: W3C CSS Color 4, section 19.
# https://www.w3.org/TR/css-color-4/#color-conversion-code
# Use sRGB's D65 reference white directly, as the presentation decision
# requires, rather than CSS Lab's D50 adaptation.
_WHITE = (0.3127 / 0.3290, 1.0, 0.3583 / 0.3290)
_TO_XYZ = ((506752 / 1228815, 87881 / 245763, 12673 / 70218),
           (87098 / 409605, 175762 / 245763, 12673 / 175545),
           (7918 / 409605, 87881 / 737289, 1001167 / 1053270))
_TO_RGB = ((12831 / 3959, -329 / 214, -1974 / 3959),
           (-851781 / 878810, 1648619 / 878810, 36519 / 878810),
           (705 / 12673, -2585 / 12673, 705 / 667))
_EPSILON, _KAPPA = 216 / 24389, 24389 / 27
_ACHROMATIC = 0.0015


def lab(colour: Color) -> tuple[float, float, float]:
    """CIE L*a*b*, sRGB/D65, on the colour actually sent to the tier."""
    rgb = colour if isinstance(colour, tuple) else XTERM[colour]
    linear = tuple(c / 255 / 12.92 if c / 255 <= .04045 else ((c / 255 + .055) / 1.055) ** 2.4
                   for c in rgb)
    xyz = [sum(a * b for a, b in zip(row, linear)) / white for row, white in zip(_TO_XYZ, _WHITE)]
    x, y, z = [v ** (1 / 3) if v > _EPSILON else (_KAPPA * v + 16) / 116 for v in xyz]
    return 116 * y - 16, 500 * (x - y), 200 * (y - z)


def light_distance(colour: Color, ground: Color = 0) -> float:
    """UI 2.2 bands: distance from the ground also works on light grounds.

    P5 ships only dark grounds. P6 must use this same measure for its
    authored _light themes; no theme is introduced by this helper.
    """
    return abs(lab(colour)[0] - lab(ground)[0])


def hue_distance(left: float, right: float) -> float:
    return abs((left - right + 180) % 360 - 180)


def _lch(value: tuple[float, float, float]) -> tuple[float, float, float]:
    light, a, b = value
    return light, hypot(a, b), degrees(atan2(b, a)) % 360


_XTERM_LAB = tuple(lab(rgb) for rgb in XTERM)
_XTERM_LCH = tuple(_lch(value) for value in _XTERM_LAB)


def _linear_rgb(light: float, chroma: float, hue: float) -> tuple[float, ...]:
    angle = radians(hue)
    y = (light + 16) / 116
    f = (y + chroma * cos(angle) / 500, y, y - chroma * sin(angle) / 200)
    xyz = tuple((v ** 3 if v ** 3 > _EPSILON else (116 * v - 16) / _KAPPA) * white
                for v, white in zip(f, _WHITE))
    return tuple(sum(a * b for a, b in zip(row, xyz)) for row in _TO_RGB)


def _gamut_rgb(light: float, chroma: float, hue: float) -> tuple[int, int, int]:
    """Keep L/hue; reduce only chroma until the colour fits sRGB."""
    linear = _linear_rgb(light, chroma, hue)
    if not all(-1e-9 <= channel <= 1 + 1e-9 for channel in linear):
        low, high = 0.0, chroma
        for _ in range(24):
            middle = (low + high) / 2
            trial = _linear_rgb(light, middle, hue)
            if all(0 <= channel <= 1 for channel in trial):
                low = middle
            else:
                high = middle
        linear = _linear_rgb(light, low, hue)
    encoded = [12.92 * c if c <= .0031308 else 1.055 * c ** (1 / 2.4) - .055 for c in linear]
    return tuple(round(max(0.0, min(1.0, c)) * 255) for c in encoded)  # type: ignore[return-value]


def _unreachable(colour: Color) -> Color:
    """An operator's palette may have no legal band: retain its colour.

    Paint caches this result just like a successful lift. Shipped palette
    tests forbid reaching this fallback; a local override must not crash a
    caller's door while rendering (P5 TR-3).
    """
    return colour


def lift(colour: Color, floor: float, tier: str, *, ground: Color = 0,
         ceiling: float | None = None) -> Color:
    """Cached by Paint's callers; never perform LCh conversion per cell."""
    distance = light_distance(colour, ground)
    if distance >= floor and (ceiling is None or distance < ceiling):
        return colour
    source = lab(colour)
    _, chroma, hue = _lch(source)
    ground_light = lab(ground)[0]
    sign = 1 if ground_light < 50 else -1
    target = max(0.0, min(100.0, ground_light + sign * floor))
    rgb = _gamut_rgb(target, chroma, hue)
    if tier == 'truecolor':
        # Quantise first and measure the actual bytes. Advance only enough
        # to clear an 8-bit rounding boundary, keeping the same hue/gamut.
        for step in range(17):
            target = max(0.0, min(100.0, ground_light + sign * (floor + step / 8)))
            rgb = _gamut_rgb(target, chroma, hue)
            shown = light_distance(rgb, ground)
            if shown >= floor and (ceiling is None or shown < ceiling):
                return rgb
        return _unreachable(colour)
    target_lab = lab(rgb)
    fits = [index for index in (range(16) if tier == '16' else range(16, 256))
            if abs(_XTERM_LAB[index][0] - ground_light) >= floor
            and (ceiling is None or abs(_XTERM_LAB[index][0] - ground_light) < ceiling)
            and (chroma <= _ACHROMATIC or _XTERM_LCH[index][1] > _ACHROMATIC)]
    if not fits:
        return _unreachable(colour)
    return min(fits, key=lambda i: (
        hue_distance(_XTERM_LCH[i][2], hue) if chroma > _ACHROMATIC else 0,
        sum((a - b) ** 2 for a, b in zip(_XTERM_LAB[i], target_lab)), i))


@dataclass(frozen=True)
class BandFloors:
    ground: Color
    structure: float
    things: float
    people: float
    jacked: float


def _hue(rgb: tuple[int, int, int]) -> float | None:
    import colorsys
    h, l, sat = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    return h * 360 if sat > 0.15 and max(rgb) - min(rgb) > 12 else None


def nearest(rgb: tuple[int, int, int]) -> int:
    """The 256-colour index for a dimmed colour. The cube has no dark steps
    between 0 and 95, so a plain RGB match turns dim amber olive. Keep the
    hue if the palette can at no more light; otherwise use grey of the same
    lightness, as the 16-colour tier does."""
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
    return choice


class Paint:
    """A palette plus the two things the shipped one does not do: bold and
    the dimmed light of known-but-unseen space."""

    def __init__(self, palette: Palette) -> None:
        self.palette = palette
        self.tier = palette.tier
        self.dims: dict[Style, Style] = {}
        self.lifted: dict[str, Color] = {}
        self.jacked_styles: dict[Style, Style] = {}
        self.styles: dict[tuple[Style, str, bool, bool], Style] = {}
        self._bands: BandFloors | None = None
        self.ground_bands: dict[tuple[str, str], BandFloors] = {}
        self.ground_styles: dict[tuple[str, str, str, bool, bool, bool, bool], Style] = {}
        self.ground_lifts: dict[tuple[str, Color, float, float | None], Color] = {}
        self.theme_policies: dict[Theme, tuple[str, str, bool]] = {}

    @property
    def bands(self) -> BandFloors:
        if self._bands is None:
            ground = self.palette.style('floor').bg
            structure = light_distance(self.palette.style('wall_face').fg, ground)
            things = min((light_distance(self.palette.style(role).fg, ground)
                          for role in self.palette.roles if role.startswith('thing_')),
                         default=structure + BAND_STEP)
            self._bands = BandFloors(ground, structure, things, things + BAND_STEP, structure + BAND_STEP)
        return self._bands

    def __call__(self, role: str, bg: str | None = None, *, bold: bool = False, reverse: bool = False) -> Style:
        # Palette owns lookup and fallback. Always request its non-reversed
        # base, so reversed/normal instances share the one cached colour.
        base = self.palette.style(role, bg=bg)
        person = role if role in self.palette.roles and role.startswith(('npc_', 'player_')) else ''
        key = base, person, bold, reverse
        if key not in self.styles:
            colour = base.fg
            if person:
                if person not in self.lifted:
                    if self.tier == '16':
                        assert isinstance(colour, int)  # Palette's validated 16-colour result.
                        self.lifted[person] = HALVARD_16 if person == 'npc_halvard' else PEOPLE_16[colour]
                    else:
                        self.lifted[person] = lift(colour, self.bands.people, self.tier, ground=self.bands.ground)
                colour = self.lifted[person]
            attrs = (*base.attrs, *((7,) if reverse else ()), *((1,) if bold and self.tier != '16' else ()))
            self.styles[key] = Style(colour, base.bg, attrs, base.tier)
        return self.styles[key]

    def has(self, role: str | None) -> bool:
        return bool(role) and role in self.palette.roles

    def bands_on(self, ground: str, wall: str) -> BandFloors:
        """P6 floors are distances from the actual theme/region ground."""
        key = ground, wall
        if key not in self.ground_bands:
            colour = self.palette.style(ground).fg
            structure = light_distance(self.palette.style(wall).fg, colour)
            # UI 2.2: sign-only lettering is checked against its wall face.
            things = min((light_distance(self.palette.style(role).fg, colour)
                          for role in self.palette.roles
                          if role.startswith('thing_') and not role.startswith('thing_sign_')),
                         default=structure + BAND_STEP)
            self.ground_bands[key] = BandFloors(colour, structure, things,
                                               things + BAND_STEP, structure + BAND_STEP)
        return self.ground_bands[key]

    def on_ground(self, role: str, ground: str, wall: str, *, light: bool = False,
                  bold: bool = False, reverse: bool = False, jacked: bool = False) -> Style:
        """Cache a person lift per role and ground; no per-cell colour math.

        The old call path remains byte-identical for zones without looks.
        An impossible operator palette still uses P5's non-raising lift.
        """
        if self.tier == '16':
            # TR-1 rule 7 is categorical, independent of theme/region L*.
            # Reuse P5's PEOPLE_16/HALVARD_16 and JACKED_16 mappings.
            style = self(role,bold=bold,reverse=reverse)
            return self.jacked(style) if jacked else style
        key = role, ground, wall, light, bold, reverse, jacked
        if key not in self.ground_styles:
            person = role.startswith(('npc_', 'player_'))
            chosen = role + '_light' if person and light and self.has(role + '_light') else role
            base = self.palette.style(chosen, bg=ground)
            colour = base.fg
            if person:
                bands = self.bands_on(ground, wall)
                floor, ceiling = (bands.jacked, bands.people) if jacked else (bands.people, None)
                lift_key = chosen, bands.ground, floor, ceiling
                if lift_key not in self.ground_lifts:
                    if jacked and self.tier == '16':
                        self.ground_lifts[lift_key] = JACKED_16  # UI 2.2 explicit ANSI exception.
                    else:
                        if jacked:
                            colour = self.scale(colour, KNOWN_FG)
                        self.ground_lifts[lift_key] = lift(colour, floor, self.tier,
                                                          ground=bands.ground, ceiling=ceiling)
                colour = self.ground_lifts[lift_key]
            attrs = () if jacked else (*base.attrs, *((7,) if reverse else ()),
                                      *((1,) if bold and self.tier != '16' else ()))
            self.ground_styles[key] = Style(colour, base.bg, attrs, base.tier)
        return self.ground_styles[key]

    def on_theme(self, role: str, theme: Theme, *, bold: bool = False,
                 reverse: bool = False, jacked: bool = False) -> Style:
        ground, wall, light = self.roles_for(theme)
        return self.on_ground(role, ground, wall, light=light, bold=bold, reverse=reverse, jacked=jacked)

    def roles_for(self, theme: Theme) -> tuple[str, str, bool]:
        if theme not in self.theme_policies:
            ground, wall, light = theme_roles(theme, self.tier)
            # A local region role can be light after mapping even if its
            # author left luma at its default. Its people still need _light.
            light = self.tier != '16' and (light or lab(self.palette.style(ground).fg)[0] >= 50)
            self.theme_policies[theme] = ground, wall, light
        return self.theme_policies[theme]

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

    def jacked(self, style: Style) -> Style:
        """Dim first, then keep the body above structure and below people."""
        if style not in self.jacked_styles:
            dimmed = self.known(style)
            colour = JACKED_16 if self.tier == '16' else lift(
                dimmed.fg, self.bands.jacked, self.tier, ground=self.bands.ground,
                ceiling=self.bands.people)
            self.jacked_styles[style] = Style(colour, dimmed.bg, (), self.tier)
        return self.jacked_styles[style]

    def scale(self, value: Color, factor: float) -> Color:
        rgb = value if isinstance(value, tuple) else XTERM[value]
        dimmed = tuple(int(c * factor) for c in rgb)
        return dimmed if self.tier == "truecolor" else nearest(dimmed)  # type: ignore[return-value]
