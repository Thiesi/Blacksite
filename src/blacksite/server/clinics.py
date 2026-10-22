"""Game 8.5/8.6: local clinic menus and confirmed, atomic operations."""

from copy import deepcopy
from dataclasses import dataclass
from math import ceil
from typing import Any, TYPE_CHECKING

from blacksite.content.schema import Vendor
from blacksite.server import drugs, implants
from blacksite.server.items import make_item
from blacksite.server.players import Player
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session
from blacksite.server.vendors import permitted
from blacksite.server.wake import menu, wrapped

if TYPE_CHECKING:
    from blacksite.server.progression_engine import ProgressionEngine


@dataclass(frozen=True)
class Operation:
    id: str
    action: str
    item: str = ""
    slot: str = ""
    owned: bool = False


@dataclass
class ClinicMenu:
    target: str
    cursor: int = 0
    confirm: str = ""


class Clinics:
    def __init__(self, progression: "ProgressionEngine") -> None:
        self.progression, self.game, self.commerce = progression, progression.game, progression.commerce
        self.sim = self.commerce.sim
        self.menus: dict[str, ClinicMenu] = {}
        self.detox_views: set[str] = set()
        self.requests: dict[str, list[str]] = {}

    def counter(self, session: Session, target: str) -> Vendor:
        vendor, _ = self.commerce.vendor(session, target)
        if not vendor.clinic or not permitted(self.game.players[session.player_id], vendor):
            raise ValueError("This counter offers no surgery to you.")
        return vendor

    def options(self, session: Session, screen: ClinicMenu) -> list[Operation]:
        vendor = self.counter(session, screen.target)
        player = self.game.players[session.player_id]
        options: list[Operation] = []
        for iid in player.inventory:
            item = self.commerce.items[iid]
            template = self.game.content.items[item.template]
            if iid in player.implants.values() or not template.implant or template.implant.portable:
                continue
            slots = ("arms1", "arms2") if template.implant.slot == "arms" else (template.implant.slot,)
            options += [Operation("install:"+iid+":"+slot,"install",iid,slot,True) for slot in slots]
        for entry in self.commerce.stock(vendor):
            template = self.game.content.items.get(entry.item)
            if (not template or not template.implant or template.implant.portable or template.id == "imp_rig_native"
                    or not permitted(player,vendor,entry) or not self.game.content.active("items",template.id)):
                continue
            slots = ("arms1", "arms2") if template.implant.slot == "arms" else (template.implant.slot,)
            options += [Operation("buy:"+template.id+":"+slot,"install",template.id,slot) for slot in slots]
        options += [Operation("remove:"+slot,"remove",iid,slot,True) for slot,iid in player.implants.items()
                    if self.commerce.items[iid].template != "imp_rig_native"]
        if vendor.clinic == "sablier":
            options.append(Operation("detox","detox"))
        return options

    def quote(self, player: Player, vendor: Vendor, op: Operation) -> implants.Quote:
        mods = self.progression.modifiers(player)
        if op.action == "detox":
            return implants.Quote(0,drugs.DETOX_CHITS,0,0,"clinic",implants.tolerance_used(
                player,self.commerce.items,self.game.content.items),mods.tolerance(player))
        template = self.game.content.items[self.commerce.items[op.item].template if op.owned else op.item]
        if op.action == "remove":
            return implants.Quote(0,implants.removal_price(template),0,0,op.slot,
                implants.tolerance_used(player,self.commerce.items,self.game.content.items,replacing=op.slot),mods.tolerance(player))
        return implants.quote(player,template,vendor.clinic,mods,self.commerce.items,
                              self.game.content.items,owned=op.owned,slot=op.slot,replace=True)

    def label(self, op: Operation) -> str:
        if op.action == "detox":
            return "Detox, ten minutes"
        template = self.game.content.items[self.commerce.items[op.item].template if op.owned else op.item]
        return ("Remove " if op.action == "remove" else "Install " if op.owned else "Buy + install ")+template.name

    def view(self, session: Session, screen: ClinicMenu) -> dict[str, Any]:
        player = self.game.players[session.player_id]
        vendor = self.counter(session,screen.target)
        options = self.options(session,screen)
        rows = []
        for op in options:
            try:
                bill = self.quote(player,vendor,op)
                cost = str(bill.total)
            except ValueError:
                cost = "locked"
            rows.append({"id":op.id,"cells":[self.label(op),op.slot,cost]})
        if not options:
            rows = [{"id":"empty","cells":["No operation is available."]}]
        cursor = min(screen.cursor,len(rows)-1)
        detail = f"Hand {player.chits_hand}. Choose an operation; review its total and risk before Y."
        if screen.confirm:
            op = next((op for op in options if op.id == screen.confirm),None)
            if op is None:
                screen.confirm = ""
                return self.view(session,screen)
            bill = self.quote(player,vendor,op)
            rows = [{"id":op.id,"cells":[self.label(op),op.slot]},
                {"id":"total","cells":[f"TOTAL {bill.total}",f"Failure {bill.failure:.0%}"]},
                {"id":"fees","cells":[f"Item {bill.item_price}",f"Service {bill.service_price}",f"Removal {bill.removal_price}"]},
                {"id":"tolerance","cells":["Tolerance after",f"{bill.used}/{bill.capacity}"]}]
            old = player.implants.get(op.slot)
            if old and op.action == "install":
                if self.commerce.items[old].template == "imp_rig_native":
                    rows.append({"id":"return","cells":["Built-in rig","No tradable item returned"]})
                else:
                    rows.append({"id":"return","cells":["Returns",self.game.content.items[self.commerce.items[old].template].name]})
            if op.action == "detox":
                detail = "Active doses end when detox starts. You stay in this clinic pocket for ten minutes. You cannot act. Detox continues offline; Ctrl-X leaves."
            else:
                detail = "Failure destroys the chosen item and holds shock 100 for 30s. Returned hardware keeps its quality. Chrome expiry may unseat hardware and unsecure excess items."
                if op.action == "remove":
                    detail = "Removal has no failure roll. You keep the item and its quality. Unsecure excess items before reducing secured capacity."
            return {**menu("CONFIRM CLINIC OPERATION",rows,min(screen.cursor,len(rows)-1),"\n".join(wrapped(detail,52)),
                "Y confirms this operation  N cancels  Esc/B leaves"),
                "actions":[{"key":"y","label":"confirm"},{"key":"n","label":"cancel"}]}
        if options:
            try:
                bill = self.quote(player,vendor,options[cursor])
                detail += f" Total {bill.total}; failure {bill.failure:.0%}; tolerance {bill.used}/{bill.capacity}."
            except ValueError as exc:
                detail = str(exc)
        return {**menu(vendor.name+" - CLINIC",rows,cursor,"\n".join(wrapped(detail,52)),"Enter reviews  Esc/B leaves"),
                "actions":[{"key":"enter","label":"review"}]}

    def open(self, session: Session, target: str) -> None:
        if not self.commerce.ready(session):
            raise ValueError("Stand at a clinic with your body free to act.")
        self.counter(session,target)
        self.commerce.close(session)
        self.menus[session.id] = ClinicMenu(target)
        self.publish(session)

    def close(self, session: Session) -> None:
        self.menus.pop(session.id,None)
        self.sim.external_views.pop(session.id,None)
        self.sim.reset_view(session,self.sim.avatars[session.user_id])

    def publish(self, session: Session) -> None:
        self.sim.external_views[session.id] = "menu",self.view(session,self.menus[session.id])

    def operate(self, session: Session, screen: ClinicMenu, op: Operation) -> bool:
        if self.commerce.pending:
            raise ValueError("The city is busy. Your operation has not started.")
        if not self.commerce.ready(session):
            raise ValueError("Your body cannot undergo this operation now.")
        vendor = self.counter(session,screen.target)
        if op not in self.options(session,screen):
            raise ValueError("That operation is no longer available.")
        player = self.game.players[session.player_id]
        actor = self.game.combat.actor(player)
        self.game.snapshot(player,self.sim.avatars[session.user_id])
        draft,items = deepcopy(player),deepcopy(self.commerce.items)
        now = self.game.clock.now_utc().timestamp()
        serial = self.commerce.serial
        if op.action == "detox":
            zone = self.game.world.zones[actor.zone]
            if vendor.clinic != "sablier" or zone.safety_at(actor.position) not in ("safe","pocket"):
                raise ValueError("Detox requires the clinic's existing safe pocket.")
            drugs.start_detox(draft,now,actor.zone,actor.position)
            message = "Detox begins. You stay in this safe clinic for ten minutes. It continues offline."
        else:
            # A failed replacement also removes the old piece. Show/refuse
            # its capacity loss before spending chits or drawing a roll.
            trial = deepcopy(draft)
            trial.implants.pop(op.slot,None)
            capacity = self.progression.modifiers(trial).secured_slots
            if sum(items[iid].secured for iid in draft.inventory) > capacity:
                raise ValueError(f"Unsecure excess items first. Removing this hardware leaves {capacity} secured slots.")
            if op.action == "remove":
                implants.remove(draft,op.slot,items,self.game.content.items)
                message = "The hardware comes free. You keep the item and its quality."
            else:
                if op.owned:
                    item = items[op.item]
                else:
                    serial = self.game.combat.next_serial()+1
                    item = make_item(f"{self.game.sessions.origin}:item:{serial}",self.game.content.items[op.item],
                                     draft.id,self.game.clock.now_utc().isoformat())
                result = implants.install(draft,item,vendor.clinic,self.progression.modifiers(draft),items,
                    self.game.content.items,now,self.game.world.zones[actor.zone].rng.random(),
                    owned=op.owned,slot=op.slot,replace=True)
                message = ("The hardware settles into place." if result.installed else
                           "The operation fails. The chosen item is destroyed. Shock holds for thirty seconds.")
        patch = {key: deepcopy(getattr(draft,key)) for key in
                 ("inventory","equipment","implants","chits_hand","health","stamina","shock","progress","drugs_active","dependencies")
                 if getattr(draft,key) != getattr(player,key)}
        def committed(success: bool) -> None:
            if success:
                for key in ("health","stamina","shock"):
                    if key in patch:
                        setattr(actor,key,getattr(player,key))
                self.progression.sync_actor(player)
                self.game.combat.log(actor,message)
                if op.action == "detox":
                    self.menus.pop(session.id,None)
                    self.detox_views.add(session.id)
            else:
                self.commerce.toast(session,"The operation could not be saved. Your chits and hardware remain.")
            if session.id in self.menus:
                self.menus[session.id].confirm = ""
                self.menus[session.id].cursor = 0
                if not session.closed:
                    self.publish(session)
        return self.commerce.settle(player,patch,items,self.commerce.caches,serial,committed)

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        player = self.game.players.get(session.player_id)
        if player is None:
            return False
        name = frame.data.get("name","") if frame.type == "intent" else ""
        args = frame.data.get("args",{})
        now = self.game.clock.now_utc().timestamp()
        if drugs.detox_until(player) > now:
            key = frame.data.get("k","") if frame.type == "key" else ""
            table = next((m for m in self.sim.keymap.get("keymaps",[]) if m["id"] == session.keymap_id),{})
            action = next((a for a,keys in table.get("bindings",{}).items() if key in keys),name)
            if (name in ("chat","emote","ignore","report") or action.startswith("chat_")
                    or session.pending_prompts.get("chat") and frame.type in ("line","key")
                    or session.pending_prompts.get("chat") and name == "prompt_cancel"):
                return False
            if name == "menu_close":
                self.detox_views.discard(session.id)
                self.sim.external_views.pop(session.id,None)
            return True
        try:
            if name == "clinic.open":
                target = args.get("target","")
                if not isinstance(target,str):
                    raise ValueError("Choose a local clinic.")
                self.open(session,target)
                return True
            screen = self.menus.get(session.id)
            if screen is None:
                vendor_menu = self.commerce.menus.get(session.id)
                if (vendor_menu and vendor_menu.kind == "vendor" and name == "menu_select"
                        and args.get("key") == "c" and frame.data.get("expected_revision") == session.view_revision):
                    self.open(session,vendor_menu.target)
                    return True
                return False
            if name == "menu_close":
                self.close(session)
            elif name == "menu_cursor" and type(args.get("delta")) is int:
                count = len(self.view(session,screen)["rows"])
                screen.cursor = max(0,min(count-1,screen.cursor+args["delta"]))
                self.publish(session)
            elif name == "menu_select":
                if frame.data.get("expected_revision") != session.view_revision:
                    return True
                request = frame.data.get("request_id","")
                if request and request in self.requests.get(session.id,()):
                    return True
                view = self.view(session,screen)
                if args.get("row") != view["rows"][view["cursor"]]["id"]:
                    return True
                key = args.get("key","enter")
                if screen.confirm:
                    if key == "n":
                        screen.confirm = ""; screen.cursor = 0
                    elif key == "y":
                        op = next(op for op in self.options(session,screen) if op.id == screen.confirm)
                        if self.operate(session,screen,op) and request:
                            self.requests.setdefault(session.id,[]).append(request)
                            self.requests[session.id] = self.requests[session.id][-128:]
                elif key == "enter":
                    op = self.options(session,screen)[view["cursor"]]
                    self.quote(player,self.counter(session,screen.target),op)
                    screen.confirm = op.id; screen.cursor = 0
                if session.id in self.menus:
                    self.publish(session)
            return True
        except (ValueError,KeyError,StopIteration,IndexError) as exc:
            self.commerce.toast(session,str(exc) if isinstance(exc,ValueError) else "That clinic operation is unavailable.")
            return True

    def tick(self) -> None:
        for sid in tuple(self.menus):
            session = self.game.sessions.active.get(sid)
            if session is None or session.closed or not self.commerce.ready(session):
                self.menus.pop(sid,None)
                if self.sim.external_views.get(sid,("",))[0] == "menu":
                    self.sim.external_views.pop(sid,None)
                continue
            try:
                self.publish(session)
            except (ValueError,KeyError):
                self.close(session)
        for session in self.game.sessions.active.values():
            player = self.game.players.get(session.player_id)
            if player is None or session.closed:
                continue
            until = drugs.detox_until(player)
            if until and until > self.game.clock.now_utc().timestamp():
                if session.needs_full_view:
                    self.detox_views.add(session.id)
                if session.id in self.detox_views:
                    seconds = max(0,ceil(until-self.game.clock.now_utc().timestamp()))
                    self.sim.external_views[session.id] = "menu",menu("DETOX",[
                        {"id":"detox","cells":[f"{seconds} seconds remain.","You are in the clinic pocket."]}],0,
                        "Detox continues offline.\nYou cannot act until it completes.","Esc/B closes this view  Ctrl-X leaves")
            elif session.id in self.detox_views:
                self.detox_views.discard(session.id)
                self.sim.external_views.pop(session.id,None)
        for sid in self.requests.keys()-self.game.sessions.active.keys():
            self.requests.pop(sid,None)
        self.detox_views.intersection_update(self.game.sessions.active)
