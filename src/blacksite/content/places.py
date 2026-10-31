"""P6 geometry and tile classes shared by authoring and view construction.

No simulation reads looks. Charting is a separate zone disclosure policy
(entities 1.1, architecture 5.5.5), validated before a world is started.
"""

from collections import deque
from typing import Iterable

from blacksite.content import schema as s
from blacksite.place import DEFAULT_THEME, theme_over


def wall(tile: s.TileType) -> bool:
    return tile.opaque and not tile.passable and tile.interaction is None


def water(tile: s.TileType) -> bool:
    # The tile registry has no water boolean; its fixed vocabulary glyph
    # supplies this class. In particular this never tests a content tile id.
    return tile.glyph == "water"


def plain(tile: s.TileType) -> bool:
    return tile.passable and not (tile.opaque or tile.cover or tile.hazard
                                or tile.interaction or water(tile))


def region_tiles(region: s.LookRegion) -> set[s.Tile]:
    if region.rect is not None:
        return set(s.Region(*region.rect).tiles())
    if region.circle is not None:
        x, y, radius = region.circle
        return {(cx, cy) for cy in range(y - radius, y + radius + 1)
                for cx in range(x - 2 * radius, x + 2 * radius + 1)
                if (cx - x) ** 2 + 4 * (cy - y) ** 2 <= 4 * radius ** 2}
    return set()


def mark_cells(mark: s.LookMark) -> list[tuple[s.Tile, str]]:
    if mark.at is not None:
        return [((mark.at[0] + i, mark.at[1]), ch) for i, ch in enumerate(mark.text)]
    if mark.line is not None:
        (ax, ay), (bx, by) = mark.line
        if ax == bx:
            return [((ax, y), mark.glyph) for y in range(min(ay, by), max(ay, by) + 1)]
        if ay == by:
            return [((x, ay), mark.glyph) for x in range(min(ax, bx), max(ax, bx) + 1)]
    return []


def public_tiles(zone: s.Zone) -> set[s.Tile]:
    regions = list(zone.meta.public) if zone.meta.charted else []
    regions.extend(p for p in zone.meta.pockets if getattr(p, 'charted', False))
    return {tile for region in regions for tile in region.tiles()}


def charting_problems(zone: s.Zone, tiles: dict[str, s.TileType]) -> Iterable[str]:
    """Reject each declared region; never trim a bad region into validity."""
    meta = zone.meta
    if meta.charted and not meta.public:
        yield 'charted zone requires a non-empty public region'
    regions = [*meta.public, *(p for p in meta.pockets if getattr(p, 'charted', False))]
    if not regions:
        return
    if meta.instanced:
        yield 'public/charted region belongs to an instanced zone'
    passable = {(x, y) for y, row in enumerate(zone.grid) for x, key in enumerate(row)
                if key in tiles and tiles[key].passable}
    hidden = {ex.tile for ex in meta.exits if ex.hidden}
    hidden_near = {(x + dx, y + dy) for x, y in hidden
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    private = {tile for obj in meta.objects if obj.housing
               for tile in s.Region(*obj.housing.origin, 6, 4).tiles()}
    # All lockable door kinds are barriers even if initially open. Their
    # runtime state must never grant permission to publish the room behind.
    barriers = hidden | {ex.tile for ex in meta.exits if ex.requirement is not None}
    barriers.update(obj.tile for obj in meta.objects
                    if obj.kind in ('door', 'gate', 'shutter', 'apartment_door'))
    barriers.update((x, y) for y, row in enumerate(zone.grid) for x, key in enumerate(row)
                    if key in tiles and tiles[key].interaction in ('door', 'gate', 'shutter', 'apartment_door'))
    allowed = passable - barriers - private
    starts = {ex.tile for ex in meta.exits if not ex.hidden and ex.requirement is None}
    if meta.spawn is not None:
        starts.add(meta.spawn)
    seen = starts & allowed
    pending = deque(seen)
    while pending:
        x, y = pending.popleft()
        for nxt in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nxt in allowed and nxt not in seen:
                seen.add(nxt)
                pending.append(nxt)
    # Architecture 5.5.5: disclose a barrier's public face, never use it
    # as a flood-fill step into the room behind or another barrier.
    faces = {(x, y) for x, y in barriers - hidden - private
             if any(nxt in seen for nxt in ((x-1,y), (x+1,y), (x,y-1), (x,y+1)))}
    for i, region in enumerate(regions):
        if (region.w <= 0 or region.h <= 0 or region.x < 0 or region.y < 0
                or region.x + region.w > zone.width or region.y + region.h > zone.height):
            yield f'public/charted region {i} is outside the map'
            continue
        cells = set(region.tiles())
        if cells & hidden or cells & passable & hidden_near:
            yield f'public/charted region {i} contains or neighbours a hidden exit'
        if cells & private:
            yield f'public/charted region {i} overlaps a private interior'
        if cells & passable - seen - faces:
            yield f'public/charted region {i} includes gated or unreachable passable ground'
