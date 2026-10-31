"""Demo geometry for Sodium Row and the Tin Halo (#143 section 9).

Draws both maps, moves every object, exit and core hardware tile to
match, regenerates the Row's charted public ground, and rewrites the
Row's look. Demo branch only: never merged.

Run from the repository root:  python scripts/demo_sodium/geometry.py
"""

import json
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT/"src/blacksite/content"

# --- Sodium Row, 100 x 30 -------------------------------------------------

W, H = 100, 30
STRIP = (9, 16)          # y range of the Strip, inclusive
AXIS = 12                # arrival row: the Stair landing and the Halo door
BARS = [                 # (interior x0, sign text, role, crowd)
    (6, " UPSTAIRS ", "thing_sign_blue", "Halvard and Sablier staff"),
    (22, "24H LONG SHIFT", "thing_sign_orange", "Kestrel"),
    (38, " quarter tone ", "thing_sign_pink", "Choir"),  # kept low
    (54, " THE CLAUSE ", "thing_sign_street", "Wakes and strays"),
    (70, " SPA E PA TS ", "thing_sign_green", "Unmoored"),
]
BAR_W = 15               # interior width; side walls between alcoves
ALCOVE = (2, 7)          # alcove interior y range; front wall at y 8


def row_map():
    g = [["#"]*W for _ in range(H)]

    def fill(x0, y0, x1, y1, ch="."):
        for y in range(y0, y1+1):
            for x in range(x0, x1+1):
                g[y][x] = ch

    # The Strip and the Stair landing at its west end.
    fill(1, STRIP[0], 89, STRIP[1])
    fill(1, 9, 4, 16)
    # Five bar alcoves on the north side, doorways in their front walls.
    for x0, *_ in BARS:
        fill(x0, ALCOVE[0], x0+BAR_W-1, ALCOVE[1])
        g[8][x0] = "+"
    # Old Works approach in the north-east corner, ending at the boundary.
    fill(87, 2, 98, 7)
    fill(87, 8, 89, 8)
    # The stage pit: the street widens south in front of the stage.
    fill(20, 17, 33, 20)
    # The card court: a half-enclosed square, tables as cover.
    fill(44, 17, 60, 21)
    for x in (47, 48, 56, 57):
        g[19][x] = "%"
    # The back alley, two tiles wide, and its two passages from the Strip.
    fill(6, 24, 89, 25)
    fill(17, 17, 18, 23)   # by the stage pit
    fill(62, 17, 63, 23)   # by the card court
    # House Lights sign-grid room off the alley, behind a door.
    fill(35, 21, 42, 22)
    g[23][38] = "+"
    # The Tin Halo's entrance bay at the Strip's east end, under a canopy.
    fill(82, 11, 89, 13)
    g[10] = g[10][:82] + ["#"]*8 + g[10][90:]
    g[14] = g[14][:82] + ["#"]*8 + g[14][90:]
    g[AXIS][90] = "+"
    # Halo back door on the alley: seen from outside, locked.
    g[24][90] = "="
    # Exit to the Plaza at the landing.
    g[AXIS][1] = ">"
    return g


ROW_OBJECTS = {
    # Bars at the back of each alcove.
    "row-bar-1": (13, 3), "row-bar-2": (29, 3), "row-bar-3": (45, 3),
    "row-bar-4": (61, 3), "row-bar-5": (77, 3),
    "row-stage": (26, 21), "row-card-table": (52, 19),
    "row-drug-dealer": (60, 21), "row-ticket-tout": (92, 5),
    # Spare Parts has a public terminal inside (gazetteer: most bars do).
    "row-public-1": (3, 15), "row-public-2": (40, 16), "row-public-3": (82, 6),
    "boundary-oldworks-main": (96, 2),
    "house-lights-sign-grid": (37, 21), "sign-grid-hardware": (38, 21),
}
ROW_EXITS = {"to-core-plaza": (1, AXIS), "to-sodium-tin-halo": (90, AXIS)}
ROW_ARRIVAL_FROM_PLAZA = (2, AXIS)
ROW_ARRIVAL_FROM_HALO = (89, AXIS)
ROW_ARRIVAL_FROM_HALO_BACK = (89, 24)
ROW_SPAWN = (3, AXIS)

# --- The Tin Halo, 44 x 22 map, the room 28 x 12 inside --------------------

HW, HH = 44, 22
ROOM = (8, 5, 35, 16)    # x0, y0, x1, y1 inclusive: 28 x 12
HALO_DOOR = (7, 10)      # west wall, on the room's long axis
VESPER = (34, 10)        # end of the bar, facing the door


