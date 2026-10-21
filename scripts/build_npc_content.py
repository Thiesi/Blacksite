"""Author the S11 hub population from game design 5.5/7.2 and gazetteer.

Run from the repository root. Runtime loads the generated JSON only.
"""

import json
from pathlib import Path

ROOT = Path("src/blacksite/content")


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8", newline="\n")


def build() -> None:
    ids = ["halvard", "sablier", "kestrel", "wardens", "choir", "sable", "unmoored", "ferrymen"]
    names = ["Halvard-Ostrom Dynamics", "Sablier Biomedical", "Kestrel Logistics", "Karst Civic Authority", "The Ninefold Choir", "Red Sable", "The Unmoored", "The Ferrymen"]
    document = Path("docs/design/00-game-design.md").read_text(encoding="utf-8")
    table = document.split("### 7.2 Relations matrix", 1)[1].split("### 7.3", 1)[0]
    matrix = [[cell.strip() for cell in line.split("|")[2:-1]]
              for line in table.splitlines() if any(line.startswith("| "+fid.title()+" |") for fid in ids)]
    write(ROOT/"factions.json", {"schema": 1, "asymmetries": [], "factions": [
        {"id": fid, "name": names[i], "short": fid.title(), "colour": "faction_"+fid,
         "relations": {other: matrix[i][j] for j, other in enumerate(ids) if j != i}}
        for i, fid in enumerate(ids)]})
    npcs = json.loads((ROOT/"npcs.json").read_text(encoding="utf-8"))["npcs"]
    npcs = [n for n in npcs if n["id"] == "npc-wake-drone"]

    def npc(key: str, name: str, faction: str | None, behaviour: str,
            armed: bool = False, **params: object) -> str:
        nid = "npc-"+key
        row: dict[str, object] = {"id": nid, "name": name, "faction": faction, "grade": 1,
            "attributes": {"frame": 20, "nerve": 20, "cortex": 10, "resonance": 5, "vitals": 20},
            "behaviours": [{"kind": behaviour, "params": params}], "xp": 0}
        if armed:
            row.update(weapon="wpn_kestrel_sidearm", armour="arm_wake_coverall")
            row.update(xp=20, loot=[{"item":"ammo_9x","chance":.5,"count":10}])
        if behaviour == "wander":
            row["loot"] = [{"item": "con_kestrel_ration", "chance": 1, "count": 1}]
        npcs.append(row)
        return nid

    npc("warden-response", "Warden responder", "wardens", "warden", True)
    npcs[-1].update(xp=0, loot=[])  # Summoned warnings are not a reward source.
    npc("warden-patrol", "Warden patrol", "wardens", "patrol", True, waypoints=[[23,3],[40,3],[40,4],[23,4]])
    npc("civilian", "Plaza resident", None, "wander")
    npc("courier", "Courier drone", "kestrel", "patrol", waypoints=[[8,4],[22,4]], bounce=True)
    npc("kestrel-staff", "Kestrel clerk", "kestrel", "talker", anchor=True)
    npc("commuter", "Commuter", None, "wander")
    npc("sablier-orderly", "Sablier orderly", "sablier", "talker", anchor=True)
    npc("sablier-guard", "Sablier security", "sablier", "guard", True)
    npc("patient", "Clinic patient", None, "wander")
    npc("sable-enforcer", "Sable enforcer", "sable", "guard", True)
    npc("sodium-regular", "Sodium regular", "sable", "wander")
    npc("halo-bouncer", "Halo bouncer", "sable", "guard", True)
    npc("halo-regular", "Halo regular", "sable", "talker", anchor=True)
    npc("resident", "Block resident", None, "wander")
    npc("plainclothes-warden", "Plainclothes Warden", "wardens", "talker", anchor=True)
    npc("maintenance-drone", "Maintenance drone", None, "guard", hostile_all=True)
    npcs[-1].update(health=40, xp=20, attack={"damage":6,"cooldown":2,"range":5,"accuracy":60,"damage_type":"kinetic"})
    population = {
        "core-plaza": [("warden-patrol",2,(23,3,18,2)),("civilian",5,(5,3,18,6)),("courier",1,(8,4,14,1))],
        "core-tram-hub": [("warden-response",2,(8,3,8,2)),("kestrel-staff",2,(20,3,6,2)),("commuter",5,(28,3,15,2))],
        "core-precinct": [("warden-response",6,(5,3,20,2))],
        "vatside-wake-hall": [("sablier-orderly",2,(8,3,6,2))],
        "vatside-clinics": [("sablier-guard",2,(50,3,4,1)),("patient",4,(28,3,9,2)),("warden-patrol",1,(40,3,1,1))],
        "vatside-vat-row": [("sablier-guard",3,(10,3,15,1)),("sablier-orderly",2,(26,3,6,1))],
        "sodium-row": [("sable-enforcer",2,(8,4,5,1)),("sodium-regular",5,(15,3,15,3)),("plainclothes-warden",1,(90,3,3,1))],
        "sodium-tin-halo": [("halo-bouncer",1,(4,3,1,1)),("halo-regular",4,(8,3,12,2))],
        "terraces-blocks": [("resident",7,(5,3,22,2))],
        "terraces-lobby": [("resident",3,(5,3,12,2))],
    }
    for zid, groups in population.items():
        path = ROOT/"zones"/(zid+".json")
        zone = json.loads(path.read_text(encoding="utf-8"))
        zone["spawners"] = [{"id": key, "npc": "npc-"+key, "count": count,
            "respawn_seconds": 60, "condition": "always",
            "region": dict(zip(("x","y","w","h"), rect))} for key,count,rect in groups]
        if zid == "vatside-wake-hall":
            zone["spawners"].append({"id": "wake-training", "npc": "npc-wake-drone", "count": 1,
                "respawn_seconds": 0, "condition": "per_player", "tile": [23,14]})
        for obj in zone["objects"]:
            vendor = obj.get("params", {}).get("vendor")
            if vendor:
                key = "vendor-"+zid+"-"+obj["id"]
                npc(key, obj["params"]["name"], None, "vendor", anchor=True)
                npcs[-1]["vendor"] = vendor
                x,y = obj["tile"]
                zone["spawners"].append({"id": key, "npc": "npc-"+key, "count": 1,
                    "respawn_seconds": 60, "condition": "always", "region": {"x":x-1,"y":y-1,"w":3,"h":3}})
        write(path, zone)
    write(ROOT/"npcs.json", {"schema": 1, "npcs": npcs})
    palette = json.loads((ROOT/"palette.json").read_text(encoding="utf-8"))
    for fid in ids:
        palette["roles"]["npc_"+fid] = palette["roles"]["faction_"+fid]
    write(ROOT/"palette.json", palette)


if __name__ == "__main__":
    build()
