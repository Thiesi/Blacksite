"""Physical safety contract consumed by logout and future combat (§5.1)."""

from karst41.content.schema import Tile
from karst41.server.world.zone import ZoneInstance


def safety_at(zone: ZoneInstance, tile: Tile) -> str:
    return zone.safety_at(tile)
