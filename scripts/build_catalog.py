"""Author S12's JSON from game design 17.1, never from guessed balances.

The catalog supplies descriptions. Classes whose behaviour belongs to a
later slice remain labelled in the live menus. Run from the repository root.
"""

import json
from pathlib import Path
import re
from typing import Any


def number(text: str) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(" ", "").replace("−", "-"))
    return float(match[0]) if match else 0


def money(text: str) -> int:
    return int(number(text))


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def tables(text: str) -> list[tuple[str, dict[str, str]]]:
    section, headers, rows = "", [], []
    for line in text.splitlines():
        if line.startswith("#### "):
            section = line[5:]
            headers = []
        elif line.startswith("| ID |"):
            headers = [x.strip() for x in line.strip("|").split("|")]
        elif line.startswith("| `") and headers:
            cells = [x.strip().replace("`", "") for x in line.strip("|").split("|")]
            rows.append((section, dict(zip(headers, cells))))
    return rows


def build(root: Path) -> None:
    design = (root / "docs/design/00-game-design.md").read_text(encoding="utf-8")
    schedule = design.split("### 17.1 ", 1)[1].split("### 17.2 ", 1)[0]
    records: list[dict[str, Any]] = []
    for section, row in tables(schedule):
        iid = row["ID"]
        if iid.startswith(("hymn_", "dis_", "apt_")):
            continue
        item: dict[str, Any] = {"id": iid, "name": row.get("Name", ""), "class": "misc",
            "tier": max(1, money(row.get("Tier", "1"))), "weight": number(row.get("Wt", row.get("Wt per unit", "0"))),
            "base_price": money(row.get("Price", row.get("Price per stack", row.get("Base price", "0")))),
            "description": row.get("Line", row.get("Effect", row.get("Notes", ""))).replace("—", ";")}
        if "Maker" in row:
            item["maker"] = row["Maker"]
        if iid.startswith("wpn_"):
            melee = "1.5 " in section
            damage = row["Dmg"]
            item.update({"class": "weapon", "tier": money(row.get("Tier", section[-1])) if not melee else money(row["Tier"])})
            item["weapon"] = {"damage": money(damage), "cooldown": 1.0 if melee else number(row["CD"]),
                "accuracy": 75 if melee else money(row["Acc"]), "damage_type": row["Type"],
                "melee": melee, "heavy": "Hardline only" in row["Line"]}
            if melee:
                item["weapon"]["stamina"] = money(row["Stamina"])
            else:
                item["weapon"].update({"range": money(row["Range"]),
                    "ammo": row["Ammo"] if row["Ammo"].startswith("ammo_") else None})
            dot = re.search(r"\(\+(\d+)/s, (\d+) s\)", damage)
            if dot:
                item["weapon"]["dot"] = {"per_second": int(dot[1]), "seconds": int(dot[2])}
            shock = re.search(r"\+(\d+) shock", damage)
            if shock:
                item["weapon"]["shock"] = int(shock[1])
            if "2-hit" in damage: item["weapon"]["hits"] = 2
            if "arc: 2 targets" in damage: item["weapon"]["targets"] = 2
            if "cone: 3 tiles" in damage: item["weapon"]["cone"] = 3
            if "Cantor only" in row["Line"]:
                item["requires_archetype"] = "cantor"
        elif iid.startswith("ammo_"):
            item.update({"class": "ammo", "stack_max": money(row["Stack"]), "ammo": {}})
            if iid == "ammo_cell":
                item["ammo"]["recharge_price"] = 10
        elif iid.startswith("arm_"):
            item.update({"class": "armour", "armour": {"slot": {"limbs": "legs"}.get(row["Layer"], row["Layer"]),
                "armour": {k: money(row["arm_" + v]) for k, v in (("kinetic", "k"), ("energy", "e"), ("chemical", "c"), ("dissonance", "d"))},
                "evasion": money(row["Evasion"]), "heavy": False}})
        elif iid.startswith("imp_") or iid.startswith("item_rig_"):
            portable = iid.startswith("item_rig_")
            item["class"] = "rig" if portable or iid.startswith("imp_rig_") else "resonance" if iid.startswith("imp_res_") else "implant"
            item["implant"] = {"slot": row.get("Slot", "rig"), "tolerance": money(row.get("Tol", "0")), "effects": {}}
            if "Slots" in row:
                item["implant"]["rig_slots"] = money(row["Slots"])
            if iid.startswith("imp_res_") or iid == "imp_rig_native":
                item["implant"]["requires"] = {"archetype": "cantor" if iid.startswith("imp_res_") else "ghost"}
        elif iid.startswith("drug_"):
            duration = number(row["Duration"]) * (60 if "min" in row["Duration"] else 1)
            window = number(row["Window"]) * (3600 if " h" in row["Window"] else 60)
            item.update({"class": "drug", "drug": {"effects": {}, "duration": duration, "crash": {}, "addiction_window": window}})
            item["description"] = row["Effect"] + ". Crash: " + row["Crash"] + "."
        elif iid.startswith("con_"):
            item.update({"class": "consumable",
                "consumable": {"effects": {}, "cooldown_class": row["Class"]}})
            if iid == "con_sablier_trauma_kit":
                item["consumable"]["use_seconds"] = 2
            if iid == "con_ow_cell_charger":
                item["consumable"]["uses"] = 3
        elif iid.startswith("drn_"):
            item.update({"class": "drone", "drone": {"health": money(row["Health"]),
                "evasion": money(row["Evasion"]), "control_range": money(row["Range"]),
                "sight": 6 if iid == "drn_ostrom_eye" else None, "speed": None,
                "tool": row["Weapon / tool"]}, "description": row["Weapon / tool"]})
            attack = re.search(r"(kinetic|chemical|energy|dissonance) (\d+)", row["Weapon / tool"])
            if attack:
                item["drone"]["attack"] = {"damage_type":attack[1], "damage":int(attack[2]),
                    "range":money(re.search(r"range (\d+)",row["Weapon / tool"])[1]) if "range " in row["Weapon / tool"] else None,
                    "melee":"melee" in row["Weapon / tool"], "accuracy":None,
                    "cooldown":number(row["Weapon / tool"].split("CD ")[-1])}
                dot = re.search(r"\(\+(\d+)/s (\d+) s\)",row["Weapon / tool"])
                if dot: item["drone"]["attack"]["dot"] = {"per_second":int(dot[1]),"seconds":int(dot[2])}
        elif iid.startswith("slv_"):
            item.update({"class": "salvage", "salvage": {"grade": row["Grade"]},
                         "name": row["Grade"].title() + " salvage",
                         "description": row["What it was"] + "; " + row["Fabrication use"]})
        elif iid.startswith("sch_"):
            output = re.search(r"(?:ammo|arm|wpn|con|drn|imp|prg)_[a-z0-9_]+", row["Makes"])[0]
            item.update({"class": "schematic", "schematic": {"output": output,
                "inputs": {grade: int(count) for grade, count in re.findall(r"(hull|optics|power|compute|intact) (\d+)", row["Salvage cost"])},
                "skill_min": money(row["Skill min"])}, "description": "Makes " + row["Makes"] + "."})
            item["base_price"] = money(re.search(r", ([\d ]+)$", row["Source"])[1]) if re.search(r", ([\d ]+)$", row["Source"]) else 0
        elif "Class" in row:
            item["class"] = row["Class"]
            if item["class"] == "consumable":
                item["consumable"] = {"effects": {}, "cooldown_class": "tool"}
            if iid.startswith("story_"):
                item["secured_default"] = True
        if iid == "arm_wake_coverall": item["secured_default"] = True
        records.append(item)

    effects = {
        "con_sablier_patch": {"health": 25}, "con_sablier_trauma_kit": {"health": 60},
        "con_kestrel_ration": {"stamina": 20, "remove_ring_dust_crash": 1},
        "con_sable_stim": {"stamina_full": 1, "shock": 10},
        "con_sablier_neutraliser": {"end_chemical_dot": 1},
        "con_ow_cell_charger": {"recharge_cell": 1},
        "con_ferry_flare_stick": {"dark_sight": 8, "seconds": 180},
        "con_halvard_breach_charge": {"breach_door": 1, "fuse_seconds": 5},
        "con_sablier_pickup": {"revive_seconds": 2}, "con_kestrel_beacon": {"convoy_mark": 1},
        "key_containment_charge": {"cut_power_radius": 3}, "key_silt_beacon": {"beacon_seconds": 3600},
        "imp_ostrom_lowlight": {"dark_sight": 3}, "imp_sablier_sub_dermal": {"arm_k": 3},
        "imp_sablier_adrenal": {"stamina_regen_multiplier": 1.5}, "imp_kestrel_loadframe": {"carry_kg": 15},
        "imp_sablier_secure_pocket": {"secured_slots": 1}, "imp_ostrom_rangefinder": {"range_penalty_multiplier": .5},
        "imp_halvard_reflex_arm": {"weapon_cooldown_multiplier": .9}, "imp_halvard_stabiliser": {"kinetic_accuracy": 8},
        "imp_sablier_shock_sink": {"shock_decay_multiplier": 2}, "imp_sablier_clotting": {"chemical_dot_multiplier": .5},
        "imp_sablier_sprint_legs": {"sprint_ms": 80, "stamina_cost_multiplier": .8}, "imp_ow_ghost_step": {"stealth_sight_reduction": .6},
        "imp_ostrom_target_lock": {"target_through_cover": 1}, "imp_sablier_second_heart": {"health": 40},
        "imp_halvard_dermal_plate": {"arm_k": 8, "arm_e": 4, "evasion": -3}, "imp_sablier_secure_vault": {"secured_slots": 2},
        "imp_sablier_detox_gland": {"crash_duration_multiplier": .5, "addiction_window_multiplier": .5},
        "imp_ow_drone_uplink": {"drone_slots": 1}, "imp_halvard_heavy_mount": {"heavy_cooldown_multiplier": .85},
        "imp_rig_native": {"jack_anywhere": 1}, "imp_rig_ow_jury": {"jack_anywhere": 1, "trace_multiplier": 1.1},
        "imp_rig_sablier_clinical": {"jack_anywhere": 1, "integrity": 10}, "imp_rig_ow_deepwater": {"jack_anywhere": 1, "cell_move_multiplier": .8},
        "imp_res_first_ear": {"hymn_tier": 1, "listening": 10}, "imp_res_throat": {"dissonance_tier": 1},
        "imp_res_second_ear": {"hidden_cell_radius": 2, "listening": 15}, "imp_res_chord": {"hymn_tier": 2, "hymn_radius": 8, "dissonance_tier": 2},
        "imp_res_tremor": {"dissonance_damage_multiplier": 1.2}, "imp_res_ninefold_lattice": {"hymn_tier": 3, "dissonance_tier": 3},
        "imp_res_tenant_ear": {"surge_inspect": 1}, "imp_res_silence": {"arm_d": 15, "dissonance_knockdown_immune": 1},
    }
    drugs = {
        "drug_sablier_focus": ({"accuracy": 10}, {"accuracy": -10}),
        "drug_sablier_calm": ({"shock_decay_multiplier": 2}, {"shock_decay_multiplier": .5}),
        "drug_sable_redline": ({"weapon_cooldown_multiplier": .8}, {"weapon_cooldown_multiplier": 1.2}),
        "drug_sable_glass": ({"evasion": 10, "sight": 2}, {"evasion": -10}),
        "drug_sable_brick": ({"arm_k": 8, "stamina_cost_multiplier": 1.2}, {"arm_k": -8}),
        "drug_sable_deepwater": ({"cell_move_multiplier": .7, "trace_multiplier": 1.2}, {"cell_move_multiplier": 1.3}),
        "drug_ow_static": ({"integrity": 20}, {"integrity": -20}),
        "drug_chapel_hush": ({"listening": 20, "cantor_cast_multiplier": .75}, {"listening": -20}),
        "drug_ferry_ringdust": ({"stamina_regen_multiplier": 3, "health_per_second": -1}, {"stamina_regen_multiplier": .3}),
        "drug_sable_lullaby": ({"health_over_time": 30, "heal_seconds": 10, "move_ms": 400}, {"health": -10}),
        "drug_sable_chrome": ({"tolerance": 1}, {"shock": 40}),
    }
    for item in records:
        for block in ("implant", "consumable"):
            if block in item:
                item[block]["effects"] = effects.get(item["id"], {})
        if item["class"] == "drug":
            item["drug"]["effects"], item["drug"]["crash"] = drugs[item["id"]]
        if not item["name"]:
            output = item.get("schematic", {}).get("output")
            item["name"] = "Plan: " + next((r["name"] for r in records if r["id"] == output), "Hunter-killer")
    write(root / "src/blacksite/content/items.json", {"schema": 1, "items": records})
    programs_path = root / "src/blacksite/content/programs.json"
    programs = json.loads(programs_path.read_text(encoding="utf-8"))
    if not any(p["id"] == "prg_hunter_killer" for p in programs["programs"]):
        programs["programs"].append({"id": "prg_hunter_killer", "name": "Hunter-killer", "class": "attack",
            "tier": 4, "slots": 2, "cast_seconds": 2, "cooldown_seconds": 15,
            "effect": {"kind": "damage", "amount": 80, "params": {"hunter_only": True}},
            "price": 4200, "target_class": "ice", "source": "core data"})
    write(programs_path, programs)
    build_vendors(root, design, records)