def halo_map():
    g = [["#"]*HW for _ in range(HH)]
    x0, y0, x1, y1 = ROOM
    for y in range(y0, y1+1):
        for x in range(x0, x1+1):
            g[y][x] = "."
    # The bar runs along the north wall toward Vesper's end.
    for x in range(14, 33):
        g[7][x] = "%"
    g[8][33] = g[9][33] = "%"  # the bar turns at its end, by Vesper
    # Booths along the south wall: partitions are tiles, not dressing.
    for x in (12, 17, 22, 27):
        g[15][x] = g[16][x] = "#"
    # Back room behind the bar, door from the room, door to the alley.
    for y in (2, 3):
        for x in range(26, 34):
            g[y][x] = "."
    g[4][30] = "+"
    g[2][34] = "+"
    g[HALO_DOOR[1]][HALO_DOOR[0]] = "+"
    return g


HALO_OBJECTS = {
    "vesper": VESPER, "halo-bar": (24, 8), "halo-cabinet-hardware": (25, 8),
    "halo-back-room": (30, 4), "ferrymen-liaison": (31, 14),
    "halo-contract-board": (9, 6), "halo-market-board": (9, 14),
}
HALO_EXITS = {"to-sodium-row": HALO_DOOR, "to-sodium-row-back": (34, 2)}
HALO_ARRIVAL = (8, 10)
HALO_SPAWN = (9, 11)


# --- Writing ---------------------------------------------------------------

def dump(path, data):
    path.write_bytes((json.dumps(data, indent=2, ensure_ascii=False)+"\n").encode("utf-8"))


def write_map(path, g):
    path.write_bytes(("\n".join("".join(r) for r in g)+"\n").encode("utf-8"))


def mark_objects(g, objects, zone):
    chars = {"vendor": "$", "terminal": "T", "light": "L", "hardware": "H", "door": "+"}
    for o in zone["objects"]:
        x, y = objects[o["id"]]
        o["tile"] = [x, y]
        g[y][x] = chars.get(o["kind"], g[y][x])


def public_rects(g, starts, doors):
    """Charted public ground: every tile reached from the arrivals without
    crossing a door, plus each door face as its own 1x1 rect (A5)."""
    seen, q = set(starts), deque(starts)
    while q:
        x, y = q.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                t = (x+dx, y+dy)
                if t in seen or t in doors or g[t[1]][t[0]] in "#=":
                    continue
                seen.add(t)
                q.append(t)
    rects = []
    for y in range(H):
        x = 0
        while x < W:
            if (x, y) in seen:
                x1 = x
                while (x1+1, y) in seen:
                    x1 += 1
                rects.append([x, y, x1-x+1, 1])
                x = x1+1
            else:
                x += 1
    merged = []
    for r in rects:  # merge equal runs on consecutive rows
        prev = next((m for m in merged if m[0] == r[0] and m[2] == r[2] and m[1]+m[3] == r[1]), None)
        if prev:
            prev[3] += 1
        else:
            merged.append(r)
    return merged + [[x, y, 1, 1] for (x, y) in sorted(doors) if (x, y) not in seen]


