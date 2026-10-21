"""Seeded, transport-free Silt topology. Game 6.5-6.7; world Lattice 6."""

from dataclasses import dataclass
from hashlib import blake2b
from random import Random

from blacksite.content.schema import SiltRules, Tile


def descent_seed(season: int, sector: str, nonce: int) -> int:
    """Stable across platforms/processes; never Python's randomized hash."""
    material = f"{season}:{sector}:{nonce}".encode("utf-8")
    return int.from_bytes(blake2b(material, digest_size=16).digest(), "big")


@dataclass(frozen=True)
class SiltCell:
    id: str
    pos: Tile
    neighbours: tuple[str, ...]
    hidden: bool = False
    role: str = "cell"


@dataclass(frozen=True)
class Band:
    id: str
    name: str
    depth: int
    cells: tuple[SiltCell, ...]
    riser: str
    sinks: tuple[str, ...]

    def cell(self, cell_id: str) -> SiltCell:
        return next(c for c in self.cells if c.id == cell_id)

    def route(self, start: str, target: str, known: set[str] | None = None) -> tuple[str, ...]:
        """Return a linked route; hidden cells require explicit knowledge."""
        index = {c.id: c for c in self.cells}
        pending: list[tuple[str, ...]] = [(start,)]
        seen = {start}
        for path in pending:
            if path[-1] == target:
                return path
            for other in index[path[-1]].neighbours:
                if other not in seen and (not index[other].hidden or known is not None and other in known):
                    seen.add(other)
                    pending.append((*path, other))
        return ()


@dataclass(frozen=True)
class Descent:
    id: str
    sector: str
    nonce: int
    seed: int
    bands: tuple[Band, ...]


def generate(origin: str, season: int, sector: str, nonce: int, rules: SiltRules) -> Descent:
    seed = descent_seed(season, sector, nonce)
    rng = Random(seed)
    bands = []
    for spec in rules.bands:
        size = rng.randint(rules.minimum_cells, rules.maximum_cells)
        hidden_count = int(size * rules.hidden_fraction)
        visible = size - hidden_count
        ids = [f"b{spec.depth}-{i:02}" for i in range(size)]
        neighbours: list[set[int]] = [set() for _ in ids]

        def link(a: int, b: int) -> None:
            neighbours[a].add(b)
            neighbours[b].add(a)

        # A visible grid includes a four-cell patrol bypass even at the
        # minimum size. Edges stay orthogonal instead of crossing labels
        # in a randomly scattered graph at 80x24.
        positions = [(i % 4, i // 4) for i in range(visible)]
        available = {(x, y) for x in range(5) for y in range(4)} - set(positions)
        while len(positions) < size:
            candidates = sorted(p for p in available if any(abs(p[0]-q[0])+abs(p[1]-q[1]) == 1 for q in positions))
            chosen = rng.choice(candidates)
            positions.append(chosen)
            available.remove(chosen)
        for i, a in enumerate(positions):
            for j, b in enumerate(positions[:i]):
                if abs(a[0]-b[0])+abs(a[1]-b[1]) == 1:
                    link(i, j)
        count = 0 if spec.depth == len(rules.bands) - 1 else rng.randint(rules.minimum_sinks, rules.maximum_sinks)
        sinks = [rng.randrange(1, visible)] if count else []
        candidates = [i for i in range(1, size) if i not in sinks]
        sinks.extend(rng.sample(candidates, max(0, count - 1)))
        mirror_x, mirror_y = rng.choice((False, True)), rng.choice((False, True))
        positions = [(4-x if mirror_x else x, 3-y if mirror_y else y) for x, y in positions]
        cells = tuple(SiltCell(ids[i], positions[i], tuple(ids[n] for n in sorted(neighbours[i])),
                               i >= visible, "riser" if i == 0 else "sink" if i in sinks else "cell")
                      for i in range(size))
        bands.append(Band(spec.id, spec.name, spec.depth, cells, ids[0], tuple(ids[i] for i in sinks)))
    return Descent(f"{origin}:silt:{season}:{sector}:{nonce}", sector, nonce, seed, tuple(bands))


def adjacent_hidden(band: Band, cell_id: str, known: set[str]) -> tuple[SiltCell, ...]:
    source = band.cell(cell_id)
    return tuple(c for c in band.cells if c.id in source.neighbours and c.hidden and c.id not in known)


def survey_directions(band: Band, cell_id: str, known: set[str]) -> tuple[str, ...]:
    """Low Listening reports direction without leaking hidden node IDs."""
    source = band.cell(cell_id)
    labels = []
    for target in adjacent_hidden(band, cell_id, known):
        dx, dy = target.pos[0] - source.pos[0], target.pos[1] - source.pos[1]
        labels.append(("north" if dy < 0 else "south" if dy > 0 else "") +
                      ("west" if dx < 0 else "east" if dx > 0 else ""))
    return tuple(sorted(set(labels)))
