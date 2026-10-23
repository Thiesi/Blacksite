"""Server-owned interlock proposals, composed effects and durable deadlines.

No storage or transport I/O: Commerce commits each proposal before its
physical effect is published. Content owns targets; S19 supplies permits
and S21 supplies live relay ownership.
"""

from collections.abc import Callable
from copy import deepcopy
from math import ceil
from typing import Any, TYPE_CHECKING

from blacksite.content.schema import ControlSpec
from blacksite.server.clock import TICK_HZ
from blacksite.server.lattice.presence import Procedure, Presence
from blacksite.server.loop import TickContext
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session
from blacksite.server.channels import PhysicalChannel as CutChannel
from blacksite.server.wake import menu

if TYPE_CHECKING:
    from blacksite.server.lattice.engine import Lattice
    from blacksite.server.players import Player

FLIP_SECONDS = 3  # Game 6.1/6.4.
FLIP_TRACE = 10  # World Lattice 7.
CUT_SECONDS = 5  # Game 6.4.
OFFLINE_SECONDS = 600  # Game 6.4.
CUT_SHOCK = 100  # Game 6.4; ordinary 3s shock-recovery delay still applies.
THEFT_SECONDS = 86400  # Game 6.4: rolling 24 h, per apartment.
HACK_LOG_LIMIT = 20  # Entity 2.9.


