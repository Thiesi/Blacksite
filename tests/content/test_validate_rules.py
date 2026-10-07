"""S02: one case per validator rule not covered by test_validate.py.

Each case makes one change to a scratch copy of the fixture world and
expects a message containing a fragment. Rules come from 01-entities.md
section 1 and 5, 00-game-design.md sections 5-13, 03-terminal-ui.md and
04-dramatis-personae.md Part III; test_validate.py holds the cases that
need more than one assertion.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from tests.content.support import World, find


@dataclass(frozen=True)
class Case:
    name: str
    change: Callable[[World], None]
    expect: str


def _edit(rel: str, fn: Callable[[dict], object]) -> Callable[[World], None]:
    return lambda w: w.edit(rel, fn)


def _table(rel: str, key: str, record: str, fn: Callable[[dict], object]) -> Callable[[World], None]:
    return _edit(rel, lambda d: fn(find(d[key], record)))


def _add(rel: str, key: str, record: dict) -> Callable[[World], None]:
    def change(w: World) -> None:
        path = w.path(rel)
        data = w.read(rel) if path.exists() else {"schema": 1, key: []}
        data[key].append(record)
        w.write(rel, data)
    return change


def _zone(zone: str, fn: Callable[[dict], object]) -> Callable[[World], None]:
    return _edit(f"zones/{zone}.json", fn)


def _core(core: str, fn: Callable[[dict], object]) -> Callable[[World], None]:
    return _edit(f"cores/{core}.json", fn)


def _ctrl(fn: Callable[[dict], object]) -> Callable[[World], None]:
    return _core("fx-core-a", lambda d: fn(find(d["rooms"], "r-control")["controls"][0]))


def _cell(cell: str, fn: Callable[[dict], object]) -> Callable[[World], None]:
    return _edit("sectors/fx-sector.json", lambda d: fn(find(d["cells"], cell)))


def _job(fn: Callable[[dict], object]) -> Callable[[World], None]:
    return _edit("contracts.json", lambda d: fn(d["contracts"][0]))


def _target(target: dict) -> Callable[[World], None]:
    return _job(lambda c: c["stages"][0].update(target=target))


def _unlock(cond: str) -> Callable[[World], None]:
    return _job(lambda c: c.update(unlock_conditions=[cond]))


def _event(fn: Callable[[dict], object]) -> Callable[[World], None]:
    return _edit("events.json", lambda d: fn(d["events"][0]))


def _effect(**changes: object) -> Callable[[World], None]:
    return _event(lambda e: e["effects"][0].update(changes))


def _season(**changes: object) -> Callable[[World], None]:
    def change(w: World) -> None:
        season = {
            "schema": 1, "number": 1, "title": "S", "depth_target": 10000,
            "contribution_weights": {"data": 250}, "level": {"zone": "fx-open", "sector": "fx-sector"},
            "phases": ["a"], "finale_choices": [{"id": "x", "label": "X", "chronicle": "text-fx-gate-1",
                                                 "balance_delta": 0}],
            "finale_lines": [{"text": "text-fx-gate-1", "tag": "CUST"}, {"text": "text-fx-gate-1", "tag": "TEN"}],
        }
        season.update(changes)
        w.write("seasons/1.json", season)
    return change


def _talker(**changes: object) -> Callable[[World], None]:
    talker = {"schema": 1, "id": "fx-talker", "name": "T", "lines": [{"id": "hi", "text": "Hello."}]}
    talker.update(changes)
    return lambda w: w.write("dialogue/fx-talker.json", talker)


ROUTE = {"id": "fx-route", "speed": 1.0,
         "waypoints": [{"zone": "fx-street", "tile": [2, 12]}, {"zone": "fx-open", "tile": [2, 14]}]}

CASES = [
    # zones (00-game-design.md 5.1, 01-entities.md 1.1)
    Case("sight radius", _zone("fx-safe", lambda d: d.update(sight_radius=0)), "sight_radius must be positive"),
    Case("pocket bounds", _zone("fx-street", lambda d: d.update(pockets=[{"x": 58, "y": 2, "w": 8, "h": 2}])),
         "pocket 0 is outside the map"),
    Case("duplicate exit", _zone("fx-open", lambda d: d["exits"][1].update(id="to-street-gate")), "duplicate exit id"),
    Case("duplicate object", _zone("fx-street", lambda d: d["objects"].append(
        {"id": "fx-street-cache", "tile": [41, 20], "kind": "cache"})), "duplicate object id"),
    Case("exit requirement", _zone("fx-safe", lambda d: d["exits"][0].update(
        requirement={"kind": "pass", "ref": "key_nothing"})), "requirement: item 'key_nothing' does not exist"),
    Case("spawner count", _zone("fx-safe", lambda d: d["spawners"][0].update(count=0)), "count must be at least 1"),
    Case("spawner tile and region", _zone("fx-safe", lambda d: d["spawners"][0].update(
        region={"x": 2, "y": 2, "w": 2, "h": 2})), "give exactly one of tile and region"),
    Case("spawner tile wall", _zone("fx-safe", lambda d: d["spawners"][0].update(tile=[0, 0])),
         "spawner fx-safe-recruiter: tile [0, 0] is not passable"),
    Case("spawner npc", _zone("fx-safe", lambda d: d["spawners"][0].update(npc="fx-nobody")),
         "NPC 'fx-nobody' does not exist"),
    Case("zone lean", _zone("fx-safe", lambda d: d.update(lean="fx-gamma")), "lean: faction 'fx-gamma' does not exist"),
    # sectors (01-entities.md 1.3)
    Case("duplicate cell", _edit("sectors/fx-sector.json", lambda d: d["cells"].append(
        dict(d["cells"][0], pos=[9, 9], neighbours=[]))), "cell ids are not unique"),
    Case("cell position", _cell("c-gate", lambda c: c.update(pos=[0, 0])), "position [0, 0] is also c-plaza"),
    Case("cell neighbour", _cell("c-gate", lambda c: c["neighbours"].append("c-x")), "neighbour 'c-x' does not exist"),
    Case("cell reciprocity", _cell("c-hidden", lambda c: c["neighbours"].remove("c-plaza")),
         "cell c-plaza: neighbour 'c-hidden' does not list it back"),
    Case("entrance needs core", _cell("c-core-b", lambda c: c.pop("core_id")), "a core entrance needs core_id"),
    Case("core id on public cell", _cell("c-plaza", lambda c: c.update(core_id="fx-core-a")),
         "only a core entrance has core_id"),
    Case("cell lore", _cell("c-plaza", lambda c: c.update(lore=["text-none"])), "text asset 'text-none' does not exist"),
    Case("entrance core exists", _cell("c-core-b", lambda c: c.update(core_id="fx-core-z")),
         "core 'fx-core-z' does not exist"),
    # cores (00-game-design.md 6.2, 6.4)
    Case("duplicate room", _core("fx-core-b", lambda d: d["rooms"].append(dict(d["rooms"][1]))),
         "room ids are not unique"),
    Case("room neighbour", _core("fx-core-b", lambda d: d["rooms"][1]["neighbours"].append("r-x")),
         "neighbour 'r-x' does not exist"),
    Case("text data asset", _core("fx-core-b", lambda d: d["rooms"][1]["data"][0].pop("asset")),
         "of kind text needs an asset"),
    Case("chits amount", _core("fx-core-a", lambda d: d["rooms"][1]["data"][0].update(amount=0)),
         "needs a positive amount"),
    Case("room ice", _core("fx-core-b", lambda d: d["rooms"][2]["ice"].append("ice_none")),
         "ICE 'ice_none' does not exist"),
    Case("duplicate control", _core("fx-core-a", lambda d: d["rooms"][1].update(controls=[{
        "id": "c-gate", "label": "x", "target": {"zone": "fx-street", "object": "fx-street-terminal"},
        "action": "call", "reset_seconds": 600}])), "duplicate control id"),
    Case("control reset", _ctrl(lambda c: c.update(reset_seconds=10)), "reset_seconds 10 is outside 300-1800"),
    Case("control revision", _ctrl(lambda c: c.update(revision=0)), "revision must be at least 1"),
    Case("alternate not an exit", _ctrl(lambda c: c.update(alternate_route="nope")),
         "alternate_route 'nope' is not an exit in fx-street"),
    Case("hazard control warning", _ctrl(lambda c: c.update(
        target={"zone": "fx-open", "object": "fx-open-hw"}, action="toggle", safety_policy="hazard",
        alternate_route=None)), "a hazard needs at least 5 s warning"),
    Case("control zone", _ctrl(lambda c: c["target"].update(zone="fx-nowhere")), "zone 'fx-nowhere' does not exist"),
    Case("three hardware", _core("fx-core-b", lambda d: d["hardware"].extend(
        [{"zone": "fx-safe", "tile": [10, 5]}, {"zone": "fx-safe", "tile": [5, 5]}])), "3 hardware locations"),
    Case("no hardware", _core("fx-core-b", lambda d: d.update(hardware=[])), "a core needs a hardware location"),
    Case("core owner", _core("fx-core-b", lambda d: d.update(owner="fx-gamma")), "owner: faction 'fx-gamma'"),
    # ICE and programs (00-game-design.md 17.2, 17.3)
    Case("ice tier", _table("ice.json", "ice", "ice_ticker", lambda r: r.update(tier=6)), "tier 6 is outside 1-5"),
    Case("ice integrity", _table("ice.json", "ice", "ice_ticker", lambda r: r.update(integrity=0)),
         "integrity must be positive"),
    Case("trace trigger", _table("ice.json", "ice", "ice_ticker", lambda r: r.update(trigger="trace")),
         "trigger_trace is set exactly when trigger is 'trace'"),
    Case("own variant", _table("ice.json", "ice", "ice_ticker", lambda r: r.update(variants=["ice_ticker"])),
         "cannot be its own variant"),
    Case("program tier", _table("programs.json", "programs", "prg_pick", lambda r: r.update(tier=0)),
         "tier 0 is outside 1-5"),
    Case("program slots", _table("programs.json", "programs", "prg_pick", lambda r: r.update(slots=0)),
         "slots must be at least 1"),
    # items (00-game-design.md 17.1)
    Case("item tier", _table("items.json", "items", "ammo_9x", lambda r: r.update(tier=4)), "tier 4 is outside 1-3"),
    Case("stack max", _table("items.json", "items", "ammo_9x", lambda r: r.update(stack_max=0)),
         "stack_max must be at least 1"),
    Case("negative weight", _table("items.json", "items", "ammo_9x", lambda r: r.update(weight=-1)),
         "weight and base_price cannot be negative"),
    Case("wrong block", _table("items.json", "items", "ammo_9x", lambda r: r.update(
        consumable={"effects": {}, "cooldown_class": "x"})), "class ammo cannot have a 'consumable' block"),
    Case("melee range", _table("items.json", "items", "wpn_kestrel_sidearm", lambda r: r["weapon"].update(melee=True)),
         "a melee weapon has stamina and no range"),
    Case("ranged range", _table("items.json", "items", "wpn_kestrel_sidearm", lambda r: r["weapon"].pop("range")),
         "a ranged weapon needs a positive range"),
    Case("schematic output", _add("items.json", "items", {
        "id": "sch_nothing", "name": "N", "class": "schematic",
        "schematic": {"output": "wpn_nothing", "inputs": {"compute": 1}}}), "item 'wpn_nothing' does not exist"),
    Case("hymn tier", _add("hymns.json", "hymns", {
        "id": "hymn_steady", "name": "Steady", "kind": "hymn", "tier": 4, "cast_seconds": 0.5,
        "cooldown_seconds": 12}), "tier 4 is outside 1-3"),
    Case("vendor stock", _add("vendors.json", "vendors", {
        "id": "fx-shop", "name": "Shop", "tier": "list", "stock": [{"item": "wpn_nothing"}]}),
        "stock: item 'wpn_nothing' does not exist"),
    Case("vendor zone", _add("vendors.json", "vendors", {
        "id": "fx-shop", "name": "Shop", "tier": "list", "stock": [], "zone": "fx-nowhere"}),
        "zone: zone 'fx-nowhere' does not exist"),
    # NPCs (01-entities.md 1.8)
    Case("npc weapon class", _table("npcs.json", "npcs", "fx-thug", lambda r: r.update(weapon="ammo_9x")),
         "weapon 'ammo_9x' is not a weapon"),
    Case("npc armour class", _table("npcs.json", "npcs", "fx-thug", lambda r: r.update(armour="ammo_9x")),
         "armour 'ammo_9x' is not armour"),
    Case("loot chance", _table("npcs.json", "npcs", "fx-thug", lambda r: r["loot"][0].update(chance=0)),
         "chance must be in (0, 1]"),
    Case("npc dialogue", _table("npcs.json", "npcs", "fx-thug", lambda r: r.update(dialogue="fx-none")),
         "dialogue 'fx-none' does not exist"),
    Case("npc vendor", _table("npcs.json", "npcs", "fx-thug", lambda r: r.update(vendor="fx-none")),
         "vendor 'fx-none' does not exist"),
    Case("npc lore", _table("npcs.json", "npcs", "fx-thug", lambda r: r.update(lore=["text-none"])),
         "text asset 'text-none' does not exist"),
    # factions (00-game-design.md 7.2)
    Case("self relation", _table("factions.json", "factions", "fx-beta", lambda r: r["relations"].update(
        {"fx-beta": "A"})), "a faction has no relation to itself"),
    Case("unknown relation", _table("factions.json", "factions", "fx-beta", lambda r: r["relations"].update(
        {"fx-gamma": "A"})), "relation to unknown faction 'fx-gamma'"),
    Case("rank order", _table("factions.json", "factions", "fx-alpha", lambda r: r["ranks"].reverse()),
         "ranks must be in ascending standing order"),
    Case("asymmetry faction", _edit("factions.json", lambda d: d["asymmetries"].append(["fx-alpha", "fx-gamma"])),
         "asymmetry names unknown faction 'fx-gamma'"),
    Case("faction hall", _table("factions.json", "factions", "fx-beta", lambda r: r.update(hall="fx-none")),
         "hall: zone 'fx-none' does not exist"),
    Case("faction recruiter", _table("factions.json", "factions", "fx-beta", lambda r: r.update(recruiter="fx-none")),
         "recruiter: NPC 'fx-none' does not exist"),
    Case("faction colour", _table("factions.json", "factions", "fx-beta", lambda r: r.update(colour="mauve")),
         "palette role 'mauve' does not exist"),
    # evidence and contracts (00-game-design.md 9)
    Case("evidence claim", _table("evidence.json", "evidence", "fx-gate-log", lambda r: r.update(claim=" ")),
         "claim must not be empty"),
    Case("duplicate stage", _job(lambda c: c["stages"][1].update(id="s1")), "stage s1: duplicate stage id"),
    Case("contract giver", _job(lambda c: c.update(faction="fx-gamma")), "faction: faction 'fx-gamma'"),
    Case("chits range", _job(lambda c: c["reward"].update(chits=[300, 200])), "chits range [300, 200]"),
    Case("no stages", _job(lambda c: c.update(stages=[])), "a contract needs at least one stage"),
    Case("publication ids", _job(lambda c: c.update(publication_options=[
        {"id": "p", "label": "A", "audience": "public"}, {"id": "p", "label": "B", "audience": "handler"}])),
        "publication option ids are not unique"),
    Case("publication reward", _job(lambda c: c.update(publication_options=[
        {"id": "p", "label": "A", "audience": "public", "reward": {"standing": {"fx-gamma": 5}}}])),
        "publication p: standing: faction 'fx-gamma'"),
    Case("branch pair", _job(lambda c: c.update(branch_group="fx-fork")), "branch_group and branch are set together"),
    Case("chain", _job(lambda c: c.update(chain="fx-none")), "chain: contract 'fx-none' does not exist"),
    Case("story season", _job(lambda c: c.update(story=True, season=9)), "season 9 is not defined"),
    Case("target zone missing", _target({"kind": "zone_object", "object": "x"}), "target needs a zone"),
    Case("target tile", _target({"kind": "zone_tile", "zone": "fx-open", "tile": [0, 0]}),
         "target: tile is not passable in fx-open"),
    Case("target room", _target({"kind": "core_room", "core": "fx-core-b", "room": "r-x"}),
         "room 'r-x' does not exist in fx-core-b"),
    Case("target core", _target({"kind": "core_room", "core": "fx-core-z", "room": "r-x"}),
         "core 'fx-core-z' does not exist"),
    Case("target core missing", _target({"kind": "core_control", "control": "c"}), "target needs a core"),
    Case("target npc", _target({"kind": "npc", "npc": "fx-none"}), "NPC 'fx-none' does not exist"),
    Case("target npc missing", _target({"kind": "npc"}), "target needs an npc"),
    Case("target item", _target({"kind": "item", "item": "wpn_none"}), "item 'wpn_none' does not exist"),
    Case("target cell", _target({"kind": "cell", "sector": "fx-sector", "cell": "c-x"}),
         "cell 'c-x' does not exist in fx-sector"),
    Case("target sector", _target({"kind": "cell", "sector": "fx-none", "cell": "c-x"}),
         "sector 'fx-none' does not exist"),
    # condition grammar (04-dramatis-personae.md Part III)
    Case("condition arity", _unlock("standing_at_least fx-alpha"), "standing_at_least takes 2 argument(s), got 1"),
    Case("condition contract", _unlock("completed_contract fx-none"), "contract 'fx-none' does not exist"),
    Case("condition item", _unlock("has_item wpn_none"), "item 'wpn_none' does not exist"),
    Case("condition event", _unlock("event_active fx-none"), "event 'fx-none' does not exist"),
    Case("condition evidence", _unlock("has_evidence fx-none"), "evidence record 'fx-none' does not exist"),
    Case("condition service", _unlock("service_state fx-none normal"), "service 'fx-none' does not exist"),
    Case("condition state", _unlock("service_state fx-pump broken"), "'broken' is not one of normal"),
    Case("condition stage", _unlock("season_stage later"), "'later' is not one of open"),
    Case("condition balance", _unlock("balance HIGH"), "'HIGH' is not one of CUST"),
    Case("condition archetype", _unlock("archetype wizard"), "'wizard' is not an archetype"),
    # routes and events (00-game-design.md 12)
    Case("route speed", _add("routes.json", "routes", dict(ROUTE, speed=0)), "speed must be positive"),
    Case("route length", _add("routes.json", "routes", dict(ROUTE, waypoints=ROUTE["waypoints"][:1])),
         "a route needs at least two waypoints"),
    Case("route tile", _add("routes.json", "routes", dict(ROUTE, waypoints=[
        {"zone": "fx-street", "tile": [0, 0]}, ROUTE["waypoints"][1]])),
        "waypoint 0: tile [0, 0] is not passable in fx-street"),
    Case("route zone", _add("routes.json", "routes", dict(ROUTE, waypoints=[
        {"zone": "fx-none", "tile": [1, 1]}, ROUTE["waypoints"][1]])), "zone 'fx-none' does not exist"),
    Case("event route", _event(lambda e: e.update(route="fx-none")), "route: route 'fx-none' does not exist"),
    Case("event duration", _event(lambda e: e.update(duration_seconds=0)), "duration must be positive"),
    Case("event where empty", _event(lambda e: e.update(where=[])), "where must name at least one zone or sector"),
    Case("event where unknown", _event(lambda e: e.update(where=["fx-none"])), "'fx-none' is not a zone or sector"),
    Case("event variant ids", _event(lambda e: e["variants"].append(dict(e["variants"][0]))),
         "variant ids are not unique"),
    Case("hazard zone", _effect(zone=None, region=None), "a hazard needs a zone"),
    Case("effect region", _effect(region={"x": 38, "y": 4, "w": 6, "h": 4}), "region is outside fx-open"),
    Case("closed exit", _event(lambda e: e["variants"][0]["effects"][0].update(exits_closed=["fx-open/nope"])),
         "exit 'fx-open/nope' does not exist"),
    Case("announce asset", _event(lambda e: e["announce"].update(end="text-none")),
         "text asset 'text-none' does not exist"),
    Case("ice variant params", _event(lambda e: e["effects"].append({"type": "ice_variant", "sector": "fx-sector"})),
         "an ice_variant effect names 'from' and 'to' ICE"),
    Case("ice variant declared", _event(lambda e: e["effects"].append(
        {"type": "ice_variant", "sector": "fx-sector", "params": {"from": "ice_ticker", "to": "ice_tripwire"}})),
        "'ice_tripwire' is not a declared variant of 'ice_ticker'"),
    # services (00-game-design.md 7.5)
    Case("service object", _edit("services.json", lambda d: d["services"][0]["target_objects"].append("fx-none")),
         "target object 'fx-none' does not exist in fx-street"),
    Case("service core", _edit("services.json", lambda d: d["services"][0].update(core="fx-core-z")),
         "core 'fx-core-z' does not exist"),
    # dialogue (04-dramatis-personae.md Part III)
    Case("no lines", _talker(lines=[]), "a talker needs at least one line"),
    Case("line ids", _talker(lines=[{"id": "a", "when": ["marked"], "text": "x"}, {"id": "a", "text": "y"}]),
         "line ids are not unique"),
    Case("offer condition", _talker(offers=[{"kind": "travel", "label": "Go", "hotkey": "T", "ref": "fx-open",
                                             "when": ["unknown_thing"]}]), "unknown condition 'unknown_thing'"),
    Case("line condition", _talker(lines=[{"id": "a", "when": ["member_of fx-gamma"], "text": "x"},
                                          {"id": "b", "text": "y"}]), "faction 'fx-gamma' does not exist"),
    # seasons (00-game-design.md 13)
    Case("depth target", _season(depth_target=0), "depth_target must be positive"),
    Case("balance delta", _season(finale_choices=[{"id": "x", "label": "X", "chronicle": "text-fx-gate-1",
                                                   "balance_delta": 5}]), "balance_delta outside -3..3"),
    Case("relations override", _season(relations_override=[{"a": "fx-alpha", "b": "fx-gamma", "value": "A"}]),
         "faction 'fx-gamma' does not exist"),
    Case("story chain", _season(story_chains=["fx-none"]), "contract 'fx-none' does not exist"),
    Case("level zone", _season(level={"zone": "fx-none", "sector": "fx-sector"}), "zone 'fx-none' does not exist"),
    Case("choice condition", _season(finale_choices=[{"id": "x", "label": "X", "chronicle": "text-fx-gate-1",
                                                      "balance_delta": 0, "condition": "bogus"}]),
         "unknown condition 'bogus'"),
    # art (01-entities.md 1.15)
    Case("art size", _edit("art/art-fx-sigil.json", lambda d: d.update(width=0)), "width and height must be positive"),
    Case("art variant", _edit("art/art-fx-sigil.json", lambda d: d.update(variants=["art-none"])),
         "art asset 'art-none' does not exist"),
    # terminal tables (03-terminal-ui.md 1 and 5)
    Case("tile char length", _table("tiles.json", "tiles", "water", lambda r: r.update(char="~~")),
         "map char '~~' must be one single-width character"),
    Case("tile char duplicate", _table("tiles.json", "tiles", "water", lambda r: r.update(char=".")),
         "map char '.' is also used by"),
    Case("tile glyph", _table("tiles.json", "tiles", "water", lambda r: r.update(glyph="nothing")),
         "glyph 'nothing' is not in glyphs.json"),
    Case("tile cover", _table("tiles.json", "tiles", "cover-3", lambda r: r.update(cover=4)), "cover 4 is outside 0-3"),
    Case("tile hazard", _table("tiles.json", "tiles", "hazard", lambda r: r["hazard"].update(damage_per_second=0)),
         "hazard damage must be positive"),
    Case("glyph length", _edit("glyphs.json", lambda d: d["glyphs"].update(two="ab")), "must be one character"),
    Case("glyph width", _edit("glyphs.json", lambda d: d["glyphs"].update(wide="界")), "is not one cell wide"),
    Case("keymap action", _edit("keymaps.json", lambda d: d["keymaps"][0]["bindings"].update(dance=["z"])),
         "binds unknown action 'dance'"),
    Case("keymap empty", _edit("keymaps.json", lambda d: d["keymaps"][0]["bindings"].update(help=[])),
         "action 'help' has no keys"),
    # bundles (02-architecture.md 15.3)
    Case("bundle kind", _edit("bundles/fx-world.json", lambda d: d["members"].update(gizmos=["x"])),
         "unknown member kind 'gizmos'"),
]


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_rule(case: Case, world: World) -> None:
    case.change(world)
    messages = world.messages()
    assert any(case.expect in m for m in messages), messages
