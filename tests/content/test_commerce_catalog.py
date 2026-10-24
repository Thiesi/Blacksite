"""Canonical numeric tables and the user-approved S12 -> S25 handoff."""

import json
from pathlib import Path
import re

from blacksite.content.loader import load_content
from blacksite.content.validate import validate


def test_every_catalog_item_loads_and_canonical_numbers_match(repo_root: Path) -> None:
    tree=load_content(repo_root/"src/blacksite/content")
    assert validate(tree)==[]
    design=(repo_root/"docs/design/00-game-design.md").read_text(encoding="utf-8")
    schedule=design.split("### 17.1 ",1)[1].split("### 17.2 ",1)[0]
    ids=set(re.findall(r"^\| `(\w+)`",schedule,re.MULTILINE))
    ids={i for i in ids if not i.startswith(("hymn_","dis_","apt_"))}
    assert ids <= tree.items.keys()
    assert len([v for v in tree.vendors.values() if not v.relay])==22
    assert {v.relay for v in tree.vendors.values() if v.relay}==set(tree.relays)
    assert tree.items["wpn_halvard_hv7"].base_price==340
    assert tree.items["wpn_halvard_hv7"].weapon.ammo=="ammo_5x"
    assert tree.items["wpn_kestrel_baton"].weight==.9
    assert tree.items["arm_wake_coverall"].armour.armour.chemical==4
    assert tree.items["con_sablier_trauma_kit"].consumable.use_seconds==2
    assert tree.items["item_rig_portable_ow_brick"].implant.rig_slots==3
    assert tree.items["drug_sablier_focus"].drug.duration==120
    from blacksite.server.items import availability
    for item in tree.items.values():
        if item.consumable and any(key in item.consumable.effects for key in
                                  ("end_chemical_dot", "recharge_cell", "dark_sight")):
            assert not availability(item), item.id


def test_s25_cannot_ship_a_zone_without_activating_its_deferred_commerce(repo_root: Path) -> None:
    tree=load_content(repo_root/"src/blacksite/content")
    # This test deliberately becomes a gate when S25's maps are added. Its
    # authoring members must then be activated and anchored in those maps.
    for vendor in tree.vendors.values():
        if vendor.zone in tree.zones:
            assert tree.active("vendors",vendor.id), f"S25 must activate {vendor.id} in {vendor.zone}"
            assert vendor.object_id, f"S25 must anchor {vendor.id}"
            assert any(o.id==vendor.object_id and o.params.get("vendor")==vendor.id
                       for o in tree.zones[vendor.zone].meta.objects)
    halls=("spire-mezzanine","vatside-clinics","tramyard-depots","core-precinct",
           "sink-terraces","oldworks-drop","chapel-nave","scour-landing")
    for zone in (*halls,"spire-atrium","tramyard-market","core-tram-hub"):
        if zone in tree.zones:
            assert any(o.kind=="bank" for o in tree.zones[zone].meta.objects), f"S25 must place the bank in {zone}"
            if zone in halls:
                assert any(o.params.get("vendor")=="sablier-clinic" for o in tree.zones[zone].meta.objects), f"S25 must place the clinic in {zone}"
    assert "tramyard-market" not in tree.zones or tree.active("vendors","kestrel-depot")


def test_catalog_authoring_is_reproducible(repo_root: Path) -> None:
    from scripts.build_catalog import tables, number
    text=(repo_root/"docs/design/00-game-design.md").read_text(encoding="utf-8").split("### 17.1 ",1)[1].split("### 17.2 ",1)[0]
    tree=load_content(repo_root/"src/blacksite/content")
    for _, row in tables(text):
        item=tree.items.get(row["ID"])
        if not item: continue
        if "Price" in row: assert item.base_price==int(number(row["Price"]))
        if "Wt" in row: assert item.weight==number(row["Wt"])
        if "Dmg" in row: assert item.weapon.damage==int(number(row["Dmg"]))
