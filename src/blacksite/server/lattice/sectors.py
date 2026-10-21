"""Sector indexes and explicit access rules, game design 6.1/6.3.

Content is loaded by the I/O boundary. This module only receives records.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from blacksite.content.schema import Cell, Sector


def access(cell: Cell) -> str:
    return cell.access_kind


@dataclass(frozen=True)
class Credentials:
    items: frozenset[str] = frozenset()
    programs: frozenset[str] = frozenset()
    program_tiers: tuple[tuple[str, int], ...] = ()
    faction: str | None = None
    standing: tuple[tuple[str, int], ...] = ()
    events: frozenset[str] = frozenset()


def requirement_label(requirement: str | None) -> str:
    if not requirement:
        return "an access credential"
    parts = requirement.split(":")
    if len(parts) == 2 and parts[0] in ("item", "program", "faction", "event"):
        return parts[1].replace("_", " ").replace("-", " ")
    if len(parts) == 3 and parts[0] == "program":
        return f"{parts[1]} program tier {parts[2]}"
    if len(parts) == 3 and parts[0] == "standing":
        return f"{parts[1]} standing {parts[2]}"
    return requirement.replace("_", " ").replace("-", " ")


def permitted(requirement: str | None, credentials: Credentials) -> bool:
    if not requirement:
        return True
    parts = requirement.split(":")
    if len(parts) == 1:
        return requirement in credentials.items | credentials.programs
    if len(parts) == 2:
        kind, key = parts
        return (key in credentials.items if kind == "item" else
                key in credentials.programs if kind == "program" else
                credentials.faction == key if kind == "faction" else
                key in credentials.events if kind == "event" else False)
    if len(parts) == 3 and parts[2].isdigit():
        kind, key, raw = parts
        minimum = int(raw)
        return (dict(credentials.program_tiers).get(key, 0) >= minimum if kind == "program" else
                dict(credentials.standing).get(key, 0) >= minimum if kind == "standing" else False)
    return False


class Sectors:
    def __init__(self, records: Iterable[Sector]) -> None:
        self.records = {sector.id: sector for sector in records}
        self.cells = {sid: {cell.id: cell for cell in sector.cells} for sid, sector in self.records.items()}

    def entrance(self, sector: str) -> str:
        record = self.records[sector]
        return record.entry or next(cell.id for cell in record.cells if access(cell) == "public")

    def known(self, sector: str, discoveries: set[str]) -> list[Cell]:
        return [cell for cell in self.records[sector].cells if access(cell) != "hidden" or cell.id in discoveries]

    def adjacent(self, sector: str, source: str, target_sector: str, target: str) -> bool:
        cell = self.cells[sector][source]
        if sector == target_sector:
            return target in cell.neighbours
        return bool(cell.uplink and (cell.uplink.sector, cell.uplink.cell) == (target_sector, target))
