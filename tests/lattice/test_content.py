"""World 03-lattice section 2 is the authored sector contract."""

from pathlib import Path
import re

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.server.lattice.sectors import Sectors, access


def test_world_2_sector_counts_layout_access_and_baseline_routes() -> None:
    root = Path(__file__).parents[2]
    tree = load_content(root / "src/blacksite/content")
    assert not validate(tree)
    table = (root / "docs/world/03-lattice.md").read_text(encoding="utf-8").split("## 2. Sectors")[1].split("Notes:")[0]
    expected, planned = {}, set()
    for line in table.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) > 4 and parts[2].isdigit():
            if "(planned, " in parts[1]:
                # Canon ahead of content (#90): a Stage 2 slice builds it and removes the marker.
                planned.add(parts[1].split(" (planned, ")[0])
                continue
            expected[parts[1]] = int(parts[2]), tuple(map(int, re.findall(r"\d+", parts[3])))
    sectors = Sectors(tree.sectors.values())
    assert len(sectors.records) == len(expected) == 11
    assert planned == {"Warmwater"}
    assert not planned & {sector.district for sector in sectors.records.values()}
    for sector in sectors.records.values():
        count, classes = expected[sector.district]
        assert len(sector.cells) == count
        assert tuple(sum(access(c) == kind for c in sector.cells) for kind in ("public", "gated", "hidden")) == classes
        assert sum(c.kind == "descent" for c in sector.cells) == 1
        assert len({c.pos for c in sector.cells}) == count
        for cell in sector.cells:
            assert 0 <= cell.pos[0] < 8 and 0 <= cell.pos[1] < 6
            for neighbour in cell.neighbours:
                assert cell.id in sectors.cells[sector.id][neighbour].neighbours
            if cell.kind == "core_entrance":
                if cell.core_placeholder:
                    assert cell.planned_core and cell.core_id is None
                else:
                    assert cell.core_id in tree.cores and tree.active("cores", cell.core_id)
                    assert cell.planned_core is None
    visited = set()
    todo = [("lat-core", sectors.entrance("lat-core"))]
    while todo:
        sid, cid = todo.pop()
        if (sid, cid) in visited:
            continue
        visited.add((sid, cid))
        cell = sectors.cells[sid][cid]
        todo.extend((sid, other) for other in cell.neighbours
                    if access(sectors.cells[sid][other]) == "public")
        if cell.uplink and not cell.uplink.requirement:
            todo.append((cell.uplink.sector, cell.uplink.cell))
    assert {sid for sid, _ in visited} == set(sectors.records)
    assert all((sid, sectors.entrance(sid)) in visited for sid in sectors.records)


def test_game_7_7_all_sixteen_relay_instances_and_service_cores() -> None:
    root = Path(__file__).parents[2]
    tree = load_content(root/"src/blacksite/content")
    design = (root/"docs/design/00-game-design.md").read_text(encoding="utf-8")
    schedule = design.split("### 7.7 Relay schedule", 1)[1].split("Cable fare", 1)[0]
    rows = re.findall(r"^\| `([^`]+)` /(.*)$", schedule, re.MULTILINE)
    relays = {slug for slug, rest in rows if "planned (#" not in rest}
    canon_only = {slug for slug, rest in rows if "planned (#" in rest}
    planned = [c.planned_core or c.core_id for sector in tree.sectors.values()
               for c in sector.cells if c.kind == "core_entrance"]
    assert len(relays) == 16
    assert canon_only == {"lamp", "boiler"}
    assert not {"lat-relay-"+slug for slug in canon_only} & (set(planned) | set(tree.cores))
    assert {"lat-relay-"+slug for slug in relays} <= set(planned)
    assert len(planned) == len(set(planned))
    assert {"lat-sump", "lat-drowned", "lat-shaft", "lat-landing"} <= set(planned)
    assert "lat-private-core" not in planned and "lat-relay-uplink" not in planned


def test_s25_complete_city_must_activate_all_district_core_entrances() -> None:
    root = Path(__file__).parents[2]
    tree = load_content(root/"src/blacksite/content")
    gazetteer = (root/"docs/world/01-gazetteer.md").read_text(encoding="utf-8")
    sections = re.split(r"^### `", gazetteer, flags=re.MULTILINE)[1:]
    zones = {section.split("`", 1)[0]: section for section in sections}
    canon_only = {z for z, section in zones.items() if "**Status:** planned (#" in section}
    ordinary = {z for z in zones if not z.startswith("blacksite-")} - canon_only
    assert len(ordinary) == 34
    assert len(canon_only) == 4 and not canon_only & tree.zones.keys()
    if ordinary <= tree.zones.keys():
        for sector in tree.sectors.values():
            for cell in sector.cells:
                if cell.kind == "core_entrance":
                    assert not cell.core_placeholder, f"S25 must activate {cell.planned_core}"
                    assert cell.core_id in tree.cores and tree.active("cores", cell.core_id)
