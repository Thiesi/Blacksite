"""Pure presence state and tick rules, game design 6.1."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import ceil, hypot

from blacksite.content.schema import Tile
from blacksite.server.clock import TICK_HZ
from blacksite.server.lattice.programs import Cast, Effects

INTEGRITY_MAX = 100
INTEGRITY_PER_SECOND = 5
MOVE_SECONDS = 1.0
MOVE_CORTEX_DIVISOR = 100
MOVE_FLOOR_SECONDS = .2
ESCAPE_SECONDS = 2
ESCAPE_INTERRUPTION_LIMIT = 3


def movement_ticks(cortex: int, multiplier: float = 1) -> int:
    """Apply modifiers before the 200ms floor and integer tick rounding."""
    seconds = max(MOVE_FLOOR_SECONDS, (MOVE_SECONDS-cortex/MOVE_CORTEX_DIVISOR)*multiplier)
    return ceil(round(seconds*TICK_HZ, 8))


def recover_integrity(integrity: float, elapsed_ticks: int) -> float:
    return min(INTEGRITY_MAX, integrity+max(0,elapsed_ticks)*INTEGRITY_PER_SECOND/TICK_HZ)


def directional_neighbour(position: Tile, neighbours: Mapping[str, Tile],
                          direction: Tile) -> str | None:
    """Nearest edge direction, then length and stable identity; no rules in UI."""
    candidates: list[tuple[float,float,str]] = []
    for key, tile in neighbours.items():
        dx,dy = tile[0]-position[0],tile[1]-position[1]
        dot = dx*direction[0]+dy*direction[1]
        length = hypot(dx,dy)
        if dot > 0 and length:
            candidates.append((-dot/length,length,key))
    return min(candidates)[2] if candidates else None


@dataclass
class EscapeChannel:
    until_tick: int
    last_hit: int
    interruptions: int = 0

    def advance(self, tick: int, hit_serial: int) -> bool:
        """After three interrupted casts the next scheduled end is certain."""
        if hit_serial != self.last_hit and self.interruptions < ESCAPE_INTERRUPTION_LIMIT:
            self.last_hit = hit_serial
            self.interruptions += 1
            self.until_tick = tick+ceil(ESCAPE_SECONDS*TICK_HZ)
            return False
        return tick >= self.until_tick


@dataclass
class Procedure:
    kind: str
    target: str
    until: int
    scope: str
    last_hit: int
    generation: int = 0
    source: str = ""
    relay_claim: str = ""


@dataclass
class Presence:
    id: str
    player_id: str
    sector: str
    cell: str
    rig: tuple[str | None, ...]
    integrity: float = INTEGRITY_MAX
    trace: float = 0
    destination: tuple[str,str] | None = None
    move_until: int = 0
    escape: EscapeChannel | None = None
    core: str | None = None
    instance: str | None = None
    room: str | None = None
    room_destination: str | None = None
    effects: Effects = field(default_factory=Effects)
    cast: Cast | None = None
    procedure: Procedure | None = None
    target: str = ""
    hit_serial: int = 0
    pinned_until: int = 0
    opened: set[str] = field(default_factory=set)
    key_tier: int = 0
    risk_consent: set[str] = field(default_factory=set)
    trace_seen: dict[str, set[int]] = field(default_factory=dict)
    redline_move: bool = False
    key_programs: set[str] = field(default_factory=set)
    last_program: str = ""
    descent: str | None = None
    depth: int = 0
    silt_return: tuple[str | None, str | None, str | None] | None = None
    return_cells: dict[int, str] = field(default_factory=dict)
    found_silt: dict[str, set[str]] = field(default_factory=dict)
    survey_records: set[str] = field(default_factory=set)
    surveyed_black: set[tuple[str, str]] = field(default_factory=set)
    """Instance/ICE ids actually surveyed by this caller (architecture 5.5.4)."""
    sampled: set[str] = field(default_factory=set)
    mapping_until: int = 0
    verified_maps: set[str] = field(default_factory=set)
    integrity_max: float = INTEGRITY_MAX
    loaned_rig: bool = False
    jack_source: str = ""
    link_failed: bool = False

    def begin_move(self, sector: str, cell: str, tick: int, cortex: int,
                   multiplier: float = 1) -> bool:
        if self.destination is not None or (sector,cell) == (self.sector,self.cell):
            return False
        self.destination = sector,cell
        self.move_until = tick+movement_ticks(cortex,multiplier)
        self.escape = None
        return True

    def arrive(self, tick: int) -> tuple[str,str] | None:
        if self.destination is None or tick < self.move_until:
            return None
        previous = self.sector,self.cell
        self.sector,self.cell = self.destination
        self.destination = None
        return previous
