"""Explicit S18 acceptance geography; never loaded by a production world.

Three room anchors temporarily occupy spare Wake floors. S25 owns the
24-door Terraces pool and its lobby and sector allocation.
"""

import json
from pathlib import Path


def build_fixture(shipped: Path, local: Path) -> None:
    directory = local/"zones"
    directory.mkdir(parents=True, exist_ok=True)
    zone = json.loads((shipped/"zones/vatside-wake-hall.json").read_text(encoding="utf-8"))
    sector = json.loads((shipped/"sectors/lat-terraces.json").read_text(encoding="utf-8"))
    # This fixture owns three Wake rooms, not the commissioned city pool.
    # Remove only real housing anchors in its explicit local overlay, so
    # they cannot consume fixture cells or change a three-room scenario.
    blocks_path = shipped/'zones/terraces-blocks.json'
    if blocks_path.exists():
        blocks = json.loads(blocks_path.read_text(encoding='utf-8'))
        if any(obj.get('housing') for obj in blocks['objects']):
            blocks['objects'] = [obj for obj in blocks['objects'] if not obj.get('housing')]
            (directory/blocks_path.name).write_text(json.dumps(blocks, indent=2)+'\n', encoding='utf-8', newline='\n')
            (directory/'terraces-blocks.map').write_bytes((shipped/'zones/terraces-blocks.map').read_bytes())
    cells = [c["id"] for c in sector["cells"] if not c.get("core_id") and not c.get("core_placeholder")
             and c['id'] != sector['entry'] and not c.get('uplink')
             and c.get("access", c['kind']) == "public"]
    for index, (class_id, origin, door, doorstep, vestibule) in enumerate((
        ("apt_terrace_cell", [2, 13], [4, 12], [4, 11], [2, 0]),
        ("apt_terrace_flat", [12, 13], [14, 12], [14, 11], [2, 0]),
        ("apt_terrace_corner", [23, 2], [25, 6], [25, 7], [2, 3]),
    )):
        zone["objects"].append({"id": f"fixture-home-{index+1}", "tile": door,
            "kind": "apartment_door", "params": {"name": f"FIXTURE home {index+1}", "open": False},
            "housing": {"class_id": class_id, "room": "apartment", "origin": origin,
                "sector": "lat-terraces", "cell": cells[index], "doorstep": doorstep, "vestibule": vestibule}})
    zone["objects"].extend([
        {"id": "fixture-letting", "tile": [6, 8], "kind": "terminal", "params": {"letting": True, "name": "FIXTURE letting"}},
        {"id": "fixture-bank", "tile": [9, 8], "kind": "bank", "params": {"name": "FIXTURE Kestrel impound"}},
    ])
    (directory/"vatside-wake-hall.json").write_text(json.dumps(zone, indent=2)+"\n", encoding="utf-8")
    (directory/"vatside-wake-hall.map").write_bytes((shipped/"zones/vatside-wake-hall.map").read_bytes())