def build_vendors(root: Path, design: str, records: list[dict[str, Any]]) -> None:
    rows = []
    section = design.split("#### 12. Vendor inventories", 1)[1].split("#### 13.", 1)[0]
    for line in section.splitlines():
        if line.startswith("| ") and not line.startswith("| Vendor"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == 4:
                rows.append(cells)
    anchors = [
        ("kestrel-depot", "tramyard-market", "kestrel", None),
        ("kestrel-armoury", "tramyard-depots", "kestrel", None),
        ("halvard-public", "spire-atrium", "halvard", None),
        ("halvard-security", "spire-mezzanine", "halvard", None),
        ("ostrom-showroom", "core-plaza", "halvard", "plaza-general-vendor"),
        ("ostrom-contract", "spire-mezzanine", "halvard", None),
        ("sablier-clinic", "vatside-clinics", "sablier", "sablier-main-clinic"),
        ("wake-outfitter", "vatside-wake-hall", "sablier", "wake-outfitter"),
        ("warden-quartermaster", "core-precinct", "wardens", "warden-quartermaster"),
        ("sink-market", "sink-rim", "sable", None),
        ("sable-back-room", "sink-terraces", "sable", None),
        ("black-clinic", "sink-floor", "sable", None),
        ("oldworks-bench", "oldworks-main", "unmoored", None),
        ("oldworks-deep", "oldworks-drop", "unmoored", None),
        ("chapel-almoner", "chapel-nave", "choir", None),
        ("chapel-foundry", "chapel-nave", "choir", None),
        ("landing-trade", "scour-landing", "ferrymen", None),
        ("ferrys-own", "scour-landing", "ferrymen", None),
        ("vesper", "sodium-tin-halo", "sable", "vesper"),
    ]
    assert len(rows) == len(anchors), (len(rows), len(anchors))
    templates = {r["id"]: r for r in records}
    programs = [(r["ID"], money(r["Tier"])) for _, r in tables(design.split("### 17.2 ", 1)[1].split("### 17.3 ", 1)[0])]
    vendors, deferred = [], []
    for (name, _, stock_text, tier), (vid, zone, faction, anchor) in zip(rows, anchors):
        faction = "red-sable" if faction == "sable" else faction
        ids = re.findall(r"`([^`]+)`", stock_text)
        if vid == "sablier-clinic":
            ids += [i for i, t in templates.items() if t["class"] == "implant" and t.get("maker") == "Sablier"]
        if vid == "wake-outfitter":
            starts = json.loads((root / "src/blacksite/content/starts.json").read_text(encoding="utf-8"))
            ids += [i for start in starts["starts"] for i in start["items"]]
        if vid == "sink-market":
            ids += [i for i, t in templates.items() if t["class"] == "drug" and t.get("maker") == "Sable Works"]
        if vid == "black-clinic":
            ids += [i for i, t in templates.items() if t["class"] == "implant"]
        if vid in ("oldworks-bench", "oldworks-deep"):
            ids += [i for i, level in programs if level in ((1, 2) if vid == "oldworks-bench" else (3,))]
        if vid == "chapel-foundry":
            ids += [i for i, t in templates.items() if t["class"] == "resonance" and t["tier"] >= 2]
        if vid in ("landing-trade", "ferrys-own"):
            ids += [i for i, t in templates.items() if t["class"] == "schematic" and (
                i in ("sch_scrap_bolts", "sch_scrap_plate", "sch_slugthrower", "sch_ring_wrench", "sch_flare_stick") if vid == "landing-trade"
                else i in ("sch_meteor_cannon", "sch_ringfall_rifle", "sch_lifter"))]
        if vid == "warden-quartermaster":
            ids = []
            from copy import deepcopy
            for original in ("arm_halvard_guard_suit", "wpn_halvard_hv9", "wpn_halvard_shock_baton"):
                clone = deepcopy(templates[original])
                clone["id"] = original.replace("halvard", "civic")
                clone["name"] = "Civic Pattern " + {"arm_halvard_guard_suit": "guard suit", "wpn_halvard_hv9": "battle rifle", "wpn_halvard_shock_baton": "shock baton"}[original]
                clone["maker"] = "Civic Pattern"
                clone["description"] = "Warden issue. The finish is blue."
                records.append(clone)
                templates[clone["id"]] = clone
                ids.append(clone["id"])
        entries = []
        for iid in dict.fromkeys(ids):
            entry: dict[str, Any] = {"item": iid}
            # Semicolon suffixes carry the catalog's higher stock gate.
            suffix = stock_text.split(";", 1)[1] if ";" in stock_text else ""
            gate = re.search(r"standing \+(\d+)", suffix)
            if gate and f"`{iid}`" in suffix:
                entry["standing"] = int(gate[1])
            if vid == "kestrel-armoury" and iid == "wpn_kestrel_gate_gun": entry["standing"] = 60
            if vid == "chapel-almoner": entry.update(standing=20, archetype="cantor")
            if vid == "chapel-foundry" and templates.get(iid, {}).get("tier") == 3: entry["standing"] = 60
            if vid == "ostrom-contract" and iid in ("wpn_ostrom_scalpel", "wpn_ostrom_sunlance", "wpn_ostrom_pulse_carbine"):
                entry.update(standing=50, factions=["halvard", "sablier"])
            gates = {"sch_meteor_cannon":30, "sch_ringfall_rifle":60, "sch_lifter":40, "sch_etcher":50, "sch_railpistol":60}
            if iid in gates: entry["standing"] = gates[iid]
            entries.append(entry)
        vendor: dict[str, Any] = {"id": vid, "name": name, "tier": tier, "stock": entries, "faction": faction, "zone": zone}
        if anchor: vendor["object_id"] = anchor
        else: deferred.append(vid)
        if vid == "black-clinic": vendor["price_multiplier"] = .6
        if vid == "landing-trade": vendor["salvage_multiplier"] = 1.2
        if vid == "vesper": vendor["daily_rotation"] = True
        vendors.append(vendor)
    write(root / "src/blacksite/content/items.json", {"schema": 1, "items": records})
    write(root / "src/blacksite/content/vendors.json", {"schema": 1, "vendors": vendors})
    write(root / "src/blacksite/content/bundles/s25-commerce.json", {"schema": 1, "id": "s25-commerce", "status": "authoring", "depends": [], "members": {"vendors": deferred}})
    for vendor in vendors:
        if not vendor.get("object_id"): continue
        path = root / "src/blacksite/content/zones" / (vendor["zone"] + ".json")
        zone = json.loads(path.read_text(encoding="utf-8"))
        obj = next((o for o in zone["objects"] if o["id"] == vendor["object_id"]), None)
        if obj is None:
            assert vendor["id"] == "wake-outfitter"
            obj = {"id": vendor["object_id"], "tile": [34,15], "kind": "vendor", "essential":True, "params":{}}
            zone["objects"].append(obj)
        if vendor["id"] == "wake-outfitter": obj["tile"] = [34,15]
        obj["params"].update(vendor=vendor["id"], name=vendor["name"])
        write(path, zone)
    for zid, tile in (("core-tram-hub",[12,7]),("core-precinct",[10,6]),("vatside-clinics",[12,10])):
        path = root / "src/blacksite/content/zones" / (zid + ".json")
        zone = json.loads(path.read_text(encoding="utf-8"))
        if not any(o["kind"] == "bank" for o in zone["objects"]):
            zone["objects"].append({"id":"kestrel-bank", "tile":tile, "kind":"bank", "essential":True, "params":{"name":"Kestrel bank"}})
            write(path, zone)
    path = root / "src/blacksite/content/zones/core-precinct.json"
    zone = json.loads(path.read_text(encoding="utf-8"))
    if not any(o.get("params",{}).get("vendor") == "sablier-clinic" for o in zone["objects"]):
        zone["objects"].append({"id":"precinct-clinic", "tile":[15,6], "kind":"vendor", "essential":True,
            "params":{"vendor":"sablier-clinic", "name":"Sablier Clinic"}})
        write(path, zone)


if __name__ == "__main__":
    build(Path(__file__).resolve().parent.parent)
