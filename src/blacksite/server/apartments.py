"""Game 8.7: rental proposals, personal storage and protected impound."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from blacksite.server import bank
from blacksite.server.clock import TICK_HZ
from blacksite.server.housing_geometry import HousingGeometry, Unit
from blacksite.server.housing_rules import (LAPSE_SECONDS, NOTICE_SECONDS, PROTECTED_DIVISOR,
    VESTIBULE_SECONDS, WEEK_SECONDS, charge, reclaim_fee, reconcile, rent_amount)
from blacksite.server.inventory import Inventory
from blacksite.server.items import ItemInstance, make_item
from blacksite.server.loop import TickContext
from blacksite.server.players import Player
from blacksite.server.progression_engine import ProgressionEngine
from blacksite.server.protocol import Frame
from blacksite.server.quality import detail as item_detail
from blacksite.server.sessions import Session
from blacksite.server.wake import menu
from blacksite.server.world.simulation import MENU_TIMEOUT_SECONDS


@dataclass
class HousingMenu:
    kind: str
    target: str
    cursor: int = 0
    opened: int = 0
    deposit: bool = True
    confirm: str = ""


class Apartments:
    def __init__(self, progression: ProgressionEngine, geometry: HousingGeometry) -> None:
        self.progression, self.geometry = progression, geometry
        self.game, self.commerce, self.clock = progression.game, progression.commerce, progression.clock
        self.sim, self.content, self.lat = self.commerce.sim, progression.content, progression.lattice
        self.interlock, self.private = self.lat.interlock, self.lat.interlock.private
        self.state.setdefault("impounds", {})
        self.state.setdefault("housing_serial", 0)
        self.state.setdefault("unit_hacks", {})
        geometry.leases = lambda: self.state["apartments"]
        self.menus: dict[str, HousingMenu] = {}
        self.prompts: dict[str, dict[str, Any]] = {}
        self.requests: dict[str, list[str]] = {}
        self.checks: set[str] = set()
        self.pending_rent: set[str] = set()
        self.rent_modifier: Callable[[Player, float], float] = lambda player, due: 1  # S21.
        self.private_core_ice_slots: Callable[[Player], int] = lambda player: 0  # S21.
        self.prompt_serial = 0
        attached = self.game.attached
        def on_attached(session: Session, player: Player) -> None:
            attached(session, player)
            self.checks.add(player.id)
            notice = player.progress.pop("housing_notice", "")
            if notice:
                self.log(player, notice)
                self.game.queue("save", player.bbs_user_id, player, immediate=True)
        self.game.attached = on_attached
        self.commerce.item_label = self.label
        self.private.before_access = self.ensure_rent
        self.private.extra_ice = lambda record: self.private_core_ice_slots(self.game.players[record["resident"]]) if record["resident"] in self.game.players else 0
        self.bindings()

    @property
    def state(self) -> dict[str, Any]:
        return self.interlock.state

    def now(self) -> float:
        return self.clock.now_utc().timestamp()

    def lease(self, player: Player) -> dict[str, Any] | None:
        record = self.state["apartments"].get(player.apartment_id)
        return record if record and record.get("resident") == player.id and record.get("unit") in self.geometry.units else None

    def unit_lease(self, unit: Unit) -> dict[str, Any] | None:
        return self.geometry.lease(unit)

    def label(self, item: ItemInstance) -> str:
        if not item.key_for:
            return self.content.items[item.template].name
        lease = self.state["apartments"].get(item.key_for)
        if not lease or lease.get("lock_tier", 1) > item.key_tier:
            return "Expired apartment key"
        unit = self.geometry.units.get(lease.get("unit"))
        return (self.unit_label(unit)+" key") if unit else "Apartment key"

    def unit_label(self, unit: Unit) -> str:
        obj = self.game.world.zones[unit.zone].objects[unit.door]
        return str(obj.spec.params.get("name", unit.definition.name))

    def log(self, player: Player, text: str) -> None:
        session = self.game.combat.session(player.id)
        if session and not session.closed:
            self.sim.log(session, text)
            self.commerce.toast(session, text)

    def ready(self, session: Session) -> Player:
        if not self.commerce.ready(session):
            raise ValueError("Return to your body before using housing services.")
        return self.game.players[session.player_id]

    def resident(self, session: Session, aid: str) -> tuple[Player, dict[str, Any], Unit]:
        player = self.ready(session)
        record = self.lease(player)
        unit = self.geometry.units.get(record.get("unit")) if record else None
        actor = self.game.combat.actor(player)
        if not record or record["id"] != aid or not unit or not actor or actor.zone != unit.zone or not unit.region.contains(actor.position):
            raise ValueError("Only the current resident inside this room may use its services.")
        return player, record, unit

    def counter(self, session: Session, target: str, letting: bool = False) -> None:
        self.ready(session)
        obj = self.commerce.nearby(session, target)
        if letting and not obj.spec.params.get("letting"):
            raise ValueError("Choose a commissioned letting terminal.")
        if not letting and obj.spec.kind != "bank":
            raise ValueError("Collect impound goods at a Kestrel bank.")

    def commit(self, proposal: dict[str, Any], player: Player | None, draft: Player | None,
               items: dict[str, ItemInstance], serial: int, message: str,
               after: Callable[[], None] = lambda: None) -> bool:
        old = deepcopy(self.state)
        patch = {key: deepcopy(getattr(draft, key)) for key in ("inventory", "equipment", "chits_hand", "chits_bank",
            "apartment_id", "progress", "zone", "tile") if draft and getattr(draft, key) != getattr(player, key)}
        def finished(success: bool) -> None:
            if success:
                self.interlock.state = proposal
                self.sync_cores(old)
                self.bindings()
                if player:
                    self.progression.sync_actor(player)
                    if message:
                        self.log(player, message)
                after()
            elif player:
                self.log(player, "The housing transfer could not be saved. Your goods remain.")
        if not self.commerce.settle(player, patch, items, self.commerce.caches, serial, finished):
            return False
        self.commerce.outbox[-1]["interlock_state"] = proposal
        return True

    def sync_cores(self, old: dict[str, Any]) -> None:
        current = self.state["apartments"]
        for aid, record in old["apartments"].items():
            if aid not in current:
                self.remove_core(record)
        for aid, record in current.items():
            if record.get("unit") not in self.geometry.units:
                continue
            if aid not in old["apartments"] or record["tier"] != old["apartments"][aid]["tier"]:
                if aid in old["apartments"]:
                    self.remove_core(old["apartments"][aid])
                self.private.install(record)

    def remove_core(self, record: dict[str, Any]) -> None:
        cid = self.private.core_id(record)
        for presence in tuple(self.lat.presences.values()):
            if presence.core == cid:
                session = self.lat.session(presence.player_id)
                if session is None and presence.player_id in self.lat.orphans:
                    session = self.lat.orphans[presence.player_id][0]
                if session:
                    self.lat.leave(session, transition=False)
        self.content.cores.pop(cid, None)
        self.interlock.hardware.pop((record["zone"], record["hardware"]), None)
        for key in tuple(self.interlock.controls):
            if key[0] == cid:
                self.interlock.controls.pop(key)
        base = next(cell for cell in self.content.sectors[record["sector"]].cells if cell.id == record["cell"])
        self.lat.sectors.cells[record["sector"]][base.id] = base
        sector = self.lat.sectors.records[record["sector"]]
        self.lat.sectors.records[sector.id] = replace(sector, cells=tuple(base if cell.id == base.id else cell for cell in sector.cells))
        for iid, instance in tuple(self.lat.encounters.instances.items()):
            if instance.graph.spec.id == cid:
                self.lat.encounters.instances.pop(iid)

    def bindings(self) -> None:
        for unit in self.geometry.units.values():
            zone = self.game.world.zones[unit.zone]
            obj, record = zone.objects[unit.door], self.unit_lease(unit)
            previous = obj.spec.params.get("apartment_id")
            params = {key: value for key, value in obj.spec.params.items() if key != "apartment_id"}
            if record:
                params["apartment_id"] = record["id"]
            obj.spec = replace(obj.spec, params=params)
            obj.state["lock_tier"] = record["lock_tier"] if record else unit.definition.lock_tier
            if previous != (record["id"] if record else None):
                obj.open = False
                self.interlock.applied.pop((unit.zone, unit.door), None)
            zone.revision += 1
        for actor in tuple(self.game.world.actors.values()):
            unit = self.geometry.containing(actor.zone, actor.position) if actor.zone else None
            if unit and not self.geometry.can_enter(actor, unit.zone, actor.position):
                self.move_out(actor, unit)
            self.geometry.mark(actor)
        self.interlock.compose()

    def move_out(self, actor: Any, unit: Unit) -> None:
        tile = self.game.world.free_tile(unit.zone, unit.anchor.doorstep, actor)
        self.game.world.enter(actor, unit.zone, tile)
        player = self.game.players.get(actor.id)
        if player:
            session = self.game.combat.session(player.id)
            avatar = self.sim.avatars.get(session.user_id) if session else None
            if avatar:
                avatar.zone = unit.zone
                self.game.snapshot(player, avatar)
                self.game.queue("save", player.bbs_user_id, player, immediate=True)
                self.sim.reset_view(session, avatar)

    def impound(self, proposal: dict[str, Any], items: dict[str, ItemInstance], pid: str,
                ids: list[str], chits: int = 0, fees: bool = False) -> None:
        destination = proposal.setdefault("impounds", {}).setdefault(pid, {"items": {}, "chits": 0})
        for iid in ids:
            item = items[iid]
            destination["items"][iid] = {"fee": reclaim_fee(item, self.content.items[item.template]) if fees else 0}
            item.owner = "impound:"+pid
        destination["chits"] += chits

    def revoke(self, proposal: dict[str, Any], record: dict[str, Any], draft: Player,
               items: dict[str, ItemInstance], fees: bool) -> None:
        self.impound(proposal, items, draft.id, record["storage"], record["safe_chits"], fees)
        proposal["apartments"].pop(record["id"])
        cid = self.private.core_id(record)
        proposal["cores"].pop(cid, None)
        proposal["effects"] = {key: effect for key, effect in proposal["effects"].items() if effect["core"] != cid}
        draft.apartment_id = None
        unit = self.geometry.units[record["unit"]]
        if draft.zone == unit.zone and unit.region.contains(draft.tile):
            draft.tile = unit.anchor.doorstep
        draft.progress["housing_notice"] = "Your lease ends. Your goods wait in Kestrel impound."

    def ensure_rent(self, pid: str) -> bool:
        player = self.game.players.get(pid)
        record = self.lease(player) if player else None
        if not record or self.now() < record["rent_paid_until"]:
            return True
        if pid in self.pending_rent:
            return False
        if self.commerce.pending:
            self.pending_rent.add(pid)
            def later() -> None:
                self.pending_rent.discard(pid)
                self.ensure_rent(pid)
            try:
                self.commerce.enqueue_system(later)
            except ValueError:
                self.pending_rent.discard(pid)
            return False
        proposal, draft, items = deepcopy(self.state), deepcopy(player), deepcopy(self.commerce.items)
        lease = proposal["apartments"][record["id"]]
        unit = self.geometry.units[lease["unit"]]
        evicted = reconcile(draft, lease, unit.definition, self.now(),
            lambda due: rent_amount(unit.definition, self.rent_modifier(player, due)))
        if evicted:
            self.revoke(proposal, lease, draft, items, True)
            message = "Two weeks pass unpaid. Your goods wait in protected Kestrel impound."
        else:
            message = "Rent settles from bank, then hand." if draft.chits_bank != player.chits_bank or draft.chits_hand != player.chits_hand else "Rent is unpaid. Two weeks lapsed ends the lease."
        if proposal == self.state and draft.record() == player.record():
            return True
        self.commit(proposal, player, draft, items, self.commerce.serial, message)
        return False

    def next_serial(self, items: dict[str, ItemInstance]) -> int:
        return max([self.commerce.serial, *(int(i.rsplit(":", 1)[-1]) for i in items if i.rsplit(":", 1)[-1].isdigit())])

    def issue_key(self, draft: Player, lease: dict[str, Any], unit: Unit,
                  items: dict[str, ItemInstance], serial: int) -> int:
        if any(item.owner == draft.id and item.key_for == lease["id"] and item.key_tier == lease["lock_tier"] for item in items.values()):
            raise ValueError("You already carry a current key.")
        serial += 1
        item = make_item(f"{self.game.sessions.origin}:item:{serial}", self.content.items[unit.definition.key_item],
                         draft.id, self.clock.now_utc().isoformat())
        item.key_for, item.key_tier = lease["id"], lease["lock_tier"]
        Inventory(items, self.content.items, self.progression.modifiers(draft).secured_slots).add(draft, item)
        return serial

    def propose(self, session: Session, action: str, args: dict[str, Any]) -> None:
        """Revalidate queued commands against current leases, position and items."""
        player = self.ready(session)
        if self.commerce.pending:
            saved = deepcopy(args)
            def later() -> None:
                if self.game.sessions.active.get(session.id) is session and not session.closed:
                    try:
                        self.propose(session, action, saved)
                    except (ValueError, KeyError) as exc:
                        self.log(player, str(exc) if isinstance(exc, ValueError) else "That tenancy has ended.")
            self.commerce.enqueue_system(later)
            return
        if not self.ensure_rent(player.id):
            if self.commerce.pending:
                self.propose(session, action, args)
            return
        proposal, draft, items = deepcopy(self.state), deepcopy(player), deepcopy(self.commerce.items)
        serial = self.next_serial(items)
        inv = Inventory(items, self.content.items, self.progression.modifiers(player).secured_slots)
        target, iid = args.get("target", ""), args.get("item", "")
        after: Callable[[], None] = lambda: None
        if action == "rent":
            self.counter(session, target, letting=True)
            if not player.legal_at:
                raise ValueError("Legal discharge is required: grade 5 or 90 days since your first decant.")
            if player.apartment_id or any(a["resident"] == player.id for a in proposal["apartments"].values()):
                raise ValueError("You already rent an apartment.")
            unit = self.geometry.units.get(args.get("unit", ""))
            if not unit or self.unit_lease(unit):
                raise ValueError("That apartment is no longer available.")
            definition = unit.definition
            amount = rent_amount(definition, self.rent_modifier(player, self.now()))
            charge(draft, amount)
            proposal["housing_serial"] += 1
            aid = f"{self.game.sessions.origin}:apartment:{proposal['housing_serial']}"
            record = {"id": aid, "resident": player.id, "unit": unit.id, "class_id": definition.id,
                "tier": definition.core_tier, "zone": unit.zone, "door": unit.door,
                "hardware": unit.object_id("hardware"), "light": unit.object_id("light"),
                "sector": unit.anchor.sector, "cell": unit.anchor.cell, "storage": [],
                "safe_chits": 0, "lock_tier": definition.lock_tier,
                "rent_paid_until": self.now()+WEEK_SECONDS, "lapsed_since": None,
                "last_invoice": {"due": self.now(), "amount": amount},
                "last_hacked_at": proposal["unit_hacks"].get(unit.id), "hack_log": [],
                "vestibule_access_until": {}}
            self.private.install(record, validate_only=True)
            proposal["apartments"][aid] = record
            draft.apartment_id = aid
            serial = self.issue_key(draft, record, unit, items, serial)
            message = f"You rent {self.unit_label(unit)}. First week paid: {amount}. A key is in your inventory."
        elif action.startswith("reclaim"):
            self.counter(session, target)
            impound = proposal["impounds"].get(player.id, {"items": {}, "chits": 0})
            if action == "reclaim_chits":
                if not impound["chits"]:
                    raise ValueError("There are no impounded chits.")
                draft.chits_bank += impound["chits"]
                impound["chits"] = 0
                message = "Impounded chits return to your bank. No fee."
            elif action == "reclaim":
                entry = impound["items"].get(iid)
                if not entry or iid not in items or items[iid].owner != "impound:"+player.id:
                    raise ValueError("That item is no longer in your impound.")
                charge(draft, entry["fee"])
                inv.add(draft, items[iid])
                impound["items"].pop(iid)
                message = f"Reclaimed for {entry['fee']} chits."
            else:
                raise ValueError("Unknown impound action.")
        else:
            _, existing, unit = self.resident(session, args.get("apartment", ""))
            record = proposal["apartments"][existing["id"]]
            definition = unit.definition
            if action == "deposit":
                if len(record["storage"]) >= definition.storage_slots:
                    raise ValueError("Your apartment storage is full.")
                item = inv.owned(draft, iid)
                if item.secured and sum(items[i].secured for i in record["storage"]) >= definition.storage_slots//PROTECTED_DIVISOR:
                    raise ValueError("Protected apartment slots are full. The item stays secured in your inventory.")
                item = inv.remove(draft, iid, item.stack, lambda: "")
                item.owner = "apartment:"+record["id"]
                items[iid] = item
                record["storage"].append(iid)
                message = "Stored. Its quality and secured status stay unchanged."
            elif action in ("withdraw", "secure"):
                if iid not in record["storage"] or iid not in items or items[iid].owner != "apartment:"+record["id"]:
                    raise ValueError("That item is no longer in your storage.")
                item = items[iid]
                if action == "withdraw":
                    inv.add(draft, item)
                    record["storage"].remove(iid)
                    message = "Withdrawn. Its quality and secured status stay unchanged."
                else:
                    if item.secured and item.template.startswith("story_"):
                        raise ValueError("Story items remain secured.")
                    if not item.secured and sum(items[i].secured for i in record["storage"]) >= definition.storage_slots//PROTECTED_DIVISOR:
                        raise ValueError("Protected apartment slots are full.")
                    item.secured = not item.secured
                    message = "Apartment secured status changed."
            elif action in ("safe_deposit", "safe_withdraw"):
                draft.chits_hand, record["safe_chits"] = bank.exchange(draft.chits_hand,
                    record["safe_chits"], args.get("amount"), action == "safe_deposit")
                message = f"Safe {record['safe_chits']}. Hand {draft.chits_hand}."
            elif action == "upgrade_core":
                if definition.core_upgrade_to is None or record["tier"] >= definition.core_upgrade_to:
                    raise ValueError("This apartment has no further core upgrade.")
                charge(draft, definition.core_upgrade_price)
                record["tier"] = definition.core_upgrade_to
                message = f"Private core upgraded to tier {record['tier']}."
            elif action == "upgrade_lock":
                if record["lock_tier"] >= definition.lock_upgrade_to:
                    raise ValueError("The lock is already upgraded.")
                charge(draft, definition.lock_upgrade_price)
                record["lock_tier"] = definition.lock_upgrade_to
                record["vestibule_access_until"] = {}
                proposal["effects"].pop(self.private.core_id(record)+":apartment-door", None)
                serial = self.issue_key(draft, record, unit, items, serial)
                message = f"Lock upgraded to tier {record['lock_tier']}. A replacement key is in your inventory."
            elif action == "key":
                serial = self.issue_key(draft, record, unit, items, serial)
                message = "A replacement key is in your inventory. It opens only the vestibule for visitors."
            elif action == "surrender":
                self.revoke(proposal, record, draft, items, False)
                message = "You surrender the lease. Your goods wait in Kestrel impound with no fee."
                after = lambda: self.close(session)
            else:
                raise ValueError("Unknown housing action.")
        if not self.commit(proposal, player, draft, items, serial, message, after):
            raise ValueError("Let the current transfer settle first.")

    def door(self, session: Session, unit: Unit) -> None:
        player = self.ready(session)
        self.commerce.nearby(session, unit.door)
        if not self.ensure_rent(player.id):
            return
        record = self.unit_lease(unit)
        if record and not self.ensure_rent(record["resident"]):
            return
        if not record:
            raise ValueError("This apartment is vacant. Visit the letting terminal.")
        actor = self.game.combat.actor(player)
        if unit.region.contains(actor.position):
            self.move_out(actor, unit)
            return
        if record["resident"] == player.id:
            self.game.world.enter(actor, unit.zone, self.game.world.free_tile(unit.zone, unit.tile(unit.room.meta.spawn), actor))
            self.game.snapshot(player, self.sim.avatars[session.user_id])
            self.game.queue("save", player.bbs_user_id, player, immediate=True)
            self.sim.reset_view(session, self.sim.avatars[session.user_id])
            return
        current_key = any((item := self.commerce.items.get(iid)) and item.owner == player.id and item.key_for == record["id"]
            and item.key_tier >= record["lock_tier"] for iid in player.inventory)
        until = record.get("vestibule_access_until", {}).get(player.id, 0)
        if current_key and until <= self.now():
            proposal = deepcopy(self.state)
            proposal["apartments"][record["id"]]["vestibule_access_until"][player.id] = self.now()+VESTIBULE_SECONDS
            def enter() -> None:
                try:
                    self.enter_visitor(session, unit)
                except ValueError as exc:
                    self.log(player, str(exc))
            self.interlock.commit(proposal, enter)
        elif until > self.now():
            self.enter_visitor(session, unit)
        else:
            raise ValueError(f"Locked. Tier {record['lock_tier']}.")

    def enter_visitor(self, session: Session, unit: Unit) -> None:
        if session.closed:
            return
        player = self.ready(session)
        self.commerce.nearby(session, unit.door)
        tile = unit.tile(unit.anchor.vestibule)
        if any(actor.id != player.id and actor.position == tile for actor in self.game.world.zones[unit.zone].actors.values()):
            raise ValueError("The vestibule is occupied.")
        self.game.world.enter(self.game.combat.actor(player), unit.zone, tile)
        self.game.snapshot(player, self.sim.avatars[session.user_id])
        self.game.queue("save", player.bbs_user_id, player, immediate=True)
        self.sim.reset_view(session, self.sim.avatars[session.user_id])
        self.log(player, "Delivery vestibule. 30s maximum. Room services stay private.")

    def close(self, session: Session) -> None:
        self.menus.pop(session.id, None)
        self.prompts.pop(session.id, None)
        self.sim.external_views.pop(session.id, None)
        avatar = self.sim.avatars.get(session.user_id)
        if avatar:
            self.sim.reset_view(session, avatar)

    def body(self, session: Session, screen: HousingMenu) -> dict[str, Any]:
        player = self.ready(session)
        rows: list[dict[str, Any]] = []
        actions: list[dict[str, str]] = []
        title, detail = screen.kind.upper(), ""
        if screen.kind == "letting":
            self.counter(session, screen.target, True)
            title = "TERRACES / LETTING"
            record = self.lease(player)
            if record:
                detail = "Your apartment: "+self.unit_label(self.geometry.units[record["unit"]])+". One lease per character."
            else:
                for unit in self.geometry.units.values():
                    if not self.unit_lease(unit):
                        d = unit.definition
                        rows.append({"id": unit.id, "cells": [self.unit_label(unit),
                            f"{rent_amount(d, self.rent_modifier(player, self.now()))}/week", f"{d.storage_slots} slots / core {d.core_tier}"]})
                detail = "Legal discharge required. First week paid from bank, then hand."
                if not rows:
                    detail += "\nNo commissioned apartments are available."
            detail += f"\nBank {player.chits_bank} / hand {player.chits_hand}."
            actions = [{"key": "enter", "label": "rent"}]
        elif screen.kind == "impound":
            self.counter(session, screen.target)
            title = "KESTREL / IMPOUND"
            record = self.state["impounds"].get(player.id, {"items": {}, "chits": 0})
            if record["chits"]:
                rows.append({"id": "chits", "cells": ["Chits to bank", str(record["chits"]), "free"]})
            for iid, entry in record["items"].items():
                item = self.commerce.items.get(iid)
                if item:
                    rows.append({"id": iid, "cells": [self.label(item), str(item.stack), f"Fee {entry['fee']}", "S" if item.secured else ""]})
            detail = f"Bank {player.chits_bank} / hand {player.chits_hand}. Fees use catalog list value."
            actions = [{"key": "enter", "label": "reclaim"}]
        else:
            _, record, unit = self.resident(session, screen.target)
            d = unit.definition
            title = self.unit_label(unit).upper()
            if screen.kind == "storage":
                ids = player.inventory if screen.deposit else record["storage"]
                title += " / "+("DEPOSIT" if screen.deposit else "WITHDRAW")
                for iid in ids:
                    item = self.commerce.items[iid]
                    rows.append({"id": iid, "cells": [self.label(item), str(item.stack), "S" if item.secured else ""]})
                used = sum(self.commerce.items[i].secured for i in record["storage"])
                detail = f"Storage {len(record['storage'])}/{d.storage_slots}. Protected {used}/{d.storage_slots//PROTECTED_DIVISOR}."
                actions = [{"key": "enter", "label": "deposit" if screen.deposit else "withdraw"}, {"key": "t", "label": "deposit/withdraw"}]
                if not screen.deposit:
                    actions.append({"key": "s", "label": "secure"})
            elif screen.kind == "safe":
                title += " / SAFE"
                rows = [{"id": "safe_deposit", "cells": ["Deposit", str(player.chits_hand)]},
                        {"id": "safe_withdraw", "cells": ["Withdraw", str(record["safe_chits"])]}]
                detail = f"Safe {record['safe_chits']}. Hand {player.chits_hand}.\nSafe chits are banked and protected. Rent uses your bank, then hand."
                actions = [{"key": "enter", "label": "choose amount"}]
            else:
                due = datetime.fromtimestamp(record["rent_paid_until"], timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                detail = f"Next due {due}. Core {record['tier']} / lock {record['lock_tier']}.\n"+(
                    "Rent is lapsed. Two weeks unpaid ends the lease." if record.get("lapsed_since") is not None else "First paid week and settled invoices are final.")
                if screen.confirm:
                    rows = [{"id": "confirm", "cells": ["Surrender this lease? Goods go to impound free."]}]
                    actions = [{"key": "y", "label": "confirm surrender"}]
                    detail = "Y confirms. Esc/B leaves without surrendering."
                else:
                    rows = [{"id": key, "cells": [label]} for key, label in (
                        ("storage", "Storage"), ("safe", "Safe"), ("log", "Core intrusion log"),
                        ("key", "Issue replacement key"), ("upgrade_lock", f"Lock tier {d.lock_upgrade_to}: {d.lock_upgrade_price} chits"),
                        ("surrender", "Surrender lease"), ("leave", "Leave apartment"), ("logout", "Log out on the bed"))]
                    if d.core_upgrade_to:
                        rows.insert(4, {"id": "upgrade_core", "cells": [f"Core tier {d.core_upgrade_to}: {d.core_upgrade_price} chits"]})
                    actions = [{"key": "enter", "label": "choose"}]
        screen.cursor = max(0, min(screen.cursor, len(rows)-1))
        if rows and rows[screen.cursor]["id"] in self.commerce.items:
            item = self.commerce.items[rows[screen.cursor]["id"]]
            detail += "\n"+item_detail(self.content.items[item.template], item.quality)
        body = menu(title, rows, screen.cursor, detail, "Esc/B returns")
        body.update(kind=screen.kind, actions=actions)
        return body

    def select(self, session: Session, screen: HousingMenu, key: str, row: str) -> None:
        body = self.body(session, screen)
        if key not in {a["key"] for a in body["actions"]}:
            return
        if screen.kind == "storage" and key == "t":
            screen.deposit, screen.cursor = not screen.deposit, 0
            return
        if row not in {r["id"] for r in body["rows"]}:
            raise ValueError("Choose an item still in this menu.")
        args = {"target": screen.target, "apartment": screen.target, "item": row}
        if screen.kind == "letting":
            self.propose(session, "rent", {"target": screen.target, "unit": row})
        elif screen.kind == "impound":
            self.propose(session, "reclaim_chits" if row == "chits" else "reclaim", args)
        elif screen.kind == "storage":
            self.propose(session, "secure" if key == "s" else "deposit" if screen.deposit else "withdraw", args)
        elif screen.kind == "safe":
            self.prompt_serial += 1
            token = f"housing:{session.id}:{self.prompt_serial}"
            self.prompts[session.id] = {"id": token, "action": row, "args": args}
            session.send(Frame("prompt", {"id": token, "kind": "line", "label": "Chits", "max_len": 10}))
        elif screen.confirm:
            if key == "y":
                screen.confirm = ""
                self.propose(session, "surrender", args)
        elif row in ("storage", "safe"):
            self.menus[session.id] = HousingMenu(row, screen.target, opened=screen.opened)
        elif row == "log":
            self.close(session)
            self.private.open_log(session, screen.target)
        elif row == "surrender":
            screen.confirm, screen.cursor = "surrender", 0
        elif row == "leave":
            _, _, unit = self.resident(session, screen.target)
            self.close(session)
            self.move_out(self.game.combat.actor(self.game.players[session.player_id]), unit)
        elif row == "logout":
            self.resident(session, screen.target)
            session.send(Frame("bye", {"reason": "logout", "text": "You lie down. The room stays quiet."}))
        else:
            self.propose(session, row, args)

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        name = frame.data.get("name", "") if frame.type == "intent" else ""
        key = frame.data.get("k", "") if frame.type == "key" else ""
        args = frame.data.get("args", {})
        try:
            if session.id in self.prompts:
                pending = self.prompts[session.id]
                if name == "prompt_cancel" and args.get("id") == pending["id"]:
                    self.prompts.pop(session.id)
                elif frame.type == "line" and frame.data.get("id") == pending["id"]:
                    self.prompts.pop(session.id)
                    value = frame.data["text"]
                    if not value.isascii() or not value.isdigit():
                        raise ValueError("Enter a positive whole number.")
                    self.propose(session, pending["action"], {**pending["args"], "amount": int(value)})
                return True
            screen = self.menus.get(session.id)
            if screen or name.startswith("housing."):
                if name == "menu_close" or key in ("escape", "b", "B"):
                    self.close(session)
                elif name == "menu_cursor" and screen and type(args.get("delta")) is int:
                    screen.cursor = max(0, min(screen.cursor+args["delta"], len(self.body(session, screen)["rows"])-1))
                elif name == "menu_select" or name.startswith("housing."):
                    if frame.data.get("expected_revision") != session.view_revision:
                        return True
                    request = frame.data.get("request_id")
                    if request and request in self.requests.get(session.id, ()):
                        return True
                    if not self.ensure_rent(session.player_id):
                        return True
                    if screen and name == "menu_select":
                        self.select(session, screen, args.get("key", "enter"), args.get("row", ""))
                    elif name != "housing.surrender":  # Surrender always requires the displayed confirmation.
                        self.propose(session, name.removeprefix("housing."), args)
                    if request:
                        self.requests.setdefault(session.id, []).append(request)
                        self.requests[session.id] = self.requests[session.id][-128:]
                return True
            bank_menu = self.commerce.menus.get(session.id)
            if name == "menu_select" and bank_menu and bank_menu.kind == "bank" and args.get("row") == "impound":
                if frame.data.get("expected_revision") == session.view_revision:
                    target = bank_menu.target
                    self.commerce.close(session)
                    self.counter(session, target)
                    self.menus[session.id] = HousingMenu("impound", target, opened=tick)
                return True
            if not self.commerce.ready(session) or session.id in self.sim.external_views or session.pending_prompts:
                return False
            if name != "interact" and key not in ("e", "E"):
                return False
            actor = self.game.combat.actor(self.game.players[session.player_id])
            objects = sorted((obj for obj in self.game.world.zones[actor.zone].objects.values()
                if max(abs(obj.spec.tile[0]-actor.x), abs(obj.spec.tile[1]-actor.y)) <= 1),
                key=lambda obj: (obj.spec.tile != actor.position, obj.spec.id))
            if not objects:
                return False
            obj = objects[0]
            if obj.spec.housing:
                self.door(session, self.geometry.units[actor.zone+":"+obj.spec.id])
                return True
            if obj.spec.params.get("letting"):
                self.counter(session, obj.spec.id, True)
                self.ensure_rent(session.player_id)
                self.menus[session.id] = HousingMenu("letting", obj.spec.id, opened=tick)
                return True
            unit = self.geometry.units.get(obj.spec.params.get("apartment_unit"))
            if unit and obj.spec.kind in ("storage", "apartment_safe", "bed"):
                record = self.unit_lease(unit)
                if not record or not self.ensure_rent(session.player_id):
                    return True
                self.resident(session, record["id"])
                kind = {"storage": "storage", "apartment_safe": "safe", "bed": "apartment"}[obj.spec.kind]
                self.menus[session.id] = HousingMenu(kind, record["id"], opened=tick)
                return True
        except (ValueError, KeyError, TypeError) as exc:
            self.commerce.toast(session, str(exc) if isinstance(exc, ValueError) else "That housing service is no longer available.")
            return True
        return False

    def tick(self, ctx: TickContext) -> None:
        self.requests = {sid: rows for sid, rows in self.requests.items() if sid in self.game.sessions.active}
        self.prompts = {sid: value for sid, value in self.prompts.items() if sid in self.game.sessions.active}
        if not self.commerce.pending:
            # Character deletion is already durable. Cleanup is resumable after
            # a crash and cannot charge or resurrect a deleted character.
            abandoned = [record for record in self.state["apartments"].values()
                         if record.get("unit") and record["resident"] not in self.game.players]
            lost_impounds = set(self.state["impounds"])-self.game.players.keys()
            if abandoned or lost_impounds:
                proposal, items = deepcopy(self.state), deepcopy(self.commerce.items)
                owners = {"impound:"+pid for pid in lost_impounds}
                for record in abandoned:
                    proposal["apartments"].pop(record["id"])
                    owners.add("apartment:"+record["id"])
                    cid = self.private.core_id(record)
                    proposal["cores"].pop(cid, None)
                    proposal["effects"] = {key: value for key, value in proposal["effects"].items() if value["core"] != cid}
                for pid in lost_impounds:
                    proposal["impounds"].pop(pid)
                items = {iid: item for iid, item in items.items() if item.owner not in owners}
                self.commit(proposal, None, None, items, self.commerce.serial, "")
        for pid in tuple(self.checks):
            if self.commerce.pending:
                break
            self.checks.discard(pid)
            if not self.ensure_rent(pid):
                self.checks.add(pid)
                continue
            player = self.game.players.get(pid)
            record = self.lease(player) if player else None
            if record and 0 <= record["rent_paid_until"]-self.now() <= NOTICE_SECONDS:
                self.log(player, "Rent is due within two days. Keep chits in bank or hand.")
        # Expiring a visitor's capability moves their body out, including sleepers.
        for actor in tuple(self.game.world.actors.values()):
            unit = self.geometry.containing(actor.zone, actor.position) if actor.zone else None
            if unit and not self.geometry.can_enter(actor, unit.zone, actor.position):
                self.move_out(actor, unit)
        for sid, screen in tuple(self.menus.items()):
            session = self.game.sessions.active.get(sid)
            if not session:
                self.menus.pop(sid, None)
                self.sim.external_views.pop(sid, None)
                continue
            try:
                if ctx.tick-screen.opened >= MENU_TIMEOUT_SECONDS*TICK_HZ:
                    raise ValueError("The housing menu closes.")
                self.sim.external_views[sid] = "menu", self.body(session, screen)
            except (ValueError, KeyError):
                self.close(session)
