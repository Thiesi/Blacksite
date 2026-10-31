"""Shared immutable presentation values, with no content loader or I/O."""

from dataclasses import dataclass, replace
from typing import Literal

# Architecture 5.4/5.5.5: charted terrain withheld for any reason carries
# the same ground-only marker, never an interaction or hazard tile id.
CHARTED_GROUND = -3


@dataclass(frozen=True)
class Theme:
    """Entities 1.21: palette roles and deterministic grain only."""

    ground_bg: str | None = None
    ground_fg: str | None = None
    texture: str = "·"
    wall_bg: str | None = None
    wall_fg: str | None = None
    luma: Literal["dark", "light"] = "dark"
    pattern: Literal["grain", "rings"] = "grain"


def theme_over(base: Theme, overlay: Theme) -> Theme:
    return replace(overlay, **{key: getattr(overlay, key) or getattr(base, key)
                             for key in ('ground_bg', 'ground_fg', 'wall_bg', 'wall_fg')})


DEFAULT_THEME = Theme('ground_black', 'floor', '·', 'wall_face', 'wall')
