"""S08 gazetteer contracts, connectivity and protected service geometry."""

from dataclasses import replace
from pathlib import Path
from time import perf_counter

from blacksite.content.loader import load_content
from blacksite.content.validate import validate, exit_warnings

ROOT = Path(__file__).resolve().parents[2]
SIZES = {"core-plaza":(90,40),"core-tram-hub":(80,30),"core-precinct":(50,24),
         "vatside-wake-hall":(40,20),"vatside-clinics":(80,34),"vatside-vat-row":(90,36),
         "sodium-row":(100,30),"sodium-tin-halo":(44,22),"terraces-blocks":(120,40),"terraces-lobby":(40,24)}


def test_ten_hub_zones_validate():
    tree = load_content(ROOT/"src/blacksite/content")
    assert set(tree.zones) == SIZES.keys()
    start = perf_counter()
    assert validate(tree) == []
    assert perf_counter()-start < 1
    assert tree.bundles["m1-zone-preview"].status == "active"


def test_sizes_match_gazetteer():
    tree = load_content(ROOT/"src/blacksite/content")
    assert {z.id:(z.width,z.height) for z in tree.zones.values()} == SIZES


def test_exits_bidirectional():
    tree = load_content(ROOT/"src/blacksite/content")
    assert exit_warnings(tree) == []
    for zone in tree.zones.values():
        for ex in zone.meta.exits:
            target = tree.zones[ex.target_zone]
            assert any(back.target_zone == zone.id for back in target.meta.exits)
            assert tree.tiles[target.tile_at(ex.target_tile)].passable
    plaza = tree.zones["core-plaza"]
    tree.zones["core-plaza"] = replace(plaza,meta=replace(plaza.meta,exits=()))
    assert exit_warnings(tree)


def test_every_gazetteer_object_present_by_id():
    tree = load_content(ROOT/"src/blacksite/content")
    required = {
        "vatside-wake-hall":{"vantongeren-desk","recruiter-cards","wake-terminal","wake-door","corridor-door",*[f"decant-vat-{i}" for i in range(1,5)]},
        "core-plaza":{"kestrel-bank","plaza-general-vendor","warden-recruiter","civic-notice-board","civic-descent",*[f"plaza-public-{i}" for i in range(1,5)]},
        "core-tram-hub":{"kestrel-ticket-office","kestrel-recruiter","hub-noodle-counter","hub-public-west","hub-public-east","platform-vatside-clinics","platform-terraces-blocks"},
        "core-precinct":{"warden-quartermaster","warden-contract-handler","marshal-office","bounty-desk","holding-cell-west","holding-cell-east","precinct-member-terminal","precinct-vault-hardware","warden-faction-vat"},
        "vatside-vat-row":{"black-clinic","vat-technicians","sablier-faction-vat","vatline-hardware"},
        "sodium-row":{"row-drug-dealer","row-ticket-tout","row-stage","row-card-table",*[f"row-public-{i}" for i in range(1,4)],*[f"row-bar-{i}" for i in range(1,6)]},
        "sodium-tin-halo":{"vesper","halo-bar","halo-back-room","ferrymen-liaison","halo-contract-board","halo-market-board"},
        "terraces-blocks":{"letting-office","corner-grocer","warden-outpost","block-relay","block-relay-hardware",*[f"blocks-public-{i}" for i in range(1,4)],*[f"block-door-{i}" for i in range(1,6)]},
        "terraces-lobby":{"lobby-concierge","lobby-lift","lobby-public-terminal","lobby-mailboxes",*[f"apartment-door-{i}" for i in range(1,6)]},
        "vatside-clinics":{"sablier-main-clinic","sablier-descent","sablier-recruiter","clinic-pharmacy","clinic-public-west","clinic-public-east","sablier-member-terminal","cold-chain-relay","cold-chain-hardware","cold-chain-replacement-socket","cold-chain-loan-terminal"},
    }
    for zid, ids in required.items():
        assert ids <= {obj.id for obj in tree.zones[zid].meta.objects}
    clinic = tree.zones["vatside-clinics"].meta
    objects = {obj.id:obj for obj in clinic.objects}
    assert not any(p.contains(objects["cold-chain-relay"].tile) for p in clinic.pockets)
    for oid in ("sablier-main-clinic","sablier-descent","sablier-recruiter","clinic-pharmacy","cold-chain-loan-terminal"):
        assert any(p.contains(objects[oid].tile) for p in clinic.pockets)


def test_future_boundaries_have_no_dangling_target():
    tree = load_content(ROOT/"src/blacksite/content")
    boundaries = [obj for zone in tree.zones.values() for obj in zone.meta.objects if "unavailable_target" in obj.params]
    assert len(boundaries) == 7
    assert all(obj.params["unavailable_target"] not in tree.zones for obj in boundaries)