def main():
    zones = CONTENT/"zones"
    g = row_map()
    row = json.loads((zones/"sodium-row.json").read_text(encoding="utf-8"))
    mark_objects(g, ROW_OBJECTS, row)
    row["spawn"] = list(ROW_SPAWN)
    for ex in row["exits"]:
        ex["tile"] = list(ROW_EXITS[ex["id"]])
        if ex["id"] == "to-sodium-tin-halo":
            ex["target_tile"] = list(HALO_ARRIVAL)
    write_map(zones/"sodium-row.map", g)
    doors = {tuple(o["tile"]) for o in row["objects"] if o["kind"] == "door"}
    doors |= {(x0, 8) for x0, *_ in BARS} | {(38, 23), (90, AXIS)}
    row["public"] = public_rects(g, [ROW_ARRIVAL_FROM_PLAZA, ROW_ARRIVAL_FROM_HALO], doors)
    # Placeholder population for a valid map; the consultant owns it.
    row["spawners"] = [
        {"id": "sable-enforcer-stair", "npc": "npc-sable-enforcer", "count": 1, "respawn_seconds": 60,
         "condition": "always", "region": {"x": 8, "y": 11, "w": 1, "h": 3}},
        {"id": "sable-enforcer-strip", "npc": "npc-sable-enforcer", "count": 1, "respawn_seconds": 60,
         "condition": "always", "region": {"x": 45, "y": 9, "w": 2, "h": 1}},
        {"id": "sodium-regular", "npc": "npc-sodium-regular", "count": 5, "respawn_seconds": 60,
         "condition": "always", "region": {"x": 10, "y": 9, "w": 70, "h": 8}},
        {"id": "plainclothes-warden", "npc": "npc-plainclothes-warden", "count": 1, "respawn_seconds": 60,
         "condition": "always", "region": {"x": 40, "y": 9, "w": 30, "h": 8}},
    ]
    dump(zones/"sodium-row.json", row)

    h = halo_map()
    halo = json.loads((zones/"sodium-tin-halo.json").read_text(encoding="utf-8"))
    mark_objects(h, HALO_OBJECTS, halo)
    halo["spawn"] = list(HALO_SPAWN)
    halo["sight_radius"] = 28  # demo: the whole room in sight (V0-3 is still open)
    halo["exits"] = [
        {"id": "to-sodium-row", "tile": list(HALO_DOOR), "target_zone": "sodium-row",
         "target_tile": list(ROW_ARRIVAL_FROM_HALO), "kind": "door"},
        {"id": "to-sodium-row-back", "tile": list(HALO_EXITS["to-sodium-row-back"]), "target_zone": "sodium-row",
         "target_tile": list(ROW_ARRIVAL_FROM_HALO_BACK), "kind": "door"},
    ]
    halo["spawners"] = [
        {"id": "halo-bouncer", "npc": "npc-halo-bouncer", "count": 1, "respawn_seconds": 60,
         "condition": "always", "region": {"x": 9, "y": 9, "w": 1, "h": 1}},
        {"id": "halo-regular", "npc": "npc-halo-regular", "count": 4, "respawn_seconds": 60,
         "condition": "always", "region": {"x": 13, "y": 12, "w": 16, "h": 2}},
        {"id": "vendor-sodium-tin-halo-vesper", "npc": "npc-vendor-sodium-tin-halo-vesper", "count": 1,
         "respawn_seconds": 60, "condition": "always", "region": {"x": 33, "y": 9, "w": 1, "h": 3}},
    ]
    write_map(zones/"sodium-tin-halo.map", h)
    dump(zones/"sodium-tin-halo.json", halo)

    # The Plaza's exit lands on the new arrival tile.
    plaza = json.loads((zones/"core-plaza.json").read_text(encoding="utf-8"))
    for ex in plaza["exits"]:
        if ex["target_zone"] == "sodium-row":
            ex["target_tile"] = list(ROW_ARRIVAL_FROM_PLAZA)
    dump(zones/"core-plaza.json", plaza)

    # Core hardware tiles follow their objects.
    for core, zone, objects in (("lat-house-lights", "sodium-row", ROW_OBJECTS),
                                ("lat-tin-halo", "sodium-tin-halo", HALO_OBJECTS)):
        path = CONTENT/f"cores/{core}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for hw in data["hardware"]:
            if hw["zone"] == zone:
                hw["tile"] = list(objects[hw["object_id"]])
        dump(path, data)

    look = json.loads((CONTENT/"looks/sodium-row.json").read_text(encoding="utf-8"))
    look["regions"] = (
        [{"theme": "sodium-lamp", "circle": [x, y, 3]} for x, y in
         ((10, 12), (32, 10), (54, 14), (76, 10), (50, 24))]
        + [{"theme": "sodium-door-teal" if i % 2 else "sodium-door-pink", "circle": [x0, 9, 2]}
           for i, (x0, *_) in enumerate(BARS)]
        + [{"theme": "sodium-stage", "circle": [26, 19, 3]},
           {"theme": "sodium-door-pink", "circle": [86, 12, 2]}]
    )
    look["signs"] = (
        [{"at": [x0+1, 8], "text": text, "role": role} for x0, text, role, _ in BARS]
        + [{"at": [82, 10], "text": " TIN HAL", "role": "thing_sign_orange"},
           {"at": [19, 21], "text": " STAGE ", "role": "thing_sign_amber"}]
    )
    look["marks"] = [
        {"at": [2, 10], "text": "← NEON STAIR", "role": "paint"},
        {"at": [5, 14], "text": "TIN HALO →", "role": "paint"},
        # The Clause's regulars chalk their days under its sign.
        {"at": [56, 10], "text": "||||/ ||||/ ||||/ ||", "role": "paint"},
    ]
    dump(CONTENT/"looks/sodium-row.json", look)


if __name__ == "__main__":
    main()
