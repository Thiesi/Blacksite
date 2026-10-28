"""Zone state and composable geometry (architecture 6.1 and 15.2)."""

from collections import deque
from dataclasses import dataclass, field
from collections.abc import Callable
import random

from blacksite.content.schema import ObjectSpec, Tile, TileType, Zone, ZoneLayout
from blacksite.server.world.actors import Actor
from blacksite.server.clock import TICK_HZ

DOOR_KINDS = ("door", "apartment_door", "shutter", "gate")

MIN_HAZARD_WARNING_TICKS = 5 * TICK_HZ  # Game design 7.7 / entity controls.


@dataclass
class ObjectState:
    spec: ObjectSpec
    open: bool | None = None
    in_use: str | None = None
    progress: int = 0
    state: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class GeometryLayer:
    source: str
    layout: ZoneLayout
    starts: int
    expires: int


@dataclass
class ZoneInstance:
    template: Zone
    tiles: dict[str, TileType]
    seed: int
    tick: int = 0
    actors: dict[str, Actor] = field(default_factory=dict)
    objects: dict[str, ObjectState] = field(default_factory=dict)
    caches: dict[str, object] = field(default_factory=dict)
    salvage_nodes: dict[str, object] = field(default_factory=dict)
    listeners: set[str] = field(default_factory=set)
    layers: dict[str, GeometryLayer] = field(default_factory=dict)
    geometry: dict[Tile, str] = field(default_factory=dict)
    revision: int = 0
    entry_policy: Callable[[Actor | None, Tile], bool] = field(default=lambda actor, tile: True, repr=False)
    # None identifies public ground allowed to every actor. Actor policies
    # may additionally admit private floors; they cannot deny public ground.
    position_update: Callable[[Actor], None] = field(default=lambda actor: None, repr=False)
    escape_origin: Callable[[Actor], Tile] = field(default=lambda actor: actor.position, repr=False)
    geometry_revision: int = 0
    rng: random.Random = field(init=False, repr=False)
    doors: dict[Tile, ObjectState] = field(init=False, repr=False)
    base_opaque: set[Tile] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.objects = {spec.id: ObjectState(spec, spec.params.get("open", self.tiles[self.template.tile_at(spec.tile)].passable) if spec.kind in DOOR_KINDS else None)
                        for spec in self.template.meta.objects}
        self.doors = {obj.spec.tile: obj for obj in self.objects.values() if obj.spec.kind in DOOR_KINDS}
        self.base_opaque = {(x, y) for y, row in enumerate(self.template.grid) for x, key in enumerate(row)
                            if self.tiles[key].opaque}

    @property
    def id(self) -> str:
        return self.template.id

    @property
    def dormant(self) -> bool:
        return not self.listeners and not self.layers

    def wake(self, tick: int) -> int:
        if tick < self.tick:
            raise ValueError("zone ticks cannot go backwards")
        elapsed = tick - self.tick
        self.tick = tick
        return elapsed

    def activate(self, listener: str, tick: int) -> int:
        elapsed = self.wake(tick) if not self.listeners else 0
        self.listeners.add(listener)
        return elapsed

    def deactivate(self, listener: str, tick: int) -> None:
        self.listeners.discard(listener)
        if not self.listeners:
            self.wake(tick)

    def safety_at(self, tile: Tile) -> str:
        meta = self.template.meta
        return "pocket" if any(region.contains(tile) for region in meta.pockets) else meta.safety

    def allows_hostile(self, tile: Tile) -> bool:
        return self.safety_at(tile) not in ("safe", "pocket")

    def tile_id(self, tile: Tile) -> str | None:
        return self.geometry.get(tile, self.template.tile_at(tile))

    def can_enter(self, actor: Actor | None, tile: Tile) -> bool:
        return self.passable(tile) and self.entry_policy(actor, tile)

    def passable(self, tile: Tile, grid: dict[Tile, str] | None = None) -> bool:
        effective = grid if grid is not None else self.geometry
        key = effective.get(tile, self.template.tile_at(tile))
        if key not in self.tiles:
            return False
        if tile in effective:
            return self.tiles[key].passable
        door = self.doors.get(tile)
        return door.open is True if door is not None else self.tiles[key].passable

    def opaque(self, tile: Tile) -> bool:
        if not (0 <= tile[0] < self.template.width and 0 <= tile[1] < self.template.height):
            return True
        if tile in self.geometry:
            return self.tiles[self.geometry[tile]].opaque
        door = self.doors.get(tile)
        return door.open is False if door is not None else tile in self.base_opaque

    def set_door(self, object_id: str, opened: bool) -> bool:
        obj = self.objects[object_id]
        if obj.spec.kind not in DOOR_KINDS:
            raise ValueError("object is not a door")
        if not opened and any(a.position == obj.spec.tile for a in self.actors.values()):
            return False
        if obj.open != opened:
            before = obj.open
            obj.open = opened
            if not self.safe_geometry(self.geometry):
                obj.open = before
                return False
            self.geometry_revision += 1
            self.revision += 1
        return True

    def safe_geometry(self, grid: dict[Tile, str]) -> bool:
        """Every composed state keeps essential services and escape reachable."""
        for tile, key in grid.items():
            if self.template.tile_at(tile) is None or key not in self.tiles:
                return False
            if self.tiles[key].hazard and not self.allows_hostile(tile):
                return False
        if any(not self.passable(actor.position, grid) for actor in self.actors.values()):
            return False
        starts: list[tuple[Actor | None, Tile]] = (
            [(None, self.template.meta.spawn)] if self.template.meta.spawn is not None else [])
        starts += [(actor, self.escape_origin(actor)) for actor in self.actors.values()]
        required = {obj.spec.tile for obj in self.objects.values() if obj.spec.essential}
        required.update(ex.tile for ex in self.template.meta.exits if not ex.hidden and ex.requirement is None)
        public: set[Tile] = set()
        for actor, start in starts:
            if not self.passable(start, grid):
                return False
            # Once public services share a component, every actor starting
            # there has the same escape. Do not flood the city per caller.
            if actor is not None and start in public:
                continue
            seen = {start}
            pending = deque([start])
            while pending:
                x, y = pending.popleft()
                for tile in ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)):
                    key = grid.get(tile, self.template.tile_at(tile))
                    if (tile not in seen and self.passable(tile, grid)
                            and self.entry_policy(actor, tile) and not self.tiles[key].hazard):
                        seen.add(tile)
                        pending.append(tile)
            if not required <= seen:
                return False
            if actor is None:
                public = seen
        return True

    def schedule_layout(self, source: str, layout_id: str, tick: int, duration: int, warning: int = 0) -> None:
        layout = next((item for item in self.template.meta.layouts if item.id == layout_id), None)
        if layout is None or duration <= 0 or warning < 0:
            raise ValueError("invalid layout change")
        # Game design 7.7 / control contract: hazardous geometry warns 5 s.
        if any(self.tiles[change.tile_id].hazard for change in layout.changes) and warning < MIN_HAZARD_WARNING_TICKS:
            raise ValueError("hazards require at least five seconds warning")
        self.layers[source] = GeometryLayer(source, layout, tick + warning, tick + warning + duration)
        self.revision += 1

    def compose(self, tick: int) -> None:
        expired = [key for key, layer in self.layers.items() if tick >= layer.expires]
        for key in expired:
            del self.layers[key]
        grid: dict[Tile, str] = {}
        for source, layer in sorted(self.layers.items()):
            if layer.starts <= tick:
                grid.update({change.tile: change.tile_id for change in layer.layout.changes})
        if grid != self.geometry:
            if not self.safe_geometry(grid):
                # Admit layers in stable source order. A conflicting closure
                # stays pending, rather than retaining a now-expired layer.
                grid = {}
                for tile, key in self.geometry.items():
                    if any(a.position == tile for a in self.actors.values()) and not self.passable(tile, {}):
                        grid[tile] = key
                for source, layer in sorted(self.layers.items()):
                    if layer.starts <= tick:
                        proposal = {**grid, **{change.tile: change.tile_id for change in layer.layout.changes}}
                        if self.safe_geometry(proposal):
                            grid = proposal
            if grid != self.geometry and self.safe_geometry(grid):
                self.geometry = grid
                self.geometry_revision += 1
                self.revision += 1
        if expired:
            self.revision += 1
