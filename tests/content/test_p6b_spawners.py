"""P6b spawner spread: armed NPCs keep clear of arrivals and of rooms."""

from collections import deque
from pathlib import Path

import pytest

from blacksite.content.loader import load_content

ROOT = Path(__file__).resolve().parents[2]
P6B_ZONES = ("core-plaza", "vatside-clinics", "sodium-row")
DOORS = ("door", "gate", "shutter")
# Armed spawns stay at least this many tiles (Chebyshev) from every
# arrival, as before the spread, so nobody is engaged on stepping in.
ARRIVAL_CLEARANCE = 5


@pytest.fixture(scope="module")
def tree():
    return load_content(ROOT/"src/blacksite/content")


def chebyshev(a, b):
    return max(abs(a[0]-b[0]), abs(a[1]-b[1]))


def arrivals(tree, zid):
    tiles = {tree.zones[zid].meta.spawn} - {None}
    for other in tree.zones.values():
        tiles |= {tuple(ex.target_tile) for ex in other.meta.exits if ex.target_zone == zid}
    return tiles


def candidates(tree, zone, spawner):
    """Tiles the spawner may use: passable, and never an exit or object tile."""
    reserved = {ex.tile for ex in zone.meta.exits} | {o.tile for o in zone.meta.objects}
    return [t for t in (spawner.region.tiles() if spawner.region else [spawner.tile])
            if 0 <= t[0] < zone.width and 0 <= t[1] < zone.height
            and tree.tiles[zone.tile_at(t)].passable and t not in reserved]


def open_ground(tree, zone, starts):
    """Passable tiles reachable from the arrivals without crossing a door."""
    doors = {o.tile for o in zone.meta.objects if o.kind in DOORS}
    seen, queue = set(starts), deque(starts)
    while queue:
        x, y = queue.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                t = (x+dx, y+dy)
                if (t in seen or t in doors or not (0 <= t[0] < zone.width and 0 <= t[1] < zone.height)
                        or not tree.tiles[zone.tile_at(t)].passable):
                    continue
                seen.add(t)
                queue.append(t)
    return seen


@pytest.mark.parametrize("zid", P6B_ZONES)
def test_armed_spawns_keep_clear_of_arrivals(tree, zid):
    zone = tree.zones[zid]
    landing = arrivals(tree, zid)
    for sp in zone.meta.spawners:
        if not tree.npcs[sp.npc].weapon:
            continue
        near = [(t, a) for t in candidates(tree, zone, sp) for a in landing if chebyshev(t, a) < ARRIVAL_CLEARANCE]
        assert not near, f"{sp.id} can spawn within {ARRIVAL_CLEARANCE} tiles of an arrival: {near[:3]}"


@pytest.mark.parametrize("zid", P6B_ZONES)
def test_street_spawns_stay_out_of_rooms_behind_doors(tree, zid):
    zone = tree.zones[zid]
    ground = open_ground(tree, zone, arrivals(tree, zid))
    for sp in zone.meta.spawners:
        if tree.npcs[sp.npc].vendor:
            continue  # Vendors stand at their own counters, indoors or out.
        inside = [t for t in candidates(tree, zone, sp) if t not in ground]
        assert not inside, f"{sp.id} can spawn behind a door: {inside[:3]}"
