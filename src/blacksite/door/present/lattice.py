"""The Lattice: linework on black (spec section 8).

The street is filled colour; the network is light drawn on nothing.
Draws an authorized LatticeView or core view. No access, movement or
trace rules: cells, links and numbers are exactly what the server sent.
"""

from typing import Any

from blacksite.door.cells import CellBuffer, display_width, truncate
from blacksite.door.layout import Layout
from blacksite.door.present import chrome
from blacksite.door.present.paint import Paint

CELLS = {"public": ("■", "lat_lit"), "gated": ("╪", "lat_gated"), "hidden": ("∙", "lat_gated"),
         "descent": ("∞", "lat_descent"), "room": ("■", "lat_lit")}


def _positions(body: dict[str, Any], area_x: int, area_y: int, width: int, height: int) -> dict[str, tuple[int, int]]:
    cells = body.get("cells", [])
    columns, rows = body.get("layout_size", [8, 6])
    used_x = sorted({int(c["x"]) for c in cells}) or [0]
    used_y = sorted({int(c["y"]) for c in cells}) or [0]
    # Spread over the columns and rows the layout uses, so a sparse sector
    # fills the view instead of hugging its top-left corner.
    span_x = max(1, max(used_x) - min(used_x)) if len(used_x) > 1 else 1
    span_y = max(1, max(used_y) - min(used_y)) if len(used_y) > 1 else 1
    sx = (width - 6) / span_x if len(used_x) > 1 else 0
    sy = min(8.0, (height - 3) / span_y) if len(used_y) > 1 else 0
    ox = area_x + 3 + (0 if len(used_x) > 1 else (width - 6) // 2)
    oy = area_y + 1 + ((height - 3 - round(sy * span_y)) // 2 if len(used_y) > 1 else (height - 3) // 2)
    return {c["id"]: (ox + round((int(c["x"]) - min(used_x)) * sx), oy + round((int(c["y"]) - min(used_y)) * sy))
            for c in cells}


def graph(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint, height: int) -> dict[str, tuple[int, int]]:
    area = layout.viewport
    positions = _positions(body, area.x, area.y, area.width, height)
    for y in range(area.y + 1, area.y + height - 1, 2):  # the old engineers' field, faintly
        for x in range(area.x + 2, area.x + area.width - 1, 4):
            buffer.put(x, y, "·", paint("lat_field"))
    for edge in body.get("edges", []):
        if edge["a"] not in positions or edge["b"] not in positions:
            continue
        (ax, ay), (bx, by) = positions[edge["a"]], positions[edge["b"]]
        kind = edge.get("kind", "public")
        horizontal, vertical = {"gated": ("═", "║"), "hidden": ("∙", ":")}.get(kind, ("─", "│"))
        glyph = horizontal if ay == by else vertical if ax == bx else "\\" if (bx - ax) * (by - ay) > 0 else "/"
        steps = max(abs(bx - ax), abs(by - ay))
        for step in range(2 if ay == by else 1, steps - (1 if ay == by else 0)):
            x, y = round(ax + (bx - ax) * step / steps), round(ay + (by - ay) * step / steps)
            if area.x <= x < area.x + area.width and area.y <= y < area.y + height:
                buffer.put(x, y, glyph, paint("lat_gated" if kind == "gated" else "lat_link"))
    me = body.get("me", {})
    sweeps = {w["cell"] for w in body.get("sweep_warnings", [])}
    peers = {p["cell"]: p for p in body.get("presences", [])}
    beacons = {b["cell"] for b in body.get("beacons", [])}
    roomy = _positions(body, 0, 0, area.width, height)
    tall = len({y for _, y in roomy.values()}) <= 1 or min(
        (abs(a[1] - b[1]) for a in roomy.values() for b in roomy.values() if a[1] != b[1]), default=4) >= 3
    for cell in body.get("cells", []):
        x, y = positions[cell["id"]]
        here = cell["id"] == me.get("cell")
        if cell.get("offline"):
            role = "panel_dim"
        elif cell["id"] in sweeps:
            role = "log_danger"
        else:
            role = None
        if cell["kind"] == "core_entrance":
            initial = (str(cell.get("label", "?")).strip() or "?")[0].upper()
            style = paint(role or "lat_core", bold=True)
            mark = paint("lat_here_fg", "lat_here_bg", bold=True) if here else style
            if tall:
                buffer.put(x - 1, y - 1, "╔═╗", style)
                buffer.put(x - 1, y, "║", style)
                buffer.put(x, y, initial, mark)
                buffer.put(x + 1, y, "║", style)
                buffer.put(x - 1, y + 1, "╚═╝", style)
            else:
                buffer.put(x - 1, y, "▐", style)
                buffer.put(x, y, initial, mark)
                buffer.put(x + 1, y, "▌", style)
        else:
            glyph, base = CELLS.get(cell["kind"], ("■", "lat_lit"))
            if cell.get("uplink"):
                glyph = "∩"
            if here:
                buffer.put(x - 1, y, f" {glyph} ", paint("lat_here_fg", "lat_here_bg", bold=True))
            else:
                buffer.put(x, y, glyph, paint(role or base, bold=base == "lat_lit", reverse=cell["id"] in sweeps))
        if cell["id"] in peers:
            peer = peers[cell["id"]]
            buffer.put(x + 2, y, "♦", paint(peer.get("marker_role", "player_neutral"), bold=True))
        elif cell["id"] in beacons:
            buffer.put(x + 2, y, "♦", paint("player_crew", bold=True))
    return positions


def caption(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint, top: int, rows: int,
            positions: dict[str, tuple[int, int]]) -> None:
    """Where you are, then where each link goes, in words (spec 8.4)."""
    area = layout.viewport
    cells = {c["id"]: c for c in body.get("cells", [])}
    here = cells.get(body.get("me", {}).get("cell", ""))
    if here is None or rows <= 0:
        return
    kind = {"core_entrance": "core entrance", "room": "room"}.get(here["kind"], here["kind"] + " cell")
    label = str(here.get("label", ""))
    buffer.put(area.x + 1, top, truncate("@ " + label, area.width - 2), paint("lat_caption", bold=True))
    if display_width(label) + 6 < area.width - 2:
        buffer.put(area.x + 4 + display_width(label), top, truncate(kind, area.width - 6 - display_width(label)), paint("panel_dim"))
    hx, hy = positions[here["id"]]
    links = []
    for edge in body.get("edges", []):
        other = edge["b"] if edge["a"] == here["id"] else edge["a"] if edge["b"] == here["id"] else None
        if other is None or other not in cells:
            continue
        ox, oy = positions[other]
        arrow = "→" if ox > hx and abs(ox - hx) >= abs(oy - hy) * 2 else "←" if ox < hx and abs(ox - hx) >= abs(oy - hy) * 2 \
            else "↓" if oy > hy else "↑"
        gate = " (gated)" if edge.get("kind") == "gated" else ""
        links.append(f"{arrow} {cells[other].get('label', other)}{gate}")
    line, row = "", top + 1
    for link in links:
        if line and display_width(line + "   " + link) > area.width - 2:
            if row >= top + rows:
                break
            buffer.put(area.x + 1, row, line, paint("panel_text"))
            line, row = "", row + 1
        line = f"{line}   {link}" if line else link
    if line and row < top + rows:
        buffer.put(area.x + 1, row, truncate(line, area.width - 2), paint("panel_text"))


def room_detail(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint, top: int) -> None:
    area, me, room = layout.viewport, body.get("me", {}), body.get("room")
    ice = room.get("ice", []) if isinstance(room, dict) else room or []
    selected = next((row for row in ice if row["id"] == me.get("target")), next(iter(ice), None))
    rows: list[tuple[str, str]] = []
    if selected:
        phase = selected["phase"] + (f" {selected['warning_ticks'] / 10:.1f}s" if selected.get("warning_ticks") else "")
        rows += [(f"{'>' if selected['id'] == me.get('target') else 'Tab'} {selected['name']}  "
                  f"{selected['integrity']:g}/{selected['maximum']:g}  {phase}", "log_danger"),
                 (f"{selected['role']} · {selected['trigger']} · {selected['damage']:g} integrity, "
                  f"{selected['meat']} body", "panel_text"),
                 (str(selected["counter"]), "panel_label")]
    else:
        data = len(room.get("data", [])) if isinstance(room, dict) else 0
        controls = len(room.get("controls", [])) if isinstance(room, dict) else 0
        rows.append((f"No active defender. E inspects {data} data, {controls} controls.", "panel_text"))
    for index, (text, role) in enumerate(rows):
        if top + index < area.y + area.height:
            buffer.put(area.x + 1, top + index, truncate(text, area.width - 2), paint(role))


def panel(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint) -> None:
    x, w, y0 = layout.side.x, layout.side.width, layout.side.y
    bottom = layout.side.y + layout.side.height
    me = body.get("me", {})
    rows: list[tuple[str, Any]] = []  # ("rule", label) | ("bar", args) | (role, text)
    rows.append(("rule", "RUNNER"))
    rows.append(("bar", ("INT", me.get("integrity", 100), me.get("integrity_max", 100), "bar_int", f"{me.get('integrity', 100):g}", None)))
    rows.append(("bar", ("TRC", me.get("trace", 0), 100, "bar_trace", f"{me.get('trace', 0):g}", 5)))
    if me.get("escape_ticks") is not None:
        rows.append(("log_danger", f"ESCAPE {me['escape_ticks'] / 10:.1f}s  {me.get('interruptions', 0)}/3"))
    elif me.get("move_ticks"):
        rows.append(("panel_label", f"linking {me['move_ticks'] / 10:.1f}s"))
    if me.get("cast"):
        rows.append(("panel_strong", f"{me['cast']['name']} {me['cast']['ticks'] / 10:.1f}s"))
    guards = ([f"shield {me['shield']['budget']:g}"] if me.get("shield") else []) + \
             ([f"decoy {me['decoy']:g}"] if me.get("decoy", 0) > 0 else [])
    if guards:
        rows.append(("bar_hp", "  ".join(guards)))
    cells = {c["id"]: c for c in body.get("cells", [])}
    for warning in body.get("sweep_warnings", [])[:2]:
        label = cells.get(warning["cell"], {}).get("label", "next cell")
        rows.append(("log_danger", f"‼ sweep {warning['ticks'] / 10:.1f}s {label}"))
    rows.append(("rule", "BODY"))
    safety = str(body.get("body_safety", ""))
    rows.append(("body", (str(body.get("body_zone", "")), safety)))
    if "body_hp" in me:
        rows.append(("bar", ("HP", me["body_hp"], me["body_hp_max"], "bar_hp", str(me["body_hp"]), None)))
    if body.get("black_risk"):
        rows.append(("log_danger", "‼ black ICE: body at risk"))
    if target := body.get("runner_target"):
        suffix = f" {target['integrity_percent']}%" if target["burn_allowed"] else " protected"
        rows.append(("rule", "TARGET"))
        rows.append(("log_danger" if target["burn_allowed"] else "panel_dim", truncate(target["name"], w - 1 - len(suffix)) + suffix))
    plans = [(str(p["summary"]), "log_danger" if p.get("warning") else "log_place") for p in (body.get("event") or {}).get("plans", [])]
    objective = body.get("objective")
    if plans or objective or body.get("published_patrol"):
        rows.append(("rule", "NOW"))
        rows += [(role, text) for text, role in plans[:2]]
        if objective:
            rows.append(("panel_strong", str(objective.get("next_action", ""))))
        if body.get("published_patrol"):
            rows.append(("panel_label", "patrol: Q / journal"))
    peers = sorted(body.get("presences", []), key=lambda p: p.get("cell") != me.get("cell"))
    crew = body.get("crew", [])
    if peers or crew or body.get("beacons"):
        rows.append(("rule", "NEAR"))
        for peer in peers[:3]:
            rows.append((peer.get("role", "panel_text"), "♦ " + str(peer.get("name", "Another runner"))))
        if len(peers) > 3:
            rows.append(("panel_label", f"+{len(peers) - 3} runners"))
        for beacon in body.get("beacons", [])[:1]:
            rows.append(("player_crew", "beacon " + str(beacon["name"])))
        for member in crew[:2]:
            rows.append(("player_crew", f"{truncate(member['name'], w - 6)} {member['hp_pct']}%"))
    rows.append(("rule", "RIG"))
    for slot in me.get("rig", []):
        rows.append(("rig", slot))
    if len(rows) > bottom - y0:
        # Never drop runner, body or danger rows to fit the rig: pack it.
        rig = [r for r in rows if r[0] == "rig"]
        rows = [r for r in rows if r[0] != "rig"]
        room = max(1, bottom - y0 - len(rows))
        per = max(1, -(-len(rig) // room))
        rows += [("rigs", rig[i:i + per]) for i in range(0, len(rig), per)]
    y = y0
    for kind, value in rows[:bottom - y0]:
        if kind == "rule":
            chrome.rule(buffer, layout, paint, y, value)
        elif kind == "bar":
            label, val, maximum, role, digits, tick = value
            chrome.bar(buffer, paint, x + 1, y, label, val, maximum, role, digits, tick=tick)
        elif kind == "body":
            zone, safety = value
            buffer.put(x + 1, y, truncate(zone or "your body", w - 10), paint("panel_text"))
            buffer.put(x + w - len(safety), y, safety.upper(), paint("word_" + safety, bold=True))
        elif kind == "rig":
            cd = f" {value['cd']:.0f}s" if value.get("cd") else ""
            name = value.get("name") or "Empty"
            buffer.put(x + 1, y, str(value["slot"]), paint("key_cap", bold=True))
            buffer.put(x + 3, y, truncate(name + cd, w - 3), paint("panel_text" if value.get("program") else "panel_dim"))
        elif kind == "rigs":
            cell = (w - 1) // len(value)
            for i, slot in enumerate(value):
                buffer.put(x + 1 + i * cell, y, str(slot[1]["slot"]), paint("key_cap", bold=True))
                buffer.put(x + 3 + i * cell, y, truncate(slot[1].get("name") or "-", cell - 3),
                           paint("panel_text" if slot[1].get("program") else "panel_dim"))
        else:
            buffer.put(x + 1, y, truncate(str(value), w - 1), paint(kind if paint.has(kind) else "panel_text"))
        y += 1


def head(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint) -> None:
    title = str(body.get("title", "LATTICE"))
    left = [("DOWN ·", "head_district"), (title.title() if title.isupper() else title, "head_zone")]
    safety = str(body.get("body_safety", ""))
    right = [("body", "head_district"), (str(body.get("body_zone", "")), "head_info"), (safety.upper(), "word_" + safety)]
    chrome.header(buffer, layout, paint, left, [r for r in right if r[0]])


def render(buffer: CellBuffer, body: dict[str, Any], layout: Layout, paint: Paint) -> None:
    area = layout.viewport
    detail = 3 if body.get("room") is not None else 0
    words = 3
    height = max(5, area.height - words - detail)
    positions = graph(buffer, body, layout, paint, height)
    caption(buffer, body, layout, paint, area.y + height, words, positions)
    if detail:
        room_detail(buffer, body, layout, paint, area.y + height + words)
    panel(buffer, body, layout, paint)
    head(buffer, body, layout, paint)
    transition = body.get("transition")
    if transition:
        text = ("The city goes quiet. Cells resolve" if transition["direction"] == "in" else "Your body returns") + "." * transition["frame"]
        buffer.put(area.x + 1, area.y, truncate(text, area.width - 2), paint("lat_caption", bold=True))
