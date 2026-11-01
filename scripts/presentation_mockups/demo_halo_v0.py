"""The demo's 28x12 Tin Halo through V0's lit renderer (#143 section 9).

Run from the repository root of this branch (demo/halo-v0, never merged):

    python scripts/presentation_mockups/demo_halo_v0.py DEMO_ROOT OUT_DIR

DEMO_ROOT is a checkout of demo/sodium-row-evening; its frozen Halo map
is the geometry. This writes a candidate folder (zone, map and a look
with lights and set pieces authored for the 28x12 room), then captures it
with V0's harness in the three V0 tiers, so the owner can judge whether
the smaller room fixes the "bowling alley".
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/"docs/design/proposals/68-presentation/candidates/sodium-row"
CAND = ROOT/"docs/design/proposals/68-presentation/candidates/demo-halo"

# The demo room: interior x 8-35, y 5-16; door (7,10) on the long axis to
# Vesper (34,10); bar along the north wall turning at her end; booths in the
# south bays between partitions at x 12, 17, 22, 27; back room behind (30,4).
OBJECTS = {"vesper": [34, 10], "halo-bar": [24, 8], "halo-cabinet-hardware": [25, 8],
           "halo-back-room": [30, 4], "ferrymen-liaison": [31, 14],
           "halo-contract-board": [9, 6], "halo-market-board": [9, 14]}


def lamp(x, y, z, glow):
    return {"kind": "lamp", "rect": [x - 0.2, y - 0.2, 0.4, 0.4], "z": [z, z + 0.2], "colour": "#3a2a1a", "glow": glow}


def light(x, y, z, colour, reach, power):
    return {"at": [x, y], "z": z, "colour": colour, "reach": reach, "power": power}


def look(base: dict) -> dict:
    scene = {k: v for k, v in base["scene"].items() if k not in ("lights", "pieces")}
    pieces = [
        {"kind": "cans", "rect": [8.4, 8.4, 3.2, 3.2], "z": [2.45, 2.9], "colour": "#8a8478"},
        {"kind": "ring", "rect": [17.0, 6.0, 10.0, 10.0], "z": [3.0, 3.12], "colour": "#3a3633", "glow": "#ffd2a0"},
        {"kind": "pipe", "rect": [8.0, 7.4, 28.0, 0.25], "z": [2.85, 3.05], "colour": "#34343a"},
        {"kind": "pipe", "rect": [8.0, 14.6, 28.0, 0.2], "z": [2.9, 3.05], "colour": "#2e2e34"},
        {"kind": "counter", "rect": [14.0, 7.0, 19.0, 1.0], "z": [0.0, 1.05], "colour": "#3b2a20"},
        {"kind": "counter", "rect": [33.0, 7.0, 1.0, 3.0], "z": [0.0, 1.05], "colour": "#3b2a20"},
        {"kind": "screens", "rect": [33.1, 8.6, 0.3, 1.3], "z": [1.05, 1.35], "colour": "#101418", "glow": "#3fd8ff"},
        {"kind": "box", "rect": [20.15, 7.15, 0.7, 0.7], "z": [1.05, 1.55], "colour": "#24202a"},
        {"kind": "shelf", "rect": [14.0, 4.0, 15.0, 1.0], "z": [0.9, 2.4], "colour": "#22180f", "glow": "#6a4424"},
        {"kind": "sign", "rect": [17.0, 4.0, 8.0, 1.0], "z": [2.5, 2.9], "colour": "#2a1408", "glow": "#ffaf00",
         "text": "TIN HALO", "role": "sign_amber"},
        {"kind": "doorway", "rect": [29.6, 4.0, 1.8, 1.0], "z": [0.0, 2.1], "colour": "#2a0c0a", "glow": "#e0402e"},
        {"kind": "board", "rect": [8.0, 4.0, 3.0, 1.0], "z": [0.9, 1.8], "colour": "#0a1418", "glow": "#00d7ff"},
        {"kind": "board", "rect": [8.0, 17.0, 3.0, 1.0], "z": [0.9, 1.8], "colour": "#141208", "glow": "#ffd700"},
        {"kind": "table", "rect": [30.1, 13.1, 1.8, 0.8], "z": [0.7, 0.8], "colour": "#5a4232"},
        lamp(31.0, 13.5, 1.8, "#ffb45a"),
        {"kind": "table", "rect": [24.1, 12.1, 2.8, 1.8], "z": [0.7, 0.8], "colour": "#5a4232"},
        lamp(25.5, 13.0, 1.95, "#ffb060"),
    ]
    pieces += [lamp(x, 7.5, 2.3, "#ff8c3a") for x in (16, 20, 24, 28)]
    for left in (13, 18, 23):  # booths between the tile partitions
        pieces += [{"kind": "bench", "rect": [left, 15.0, 1.0, 2.0], "z": [0.0, 1.25], "colour": "#4a2426"},
                   {"kind": "bench", "rect": [left + 3, 15.0, 1.0, 2.0], "z": [0.0, 1.25], "colour": "#4a2426"},
                   {"kind": "table", "rect": [left + 1.05, 15.05, 1.9, 1.9], "z": [0.7, 0.8], "colour": "#5a4232"},
                   lamp(left + 2.0, 16.0, 1.75, "#ffb45a")]
    lights = [light(10.0, 10.0, 2.6, "#ffd9a0", 6.0, 0.9), light(22.0, 11.0, 3.0, "#ffcf9a", 16.0, 0.7),
              light(33.5, 9.3, 1.3, "#3fd8ff", 2.8, 0.8), light(30.5, 4.4, 1.3, "#e0402e", 4.0, 1.1),
              light(9.5, 4.8, 1.4, "#00d7ff", 2.5, 0.5), light(9.5, 16.4, 1.4, "#ffd700", 2.5, 0.4),
              light(31.0, 13.5, 1.9, "#ffb45a", 3.0, 0.7), light(21.0, 4.6, 2.7, "#ffaf00", 3.5, 0.5)]
    lights += [light(x, 7.5, 2.4, "#ff8c3a", 4.5, 0.8) for x in (16, 20, 24, 28)]
    lights += [light(x, 16.0, 1.85, "#ffb45a", 3.0, 0.9) for x in (15, 20, 25)]
    scene.update(pieces=pieces, lights=lights)
    places = [
        {"name": "Under the halo", "rect": [8, 8, 4, 5], "at": [9, 11],
         "text": "You stand under a halo of tin cans a drunk welded up forty years ago. Nobody has taken it down."},
        {"name": "The bar", "rect": [14, 8, 20, 2], "at": [22, 8],
         "text": "The counter runs to the end of the room. Vesper sits where it turns, facing the door."},
        {"name": "The booths", "rect": [13, 15, 14, 2], "at": [14, 15],
         "text": "High-backed booths under their own lamps. The regulars know things. Some of the things are true."},
        {"name": "The back room", "rect": [26, 2, 8, 2], "at": [30, 3],
         "text": "A red light over a door you were not asked through."},
        {"name": "The quiet end", "rect": [29, 12, 6, 4], "at": [31, 13],
         "text": "A table at the quiet end of the bar. The Ferrymen liaison is sometimes in."},
        {"name": "The Tin Halo", "rect": [8, 5, 28, 12], "at": [22, 11],
         "text": "The old advertising ring lights the ceiling now. Everyone who wants work comes here."},
    ]
    return {**base, "scene": scene, "places": places}


def candidate(demo: Path) -> None:
    if CAND.exists():
        shutil.rmtree(CAND)
    shutil.copytree(BASE, CAND)
    content = demo/"src/blacksite/content/zones"
    shutil.copy(content/"sodium-tin-halo.map", CAND/"zones/sodium-tin-halo.map")
    zone = json.loads((CAND/"zones/sodium-tin-halo.json").read_text(encoding="utf-8"))
    zone["sight_radius"] = 28
    zone["spawn"] = [9, 11]
    zone["exits"][0]["tile"] = [7, 10]
    for obj in zone["objects"]:
        obj["tile"] = OBJECTS[obj["id"]]
    zone["spawners"] = [
        {"id": "halo-bouncer", "npc": "npc-halo-bouncer", "count": 1, "respawn_seconds": 60,
         "condition": "always", "region": {"x": 9, "y": 9, "w": 1, "h": 1}},
        {"id": "halo-regular", "npc": "npc-halo-regular", "count": 4, "respawn_seconds": 60,
         "condition": "always", "region": {"x": 12, "y": 10, "w": 18, "h": 3}},
        {"id": "vendor-sodium-tin-halo-vesper", "npc": "npc-vendor-sodium-tin-halo-vesper", "count": 1,
         "respawn_seconds": 60, "condition": "always", "region": {"x": 33, "y": 10, "w": 1, "h": 1}},
    ]
    (CAND/"zones/sodium-tin-halo.json").write_bytes((json.dumps(zone, indent=2)+"\n").encode("utf-8"))
    row = json.loads((CAND/"zones/sodium-row.json").read_text(encoding="utf-8"))
    for ex in row["exits"]:
        if ex["target_zone"] == "sodium-tin-halo":
            ex["target_tile"] = [8, 10]
    (CAND/"zones/sodium-row.json").write_bytes((json.dumps(row, indent=2)+"\n").encode("utf-8"))
    # The Halo core's hardware follows its cabinet to the new tile.
    core = json.loads((ROOT/"src/blacksite/content/cores/lat-tin-halo.json").read_text(encoding="utf-8"))
    for hw in core["hardware"]:
        if hw["zone"] == "sodium-tin-halo":
            hw["tile"] = OBJECTS[hw["object_id"]]
    (CAND/"cores").mkdir(exist_ok=True)
    (CAND/"cores/lat-tin-halo.json").write_bytes((json.dumps(core, indent=2)+"\n").encode("utf-8"))
    base = json.loads((BASE/"looks/sodium-tin-halo.json").read_text(encoding="utf-8"))
    (CAND/"looks/sodium-tin-halo.json").write_bytes(
        (json.dumps(look(base), indent=2, ensure_ascii=False)+"\n").encode("utf-8"))


def main() -> None:
    demo, out = Path(sys.argv[1]), Path(sys.argv[2])
    candidate(demo)
    sys.argv = [sys.argv[0], str(out)]
    sys.path.insert(0, str(Path(__file__).parent))
    import v0_tin_halo as v0
    v0.CANDIDATE = CAND
    v0.SHOTS = {"door": ((8, 10), "right"),   # from the door, down the long axis to Vesper
                "bar": ((22, 10), "up")}       # facing the bar and the shelf
    out.mkdir(parents=True, exist_ok=True)
    costs = [v0.capture(shot, *tier, out) for shot in v0.SHOTS for tier in v0.TIERS]
    for row in costs:
        print(row)
    (out/"demo-halo-v0-costs.json").write_text(json.dumps(costs, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
