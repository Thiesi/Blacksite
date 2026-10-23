"""Game 8.5: surgical quotes and validation on transaction drafts."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import ceil
from typing import Literal

from blacksite.content.schema import ItemTemplate
from blacksite.server.items import ItemInstance
from blacksite.server.modifiers import Modifiers
from blacksite.server.players import Player

Clinic = Literal["sablier", "black"]
SLOTS = ("head", "eyes", "spine", "arms1", "arms2", "torso", "legs", "rig")
SABLIER_FAILURE = .02  # Game 8.5.
BLACK_FAILURE = .15
FAILURE_SHOCK = 100
FAILURE_SHOCK_SECONDS = 30
CHOIR_INSTALL_STANDING = 20
RIG_CORTEX = 20


@dataclass(frozen=True)
class Quote:
    item_price: int
    service_price: int
    removal_price: int
    failure: float
    slot: str
    used: int
    capacity: int

    @property
    def total(self) -> int:
        return self.item_price+self.service_price+self.removal_price


def tolerance_used(player: Player, items: Mapping[str, ItemInstance],
                   templates: Mapping[str, ItemTemplate], replacing: str = "") -> int:
    return sum(templates[items[iid].template].implant.tolerance
               for slot, iid in player.implants.items() if slot != replacing
               and iid in items and templates[items[iid].template].implant is not None)


def removal_price(template: ItemTemplate) -> int:
    return ceil(template.base_price*.2)  # Game 8.5, both clinics, no failure.


def quote(player: Player, template: ItemTemplate, clinic: Clinic,
          modifiers: Modifiers, items: Mapping[str, ItemInstance],
          templates: Mapping[str, ItemTemplate], *, owned: bool,
          slot: str = "", replace: bool = False, service_multiplier: float = 1) -> Quote:
    block = template.implant
    if clinic not in ("sablier", "black"):
        raise ValueError("This is not a surgery clinic.")
    if not block or block.portable:
        raise ValueError("That item is not an implant.")
    if template.id == "imp_rig_native":
        raise ValueError("The native rig is built in and cannot be bought or removed.")
    required = block.requires
    if required:
        if required.archetype and required.archetype != player.archetype:
            raise ValueError("Your archetype cannot install that implant.")
        if required.faction and player.standing.get(required.faction, 0) < (required.standing or 0):
            raise ValueError("Your standing does not meet the installation requirement.")
    # Starter First Ear is issued with the Cantor; all subsequent resonance
    # purchases and owned-item operations require the same Choir standing.
    if template.class_ == "resonance" and (player.archetype != "cantor"
            or player.standing.get("choir", 0) < CHOIR_INSTALL_STANDING):
        raise ValueError("Resonance installation requires Cantor and Choir +20.")
    if block.slot == "rig" and modifiers.attribute(player, "cortex") < RIG_CORTEX:
        raise ValueError("A rig implant requires Cortex 20.")
    allowed = ("arms1", "arms2") if block.slot == "arms" else (block.slot,)
    slot = slot or next((s for s in allowed if s not in player.implants), allowed[0])
    if slot not in allowed:
        raise ValueError("That implant does not fit that slot.")
    previous = items.get(player.implants.get(slot, ""))
    native = bool(previous and previous.template == "imp_rig_native")
    if previous and not (replace or native):
        raise ValueError("That slot is occupied. Choose replacement to see both fees.")
    used = tolerance_used(player, items, templates, replacing=slot)+block.tolerance
    capacity = modifiers.tolerance(player)
    if used > capacity:
        raise ValueError("The implant exceeds your current tolerance.")
    price = template.base_price
    if clinic == "sablier":
        item_price, service, failure = (0 if owned else price), ceil(price*.2), SABLIER_FAILURE
    else:
        item_price, service, failure = (0 if owned else ceil(price*.6)), (ceil(price*.12) if owned else 0), BLACK_FAILURE
    old_fee = removal_price(templates[previous.template]) if previous and not native else 0
    service = ceil(service * service_multiplier)  # Game 7.5: service only, never item/removal.
    return Quote(item_price, service, old_fee, failure, slot, used, capacity)


@dataclass(frozen=True)
class Surgery:
    installed: bool
    slot: str
    cost: int
    returned: str | None


def install(player: Player, item: ItemInstance, clinic: Clinic,
            modifiers: Modifiers, items: dict[str, ItemInstance],
            templates: Mapping[str, ItemTemplate], now: float,
            roll: float, *, owned: bool, slot: str = "", replace: bool = False,
            service_multiplier: float = 1) -> Surgery:
    """The owning transaction supplies a seeded roll and purchase instance.

    On failure both the charge and destroyed item persist. A replaced
    implant is returned even when installation fails. Never publish this
    draft before the enclosing storage receipt succeeds.
    """
    if not 0 <= roll < 1:
        raise ValueError("Surgery needs a seeded probability roll.")
    template = templates[item.template]
    bill = quote(player, template, clinic, modifiers, items, templates,
                 owned=owned, slot=slot, replace=replace, service_multiplier=service_multiplier)
    if owned and (item.id not in player.inventory or item.owner != player.id
                  or item.id in player.implants.values() or item.stack != 1):
        raise ValueError("Choose an uninstalled implant you carry.")
    if player.chits_hand < bill.total:
        raise ValueError("You do not carry enough chits for this operation.")
    old = player.implants.pop(bill.slot, None)
    if old and items[old].template == "imp_rig_native":
        # The built-in Ghost rig cannot become a free tradable item.
        player.inventory.remove(old)
        del items[old]
        old = None
    player.chits_hand -= bill.total
    order = player.progress.setdefault("implant_order", [])
    order[:] = [iid for iid in order if iid != old]
    if roll < bill.failure:
        if owned:
            player.inventory.remove(item.id)
            del items[item.id]
        surgical_shock(player, now)
        return Surgery(False, bill.slot, bill.total, old)
    if not owned:
        item.owner = player.id
        items[item.id] = item
        player.inventory.append(item.id)
    player.implants[bill.slot] = item.id
    order.append(item.id)
    return Surgery(True, bill.slot, bill.total, old)


def remove(player: Player, slot: str, items: Mapping[str, ItemInstance],
           templates: Mapping[str, ItemTemplate]) -> str:
    iid = player.implants.get(slot)
    if not iid or iid not in items:
        raise ValueError("That implant slot is empty.")
    template = templates[items[iid].template]
    if template.id == "imp_rig_native":
        raise ValueError("The native rig is built in.")
    cost = removal_price(template)
    if player.chits_hand < cost:
        raise ValueError("You do not carry enough chits for removal.")
    player.chits_hand -= cost
    del player.implants[slot]
    player.progress["implant_order"] = [i for i in player.progress.get("implant_order", []) if i != iid]
    return iid


def surgical_shock(player: Player, now: float) -> None:
    player.shock = FAILURE_SHOCK
    player.progress["surgery_shock_until"] = max(now+FAILURE_SHOCK_SECONDS,
                                                player.progress.get("surgery_shock_until", 0))


def enforce_tolerance(player: Player, items: Mapping[str, ItemInstance],
                      templates: Mapping[str, ItemTemplate], modifiers: Modifiers,
                      now: float) -> tuple[str, ...]:
    """Chrome expiry unseats the newest hardware until the body fits.

    The items remain in inventory with their original quality. Increasing
    Vitals before expiry naturally raises capacity and avoids ejection.
    """
    order = player.progress.get("implant_order", [])
    slots = sorted(player.implants, key=lambda s:(
        order.index(player.implants[s]) if player.implants[s] in order else -1, s), reverse=True)
    ejected = []
    for slot in slots:
        if tolerance_used(player, items, templates) <= modifiers.tolerance(player):
            break
        iid = player.implants[slot]
        if templates[items[iid].template].implant.tolerance:
            del player.implants[slot]
            ejected.append(iid)
    if ejected:
        player.progress["implant_order"] = [i for i in order if i not in ejected]
        surgical_shock(player, now)
    return tuple(ejected)
