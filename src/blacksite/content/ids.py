"""Content ID rules.

Content IDs (zones, sectors, cores, factions, NPCs, contracts, events,
text and art assets, dialogue, bundles) are hyphenated slugs
(04-assets.md section 8). Table records from the catalog (items,
programs, ICE, hymns) may also use the underscore form the catalog uses,
such as `wpn_kestrel_sidearm` (00-game-design.md section 17).
"""

import re
import unicodedata
from typing import Final

SLUG_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CATALOG_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z]+_[a-z0-9_]+$")

# Kinds whose IDs may use the catalog's underscore form.
CATALOG_KINDS: Final[frozenset[str]] = frozenset({"item", "program", "ice", "hymn"})


def is_slug(value: str) -> bool:
    """A hyphenated content slug: `core-plaza`, `text-ration-1`."""
    return bool(SLUG_RE.fullmatch(value))


def is_catalog_id(value: str) -> bool:
    """A catalog table ID: `wpn_kestrel_sidearm`, `prg_pick`."""
    return bool(CATALOG_RE.fullmatch(value))


def valid_id(kind: str, value: str) -> bool:
    """Whether `value` is a legal ID for content of `kind`."""
    if kind in CATALOG_KINDS:
        return is_catalog_id(value) or is_slug(value)
    return is_slug(value)


def display_width(char: str) -> int:
    """Terminal cells one character takes, by the client's rule.

    East Asian wide and fullwidth characters take two cells; combining
    marks and other zero-width characters take none (03-terminal-ui.md
    section 6).
    """
    if unicodedata.combining(char) or unicodedata.category(char) in ("Mn", "Me", "Cf"):
        return 0
    if unicodedata.east_asian_width(char) in ("W", "F"):
        return 2
    return 1
