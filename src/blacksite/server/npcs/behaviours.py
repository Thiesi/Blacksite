"""Small, deterministic behaviour decisions; movement uses ordinary rules."""

from blacksite.content.schema import Region, Tile
from blacksite.server.world.actors import Actor
from blacksite.server.world.movement import move
from blacksite.server.world.zone import ZoneInstance


def step_toward(actor: Actor, zone: ZoneInstance, target: Tile, tick: int,
                region: Region | None = None, avoid: set[Tile] | None = None) -> bool:
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
