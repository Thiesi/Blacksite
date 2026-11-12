"""Small, deterministic behaviour decisions; movement uses ordinary rules."""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from karst41.content.schema import Region, Tile
from karst41.server.world.actors import Actor, mission_pair
from karst41.server.world.movement import move
from karst41.server.world.zone import ZoneInstance


def step_toward(actor: Actor, zone: ZoneInstance, target: Tile, tick: int,
                region: Region | None = None, avoid: set[Tile] | None = None,
                permit: Callable[[Tile], bool] | None = None) -> bool:
    if actor.position == target or tick < actor.cooldowns.get("move", 0):
        return False
    dx, dy = target[0] - actor.x, target[1] - actor.y
    horizontal = "right" if dx > 0 else "left"
    vertical = "down" if dy > 0 else "up"
    choices = ([horizontal, vertical] if abs(dx) >= abs(dy) else [vertical, horizontal])
    vectors = {"right": (1, 0), "left": (-1, 0), "up": (0, -1), "down": (0, 1)}
    # Greedy wall sliding needs a short memory: two patrols meeting head-on
    # must step around each other rather than oscillate into the same tile.
    if actor.behaviour.get("nav_target") != target:
        actor.behaviour.update(nav_target=target, nav_recent=[])
    recent = actor.behaviour["nav_recent"]
    alternatives = sorted(vectors, key=lambda name: (
        abs(actor.x+vectors[name][0]-target[0])+abs(actor.y+vectors[name][1]-target[1]), name))
    for name in dict.fromkeys([*choices, *alternatives]):
        vx, vy = vectors[name]
        tile = actor.x + vx, actor.y + vy
        if tile in recent or (region and not region.contains(tile)) or tile in (avoid or set()):
            continue
        if permit is not None and not permit(tile):
            continue
        before = actor.position
        if move(actor, zone, name, tick):
            actor.behaviour["nav_recent"] = [*recent, before][-8:]
            return True
    actor.behaviour["nav_recent"] = []
    return False


def patrol(actor: Actor, zone: ZoneInstance, waypoints: list[Tile], tick: int,
           bounce: bool = False, avoid: set[Tile] | None = None) -> None:
    if not waypoints:
        return
    index = int(actor.behaviour.get("waypoint", 0)) % len(waypoints)
    if actor.position == waypoints[index]:
        direction = int(actor.behaviour.get("patrol_direction", 1))
        if bounce and not 0 <= index + direction < len(waypoints):
            direction = -direction
        index = (index + direction) % len(waypoints)
        actor.behaviour.update(waypoint=index, patrol_direction=direction)
    step_toward(actor, zone, waypoints[index], tick, avoid=avoid)


# S44 (#187): hunt routing. A breadth-first search over the zone's passable
# tiles, bounded per call: at most ROUTE_NODES tiles are expanded, inside the
# box around the hunter and its goal widened by ROUTE_MARGIN. Neighbours are
# expanded in a fixed order and no RNG is drawn, so a route is deterministic.
ROUTE_NODES = 1024
ROUTE_MARGIN = 8
STEPS = (("left", (-1, 0)), ("right", (1, 0)), ("up", (0, -1)), ("down", (0, 1)))


@dataclass
class Route:
    """A cached path; recomputed only when its goal or blocking set changes."""
    key: tuple = ()
    path: list[Tile] = field(default_factory=list)
    blocked: frozenset[Tile] = frozenset()
    searches: int = 0  # Tests count recomputations.


def blocking(zone: ZoneInstance, avoid: set[Tile] | None, blocked: frozenset[Tile]) -> tuple:
    doors = tuple(sorted((tile, obj.open) for tile, obj in zone.doors.items()))
    return zone.geometry_revision, doors, frozenset(avoid or ()), blocked


def search(actor: Actor, zone: ZoneInstance, goal: Tile, avoid: set[Tile] | None,
           blocked: frozenset[Tile]) -> list[Tile]:
    """Shortest 4-way path from the actor to goal, or [] past the bound.

    A zone exit is never a step (guards never cross one) unless it is the
    goal itself; reserved spawn tiles and known blocking bodies are skipped.
    """
    start = actor.position
    exits = {ex.tile for ex in zone.template.meta.exits}
    skip = (set(avoid or ()) | exits | blocked) - {goal}
    x0, x1 = min(start[0], goal[0]) - ROUTE_MARGIN, max(start[0], goal[0]) + ROUTE_MARGIN
    y0, y1 = min(start[1], goal[1]) - ROUTE_MARGIN, max(start[1], goal[1]) + ROUTE_MARGIN
    parents: dict[Tile, Tile | None] = {start: None}
    queue = deque([start])
    expanded = 0
    while queue and expanded < ROUTE_NODES:
        current = queue.popleft()
        expanded += 1
        if current == goal:
            path = []
            node: Tile | None = current
            while node is not None:
                path.append(node)
                node = parents[node]
            return path[::-1]
        for _, (dx, dy) in STEPS:
            tile = current[0] + dx, current[1] + dy
            if (tile in parents or tile in skip or not (x0 <= tile[0] <= x1 and y0 <= tile[1] <= y1)
                    or not zone.can_enter(actor, tile)):
                continue
            parents[tile] = current
            queue.append(tile)
    return []


def route_toward(actor: Actor, zone: ZoneInstance, target: Tile, tick: int, route: Route,
                 avoid: set[Tile] | None = None) -> bool:
    """One ordinary move along a bounded shortest path (#187).

    Movement, cooldown and collision stay the ordinary rules (`move`).
    A body on the next tile joins the blocking set, which recomputes the
    path once; past the search bound the greedy step is the fallback.
    """
    if actor.position == target or tick < actor.cooldowns.get("move", 0):
        return False
    if route.key[:1] != (target,):
        route.blocked = frozenset()
    elif route.blocked:
        # A body that has moved on no longer blocks; that changes the key.
        held = {other.position for other in zone.actors.values() if other.id != actor.id}
        route.blocked = route.blocked & held
    for _ in range(2):
        key = (target, *blocking(zone, avoid, route.blocked))
        if key != route.key or actor.position not in route.path[:-1]:
            route.key, route.path = key, search(actor, zone, target, avoid, route.blocked)
            route.searches += 1
        if not route.path:
            return step_toward(actor, zone, target, tick, avoid=avoid)
        nxt = route.path[route.path.index(actor.position) + 1]
        if any(other.id != actor.id and other.position == nxt and mission_pair(actor, other)
               and not (other.behaviour.get("training") and other.owner != actor.id)
               for other in zone.actors.values()):
            if nxt == target:
                return False  # The goal is held; wait beside it.
            route.blocked = route.blocked | {nxt}
            continue
        name = next(name for name, (dx, dy) in STEPS if (actor.x + dx, actor.y + dy) == nxt)
        return move(actor, zone, name, tick)
    return False
