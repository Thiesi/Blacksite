"""Physical safety contract consumed by logout and future combat (§5.1)."""

from blacksite.content.schema import Tile
from blacksite.server.world.zone import ZoneInstance


def safety_at(zone: ZoneInstance, tile: Tile) -> str:
    return zone.safety_at(tile)
