"""Game 8.4: seeded salvage proposals and uptime persistence, without I/O."""

from collections.abc import Callable
from copy import deepcopy
from random import Random
from typing import Any

from blacksite.content.schema import ObjectSpec
from blacksite.server.clock import TICK_HZ
from blacksite.server.commerce import Commerce
from blacksite.server.inventory import Inventory
from blacksite.server.items import ItemInstance, make_item
from blacksite.server.players import Player
from blacksite.server.world.zone import ObjectState

GRADES = ("hull", "optics", "power", "compute", "intact")


def tuples(value: Any) -> Any:
    """JSON arrays back to Random's nested state tuples."""
    return tuple(tuples(part) for part in value) if isinstance(value, (list, tuple)) else value


class Salvage:
    def __init__(self, commerce: Commerce, saved: dict[str, Any] | None = None) -> None:
        self.commerce, self.game = commerce, commerce.game
        self.clock, self.world, self.rules = commerce.clock, commerce.sim.world, commerce.content.salvage
        self.state = deepcopy(saved or {})
        self.state.setdefault("zones", {})
        self.state.setdefault("craft_rng", {})
        self.state.setdefault("serial", 0)
        self.started = self.clock.now_tick()
        self.elapsed = float(self.state.get("uptime", 0))
        self.crash_relay_bonus: Callable[[str], bool] = lambda zid: False  # S21.
        self.sync()

    @property
    def uptime(self) -> float:
        return self.elapsed+(self.clock.now_tick()-self.started)/TICK_HZ

    def record(self) -> dict[str, Any]:
        return {**deepcopy(self.state), "uptime": self.uptime}

    def rng(self, zid: str, state: dict[str, Any], *, craft: bool = False) -> Random:
        rng = Random(self.world.zones[zid].seed+(1 if craft else 0))
        saved = state["craft_rng"].get(zid) if craft else state["zones"][zid].get("rng")
        if saved:
            rng.setstate(tuples(saved))
        return rng

    def commit(self, state: dict[str, Any], player: Player | None = None,
               patch: dict[str, Any] | None = None, items: dict[str, ItemInstance] | None = None,
               serial: int | None = None, callback: Callable[[bool], None] = lambda ok: None,
               identity: dict[str, Any] | None = None) -> bool:
        def finished(success: bool) -> None:
            if success:
                self.state = state
                self.sync()
            callback(success)
        accepted = self.commerce.settle(player, patch or {}, self.commerce.items if items is None else items,
            self.commerce.caches, self.commerce.serial if serial is None else serial, finished, identity)
        if accepted:
            self.commerce.outbox[-1]["salvage_state"] = {**deepcopy(state), "uptime": self.uptime}
        return accepted

    def spawn(self, zid: str, state: dict[str, Any], rng: Random) -> bool:
        zone, field = self.world.zones[zid], state["zones"][zid]
        occupied = {tuple(node["tile"]) for node in field["nodes"].values()}
        occupied.update(obj.spec.tile for obj in zone.objects.values())
        occupied.update(actor.position for actor in zone.actors.values())
        occupied.update(ex.tile for ex in zone.template.meta.exits)
        tiles = [(x, y) for y, row in enumerate(zone.template.grid) for x in range(len(row))
                 if zone.passable((x, y)) and not zone.tiles[zone.tile_id((x, y))].hazard
                 and (x, y) not in occupied]
        if not tiles:
            return False
        weights = self.rules.weights[str(field["ring"])]
        grade = rng.choices(list(weights), weights=list(weights.values()))[0]
        if field["ring"] == 3 and self.crash_relay_bonus(zid):
            grade = GRADES[min(GRADES.index(grade)+1, GRADES.index("compute"))]
        state["serial"] += 1
        oid = f"salvage:{zid}:{state['serial']}"
        field["nodes"][oid] = {"tile": list(rng.choice(tiles)), "grade": grade,
            "units": rng.randint(self.rules.minimum_units, self.rules.maximum_units)}
        return True

    def tick(self) -> None:
        if not self.rules or self.commerce.pending:
            return
        proposal = deepcopy(self.state)
        changed = False
        for zid, zone in self.world.zones.items():
            marker = next((obj for obj in zone.objects.values() if obj.spec.kind == "salvage_field"), None)
            if not marker:
                continue
            ring = marker.spec.params["ring"]
            field = proposal["zones"].get(zid)
            if field is None:
                field = {"ring": ring, "nodes": {}, "respawn_at": self.uptime+self.rules.respawn_seconds}
                proposal["zones"][zid] = field
                rng = self.rng(zid, proposal)
                for _ in range(rng.randint(self.rules.minimum_nodes, self.rules.maximum_nodes)):
                    self.spawn(zid, proposal, rng)
                changed = True
            elif self.uptime >= field["respawn_at"]:
                rng = self.rng(zid, proposal)
                periods = int((self.uptime-field["respawn_at"])//self.rules.respawn_seconds)+1
                for _ in range(min(periods, self.rules.maximum_nodes-len(field["nodes"]))):
                    self.spawn(zid, proposal, rng)
                field["respawn_at"] += periods*self.rules.respawn_seconds
                changed = True
            else:
                continue
            field["rng"] = rng.getstate()
        if changed:
            self.commit(proposal)

    def sync(self) -> None:
        for zid, field in self.state["zones"].items():
            zone = self.world.zones.get(zid)
            if not zone:
                continue
            for oid in tuple(zone.objects):
                if zone.objects[oid].spec.params.get("salvage_generated") and oid not in field["nodes"]:
                    del zone.objects[oid]
                    zone.revision += 1
            zone.salvage_nodes = deepcopy(field["nodes"])
            for oid, node in field["nodes"].items():
                spec = ObjectSpec(oid, tuple(node["tile"]), "salvage_node", params={"salvage_generated": True})
                public = {"grade": node["grade"], "units": node["units"]}
                if oid not in zone.objects or zone.objects[oid].state != public:
                    zone.objects[oid] = ObjectState(spec, state=public)
                    zone.revision += 1

    def harvest(self, player: Player, zid: str, oid: str,
                callback: Callable[[bool, str], None]) -> None:
        proposal = deepcopy(self.state)
        node = proposal["zones"].get(zid, {}).get("nodes", {}).get(oid)
        if not node or node["units"] < 1:
            raise ValueError("That salvage node is empty.")
        draft, items = deepcopy(player), deepcopy(self.commerce.items)
        serial = max([self.commerce.serial, *(int(i.rsplit(":", 1)[-1]) for i in items
                    if i.rsplit(":", 1)[-1].isdigit())])+1
        template = next(item for item in self.commerce.content.items.values()
                        if item.salvage and item.salvage.grade == node["grade"])
        inventory = Inventory(items, self.commerce.content.items, self.game.progression.modifiers(draft).secured_slots)
        inventory.add(draft, make_item(f"{self.game.sessions.origin}:item:{serial}", template,
                                      draft.id, self.clock.now_utc().isoformat()))
        node["units"] -= 1
        if not node["units"]:
            del proposal["zones"][zid]["nodes"][oid]
        if not self.commit(proposal, player, {"inventory": draft.inventory}, items, serial,
                           lambda ok: callback(ok, template.name)):
            raise ValueError("The city is busy. Try the node again.")
