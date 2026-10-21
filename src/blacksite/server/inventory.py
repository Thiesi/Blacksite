"""Pure inventory operations; callers transact copies before publishing."""

from collections.abc import Callable
from dataclasses import replace

from blacksite.content.schema import ItemTemplate
from blacksite.server.items import ItemInstance, SECURED_SLOTS
from blacksite.server.players import Player


class Inventory:
    def __init__(self, items: dict[str, ItemInstance], templates: dict[str, ItemTemplate]) -> None:
        self.items, self.templates = items, templates

    def owned(self, player: Player, iid: str) -> ItemInstance:
        item = self.items.get(iid)
        if item is None or iid not in player.inventory or item.owner != player.id:
            raise ValueError("You do not carry that item.")
        return item

    def weight(self, player: Player) -> float:
        return sum(self.templates[self.items[i].template].weight * self.items[i].stack
                   for i in player.inventory if i in self.items and i not in player.implants.values())

    def add(self, player: Player, item: ItemInstance) -> None:
        template = self.templates[item.template]
        item.owner = player.id
        # Installed/equipped stacks cannot absorb other instances.
        for iid in player.inventory:
            target = self.items[iid]
            if (iid not in (*player.equipment.values(), *player.implants.values())
                    and (target.template, target.quality, target.secured, target.bound, target.charges, target.ammo)
                    == (item.template, item.quality, item.secured, item.bound, item.charges, item.ammo)):
                moved = min(item.stack, template.stack_max - target.stack)
                target.stack += moved
                item.stack -= moved
                if not item.stack:
                    self.items.pop(item.id, None)
                    return
        if item.secured and sum(self.items[i].secured for i in player.inventory) >= SECURED_SLOTS:
            raise ValueError("Your secured slots are full.")
        self.items[item.id] = item
        player.inventory.append(item.id)

    def remove(self, player: Player, iid: str, count: int, next_id: Callable[[], str]) -> ItemInstance:
        item = self.owned(player, iid)
        if type(count) is not int or not 1 <= count <= item.stack:
            raise ValueError("Choose a quantity you carry.")
        if iid in player.implants.values():
            raise ValueError("Installed implants require surgery.")
        if count == item.stack:
            player.inventory.remove(iid)
            player.equipment = {slot: equipped for slot, equipped in player.equipment.items() if equipped != iid}
            return self.items.pop(iid)
        item.stack -= count
        return replace(item, id=next_id(), stack=count)

    def split(self, player: Player, iid: str, count: int, next_id: Callable[[], str]) -> None:
        item = self.owned(player, iid)
        if type(count) is not int or not 0 < count < item.stack:
            raise ValueError("Split fewer than the whole stack.")
        if item.secured and sum(self.items[i].secured for i in player.inventory) >= SECURED_SLOTS:
            raise ValueError("Your secured slots are full.")
        part = replace(item, id=next_id(), stack=count)
        item.stack -= count
        self.items[part.id] = part
        player.inventory.append(part.id)

    def secure(self, player: Player, iid: str) -> None:
        item = self.owned(player, iid)
        if not item.secured and sum(self.items[i].secured for i in player.inventory) >= SECURED_SLOTS:
            raise ValueError("You have three secured slots.")
        if item.secured and item.template.startswith("story_"):
            raise ValueError("Story items remain secured.")
        item.secured = not item.secured

    def slots(self, player: Player, iid: str) -> tuple[str, ...]:
        item = self.owned(player, iid)
        template = self.templates[item.template]
        if template.requires_archetype and template.requires_archetype != player.archetype:
            raise ValueError("Your archetype cannot equip that item.")
        if (template.weapon and template.weapon.heavy or template.armour and template.armour.heavy) and player.archetype != "hardline":
            raise ValueError("Heavy equipment requires Hardline.")
        if template.weapon:
            allowed = ("melee",) if template.weapon.melee else ("weapon_main", "weapon_side")
        elif template.armour:
            allowed = (template.armour.slot,)
        elif template.class_ == "rig" and template.implant and template.implant.tolerance == 0:
            allowed = ("rig",)
        elif template.class_ == "consumable":
            allowed = tuple(f"quick{i}" for i in range(1, 6))
        else:
            raise ValueError("That item has no equipment slot.")
        return allowed

    def equip(self, player: Player, iid: str, slot: str = "") -> None:
        allowed = self.slots(player, iid)
        slot = {"torso": "body", "arms": "hands"}.get(slot, slot) or allowed[0]
        if slot not in allowed:
            raise ValueError("That item does not fit that slot.")
        player.equipment = {s: value for s, value in player.equipment.items() if value != iid}
        player.equipment[slot] = iid

    def unequip(self, player: Player, slot: str) -> None:
        if slot not in player.equipment:
            raise ValueError("That slot is empty.")
        del player.equipment[slot]