class Interlock:
    def __init__(self, lattice: "Lattice", saved: dict[str, Any] | None = None) -> None:
        self.lat = lattice
        self.game, self.combat = lattice.game, lattice.combat
        self.content, self.clock, self.sim = lattice.content, lattice.clock, lattice.sim
        self.commerce = self.combat.commerce
        self.state = deepcopy(saved or {})
        for key in ("cores", "effects", "apartments", "holds"):
            self.state.setdefault(key, {})
        self.state.setdefault("serial", 0)
        self.controls: dict[tuple[str, str], ControlSpec] = {}
        self.hardware: dict[tuple[str, str], str] = {}
        self.cuts: dict[str, CutChannel] = {}
        self.menus: dict[str, tuple[str, str, bool | str]] = {}
        self.log_menus: set[str] = set()
        self.permit: Callable[[str, str, str], bool] = lambda pid, core, action: False
        self.layout_for: Callable[[str, str, str], str | None] = lambda pid, core, control: None
        self.on_cut_power: Callable[["Player", str], None] = lambda actor, core: None
        self.cut_patch: Callable[["Player", str], dict[str, Any]] = lambda player, core: {}
        for core in self.content.cores.values():
            if core.template or not self.content.active("cores", core.id):
                continue
            for room in core.rooms:
                for control in room.controls:
                    zone = self.game.world.zones[control.target.zone]
                    if control.target.object not in zone.objects:
                        raise ValueError(f"Unresolved control {core.id}/{control.id}")
                    self.controls[core.id, control.id] = control
            for location in core.hardware:
                zone = self.game.world.zones[location.zone]
                obj = next(o for o in zone.objects.values() if o.spec.tile == location.tile
                           and o.spec.kind == "hardware")
                self.hardware[zone.id, obj.spec.id] = core.id
        from blacksite.server.private_cores import PrivateCores
        self.private = PrivateCores(self)
        from blacksite.server.interlock_effects import PhysicalEffects
        self.physical = PhysicalEffects(self)
        encounter_hits = self.commerce.after_settle
        def flush_impacts() -> None:
            encounter_hits()
            self.physical.flush_hits()
        self.commerce.after_settle = flush_impacts
        self.applied: dict[tuple[str, str], dict[str, Any]] = {}
        self.compose()

    def now(self) -> float:
        return self.clock.now_utc().timestamp()

    def offline(self, core: str) -> float:
        return max(0, self.state["cores"].get(core, {}).get("offline_until", 0)-self.now())

    def owned(self, core: str) -> str | None:
        return self.state["cores"].get(core, {}).get("owner_faction")

    def control(self, presence: Presence, cid: str) -> ControlSpec:
        apartment = self.private.apartment(presence.core)
        if apartment and not self.private.before_access(apartment["resident"]):
            raise ValueError("The lease is being reconciled. Inspect the current core again.")
        instance = self.lat.encounters.core(presence)
        control = next((c for c in instance.graph.room(presence.room).controls if c.id == cid), None) if instance else None
        if control is None or (presence.core, cid) not in self.controls:
            raise ValueError("That control is not in this room.")
        if control.permission != "public" and not self.permit(presence.player_id, presence.core, cid):
            raise ValueError("This control needs its scoped work-order permission.")
        if self.offline(presence.core):
            raise ValueError("The core is offline.")
        return control

    def start_flip(self, presence: Presence, cid: str) -> None:
        control = self.control(presence, cid)
        if not self.lat.encounters.idle(presence):
            raise ValueError("Finish or cancel your current action first.")
        layout = self.check_effect(control, presence.player_id, presence.core)
        presence.procedure = Procedure("flip", cid, self.clock.now_tick()+FLIP_SECONDS*TICK_HZ,
            presence.instance, self.lat.encounters.hit_serial(presence), control.revision, layout or "")
        self.lat.encounters.log(presence, f"{control.label}: {control.action}, 3s channel, +10 trace on completion. Esc cancels.")

    def check_effect(self, control: ControlSpec, player_id: str = "", core: str = "") -> str | None:
        zone = self.game.world.zones[control.target.zone]
        obj = zone.objects[control.target.object]
        layout = None
        enabling_turret = obj.spec.kind == "turret" and (control.action in ("enable", "open", "call") or
            control.action == "toggle" and not obj.state.get("enabled", True))
        if control.safety_policy == "hazard" or enabling_turret:
            player = self.game.players.get(player_id)
            actor = self.combat.actor(player) if player else None
            if not actor or actor.zone not in self.game.world.zones or not self.game.world.zones[actor.zone].allows_hostile(actor.position):
                raise ValueError("Harmful machinery cannot be armed from a protected body.")
        if control.safety_policy == "hazard" or obj.spec.kind in ("pump", "gantry"):
            layout = self.layout_for(player_id, core, control.id) or obj.spec.params.get("layout")
            if not layout or not any(x.id == layout for x in zone.template.meta.layouts):
                raise ValueError("This machine has no commissioned work-order layout.")
            if obj.spec.params.get("work_order_layouts") and layout not in obj.spec.params["work_order_layouts"]:
                raise ValueError("That allocation is not one of this machine's work orders.")
            if control.warning_seconds < 5:
                raise ValueError("This machine needs at least five seconds of visible warning.")
            chosen = next(x for x in zone.template.meta.layouts if x.id == layout)
            if any(zone.tiles[change.tile_id].hazard for change in chosen.changes):
                player = self.game.players.get(player_id)
                actor = self.combat.actor(player) if player else None
                if not actor or actor.zone not in self.game.world.zones or not self.game.world.zones[actor.zone].allows_hostile(actor.position):
                    raise ValueError("Harmful machinery cannot be armed from a protected body.")
        if obj.spec.kind in ("cable_car", "lift", "gate", "shutter") and control.action in ("close", "disable", "toggle"):
            exits = obj.spec.params.get("exits", ())
            if not exits or not control.alternate_route or control.alternate_route in exits:
                raise ValueError("This route control needs commissioned exits and an alternate return.")
        if obj.spec.kind == "tram_stop" and control.action == "call":
            platforms = self.platforms(zone, obj)
            if not platforms:
                raise ValueError("This platform has no commissioned departure.")
            if any(self.now() < self.state["holds"].get(zone.id+":"+ex.id, [0, 0])[1] for ex in platforms):
                raise ValueError("The platform is in its departure immunity window.")
        return layout

    def complete_flip(self, presence: Presence, procedure: Procedure) -> None:
        control = self.control(presence, procedure.target)
        layout = self.check_effect(control, presence.player_id, presence.core)
        if control.revision != procedure.generation or (layout or "") != procedure.source:
            raise ValueError("The work order changed. Inspect the current control before retrying.")
        player = self.game.players[presence.player_id]
        proposal = deepcopy(self.state)
        proposal["serial"] += 1
        key = presence.core+":"+control.id
        obj = self.game.world.zones[control.target.zone].objects[control.target.object]
        persistent = (control.owner_policy and control.safety_policy == "none" and control.scope == "public"
            and obj.spec.kind not in ("tram_stop", "cable_car", "pump", "lift", "gate", "vat", "gantry", "shutter")
            and self.owned(presence.core) is not None and self.owned(presence.core) == player.faction)
        enabled = obj.open if obj.open is not None else obj.state.get("enabled", True)
        proposal["effects"][key] = {"core": presence.core, "control": control.id,
            "revision": control.revision,
            "enabled": not enabled if control.action == "toggle" else control.action not in ("close", "disable"),
            "expires": None if persistent else self.now()+control.warning_seconds+control.reset_seconds,
            "serial": proposal["serial"], "actor": player.id, "starts": self.now()+control.warning_seconds}
        apartment = self.private.apartment(presence.core)
        if apartment and apartment.get("unit") and control.id == "apartment-door":
            proposal["apartments"][apartment["id"]].setdefault("vestibule_access_until", {})[player.id] = self.now()+control.reset_seconds
        if layout:
            proposal["effects"][key]["layout"] = layout
        if obj.spec.kind == "tram_stop" and control.action == "call":
            from blacksite.server.world.exits import schedule, MAX_HOLD_SECONDS, HOLD_IMMUNITY_SECONDS
            zone = self.game.world.zones[control.target.zone]
            for ex in self.platforms(zone, obj):
                until = schedule(ex, self.now()).departure+MAX_HOLD_SECONDS
                proposal["holds"][zone.id+":"+ex.id] = [until, until+HOLD_IMMUNITY_SECONDS]
        def applied() -> None:
            before = presence.trace
            if hasattr(self.game, 'crews'):
                self.game.crews.control_committed(player.id, presence.core)
            if self.lat.presences.get(presence.player_id) is presence:
                self.lat.encounters.trace(presence, FLIP_TRACE)
            self.zone_log(control.target.zone, self.effect_line(control))
            self.lat.encounters.log(presence, f"{control.label} changes. {max(0, presence.trace-before):g} trace.")
        self.commit(proposal, applied)

    def commit(self, proposal: dict[str, Any], applied: Callable[[], None]) -> None:
        def finished(success: bool) -> None:
            if success:
                self.state = proposal
                self.compose()
                applied()
        if not self.commerce.settle(None, {}, self.commerce.items, self.commerce.caches,
                                    self.commerce.serial, finished):
            raise ValueError("Let the current transfer settle first.")
        self.commerce.outbox[-1]["interlock_state"] = proposal

    def effect_line(self, control: ControlSpec) -> str:
        obj = self.game.world.zones[control.target.zone].objects[control.target.object]
        if obj.state.get("pending"):
            return "The latch waits for the floor and return route to clear."
        key = "interlock-"+obj.spec.kind.replace("_", "-")+("-enabled" if obj.state.get("enabled", True) else "-disabled")
        asset = self.content.text.get(key) or self.content.text.get("interlock-"+control.action)
        return asset.body.strip() if asset else f"{control.label} changes. Nobody touches it."

    def zone_log(self, zid: str, text: str) -> None:
        for session in self.game.sessions.active.values():
            avatar = self.lat.avatar(session)
            if avatar and avatar.actor.zone == zid and not session.closed:
                self.sim.log(session, text)

    @staticmethod
    def platforms(zone: Any, obj: Any) -> list[Any]:
        ids = obj.spec.params.get("exits")
        return [ex for ex in zone.template.meta.exits if ex.kind == "tram"
                and (ex.id in ids if ids is not None else ex.tile == obj.spec.tile)]

    def compose(self) -> None:
        now, tick = self.now(), self.clock.now_tick()
        targets = {(c.target.zone, c.target.object) for c in self.controls.values()}
        for zid, oid in sorted(targets):
            zone, obj = self.game.world.zones[zid], self.game.world.zones[zid].objects[oid]
            layers = [(e["serial"], e, self.controls.get((e["core"], e["control"])))
                      for e in self.state["effects"].values() if e["expires"] is None or e["expires"] > now]
            layers = sorted((serial, e, c) for serial, e, c in layers if c and e.get("revision") == c.revision
                            and (c.target.zone, c.target.object) == (zid, oid))
            default = (obj.spec.params.get("open", zone.tiles[zone.template.tile_at(obj.spec.tile)].passable)
                       if obj.open is not None else obj.spec.params.get("powered", True))
            value = {"enabled": bool(default), "controlled": bool(layers)}
            if layers:
                value.update(enabled=layers[-1][1]["enabled"], actor=layers[-1][1]["actor"],
                             warning=layers[-1][1]["starts"] > now, serial=layers[-1][1]["serial"])
            pending = False
            if obj.spec.kind in ("door", "apartment_door", "gate", "shutter") and (layers or (zid, oid) in self.applied):
                if self.applied.get((zid, oid)) != value:
                    if zone.set_door(oid, value["enabled"] if layers else default):
                        self.applied[zid, oid] = deepcopy(value)
                    else:
                        pending = True
            value["pending"] = pending
            if obj.state != value:
                obj.state = value
                zone.wake(tick)
                zone.revision += 1
                zone.geometry_revision += 1
        self.physical.compose()
        self.sim.departures.deadlines = {tuple(key.rsplit(":", 1)): tuple(value) for key, value in self.state["holds"].items()}

    def control_view(self, core: str, control: ControlSpec) -> dict[str, Any]:
        effect = self.state["effects"].get(core+":"+control.id)
        obj = self.game.world.zones[control.target.zone].objects[control.target.object]
        active = bool(effect and effect.get("revision") == control.revision
                      and (effect["expires"] is None or effect["expires"] > self.now()))
        enabled = obj.open if obj.open is not None else obj.state.get("enabled", True)
        return {"state": "waiting for safe closure" if obj.state.get("pending") else "on" if enabled else "off",
                "reset_in": ceil(max(0, effect["expires"]-self.now())) if active and effect["expires"] else None}

    def control_row(self, core: str, control: ControlSpec) -> dict[str, Any]:
        view = self.control_view(core, control)
        reset = f"{view['reset_in']}s remaining" if view["reset_in"] is not None else f"{control.reset_seconds}s ordinary reset"
        return {"id": "control:"+control.id, "cells": ["Flip "+control.label,
                view["state"]+" / "+reset, "3s / +10 base trace"]}

    def open_vestibule(self, presence: Presence, on_changed: Callable[[], None] | None = None,
                       key_tier: int = 1) -> None:
        """Passkey's typed effect: no storage, bed, bank or ICE unlock."""
        if not self.private.apartment(presence.core) or self.offline(presence.core):
            raise ValueError("No powered private vestibule is connected.")
        apartment = self.private.apartment(presence.core)
        if not self.private.before_access(apartment["resident"]):
            raise ValueError("The lease is being reconciled. Try again.")
        if key_tier < apartment.get("lock_tier", 1):
            raise ValueError(f"Locked. Tier {apartment['lock_tier']}.")
        control = self.controls[presence.core, "apartment-door"]
        current = self.state["effects"].get(presence.core+":"+control.id)
        changed = not current or not current["enabled"] or current["expires"] <= self.now()
        proposal = deepcopy(self.state)
        if apartment.get("unit"):
            proposal["apartments"][apartment["id"]].setdefault("vestibule_access_until", {})[presence.player_id] = self.now()+control.reset_seconds
        proposal["serial"] += 1
        proposal["effects"][presence.core+":"+control.id] = {
            "core": presence.core, "control": control.id, "revision": control.revision, "enabled": True,
            "expires": self.now()+control.reset_seconds, "starts": self.now(),
            "serial": proposal["serial"], "actor": presence.player_id}
        def committed() -> None:
            self.lat.encounters.log(presence,
                "Passkey opens the delivery vestibule for 30s. Storage stays protected.")
            if changed and on_changed:
                on_changed()
        self.commit(proposal, committed)

    def set_owner(self, core: str, faction: str | None) -> None:
        """S21 hook: remove only old ownership effects, preserving other layers."""
        if core not in self.content.cores or faction is not None and faction not in self.content.factions:
            raise ValueError("Unknown core or faction.")
        proposal = deepcopy(self.state)
        proposal["cores"].setdefault(core, {})["owner_faction"] = faction
        if faction != self.owned(core):
            proposal["effects"] = {key: effect for key, effect in proposal["effects"].items()
                                   if effect["core"] != core or effect["expires"] is not None}
        self.commit(proposal, lambda: None)

    def affected(self, core: str) -> list[Presence]:
        return [p for p in self.lat.presences.values() if p.core == core and not p.descent]

    def authorize_cut(self, session: Session, core: str, zid: str, oid: str, charge: bool = False) -> Any:
        player = self.game.players.get(session.player_id)
        actor = self.combat.actor(player) if player else None
        zone = self.game.world.zones.get(zid)
        obj = zone.objects.get(oid) if zone else None
        if (not actor or actor.zone != zid or actor.stance != "normal" or not obj
                or not self.game.world.object_access(actor, obj.spec)
                or max(abs(actor.x-obj.spec.tile[0]), abs(actor.y-obj.spec.tile[1])) > (3 if charge else 1)
                or self.hardware.get((zid, oid)) != core):
            raise ValueError("Stand beside the hardware with your body free to work.")
        if self.offline(core):
            raise ValueError("The core is already offline.")
        if not zone.allows_hostile(actor.position) and not self.permit(player.id, core, "cut"):
            raise ValueError("Safe hardware needs a scoped service work order.")
        for presence in self.affected(core):
            target = self.lat.encounters.actor(presence)
            if not target or not self.combat.permits_indirect(actor, target):
                raise ValueError("Cut refused: an affected runner's body is protected.")
        return actor

    def start_cut(self, session: Session, core: str, zid: str, oid: str, charge: bool = False) -> None:
        actor = self.authorize_cut(session, core, zid, oid, charge)
        if charge:
            player = self.game.players[session.player_id]
            if not self.charge_item(player):
                raise ValueError("Carry a containment charge first.")
            quote = self.game.factions.containment_fee(player,
                deepcopy(self.game.identities[player.bbs_user_id]))
            if player.chits_hand < quote:
                raise ValueError("The containment-charge service fee is 150 chits.")
        if session.player_id in self.cuts or actor.behaviour.get("channel") or session.id in self.commerce.using:
            raise ValueError("Finish or cancel your current action first.")
        self.cuts[session.player_id] = CutChannel(core, zid, oid, actor.position,
            self.clock.now_tick()+CUT_SECONDS*TICK_HZ, int(actor.behaviour.get("hit_serial", 0)), kind="charge_cut" if charge else "cut")
        self.sim.log(session, "You cut power. Hold still for 5s. Any damage interrupts; Esc cancels.")

    def charge_item(self, player: "Player") -> Any:
        return next((self.commerce.items[iid] for iid in player.inventory
                     if iid in self.commerce.items and self.commerce.items[iid].owner == player.id
                     and self.commerce.items[iid].template == "key_containment_charge"), None)

    def finish_cut(self, session: Session, channel: CutChannel) -> None:
        charged = channel.kind == "charge_cut"
        self.authorize_cut(session, channel.core, channel.zone, channel.object, charged)
        proposal = deepcopy(self.state)
        proposal["cores"].setdefault(channel.core, {})["offline_until"] = self.now()+OFFLINE_SECONDS
        player = self.game.players[session.player_id]
        standing_patch = self.cut_patch(player, channel.core)
        before_standing = deepcopy(player.standing)
        source = self.combat.actor(player)
        marks = any(self.combat.would_mark(source, self.lat.encounters.actor(presence), indirect=True)
                    for presence in self.affected(channel.core))
        if marks:
            from datetime import timedelta
            from blacksite.server.rules.combat import MARKED_SECONDS
            standing_patch["marked_until"] = (self.clock.now_utc()+timedelta(seconds=MARKED_SECONDS)).isoformat()
        charge_patch, identity = {}, None
        items = deepcopy(self.commerce.items)
        if charged:
            item = self.charge_item(player)
            if not item:
                raise ValueError("The containment charge is no longer carried.")
            identity = deepcopy(self.game.identities[player.bbs_user_id])
            fee = self.game.factions.containment_fee(player, identity)
            if player.chits_hand < fee:
                raise ValueError("The containment-charge service fee is 150 chits.")
            inventory = list(player.inventory)
            if item.stack > 1:
                items[item.id].stack -= 1
            else:
                items.pop(item.id)
                inventory.remove(item.id)
            charge_patch = {"inventory": inventory, "chits_hand": player.chits_hand-fee,
                            "equipment": {slot: iid for slot, iid in player.equipment.items() if iid in inventory}}
        def applied() -> None:
            if marks:
                if not source.marked:
                    self.combat.log(source, "You are Marked for fifteen minutes.", True)
                source.marked = True
            for presence in self.affected(channel.core):
                self.lat.encounters.log(presence, "The floor goes dark. Hardware power fails.", True)
                self.lat.encounters.actor(presence).cooldowns["last_hit"] = self.clock.now_tick()
                self.lat.encounters.force_out(presence)
            self.zone_log(channel.zone, "The hardware goes dark. The core is offline for ten minutes.")
            self.on_cut_power(self.game.players[session.player_id], channel.core)
            if hasattr(self.game, 'crews'):
                self.game.crews.control_committed(player.id, channel.core)
            if hasattr(self.game, "factions"):
                self.game.factions.notify_standing(player, before_standing, "cut power")
        self.commit(proposal, applied)
        self.commerce.outbox[-1]["player_patches"] = {
            presence.player_id: {"shock": max(CUT_SHOCK, self.lat.encounters.actor(presence).shock),
                                 "progress": {"last_hit_at": self.now()}}
            for presence in self.affected(channel.core)}
        patches = self.commerce.outbox[-1]["player_patches"]
        if standing_patch or charge_patch:
            patches.setdefault(player.id, {}).update({**standing_patch, **charge_patch})
        if charged:
            effect = self.commerce.outbox[-1]
            effect["items"].update({iid: item for iid, item in items.items() if item != self.commerce.items.get(iid)})
            effect["delete_items"] = sorted(set(self.commerce.items)-set(items))
            effect["identities"] = {player.bbs_user_id: identity}

    def close(self, session: Session) -> None:
        self.menus.pop(session.id, None)
        self.log_menus.discard(session.id)
        self.private.log_apartments.pop(session.id, None)
        overlay = self.sim.external_views.get(session.id)
        if overlay and overlay[0] == "menu" and overlay[1].get("title") in ("HARDWARE", "APARTMENT / CORE LOG"):
            self.sim.external_views.pop(session.id, None)
        avatar = self.lat.avatar(session)
        if avatar:
            self.sim.reset_view(session, avatar)

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        name = frame.data.get("name", "") if frame.type == "intent" else ""
        key = frame.data.get("k", "") if frame.type == "key" else ""
        if session.id in self.log_menus:
            if name == "menu_close" or key in ("escape", "b", "B"):
                self.close(session)
            elif name == "menu_select" and frame.data.get("expected_revision") == session.view_revision:
                body = self.sim.external_views[session.id][1]
                args = frame.data.get("args", {})
                if args.get("key") == "r" and body["rows"] and args.get("row") == body["rows"][body["cursor"]]["id"]:
                    try:
                        self.private.report_theft(session, self.private.log_apartments[session.id], args["row"])
                    except ValueError as exc:
                        self.sim.log(session, str(exc))
            elif name == "menu_cursor" and type(frame.data.get("args", {}).get("delta")) is int:
                body = self.sim.external_views[session.id][1]
                self.private.open_log(session, self.private.log_apartments[session.id],
                    body["cursor"]+frame.data["args"]["delta"])
            return True
        if session.player_id in self.cuts and (name == "menu_close" or key in ("escape", "b", "B")):
            self.cuts.pop(session.player_id)
            self.sim.log(session, "You stop cutting power.")
            return True
        screen = self.menus.get(session.id)
        if screen:
            if name == "menu_select" and frame.data.get("expected_revision") != session.view_revision:
                return True
            zid, oid, confirming = screen
            if name == "menu_close" or key in ("escape", "b", "B"):
                self.close(session)
            elif confirming and (key in ("y", "Y") or name == "menu_select" and frame.data.get("args", {}).get("key") == "y"):
                self.close(session)
                try:
                    self.start_cut(session, self.hardware[zid, oid], zid, oid, confirming == "charge")
                except ValueError as exc:
                    self.sim.log(session, str(exc))
            elif not confirming and (key in ("c", "C", "x", "X") or name == "menu_select"):
                chosen = frame.data.get("args", {}).get("key", "c") if name == "menu_select" else key.lower()
                if chosen in ("c", "x"):
                    actor = self.lat.avatar(session).actor
                    tile = self.game.world.zones[zid].objects[oid].spec.tile
                    if chosen == "c" and max(abs(actor.x-tile[0]), abs(actor.y-tile[1])) > 1:
                        self.sim.log(session, "Move adjacent for a manual cut. A charge reaches three tiles.")
                    else:
                        self.menus[session.id] = zid, oid, "charge" if chosen == "x" else True
            return True
        if name != "interact" and key not in ("e", "E"):
            return False
        avatar = self.lat.avatar(session)
        if not avatar or avatar.actor.stance != "normal" or session.id in self.sim.external_views:
            return False
        actor = avatar.actor
        zone = self.game.world.zones[actor.zone]
        if any(obj.spec.tile == actor.position and (obj.spec.kind in ("bank", "vendor", "cache", "terminal", "workshop", "salvage_node")
                or obj.spec.params.get("vendor")) for obj in zone.objects.values()):
            return False  # An adjacent cabinet cannot steal the counter key.
        apartment_door = next((obj for obj in zone.objects.values() if obj.spec.kind == "apartment_door"
            and obj.spec.params.get("apartment_id")
            and max(abs(actor.x-obj.spec.tile[0]), abs(actor.y-obj.spec.tile[1])) <= 1), None)
        if apartment_door:
            try:
                self.private.open_log(session, apartment_door.spec.params["apartment_id"])
            except ValueError as exc:
                self.sim.log(session, str(exc))
            return True
        candidates = [(zid, oid) for zid, oid in self.hardware if zid == actor.zone
            and max(abs(actor.x-self.game.world.zones[zid].objects[oid].spec.tile[0]),
                    abs(actor.y-self.game.world.zones[zid].objects[oid].spec.tile[1])) <= 3]
        if not candidates:
            return False
        zid, oid = min(candidates, key=lambda key: (
            self.game.world.zones[key[0]].objects[key[1]].spec.tile != actor.position, key))
        self.menus[session.id] = zid, oid, False
        return True

    def tick(self, ctx: TickContext) -> None:
        self.compose()
        self.physical.hazards()
        for sid in tuple(self.log_menus):
            session = self.game.sessions.active.get(sid)
            avatar = self.lat.avatar(session) if session else None
            if not session or session.closed or not avatar or avatar.actor.stance != "normal":
                if session:
                    self.close(session)
                else:
                    self.log_menus.discard(sid)
                    self.private.log_apartments.pop(sid, None)
                continue
            body = self.sim.external_views.get(sid, ("", {}))[1]
            try:
                self.private.open_log(session, self.private.log_apartments[sid], body.get("cursor", 0))
            except ValueError:
                self.close(session)
        for pid, channel in tuple(self.cuts.items()):
            session = self.lat.session(pid)
            actor = self.combat.actor(self.game.players[pid])
            if not session or session.closed or not channel.valid(actor):
                self.cuts.pop(pid)
                if session:
                    self.sim.log(session, "Your power cut is interrupted.")
            elif ctx.tick >= channel.until and not self.commerce.pending:
                self.cuts.pop(pid)
                try:
                    self.finish_cut(session, channel)
                except ValueError as exc:
                    self.sim.log(session, str(exc))
        for sid, (zid, oid, confirming) in tuple(self.menus.items()):
            session = self.game.sessions.active.get(sid)
            avatar = self.lat.avatar(session) if session else None
            obj = self.game.world.zones[zid].objects[oid]
            if (not session or session.closed or not avatar or avatar.actor.stance != "normal"
                    or avatar.actor.zone != zid or max(abs(avatar.actor.x-obj.spec.tile[0]), abs(avatar.actor.y-obj.spec.tile[1])) > 3):
                self.menus.pop(sid)
                if session:
                    self.close(session)
                continue
            core = self.hardware[zid, oid]
            detail = (f"Core: {self.content.cores[core].name}\n5s channel; damage interrupts."
                      "\nRunners: 100 shock. Core: offline 10 minutes."
                      "\nProtected bodies cannot be harmed.")
            body = menu("HARDWARE", [{"id": "cut", "cells": ["Cut power"]}], 0, detail,
                        "Y confirms cut / Esc/B returns" if confirming else "C cut power / Esc/B returns")
            body["kind"] = "hardware"
            adjacent = max(abs(avatar.actor.x-obj.spec.tile[0]), abs(avatar.actor.y-obj.spec.tile[1])) <= 1
            body["actions"] = ([{"key": "y", "label": "confirm cut"}] if confirming else
                               [{"key": "c", "label": "manual cut (adjacent)"}] if adjacent else [])
            body["hint"] = "Y confirms cut / Esc/B returns" if confirming else "C manual (adjacent) / X charge (range 3) / Esc/B returns" if adjacent else "X charge (range 3) / Esc/B returns"
            if not confirming:
                body["actions"].append({"key": "x", "label": "containment charge (range 3)"})
            if confirming == "charge":
                player = self.game.players[session.player_id]
                fee = self.game.factions.containment_fee(player,
                    deepcopy(self.game.identities[player.bbs_user_id]))
                body["detail"] = (f"Core: {self.content.cores[core].name}\n5s; 100 shock; core offline 10 min."
                    f"\nConsumes one charge; service fee {fee} chits."
                    "\nDamage interrupts. Protected bodies stay safe.")

            self.sim.external_views[sid] = "menu", body
