"""S44: a truce's price, stated before it is paid (terminal UI 2.1, 2.5).

One copy of the three canon price lines, shared by the server (the arrival
notice), the door (the first-target notice) and the content validator (the
keeper-name fit). Numbers come from the rule constants, never literals.
"""

from karst41.door.cells import display_width
from karst41.layout import compute
from karst41.server.rules.combat import MARKED_SECONDS

MARKED_MINUTES = MARKED_SECONDS // 60


def arrival(keeper: str) -> str:
    """First arrival in a truce zone, once per character."""
    return f'Fire: {keeper} comes, no Halo. At a player: Marked {MARKED_MINUTES}m, no work.'


def at_player() -> str:
    """Beside TARGET's "Firing marks you"."""
    return f'Fire: Marked {MARKED_MINUTES}m. No Halo, no work.'


def at_npc(keeper: str) -> str:
    """Beside TARGET's "Truce: <Keeper> answers"."""
    return f'Fire here and {keeper} comes. No Halo.'


# The notice's room in the 80x24 header (P4: half the header row). Both
# target lines must fit it; the arrival line fits the hint row.
HEADER_NOTICE_CELLS = compute(80, 24).header.width // 2
HINT_CELLS = compute(80, 24).hint.width
KEEPER_NAME_CELLS = HEADER_NOTICE_CELLS - display_width(at_npc(''))
