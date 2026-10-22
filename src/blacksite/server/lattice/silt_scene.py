"""Populate seeded Silt bands from typed content, without I/O or rewards.

Generated site identities belong to the season/district/band, not the
descent nonce. A new layout cannot replenish the shared source ledger.
"""

from dataclasses import dataclass
from random import Random

from blacksite.content.loader import ContentTree
from blacksite.content.schema import DataSpec, Room
from blacksite.server.lattice.silt import Band, Descent


@dataclass(frozen=True)
class BandSpec:
    id: str
    name: str
    tier: int
    training: bool = False
    trace_policy: str = "none"
    affiliation: str | None = None
    owner: str = "unowned"
    owner_kind: str = "abandoned"


class BandGraph:
    def __init__(self, descent: Descent, band: Band, content: ContentTree) -> None:
        self.band, self.descent = band, descent
        self.spec = BandSpec(band.id, band.name, band.depth+1)
        self.entry = band.riser
        rules = content.silt.bands[band.depth]
        rng = Random(descent.seed + band.depth)
        visible = [cell.id for cell in band.cells if not cell.hidden]
        optional = [cell.id for cell in band.cells if cell.id != band.riser]
        defenders: dict[str, list[str]] = {cell.id: [] for cell in band.cells}
        self.patrols: dict[str, tuple[str, ...]] = {}
        # A grid square always has a visible alternate edge around the sweep.
        positions = {cell.pos: cell.id for cell in band.cells if not cell.hidden}
        squares = [(cid, positions[x+1, y], positions[x+1, y+1], positions[x, y+1])
                   for (x, y), cid in positions.items()
                   if all(p in positions for p in ((x+1, y), (x+1, y+1), (x, y+1)))]
        for spawn in rules.ice:
            for _ in range(rng.randint(spawn.minimum, spawn.maximum)):
                if spawn.route == "patrol":
                    route = rng.choice(sorted(route for route in squares if band.riser not in route))
                    cell_id = route[0]
                    self.patrols[cell_id+":"+str(len(defenders[cell_id]))] = route
                elif spawn.route == "signal":
                    cell_id = rng.choice([cid for cid in visible if cid != band.riser])
                else:
                    cell_id = rng.choice(optional)
                defenders[cell_id].append(spawn.template)
        data: dict[str, list[DataSpec]] = {cell.id: [] for cell in band.cells}
        # Each authored data row is one stable site, even if its cell moves.
        self.sites: dict[str, str] = {}
        for record in rules.data:
            cid = rng.choice(optional)
            data[cid].append(record)
            self.sites[record.id] = f"{descent.sector}:{band.id}:{record.id}"
        self.rooms = {cell.id: Room(cell.id, cell.neighbours, tuple(data[cell.id]),
            ice=tuple(defenders[cell.id]), label=band.name+" / "+cell.role, pos=cell.pos)
            for cell in band.cells}

    def room(self, room: str) -> Room:
        return self.rooms[room]

    def adjacent(self, source: str, target: str) -> bool:
        return source in self.rooms and target in self.rooms[source].neighbours

    def route(self, source: str, target: str) -> tuple[str, ...]:
        # The public escape never depends on discovering a hidden cell.
        return self.band.route(source, target, {source})
