"""Symmetric integer Bresenham visibility (game design 5.2)."""

from blacksite.content.schema import Tile
from blacksite.server.world.actors import Actor
from blacksite.server.world.zone import ZoneInstance
from blacksite.server.interlock_effects import lighting_radius


def sight_radius(actor: Actor, zone: ZoneInstance, night: bool) -> int:
    base = (zone.template.meta.sight_radius_night if night else None) or zone.template.meta.sight_radius
    radius = lighting_radius(actor, zone, base)
    dark = radius < zone.template.meta.sight_radius or radius <= 5
    radius += actor.modifiers.get("sight", 0)
    if dark:
        radius += actor.modifiers.get("dark_sight_bonus", 0)
    floor = max(actor.modifiers.get("dark_sight", 0),
                max((float(e.get("dark_sight", 0)) for e in actor.effects), default=0))
    return max(1, int(radius), int(floor))


def detection_limit(radius: int, target: Actor) -> float:
    reduction = target.modifiers.get("stealth_sight_reduction", .5) if target.stance == "stealth" else 0
    return radius*(1-reduction)


def line(a: Tile, b: Tile) -> list[Tile]:
    # Canonical endpoint ordering makes Bresenham tie choices reciprocal.
    if a > b:
        return list(reversed(line(b, a)))
    x, y = a
    dx, dy = abs(b[0] - x), -abs(b[1] - y)
    sx, sy = (1 if x < b[0] else -1), (1 if y < b[1] else -1)
    error = dx + dy
    result = []
    while True:
        result.append((x, y))
        if (x, y) == b:
            return result
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x += sx
        if doubled <= dx:
            error += dx
            y += sy


def line_of_sight(zone: ZoneInstance, a: Tile, b: Tile) -> bool:
    return not any(zone.opaque(tile) for tile in line(a, b)[1:-1])


def visible_tiles(actor: Actor, zone: ZoneInstance, radius: int) -> set[Tile]:
    key = (zone.id, actor.position, radius, zone.geometry_revision)
    if actor.sight_key != key:
        actor.visible = {(x, y) for y in range(max(0, actor.y - radius), min(zone.template.height, actor.y + radius + 1))
                         for x in range(max(0, actor.x - radius), min(zone.template.width, actor.x + radius + 1))
                         if (x - actor.x) ** 2 + (y - actor.y) ** 2 <= radius ** 2
                         and line_of_sight(zone, actor.position, (x, y))}
        actor.sight_key = key
    return actor.visible


def private_visible(observer: Actor, target: Actor) -> bool:
    owner = target.behaviour.get("private_owner")
    return not owner or observer.id in (owner, target.id) or bool(
        observer.kind == "drone" and observer.behaviour.get("player_drone") and observer.owner == owner)


def sees_actor(observer: Actor, target: Actor, visible: set[Tile], radius: int) -> bool:
    if not private_visible(observer, target):
        return False
    if target.behaviour.get("training") and target.owner != observer.id:
        return False
    if target.position not in visible:
        return False
    limit = detection_limit(radius, target)
    return (observer.x - target.x) ** 2 + (observer.y - target.y) ** 2 <= limit ** 2
