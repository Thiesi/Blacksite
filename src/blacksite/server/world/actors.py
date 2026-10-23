"""Live physical actors (entity model section 3.1)."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Actor:
    id: str
    name: str
    handle: str = ""
    kind: Literal["player", "npc", "drone"] = "player"
    zone: str | None = None
    x: int = 0
    y: int = 0
    facing: str = "down"
    # S06 previews use the Hardline starting pools, not a saved character:
    # game design 3.1/3.2: 50 + 2*40 HP; 30 + 20 + 40/2 STA.
    health: int = 130
    health_max: int = 130
    stamina: float = 70
    stamina_max: int = 70
    shock: float = 0
    cooldowns: dict[str, int | float] = field(default_factory=dict)
    modifiers: dict[str, float] = field(default_factory=dict)
    effects: list[dict[str, object]] = field(default_factory=list)
    target: str | None = None
    stance: str = "normal"
    faction: str | None = None
    marked: bool = False
    visible_to: set[str] = field(default_factory=set)
    behaviour: dict[str, object] = field(default_factory=dict)
    owner: str | None = None
    last_sprint_tick: int = -1
    sight_key: tuple[object, ...] | None = None
    visible: set[tuple[int, int]] = field(default_factory=set)
    overweight: bool = False

    @property
    def position(self) -> tuple[int, int]:
        return self.x, self.y


def mission_pair(one: Actor, other: Actor) -> bool:
    """Game 9.3: frozen mission copies cannot collide with or harm outsiders.

    Unscoped S11 actors retain their existing ownership rules. A player
    drone acts for its controller; a mission NPC is not that controller.
    """
    for scoped, observer in ((one, other), (other, one)):
        roster = scoped.behaviour.get('mission_roster')
        if roster is None:
            continue
        if (observer.behaviour.get('mission_roster') is not None
                and observer.behaviour.get('mission') == scoped.behaviour.get('mission')):
            continue
        identity = observer.owner if observer.behaviour.get('player_drone') else observer.id
        if identity not in roster:
            return False
    return True
