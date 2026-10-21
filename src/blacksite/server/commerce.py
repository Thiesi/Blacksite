"""S12 social-world adapter. Proposals commit in the I/O layer, then publish."""

from copy import deepcopy
from collections import deque
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any
from collections.abc import Callable

from blacksite.content.schema import ObjectSpec, Vendor, VendorStock
from blacksite.server import bank
from blacksite.server.characters import Characters
from blacksite.server.inventory import Inventory
from blacksite.server.items import CACHE_SECONDS, CONSUMABLE_SECONDS, ItemInstance, availability, make_item
from blacksite.server.loop import TickContext
from blacksite.server.players import Player
from blacksite.server.protocol import Frame
from blacksite.server.sessions import QUEUE_LIMIT, Session
from blacksite.server.vendors import VendorBudget, permitted, price
from blacksite.server.wake import menu
from blacksite.server.world.simulation import MENU_TIMEOUT_SECONDS
from blacksite.server.world.zone import ObjectState
from blacksite.server.clock import TICK_HZ


@dataclass
class CommerceMenu:
    kind: str
    target: str = ""
    cursor: int = 0
    sell: bool = False
    opened: int = 0


class Commerce:
    def __init__(self, characters: Characters, state: dict[str, Any]) -> None:
        self.game, self.sim = characters, characters.sim
        self.clock, self.content = characters.clock, characters.content
        self.items = characters.items
        self.budgets = {key: VendorBudget(**value) for key, value in state.get("budgets", {}).items()}
        self.caches: dict[str, dict[str, Any]] = deepcopy(state.get("caches", {}))
        self.serial = state.get("item_serial", 0)
        self.menus: dict[str, CommerceMenu] = {}
        self.prompts: dict[str, dict[str, Any]] = {}
        self.using: dict[str, dict[str, Any]] = {}
        self.requests: dict[str, list[str]] = {}
        self.outbox: list[dict[str, Any]] = []
        self.pending = False
        self.waiting: deque[tuple[str,str,dict[str,Any],bool] | Callable[[], None]] = deque()
        self.prompt_serial = 0
        self.sync_caches()

    def ready(self, session: Session) -> bool:
        av = self.sim.avatars.get(session.user_id)
        return bool(session.role == "caller" and not session.closed and av and session.player_id == av.actor.id
                    and session.player_id in self.game.players
                    and session.id not in self.game.screens and not av.travel and av.actor.zone
                    and av.actor.stance not in ("down", "dead", "sleeper"))

    def toast(self, session: Session, text: str) -> None:
        session.send(Frame("toast", {"text": text, "role": "ui_text", "seconds": 4}))

    def close(self, session: Session) -> None:
        self.menus.pop(session.id, None)
        self.prompts.pop(session.id, None)
        self.using.pop(session.id, None)
        self.sim.external_views.pop(session.id, None)
        self.sim.reset_view(session, self.sim.avatars[session.user_id])

    def nearby(self, session: Session, target: str) -> Any:
        av = self.sim.avatars[session.user_id]
        obj = self.sim.world.zones[av.zone].objects.get(target)
        if obj is None or max(abs(obj.spec.tile[0]-av.actor.x), abs(obj.spec.tile[1]-av.actor.y)) > 1:
            raise ValueError("Move next to the counter or cache.")
        return obj

    def vendor(self, session: Session, target: str) -> tuple[Vendor, str]:
        obj = self.nearby(session, target)
        vid = obj.spec.params.get("vendor")
        vendor = self.content.vendors.get(vid)
        if not vendor or not self.content.active("vendors", vid) or obj.spec.kind != "vendor":
            raise ValueError("That counter is not open.")
        # The local, server-owned object is the authority. A clinic template
        # serves several halls, with a distinct budget for each object.
        return vendor, self.sim.avatars[session.user_id].zone + ":" + target

    def stock(self, vendor: Vendor) -> list[VendorStock]:
        entries = list(vendor.stock)
        # The catalog requires ammunition alongside every weapon sold.
        seen = {s.item for s in entries}
        for entry in vendor.stock:
            template = self.content.items.get(entry.item)
            ammo = template.weapon.ammo if template and template.weapon else None
            if ammo and ammo not in seen:
                entries.append(VendorStock(ammo))
                seen.add(ammo)
        if vendor.daily_rotation:
            candidates = sorted(i.id for i in self.content.items.values()
                                if i.tier == 2 and i.base_price > 0 and not i.id.startswith("story_"))
            if candidates:
                entries.append(VendorStock(candidates[self.clock.now_utc().date().toordinal() % len(candidates)], price_multiplier=1.4))
        return entries

    def quote(self, player: Player, vendor: Vendor, entry: VendorStock, count: int, quality: float = 1) -> int:
        from fractions import Fraction
        template = self.content.items.get(entry.item)
        base = template.base_price if template else self.content.programs[entry.item].price
        pack = template.stack_max if template and template.class_ == "ammo" else 1
        return price(Fraction(base * count, pack), quality, player.standing.get(vendor.faction or "", 0),
                     player.faction is None, vendor.price_multiplier * entry.price_multiplier)

    def propose(self, session: Session, name: str, args: dict[str, Any], from_channel: bool = False) -> None:
        if self.pending:
            if len(self.waiting) >= QUEUE_LIMIT:
                raise ValueError("The counter is busy. Try again.")
            self.waiting.append((session.id,name,deepcopy(args),from_channel))
            return
        player = self.game.players[session.player_id]
        av = self.sim.avatars[session.user_id]
        self.game.snapshot(player, av)
        draft = deepcopy(player)
        items, caches, budgets = deepcopy(self.items), deepcopy(self.caches), deepcopy(self.budgets)
        inventory = Inventory(items, self.content.items)
        serial = max(self.serial, max((int(i.rsplit(":", 1)[-1]) for i in items), default=0))
        def next_id() -> str:
            nonlocal serial
            serial += 1
            return f"{self.game.sessions.origin}:item:{serial}"
        now = self.clock.now_utc().timestamp()
        iid = args.get("item", "")
        if not isinstance(iid, str):
            raise ValueError("Choose an item.")
        target = args.get("target", "")
        if not isinstance(target, str):
            raise ValueError("Choose a counter or cache.")
        message = "Your transfer settles."
        actor_effects: list[dict[str, Any]] | None = None
        if name.startswith("vendor."):
            vendor, budget_key = self.vendor(session, target)
            if not permitted(player, vendor):
                raise ValueError("This counter requires membership.")
            if not session.allow("trade", self.clock.now_tick(), 1, 1):
                raise ValueError("One counter trade per second.")
            if name == "vendor.buy":
                entry = next((entry for entry in self.stock(vendor) if entry.item == iid), None)
                if entry is None or not permitted(player, vendor, entry):
                    raise ValueError("That stock is not available to you.")
                template = self.content.items.get(iid)
                count = args.get("qty", template.stack_max if template and template.class_ == "ammo" else 1)
                if type(count) is not int or not 1 <= count <= (template.stack_max if template else 1):
                    raise ValueError("Choose one available pack.")
                cost = self.quote(player, vendor, entry, count)
                if cost <= 0:
                    raise ValueError("That item is not for sale.")
                if draft.chits_hand < cost:
                    raise ValueError("You do not have enough chits on hand.")
                if iid.startswith("prg_") or template.class_ == "schematic":
                    key = "known_programs" if iid.startswith("prg_") else "known_schematics"
                    learned = draft.progress.setdefault(key, [])
                    if iid in learned:
                        raise ValueError("You already know that.")
                    learned.append(iid)
                else:
                    inventory.add(draft, make_item(next_id(), template, draft.id, self.clock.now_utc().isoformat(), count))
                draft.chits_hand -= cost
                message = f"Bought {template.name if template else self.content.programs[iid].name} for {cost} chits."
            elif name == "vendor.sell":
                item = inventory.owned(draft, iid)
                template = self.content.items[item.template]
                if item.bound or item.template.startswith("story_") or item.template == "slv_intact" or item.secured:
                    raise ValueError("That item cannot be sold. Unsecure ordinary goods first.")
                count = args.get("qty", item.stack)
                if type(count) is not int or not 1 <= count <= item.stack:
                    raise ValueError("Choose a quantity you carry.")
                proceeds = self.resale(vendor, item, count)
                if not proceeds:
                    raise ValueError("That quantity has no resale value.")
                budget = budgets.setdefault(budget_key, VendorBudget(int(now) // 3600))
                budget.refill(now)
                if budget.remaining < proceeds:
                    raise ValueError("This counter's hourly buy-back budget is spent.")
                inventory.remove(draft, iid, count, next_id)
                budget.remaining -= proceeds
                draft.chits_hand += proceeds
                message = f"Sold {template.name} for {proceeds} chits."
            else:
                raise ValueError("Choose buy or sell.")
        elif name.startswith("bank."):
            if name not in ("bank.deposit", "bank.withdraw"): raise ValueError("Choose deposit or withdraw.")
            if self.nearby(session, target).spec.kind != "bank":
                raise ValueError("Choose a bank branch.")
            bank.transfer(draft, args.get("amount"), name == "bank.deposit")
            message = f"Bank balance: {draft.chits_bank}. Hand: {draft.chits_hand}."
        elif name == "inv.equip": inventory.equip(draft, iid, args.get("slot", ""))
        elif name == "inv.unequip": inventory.unequip(draft, args.get("slot", ""))
        elif name == "inv.secure": inventory.secure(draft, iid)
        elif name == "inv.split": inventory.split(draft, iid, args.get("qty"), next_id)
        elif name == "inv.drop":
            item = inventory.owned(draft, iid)
            if item.bound or item.template.startswith("story_"):
                raise ValueError("Bound and story items stay with you.")
            part = inventory.remove(draft, iid, args.get("qty", item.stack), next_id)
            if part.secured:
                raise ValueError("Unsecure that item before dropping it.")
            cache_id = f"{self.game.sessions.origin}:cache:{next_id().rsplit(':', 1)[1]}"
            part.owner = cache_id
            items[part.id] = part
            caches[cache_id] = {"zone": av.zone, "tile": list(av.actor.position), "items": [part.id], "expires": now + CACHE_SECONDS}
            message = f"Dropped {self.content.items[part.template].name}."
        elif name == "inv.pickup":
            self.nearby(session, target)
            cache = caches.get(target)
            if not cache or cache["expires"] <= now or iid not in cache["items"]:
                raise ValueError("That cache is empty.")
            if cache.get("private_until",0)>now and draft.id not in (cache.get("killer"),cache.get("victim")):
                raise ValueError("The victim and killer have first recovery rights for sixty seconds.")
            item = items[iid]
            if item.owner != target:
                raise ValueError("That item is no longer in the cache.")
            cache["items"].remove(iid)
            inventory.add(draft, item)
            if not cache["items"]: del caches[target]
            message = "You pick up the item."
        elif name == "inv.use":
            if any(effect.get("hush") for effect in av.actor.effects):
                raise ValueError("You cannot use consumables yet.")
            item = inventory.owned(draft, iid)
            template = self.content.items[item.template]
            block = template.consumable
            if not block:
                raise ValueError(availability(template) or "You cannot use that item here.")
            if draft.progress.get("item_cooldowns", {}).get(block.cooldown_class, 0) > now:
                raise ValueError("That consumable class is cooling down.")
            if block.use_seconds and not from_channel:
                self.using[session.id] = {"item": iid, "zone": av.zone, "tile": av.actor.position,
                    "until": now + block.use_seconds, "last_hit": av.actor.cooldowns.get("last_hit")}
                self.toast(session, "You use the kit. Stay still; Esc cancels.")
                return
            effects = block.effects
            actor_effects = deepcopy(av.actor.effects)
            supported = False
            if "health" in effects:
                draft.health = min(av.actor.health_max, draft.health + effects["health"]); supported = True
            if "stamina" in effects or "stamina_full" in effects:
                draft.stamina = av.actor.stamina_max if effects.get("stamina_full") else min(av.actor.stamina_max, draft.stamina + effects["stamina"])
                supported = True
            draft.shock = min(100, draft.shock + effects.get("shock", 0))
            if effects.get("remove_ring_dust_crash"):
                actor_effects = [e for e in actor_effects if e.get("kind") != "ring_dust_crash"]
            if effects.get("end_chemical_dot"):
                actor_effects = [e for e in actor_effects if e.get("damage_type") != "chemical"]; supported = True
            if effects.get("recharge_cell"):
                cell = next((i for i in items.values() if i.owner == draft.id and i.template == "ammo_cell"
                    and i.stack < self.content.items["ammo_cell"].stack_max), None)
                if not cell: raise ValueError("You carry no depleted energy cell.")
                cell.stack = self.content.items["ammo_cell"].stack_max; supported = True
            if effects.get("dark_sight"):
                actor_effects.append({"kind": "flare", "dark_sight": effects["dark_sight"], "expires": now + effects["seconds"]}); supported = True
            draft.progress["item_effects"] = [e for e in actor_effects if e.get("kind") == "flare"]
            if not supported: raise ValueError(availability(template))
            if item.charges > 1: item.charges -= 1
            else: inventory.remove(draft, iid, 1, next_id)
            draft.progress.setdefault("item_cooldowns", {})[block.cooldown_class] = now + CONSUMABLE_SECONDS
            message = f"Used {template.name}."
        else: raise ValueError("Unknown item action.")
        if message == "Your transfer settles.":
            verb = {"inv.equip":"Equipped", "inv.unequip":"Unequipped", "inv.secure":"Changed secured status for", "inv.split":"Split"}.get(name, "Updated")
            label = self.content.items[self.items[iid].template].name if iid in self.items else args.get("slot", "equipment")
            message = f"{verb} {label}."
        patches = {key: deepcopy(getattr(draft, key)) for key in ("inventory", "equipment", "chits_hand", "chits_bank", "health", "stamina", "shock", "progress")
                   if getattr(draft, key) != getattr(player, key)}
        self.outbox.append({"session": session.id, "player_id": player.id, "patch": patches,
            "progress_base":deepcopy(player.progress),
            "items": {key: item for key, item in items.items() if item != self.items.get(key)},
            "delete_items": sorted(set(self.items) - set(items)), "caches": caches, "budgets": budgets, "serial": serial,
            "message": message, "actor_effects": actor_effects})
        self.pending = True

    def prepare(self, effect: dict[str, Any]) -> dict[str, Any]:
        player = self.game.players.get(effect["player_id"])
        return {"player": {**player.record(), **self.settled_patch(effect)} if player else None,
            "items": [item.record() for item in effect["items"].values()],
            "delete_items": effect["delete_items"], "caches": effect["caches"],
            "budgets": {key: asdict(value) for key, value in effect["budgets"].items()}, "serial": effect["serial"],
            **({"npc_state": effect["npc_state"]} if "npc_state" in effect else {}),
            **({"identity":effect["identity"], "user":player.bbs_user_id} if "identity" in effect else {})}

    def settled_patch(self, effect: dict[str, Any]) -> dict[str, Any]:
        patch = deepcopy(effect["patch"])
        player = self.game.players.get(effect["player_id"])
        if player and "progress" in patch and "progress_base" in effect:
            base,desired = effect["progress_base"],patch["progress"]
            current = deepcopy(player.progress)
            for key in base.keys()|desired.keys():
                if key not in desired: current.pop(key,None)
                elif key not in base or desired[key] != base[key]: current[key] = deepcopy(desired[key])
            patch["progress"] = current
        return patch

    def enqueue_system(self, action: Callable[[], None]) -> None:
        """Server-owned combat actions share the bounded transfer queue."""
        if self.pending:
            if len(self.waiting) >= QUEUE_LIMIT:
                raise ValueError("The city is busy. Try again.")
            self.waiting.append(action)
        else:
            action()

    def settle(self, player: Player | None, patch: dict[str, Any], items: dict[str, ItemInstance],
               caches: dict[str, dict[str, Any]], serial: int,
               callback: Callable[[bool], None], identity: dict[str, Any] | None = None) -> bool:
        """A server proposal; only its commit callback changes live combat."""
        if self.pending:
            return False
        effect = {"session":"", "player_id":player.id if player else "", "patch":deepcopy(patch),
            "progress_base":deepcopy(player.progress) if player else {},
            "items":{key:value for key,value in items.items() if value != self.items.get(key)},
            "delete_items":sorted(set(self.items)-set(items)), "caches":deepcopy(caches),
            "budgets":deepcopy(self.budgets), "serial":serial, "message":"", "actor_effects":None,
            "callback":callback}
        if identity is not None: effect["identity"] = deepcopy(identity)
        self.outbox.append(effect)
        self.pending = True
        return True

    def committed(self, effect: dict[str, Any], success: bool) -> None:
        self.pending = False
        session = self.game.sessions.active.get(effect["session"])
        if success:
            player = self.game.players.get(effect["player_id"])
            if player:
                for key, value in self.settled_patch(effect).items(): setattr(player, key, value)
                if "identity" in effect: self.game.identities[player.bbs_user_id] = effect["identity"]
            for iid in effect["delete_items"]: self.items.pop(iid, None)
            self.items.update(effect["items"])
            self.game.item_templates = {key: item.template for key, item in self.items.items()}
            self.caches, self.budgets, self.serial = effect["caches"], effect["budgets"], effect["serial"]
            self.sync_caches()
            if session and session.player_id == effect["player_id"]:
                av = self.sim.avatars.get(session.user_id)
                if av:
                    av.actor.overweight = Inventory(self.items, self.content.items).weight(player) > player.attributes["frame"] / 2
                    for key in ("health", "stamina", "shock"):
                        if key in effect["patch"]: setattr(av.actor, key, effect["patch"][key])
                    if effect["actor_effects"] is not None: av.actor.effects = effect["actor_effects"]
                    self.sim.world.zones[av.zone].revision += 1
                session.send(Frame("log", {"lines": [{"channel": "system", "text": effect["message"], "role": "chan_sys", "at": self.clock.now_utc().isoformat()}]}))
                self.toast(session, effect["message"])
        elif session:
            self.toast(session, "The transfer could not be saved. Your goods remain.")
        if effect.get("callback"): effect["callback"](success)
        while self.waiting and not self.pending:
            job = self.waiting.popleft()
            if callable(job):
                job()
                continue
            sid,name,args,from_channel = job
            queued = self.game.sessions.active.get(sid)
            if queued is None or not self.ready(queued): continue
            try:
                self.propose(queued,name,args,from_channel)
            except (ValueError,KeyError,TypeError) as exc:
                self.toast(queued,str(exc) if isinstance(exc,ValueError) else "That action is no longer available.")

    def sync_caches(self) -> None:
        for zone in self.sim.world.zones.values():
            for key in tuple(zone.objects):
                if zone.objects[key].spec.params.get("dropped_item") and key not in self.caches:
                    del zone.objects[key]; zone.revision += 1
        for key, cache in self.caches.items():
            zone = self.sim.world.zones.get(cache["zone"])
            if zone and key not in zone.objects:
                zone.objects[key] = ObjectState(ObjectSpec(key, tuple(cache["tile"]), "cache", params={"dropped_item": True,
                    "name": "Corpse cache" if cache.get("victim") else "Dropped goods",
                    "cache_state":{"items":len(cache["items"]),"killer_only_until":cache.get("private_until",0)}}))
                zone.revision += 1

    def prompt(self, session: Session, name: str, args: dict[str, Any]) -> None:
        self.prompt_serial += 1
        token = f"item:{session.id}:{self.prompt_serial}"
        self.prompts[session.id] = {"id": token, "name": name, "args": args}
        session.send(Frame("prompt", {"id": token, "kind": "line", "label": "Chits" if name.startswith("bank.") else "Quantity", "max_len": 10}))

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        if not self.ready(session): return False
        if session.pending_prompts.get("chat"): return False
        name = frame.data.get("name", "") if frame.type == "intent" else ""
        args = frame.data.get("args", {})
        key = frame.data.get("k", "") if frame.type == "key" else ""
        pending = self.prompts.get(session.id)
        try:
            if pending:
                if name == "prompt_cancel" and args.get("id") == pending["id"]:
                    self.prompts.pop(session.id); return True
                if frame.type == "line" and frame.data["id"] == pending["id"]:
                    self.prompts.pop(session.id)
                    value = frame.data["text"]
                    if not value.isascii() or not value.isdigit(): raise ValueError("Enter a positive whole number.")
                    self.propose(session, pending["name"], {**pending["args"], "amount" if pending["name"].startswith("bank.") else "qty": int(value)})
                return True
            if session.id in self.using and key in ("escape", "b", "B"):
                self.using.pop(session.id); return True
            if name.startswith(("inv.", "vendor.", "bank.")):
                if name == "inv.open":
                    self.menus[session.id] = CommerceMenu("inventory", opened=tick)
                else:
                    request = frame.data.get("request_id")
                    if request and request in self.requests.get(session.id, []): return True
                    self.propose(session, name, args)
                    if request:
                        self.requests.setdefault(session.id, []).append(request)
                        self.requests[session.id] = self.requests[session.id][-128:]
                return True
            screen = self.menus.get(session.id)
            if screen:
                if name == "menu_close": self.close(session)
                elif name == "menu_cursor" and type(args.get("delta")) is int:
                    screen.cursor = max(0, min(screen.cursor + args["delta"], len(self.body(session, screen)["rows"])-1))
                elif name == "menu_select":
                    if frame.data.get("expected_revision") != session.view_revision: return True
                    request = frame.data.get("request_id", "")
                    if request and request in self.requests.get(session.id, []): return True
                    self.requests.setdefault(session.id, []).append(request)
                    self.requests[session.id] = self.requests[session.id][-128:]
                    action, row = args.get("key", "enter"), args.get("row", "")
                    self.select(session, screen, action, row)
                return True
            if session.id in self.game.screens or session.id in self.sim.maps or session.id in self.sim.external_views: return False
            table = next((m for m in self.sim.keymap.get("keymaps", []) if m["id"] == session.keymap_id), {})
            action = next((a for a, keys in table.get("bindings", {}).items() if key in keys), name)
            if action == "inventory": self.menus[session.id] = CommerceMenu("inventory", opened=tick); return True
            if action == "equipment": self.menus[session.id] = CommerceMenu("equipment", opened=tick); return True
            if action == "interact" or key in ("e", "E"):
                av = self.sim.avatars[session.user_id]
                zone = self.sim.world.zones[av.zone]
                objects = sorted((o for o in zone.objects.values() if max(abs(o.spec.tile[0]-av.actor.x),abs(o.spec.tile[1]-av.actor.y)) <= 1),
                    key=lambda o:(o.spec.tile != av.actor.position, o.spec.id))
                if objects:
                    obj = objects[0]
                    if obj.spec.kind == "bank" or obj.spec.id in self.caches or obj.spec.params.get("vendor"):
                        kind = "bank" if obj.spec.kind == "bank" else "cache" if obj.spec.id in self.caches else "vendor"
                        self.menus[session.id] = CommerceMenu(kind, obj.spec.id, opened=tick); return True
        except (ValueError, KeyError, TypeError) as exc:
            self.toast(session, str(exc) if isinstance(exc, ValueError) else "That action is no longer available.")
            return True
        return False

    def select(self, session: Session, screen: CommerceMenu, action: str, row: str) -> None:
        if screen.kind == "vendor":
            if action == "t": screen.sell, screen.cursor = not screen.sell, 0; return
            self.propose(session, "vendor.sell" if screen.sell else "vendor.buy", {"target": screen.target, "item": row})
        elif screen.kind == "bank":
            self.prompt(session, "bank.withdraw" if row == "withdraw" else "bank.deposit", {"target": screen.target})
        elif screen.kind == "cache": self.propose(session, "inv.pickup", {"target": screen.target, "item": row})
        elif screen.kind == "equipment":
            if action == "enter": self.propose(session, "inv.unequip", {"slot": row})
        elif screen.kind == "slots":
            self.propose(session, "inv.equip", {"item": screen.target, "slot": row})
            self.menus[session.id] = CommerceMenu("inventory", opened=screen.opened)
        else:
            if action == "e": self.menus[session.id] = CommerceMenu("equipment", opened=screen.opened); return
            if action == "f":
                player = self.game.players[session.player_id]
                Inventory(self.items,self.content.items).slots(player,row)
                self.menus[session.id] = CommerceMenu("slots",row,opened=screen.opened); return
            command = {"enter":"inv.equip", "q":"inv.equip", "s":"inv.secure", "d":"inv.drop", "u":"inv.use", "x":"inv.split"}.get(action)
            if command == "inv.split": self.prompt(session, command, {"item": row})
            elif command: self.propose(session, command, {"item": row})

    def resale(self, vendor: Vendor, item: ItemInstance, count: int) -> int:
        template = self.content.items[item.template]
        pack = template.stack_max if template.class_ == "ammo" else 1
        multiplier = vendor.salvage_multiplier if template.class_ == "salvage" else 1
        return price(Fraction(template.base_price * count, pack), item.quality, multiplier=multiplier, resale=True)

    def body(self, session: Session, screen: CommerceMenu) -> dict[str, Any]:
        player = self.game.players[session.player_id]
        rows: list[dict[str, Any]] = []
        detail, title, actions = "", screen.kind.upper(), []
        inventory = Inventory(self.items, self.content.items)
        if screen.kind == "vendor":
            vendor, budget_key = self.vendor(session, screen.target)
            budget = deepcopy(self.budgets.get(budget_key, VendorBudget(int(self.clock.now_utc().timestamp())//3600)))
            budget.refill(self.clock.now_utc().timestamp())
            title = vendor.name
            title += " - " + ("SELL" if screen.sell else "BUY")
            detail = f"Hand {player.chits_hand}  Buy-back budget {budget.remaining}/2000"
            if screen.sell:
                for iid in player.inventory:
                    item = self.items[iid]
                    locked = (item.bound or item.secured or item.template.startswith("story_")
                              or item.template == "slv_intact" or iid in player.implants.values())
                    proceeds = self.resale(vendor, item, item.stack)
                    rows.append({"id": iid, "cells": [self.content.items[item.template].name,
                        str(item.stack), str(proceeds) if proceeds and not locked else "not for sale"]})
            else:
                for entry in self.stock(vendor):
                    template = self.content.items.get(entry.item)
                    count = template.stack_max if template and template.class_ == "ammo" else 1
                    label = template.name if template else self.content.programs.get(entry.item).name if entry.item in self.content.programs else entry.item
                    allowed = permitted(player, vendor, entry) and self.content.active("items", entry.item)
                    cost = self.quote(player, vendor, entry, count) if template or entry.item in self.content.programs else 0
                    rows.append({"id": entry.item, "cells": [label, str(count), str(cost) if cost else "not for sale", "" if allowed else "locked"]})
            actions = [{"key":"enter", "label":"sell" if screen.sell else "buy"}, {"key":"t","label":"buy/sell"}]
        elif screen.kind == "bank":
            self.nearby(session, screen.target)
            title = "KESTREL BANK"
            rows = [{"id": "deposit", "cells": ["Deposit", str(player.chits_hand)]}, {"id":"withdraw", "cells":["Withdraw",str(player.chits_bank)]}]
            detail = f"Hand {player.chits_hand}\nBank {player.chits_bank}\nChoose an action, then enter chits."
        elif screen.kind == "equipment":
            rows = [{"id": slot, "cells": [slot.replace("_"," ").title(), self.content.items[self.items[iid].template].name]} for slot,iid in player.equipment.items() if iid in self.items]
            actions = [{"key":"enter", "label":"unequip"}]
        elif screen.kind == "slots":
            title = "CHOOSE EQUIPMENT SLOT"
            rows = [{"id":slot,"cells":[slot.replace("_"," ").title(), self.content.items[self.items[player.equipment[slot]].template].name if slot in player.equipment else "Empty"]}
                    for slot in inventory.slots(player,screen.target)]
        else:
            ids = player.inventory if screen.kind == "inventory" else self.caches.get(screen.target, {}).get("items", [])
            if screen.kind == "cache": self.nearby(session, screen.target)
            for iid in ids:
                item = self.items[iid]
                slot = next((key for key,value in player.equipment.items() if value == iid), "")
                rows.append({"id": iid, "cells": [self.content.items[item.template].name, str(item.stack), f"{self.content.items[item.template].weight*item.stack:g}kg", "S" if item.secured else "", slot]})
            detail = f"Carry {inventory.weight(player):g}/{player.attributes['frame']/2:g} kg. Three secured slots."
            if screen.kind == "inventory":
                actions = [{"key":k,"label":v} for k,v in (("q","equip"),("f","slot"),("e","equipment"),("s","secure"),("d","drop"),("x","split"),("u","use"))]
        screen.cursor = max(0, min(screen.cursor, len(rows)-1))
        if rows:
            selected = rows[screen.cursor]["id"]
            template = self.content.items.get(selected) if screen.kind == "vendor" and not screen.sell else self.content.items.get(self.items[selected].template) if selected in self.items else None
            if template:
                detail += "\n" + availability(template) + "\n" + template.description
                if template.weapon: detail += f"\nDamage {template.weapon.damage}, range {template.weapon.range or 'melee'}."
                if template.armour:
                    values=template.armour.armour
                    detail += f"\nArmour K{values.kinetic} E{values.energy} C{values.chemical} D{values.dissonance}"
        return {**menu(title, rows, screen.cursor, detail, "Esc/B returns"), "actions": actions,
                "page": 2 if screen.sell else 1}

    def tick(self, ctx: TickContext) -> None:
        now = self.clock.now_utc().timestamp()
        self.requests = {sid: rows for sid,rows in self.requests.items() if sid in self.game.sessions.active}
        self.prompts = {sid: prompt for sid,prompt in self.prompts.items() if sid in self.game.sessions.active}
        for session in ctx.sessions:
            av = self.sim.avatars.get(session.user_id)
            if av and session.player_id in self.game.players:
                player = self.game.players[session.player_id]
                av.actor.overweight = Inventory(self.items, self.content.items).weight(player) > player.attributes["frame"] / 2
                before = deepcopy(av.actor.effects)
                for effect in player.progress.get("item_effects", []):
                    if effect.get("expires",0) > now and effect not in av.actor.effects: av.actor.effects.append(effect)
                av.actor.effects[:] = [effect for effect in av.actor.effects if effect.get("expires", now+1) > now]
                if before != av.actor.effects: self.sim.world.zones[av.zone].revision += 1
        for sid, use in tuple(self.using.items()):
            session = self.game.sessions.active.get(sid)
            av = self.sim.avatars.get(session.user_id) if session else None
            if not session or not self.ready(session) or (av.zone, av.actor.position, av.actor.cooldowns.get("last_hit")) != (use["zone"],use["tile"],use["last_hit"]):
                self.using.pop(sid); continue
            if now >= use["until"] and not self.pending:
                self.using.pop(sid)
                try: self.propose(session, "inv.use", {"item":use["item"]}, from_channel=True)
                except ValueError as exc: self.toast(session, str(exc))
        if not self.pending:
            expired = {key for key, value in self.caches.items() if value["expires"] <= now}
            if expired:
                self.outbox.append({"session":"", "player_id":None, "patch":{}, "items":{}, "delete_items":[key for key,item in self.items.items() if item.owner in expired],
                    "caches":{key:cache for key,cache in self.caches.items() if key not in expired}, "budgets":deepcopy(self.budgets), "serial":self.serial,
                    "message":"", "actor_effects":None})
                self.pending = True
        for sid, screen in tuple(self.menus.items()):
            session = self.game.sessions.active.get(sid)
            if session is None or not self.ready(session):
                self.menus.pop(sid); self.prompts.pop(sid,None); self.sim.external_views.pop(sid,None); continue
            av = self.sim.avatars[session.user_id]
            if ctx.tick-screen.opened >= MENU_TIMEOUT_SECONDS*TICK_HZ and self.sim.world.zones[av.zone].allows_hostile(av.actor.position):
                self.close(session); continue
            try: self.sim.external_views[sid] = "menu", self.body(session, screen)
            except (ValueError, KeyError): self.close(session)
