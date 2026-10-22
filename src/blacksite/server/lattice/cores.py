"""Core topology and persistent source proposals, without storage or I/O.

Game 6.2/6.7 and architecture 15.2: claiming a source produces a proposal;
the caller publishes it only after the combined reward transaction commits.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from hashlib import blake2b
from random import Random
from typing import Any

from blacksite.content.schema import Core, DataSpec, Room
from blacksite.server.clock import TICK_HZ

CORE_IDLE_RESET_SECONDS = 30  # Game 6.7.
TRACE_PER_SECOND = (0, .5, 1, 1.5, 2, 3)  # World Lattice 7.
STREET_LOCK_SECONDS = 300  # Game 6.7, identity/core scope.


class CoreGraph:
    def __init__(self, core: Core) -> None:
        self.spec = core
        self.rooms = {r.id: r for r in core.rooms}
        self.entry = core.entry or core.rooms[0].id

    def room(self, room: str) -> Room:
        return self.rooms[room]

    def adjacent(self, source: str, target: str) -> bool:
        return source in self.rooms and target in self.rooms[source].neighbours

    def route(self, source: str, target: str) -> tuple[str, ...]:
        pending = [(source,)]
        seen = {source}
        for path in pending:
            if path[-1] == target:
                return path
            for rid in self.rooms[path[-1]].neighbours:
                if rid not in seen:
                    seen.add(rid)
                    pending.append((*path, rid))
        return ()


@dataclass(frozen=True)
class Source:
    generation: int = 0
    ready_at: float = 0
    available: bool = False


@dataclass(frozen=True)
class Claim:
    key: str
    generation: int
    unit_id: str
    next_source: Source


class Sources:
    def __init__(self, origin: str, saved: Mapping[str, Any], start_tick: int = 0) -> None:
        self.origin = origin
        self.base_uptime = float(saved.get("uptime", 0))
        self.start_tick = start_tick
        self.nonce = int(saved.get("nonce", 0))
        self.sources = {key: Source(**value) for key, value in saved.get("sources", {}).items()}
        self.locks: dict[str, dict[str, float]] = {key: dict(value) for key, value in saved.get("locks", {}).items()}
        self.reserved: set[str] = set()
        self.revision = 0

    def uptime(self, tick: int) -> float:
        return self.base_uptime + max(0, tick - self.start_tick) / TICK_HZ

    def unit_id(self, key: str, generation: int) -> str:
        digest = blake2b(key.encode("utf-8"), digest_size=12).hexdigest()
        return f"{self.origin}:data:{digest}:{generation}"

    def refresh(self, key: str, spec: DataSpec, tick: int) -> Source:
        source = self.sources.get(key, Source())
        now = self.uptime(tick)
        if source.available or source.ready_at > now or key in self.reserved:
            return source
        # The draw belongs to the stable source generation, never a new
        # descent seed. Reconnect or inspection cannot reroll it.
        seed = int.from_bytes(blake2b(self.unit_id(key, source.generation).encode(), digest_size=16).digest(), "big")
        available = Random(seed).random() < spec.chance
        source = (replace(source, available=True) if available else
                  Source(source.generation + 1, now + spec.respawn_seconds, False))
        self.sources[key] = source
        self.revision += 1
        return source

    def propose(self, key: str, spec: DataSpec, generation: int, tick: int) -> Claim:
        source = self.refresh(key, spec, tick)
        if key in self.reserved:
            raise ValueError("That transfer is settling.")
        if source.generation != generation:
            raise ValueError("That source changed. Inspect its current record.")
        if not source.available:
            raise ValueError("That source is not available yet.")
        self.reserved.add(key)
        return Claim(key, generation, self.unit_id(key, generation),
                     Source(generation + 1, self.uptime(tick) + spec.respawn_seconds, False))

    def finish(self, claim: Claim, success: bool) -> None:
        if success:
            self.sources[claim.key] = claim.next_source
            self.revision += 1
        self.reserved.discard(claim.key)

    def locked(self, identity: str, core: str, utc: float) -> bool:
        return self.locks.get(identity, {}).get(core, 0) > utc

    def lock(self, identity: str, core: str, utc: float) -> None:
        self.locks.setdefault(identity, {})[core] = utc + STREET_LOCK_SECONDS
        self.revision += 1

    def record(self, tick: int, claim: Claim | None = None, *, nonce: int | None = None) -> dict[str, Any]:
        sources = {key: asdict(value) for key, value in self.sources.items()}
        if claim:
            sources[claim.key] = asdict(claim.next_source)
        return {"uptime": self.uptime(tick), "nonce": self.nonce if nonce is None else nonce,
                "sources": sources, "locks": {key: dict(value) for key, value in self.locks.items()}}


def trace_thresholds(before: float, after: float, seen: set[int]) -> tuple[int, ...]:
    result = tuple(n for n in (50, 100) if before < n <= after and n not in seen)
    seen.update(result)
    return result
