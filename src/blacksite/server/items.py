"""Item instances and quality bounds (entities 2.2, game design 8.4)."""

from dataclasses import asdict, dataclass
from typing import Any

from blacksite.content.schema import CharacterStart, ItemTemplate
from blacksite.server.players import Player

QUALITY_MIN = .85  # Game design 8.4.
QUALITY_MAX = 1.15
SECURED_SLOTS = 3  # Game design 5.4.
CACHE_SECONDS = 300  # Game design 5.4 / S12 dropped caches.
CONSUMABLE_SECONDS = 10  # Game design 5.3.


@dataclass
class ItemInstance:
    id: str
    template: str
    owner: str | None
    quality: float = 1.0
    ammo: int = 0
    charges: int = 0
    secured: bool = False
    stack: int = 1
    created_at: str = ""
    bound: bool = False

    def __post_init__(self) -> None:
        if not QUALITY_MIN <= self.quality <= QUALITY_MAX or self.stack < 1:
            raise ValueError("invalid item quality or stack")

    @classmethod
    def from_record(cls, row: dict[str, Any]) -> "ItemInstance":
        return cls(**{key: value for key, value in row.items() if key in cls.__dataclass_fields__})

    def record(self) -> dict[str, Any]:
        return asdict(self)


def make_item(iid: str, template: ItemTemplate, owner: str, at: str,
              stack: int = 1, quality: float = 1.0) -> ItemInstance:
    if not 1 <= stack <= template.stack_max:
        raise ValueError("stack exceeds template limit")
    return ItemInstance(iid, template.id, owner, quality, secured=template.secured_default,
                        stack=stack, created_at=at,
                        charges=template.consumable.uses if template.consumable else 0)


def availability(template: ItemTemplate) -> str:
    """State future behaviour openly when selling physical items now."""
    owner = {"weapon": "combat", "armour": "protection", "drone": "drone operation",
             "implant": "surgery", "resonance": "surgery", "drug": "drug effects",
             "rig": "rig operation", "pass": "restricted access", "key": "controls",
             "data": "objectives", "misc": "objectives", "salvage": "fabrication"}
    supported = ("health", "stamina", "stamina_full", "end_chemical_dot", "recharge_cell", "dark_sight")
    if template.class_ == "consumable" and not any(k in template.consumable.effects for k in supported):
        return "Not yet usable: this item's effect."
    return "Not yet usable: " + owner[template.class_] + "." if template.class_ in owner else ""


def grant_starter_kit(player: Player, start: CharacterStart, templates: dict[str, ItemTemplate], serial: int) -> list[dict[str, Any]]:
    """Catalog 11; issuance is committed with character creation exactly once."""
    records = []
    for template_id, quantity in start.items.items():
        template = templates[template_id]
        while quantity:
            count = min(quantity, template.stack_max)
            iid = f"{player.origin}:item:{(serial << 32) + len(records)}"
            records.append(make_item(iid, template, player.id, player.created_at, count).record())
            player.inventory.append(iid)
            for slot, key in start.equipment.items():
                if key == template_id: player.equipment[slot] = iid
            for slot, key in start.implants.items():
                if key == template_id: player.implants[slot] = iid
            quantity -= count
    return records
