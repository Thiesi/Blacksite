"""Draw authorized cell coordinates and edges; no access or movement rules."""

from typing import Any

from blacksite.door.cells import CellBuffer, truncate
from blacksite.door.layout import Rect
from blacksite.door.palette import Palette


def render_lattice(buffer: CellBuffer, body: dict[str, Any], area: Rect, palette: Palette) -> None:
    buffer.put(2, 0, truncate(str(body.get("title", "LATTICE")), buffer.width-6), palette.style("title"))
    columns, rows = body.get("layout_size", [8, 6])
    cells = body.get("cells", [])
    positions = {c["id"]: (area.x+1+int(c["x"])*(area.width-6)//max(1, columns-1),
                            area.y+1+int(c["y"])*(area.height-3)//max(1, rows-1)) for c in cells}
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
    side_x, side_w = buffer.width-23, 22
    status: list[tuple[str, str]] = [
        (f"INTEGRITY {me.get('integrity', 100):g}", "hp_ok"),
        (f"TRACE {me.get('trace', 0):g}", "ui_highlight"),
        ("BODY "+str(body.get("body_safety", "")).upper(), "safety_"+str(body.get("body_safety", "safe"))),
    ]
    if "body_hp" in me:
        status.append((f"HP {me['body_hp']}/{me['body_hp_max']}", "text"))
    if me.get("escape_ticks") is not None:
        status += [(f"ESCAPE {me['escape_ticks']/10:.1f}s", "warning"),
                   (f"Interruptions {me.get('interruptions', 0)}/3", "warning")]
    elif me.get("move_ticks"):
        status.append((f"LINK {me['move_ticks']/10:.1f}s", "muted"))
    status.append(("RIG", "title"))
    status.extend((f"{r['slot']} {r.get('name', 'Empty')}", "text") for r in me.get("rig", []))
    status += [("ROOM", "title"), (str(body.get("label", "")), "text")]
    for peer in peers:
        status += [("♦ "+str(peer.get("name", "Another runner")), peer.get("role", "text"))]
    for index, (text, role) in enumerate(status[:area.height]):
        buffer.put(side_x, area.y+index, truncate(text, side_w), palette.style(role))
    transition = body.get("transition")
    if transition:
        text = ("Cells resolve" if transition["direction"] == "in" else "Your body returns")+"."*transition["frame"]
        buffer.put(area.x+1, area.y, truncate(text, area.width-2), palette.style("title"))
