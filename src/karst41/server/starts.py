"""The start a character's archetype gives, and the unread body's (S48)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class UnreadStart:
    """Before the decant record is read: no rig slots, no recovery kit, and
    only the programs every template shares (so the terminal lesson works)."""

    programs: tuple[str, ...] = ()
    hymns: tuple[str, ...] = ()
    rig_slots: int = 0
    recovery_items: dict[str, int] = field(default_factory=dict)


def start_for(content: Any, archetype: str) -> Any:
    start = content.starts.get(archetype)
    if start is not None:
        return start
    shared = None
    for each in content.starts.values():
        shared = set(each.programs) if shared is None else shared & set(each.programs)
    return UnreadStart(programs=tuple(sorted(shared or ())))
