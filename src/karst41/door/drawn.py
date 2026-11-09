"""Width-safe right-aligned state labels for the round 4 demo."""

from karst41.door.cells import CellBuffer, truncate
from karst41.door.palette import Style


def label(buffer: CellBuffer, x: int, y: int, width: int, name: str,
          marker: str, normal: Style, warning: Style) -> None:
    """The name yields cells first; the state word keeps its whole width."""
    if width < len(marker):
        return
    buffer.put(x, y, truncate(name, max(0, width - len(marker) - 1)), normal)
    buffer.put(x + width - len(marker), y, marker, warning)
