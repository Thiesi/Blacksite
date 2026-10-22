"""Draw authorized cell coordinates and edges; no access or movement rules."""

from typing import Any

from blacksite.door.cells import CellBuffer, display_width, truncate
from blacksite.door.layout import Rect
from blacksite.door.palette import Palette


def render_lattice(buffer: CellBuffer, body: dict[str, Any], area: Rect, palette: Palette) -> None:
    buffer.put(2, 0, truncate(str(body.get("title", "LATTICE")), buffer.width-6), palette.style("title"))
    columns, rows = body.get("layout_size", [8, 6])
    cells = body.get("cells", [])
    room = body.get("room")
    room_ice = room.get("ice", []) if isinstance(room, dict) else room
    graph_height = max(4, area.height-5) if room is not None else area.height
    positions = {c["id"]: (area.x+1+int(c["x"])*(area.width-6)//max(1, columns-1),
                            area.y+1+int(c["y"])*(graph_height-3)//max(1, rows-1)) for c in cells}
    for edge in body.get("edges", []):
        if edge["a"] not in positions or edge["b"] not in positions:
            continue
        ax, ay = positions[edge["a"]]
        bx, by = positions[edge["b"]]
        ax, bx = ax+2, bx+2
        steps = max(abs(bx-ax), abs(by-ay))
        horizontal, vertical = ("═", "║") if edge["kind"] == "gated" else ("·", "┆") if edge["kind"] == "hidden" else ("─", "│")
        glyph = horizontal if ay == by else vertical if ax == bx else "\\" if (bx-ax)*(by-ay) > 0 else "/"
        for step in range(1, steps):
            x, y = round(ax+(bx-ax)*step/steps), round(ay+(by-ay)*step/steps)
            if area.x <= x < area.x+area.width and area.y <= y < area.y+area.height:
                buffer.put(x, y, glyph, palette.style("muted"))
    me = body.get("me", {})
    peers = body.get("presences", [])
    cores = 0
    for index, cell in enumerate(cells, 1):
        x, y = positions[cell["id"]]
        if cell["kind"] == "core_entrance":
            cores += 1
            token = f"[C{cores}]"
        else:
            # Identity comes from the authored layout, so discovery never
            # renumbers already-visible cells.
            token = f"({int(cell['y'])*columns+int(cell['x'])+1:02})"
        reverse = cell["id"] == me.get("cell")
        role = "ui_highlight" if reverse else "ui_text"
        buffer.put(x, y, token, palette.style(role, reverse=reverse))
        peer = next((p for p in peers if p["cell"] == cell["id"]), None)
        if peer:
            buffer.put(x+1, y, "♦", palette.style(peer.get("marker_role", "player_neutral"), reverse=reverse))
        elif any(beacon["cell"] == cell["id"] for beacon in body.get("beacons", [])):
            buffer.put(x+1, y, "♦", palette.style("player_crew", reverse=reverse))
    side_x, side_w = buffer.width-23, 22
    status: list[tuple[str, str]] = [
        (f"INTEGRITY {me.get('integrity', 100):g}", "hp_ok"),
        (f"TRACE {me.get('trace', 0):g}", "ui_highlight"),
        ("BODY "+str(body.get("body_safety", "")).upper(), "safety_"+str(body.get("body_safety", "safe"))),
    ]
    if "body_hp" in me:
        status.append((f"HP {me['body_hp']}/{me['body_hp_max']}", "text"))
    if body.get("black_risk"):
        status.append(("BLACK ICE / BODY RISK", "warning"))
    for warning in body.get("sweep_warnings", []):
        cell = next((c for c in cells if c["id"] == warning["cell"]), None)
        marker = f"({cell['y']*columns+cell['x']+1:02})" if cell else "next cell"
        status.append((f"SWEEP {marker} {warning['ticks']/10:.1f}s", "warning"))
    if me.get("escape_ticks") is not None:
        status += [(f"ESCAPE {me['escape_ticks']/10:.1f}s", "warning"),
                   (f"Interruptions {me.get('interruptions', 0)}/3", "warning")]
    elif me.get("move_ticks"):
        status.append((f"LINK {me['move_ticks']/10:.1f}s", "muted"))
    if me.get("cast"):
        cast = me["cast"]
        status.append((f"{cast['name']} {cast['ticks']/10:.1f}s", "ui_highlight"))
    if me.get("shield"):
        shield = me["shield"]
        status.append((f"SHIELD {shield['budget']:g} {shield['name']}", "hp_ok"))
    if me.get("decoy", 0) > 0:
        status.append((f"DECOY {me['decoy']:g}", "ui_highlight"))
    status.append(("RIG", "title"))
    rig = [f"{r['slot']} {r.get('name', 'Empty')}"+
           (f" {r['cd']:.1f}s" if r.get("cd") else "") for r in me.get("rig", [])]
    if len(status)+len(rig)+2 > area.height:
        packed = []
        for index in range(0, len(rig), 2):
            line = truncate(rig[index], 10)
            if index+1 < len(rig):
                line += ' '*(11-display_width(line))+truncate(rig[index+1], 10)
            packed.append(line)
        rig = packed
    status.extend((line, "text") for line in rig)
    status += [("ROOM", "title"), (str(body.get("label", "")), "text")]
    for peer in peers:
        status += [("♦ "+str(peer.get("name", "Another runner")), peer.get("role", "text"))]
    for beacon in body.get("beacons", []):
        status.append(("BEACON "+beacon["name"], "player_crew"))
    for index, (text, role) in enumerate(status[:area.height]):
        buffer.put(side_x, area.y+index, truncate(text, side_w), palette.style(role))
    if room is not None:
        selected = next((row for row in room_ice if row["id"] == me.get("target")), next(iter(room_ice), None))
        details = [("ROOM / "+str(body.get("label", "")), "title")]
        if selected:
            phase = selected['phase']
            if selected.get('warning_ticks'):
                phase += f" {selected['warning_ticks']/10:.1f}s"
            details += [(f"{'>' if selected['id'] == me.get('target') else 'Tab'} {selected['name']} "
                         f"{selected['integrity']:g}/{selected['maximum']:g} [{phase}]", "warning"),
                        (f"{selected['role']} / {selected['trigger']} / {selected['damage']:g} integrity, "
                         f"{selected['meat']} body damage", "text"),
                        (str(selected['counter']), "muted")]
        else:
            data_count = len(room.get("data", [])) if isinstance(room, dict) else 0
            controls_count = len(room.get("controls", [])) if isinstance(room, dict) else 0
            details += [(f"No active defender. E inspects {data_count} data / {controls_count} controls.", "text")]
        for index, (text, role) in enumerate(details):
            buffer.put(area.x+1, area.y+graph_height+index, truncate(text, area.width-2), palette.style(role))
    transition = body.get("transition")
    if transition:
        text = ("Cells resolve" if transition["direction"] == "in" else "Your body returns")+"."*transition["frame"]
        buffer.put(area.x+1, area.y, truncate(text, area.width-2), palette.style("title"))
