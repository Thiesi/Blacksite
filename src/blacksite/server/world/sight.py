"""Symmetric integer Bresenham visibility (game design 5.2)."""

from blacksite.content.schema import Tile
from blacksite.server.world.actors import Actor
from blacksite.server.world.zone import ZoneInstance


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


def sees_actor(observer: Actor, target: Actor, visible: set[Tile], radius: int) -> bool:
    if target.position not in visible:
        return False
    limit = radius / 2 if target.stance == "stealth" else radius
    return (observer.x - target.x) ** 2 + (observer.y - target.y) ** 2 <= limit ** 2
