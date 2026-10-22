"""Narrow private-core authority. S18 supplies rentals and stored goods.

Storage manifests are server-owned apartment records, never player bank,
equipment, carried inventory or impound. A transfer and its shared daily
receipt use the same Commerce transaction.
"""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from blacksite.content.schema import ControlTarget, HardwareLocation
from blacksite.server.inventory import Inventory
from blacksite.server.lattice.presence import Presence, Procedure
from blacksite.server.clock import TICK_HZ
from blacksite.server.progression import Grant, award
from blacksite.server.wake import menu, wrapped

if TYPE_CHECKING:
    from blacksite.server.interlock import Interlock
    from blacksite.server.sessions import Session


class PrivateCores:
    def __init__(self, interlock: "Interlock") -> None:
        self.interlock = interlock
        self.lat, self.game = interlock.lat, interlock.game
        self.content = interlock.content
        self.log_apartments: dict[str, str] = {}
        for apartment in interlock.state["apartments"].values():
            self.install(apartment)

    def core_id(self, apartment: dict[str, Any]) -> str:
        return "lat-apartment-"+apartment["id"]

    def apartment(self, core: str) -> dict[str, Any] | None:
        return next((a for a in self.interlock.state["apartments"].values() if self.core_id(a) == core), None)

    def install(self, apartment: dict[str, Any], validate_only: bool = False) -> None:
        """S18 integration seam, called for committed rentals and at rebuild."""
        if not 1 <= apartment["tier"] <= 3:
            raise ValueError("Private core tier must be 1 through 3.")
        core_id = self.core_id(apartment)
        sector = self.lat.sectors.records[apartment["sector"]]
        cell = self.lat.sectors.cells[sector.id][apartment["cell"]]
        if cell.core_id not in (None, core_id):
            raise ValueError("That entrance already belongs to another core.")
        zone = self.game.world.zones[apartment["zone"]]
        hardware = zone.objects[apartment["hardware"]]
        if hardware.spec.kind != "hardware" or (zone.id, hardware.spec.id) in self.interlock.hardware and self.interlock.hardware[zone.id, hardware.spec.id] != core_id:
            raise ValueError("Private core needs its own hardware object.")
        template = self.content.cores["lat-private-core"]
        controls = {"apartment-door": apartment["door"], "apartment-lights": apartment["light"]}
        if zone.objects[apartment["door"]].spec.kind not in ("door", "apartment_door"):
            raise ValueError("The private vestibule needs a door.")
        rooms = tuple(replace(room, controls=tuple(replace(c, target=ControlTarget(zone.id, controls[c.id]))
                      for c in room.controls)) for room in template.rooms)
        # World Lattice 3: tier 1 Tripwire; tier 2 adds Turnstile;
        # tier 3 adds Mastiff. No NPC feedback consent for this owner kind.
        roster = {1: ("ice_tripwire",), 2: ("ice_tripwire", "ice_turnstile"),
                  3: ("ice_tripwire", "ice_glasshouse", "ice_mastiff")}[apartment["tier"]]
        rooms = tuple(replace(room, ice=roster) if room.id == "index" else room for room in rooms)
        spec = replace(template, id=core_id, template=False, tier=apartment["tier"], rooms=rooms,
                       hardware=(HardwareLocation(zone.id, hardware.spec.tile, hardware.spec.id),))
        if validate_only:
            return
        self.content.cores[core_id] = spec
        entrance = replace(cell, kind="core_entrance", core_id=core_id, core_placeholder=None)
        self.lat.sectors.cells[sector.id][cell.id] = entrance
        self.lat.sectors.records[sector.id] = replace(sector, cells=tuple(entrance if c.id == cell.id else c for c in sector.cells))
        self.interlock.hardware[zone.id, hardware.spec.id] = core_id
        for room in rooms:
            for control in room.controls:
                self.interlock.controls[core_id, control.id] = control

    def register(self, apartment: dict[str, Any]) -> None:
        """Trusted server rental hook; no client may submit apartment records."""
        proposal = deepcopy(self.interlock.state)
        record = deepcopy(apartment)
        record.setdefault("storage", [])
        record.setdefault("last_hacked_at", None)
        record.setdefault("hack_log", [])
        if record["id"] in proposal["apartments"]:
            raise ValueError("This apartment is already registered.")
        # Validate against a disposable installation before committing any state.
        # install performs no I/O; registration callers must supply commissioned
        # objects and an unallocated cell.
        self.install(record, validate_only=True)
        proposal["apartments"][record["id"]] = record
        self.interlock.commit(proposal, lambda: self.install(record))

    def manifest(self, presence: Presence) -> list[Any]:
        apartment = self.apartment(presence.core)
        if not apartment or presence.room != "index":
            return []
        return [item for iid in apartment["storage"] if (item := self.interlock.commerce.items.get(iid))
                and item.owner == "apartment:"+apartment["id"] and not item.secured and not item.bound
                and item.stack > 0]

    def rows(self, presence: Presence) -> list[dict[str, Any]]:
        from blacksite.server.interlock import THEFT_SECONDS
        apartment = self.apartment(presence.core)
        if not apartment:
            return []
        remaining = (max(0, apartment["last_hacked_at"]+THEFT_SECONDS-self.interlock.now())
                     if apartment["last_hacked_at"] is not None else 0)
        status = f"Locked {int(remaining)//3600}h {int(remaining)%3600//60}m" if remaining else "1 unit/24h ready"
        return [{"id": "theft:"+item.id, "cells": [self.content.items[item.template].name,
                 f"Lift 1 (x{item.stack})", status]} for item in self.manifest(presence)]

    def start_theft(self, presence: Presence, iid: str) -> None:
        from blacksite.server.interlock import THEFT_SECONDS, FLIP_TRACE
        apartment = self.apartment(presence.core)
        if not apartment or iid not in {i.id for i in self.manifest(presence)}:
            raise ValueError("That unsecured unit is not in this manifest.")
        if apartment["resident"] == presence.player_id:
            raise ValueError("Use your apartment storage menu for your own goods.")
        if apartment["last_hacked_at"] is not None and self.interlock.now() < apartment["last_hacked_at"]+THEFT_SECONDS:
            raise ValueError("This apartment's one-unit limit lasts 24 hours.")
        if not self.lat.encounters.idle(presence):
            raise ValueError("Finish or cancel your current action first.")
        for ice in self.lat.encounters.defenders(presence):
            if ice.template.params.get("shields_data") or ice.blocks(self.interlock.now()) and ice.id not in presence.opened:
                self.lat.encounters.activate(ice, presence, "data")
                raise ValueError(ice.template.name+" protects this manifest. Open or destroy it first.")
            if ice.template.trigger in ("data", "touch"):
                self.lat.encounters.activate(ice, presence, "data")
        presence.procedure = Procedure("theft", iid, self.interlock.clock.now_tick()+3*TICK_HZ,
            presence.instance, self.lat.encounters.hit_serial(presence))
        self.lat.encounters.trace(presence, FLIP_TRACE)
        self.lat.encounters.log(presence, "You lift one unsecured unit. 3s; +10 trace spent. Esc cancels.")

    def complete_theft(self, presence: Presence, procedure: Procedure) -> None:
        from blacksite.server.interlock import THEFT_SECONDS, HACK_LOG_LIMIT
        apartment = self.apartment(presence.core)
        item = next((i for i in self.manifest(presence) if i.id == procedure.target), None)
        if not item or apartment["last_hacked_at"] is not None and self.interlock.now() < apartment["last_hacked_at"]+THEFT_SECONDS:
            raise ValueError("Another runner already took this apartment's daily unit.")
        commerce = self.interlock.commerce
        items = deepcopy(commerce.items)
        player = self.game.players[presence.player_id]
        draft = deepcopy(player)
        serial = commerce.serial+1
        stolen = replace(item, id=f"{self.game.sessions.origin}:item:{serial}", owner=player.id, stack=1)
        if item.stack > 1:
            items[item.id].stack -= 1
        else:
            items.pop(item.id)
        Inventory(items, self.content.items).add(draft, stolen)
        proposal = deepcopy(self.interlock.state)
        record = proposal["apartments"][apartment["id"]]
        if item.stack == 1:
            record["storage"].remove(item.id)
        record["last_hacked_at"] = self.interlock.now()
        at = self.interlock.clock.now_utc().isoformat()
        record["hack_log"] = (record["hack_log"]+[{"at": at, "item": item.template, "unit": 1}])[-HACK_LOG_LIMIT:]
        identity = deepcopy(self.game.identity(player.bbs_user_id))
        reward = award(draft, identity, Grant("run", stolen.id, True,
            scope=presence.core, core=presence.core, tier=apartment["tier"]),
            self.interlock.clock.now_utc(), self.game.progression.modifiers(draft))
        def finished(success: bool) -> None:
            if success:
                self.interlock.state = proposal
                self.lat.encounters.log(presence, "Transfer committed: one unsecured unit. The resident is told.")
                self.notify_owner(record)
                self.game.progression.notify_reward(player, reward)
        patch = {key: deepcopy(getattr(draft, key)) for key in
                 ("inventory", "xp", "grade", "attributes", "progress", "health", "legal_at")}
        if not commerce.settle(player, patch, items, commerce.caches, serial, finished, identity):
            raise ValueError("Let the current transfer settle first.")
        commerce.outbox[-1]["interlock_state"] = proposal

    def log_lines(self, apartment: dict[str, Any]) -> list[str]:
        return [f"Someone was in your core at {datetime.fromisoformat(row['at']).astimezone(timezone.utc):%Y-%m-%d %H:%M} UTC. They took a {self.content.items[row['item']].name}."
                for row in apartment["hack_log"]]

    def notify_owner(self, apartment: dict[str, Any]) -> None:
        session = self.lat.session(apartment["resident"])
        if session and not session.closed and apartment["hack_log"]:
            self.lat.log(session, self.log_lines(apartment)[-1], True)

    def on_login(self, session: "Session") -> None:
        player = self.game.players.get(session.player_id)
        if not player:
            return
        for apartment in self.interlock.state["apartments"].values():
            if apartment["resident"] != player.id or not apartment["hack_log"]:
                continue
            latest = apartment["hack_log"][-1]["at"]
            seen = player.progress.setdefault("private_hack_notice", {})
            if seen.get(apartment["id"]) != latest:
                self.notify_owner(apartment)
                seen[apartment["id"]] = latest
                self.game.queue("save", player.bbs_user_id, player, immediate=True)

    def open_log(self, session: "Session", aid: str, cursor: int = 0) -> None:
        apartment = self.interlock.state["apartments"].get(aid)
        if not apartment or apartment["resident"] != session.player_id:
            raise ValueError("Only the resident may read this core log.")
        lines = self.log_lines(apartment)
        cursor = max(0, min(cursor, len(lines)-1))
        detail = ("\n".join(wrapped(lines[cursor], 52 if session.caps["width"] >= 100 else 66))
                  if lines else "No intrusion recorded.")
        self.lat.sim.external_views[session.id] = "menu", menu("APARTMENT / CORE LOG",
            [{"id": str(i), "cells": [line]} for i, line in enumerate(lines)], cursor,
            detail, "Esc/B returns")
        self.interlock.log_menus.add(session.id)
        self.log_apartments[session.id] = aid
