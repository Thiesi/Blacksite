"""Prototype presentation renderer for issue #68 (not shipped with the game).

Draws real ZoneView and LatticeView bodies with the proposed visual
grammar. It uses the door's own CellBuffer, Style and layout geometry, so
every frame it produces is a byte stream the shipped client could emit:
CP437-safe glyphs, single-width cells, SGR colour per tier, nothing in the
bottom-right corner. Proposed view-model fields that do not exist yet
(theme, dressing, charted terrain, focus) are computed here from the data
in presentation.json and named as such in the brief.
"""

from dataclasses import dataclass
from typing import Any

from blacksite.door.cells import CellBuffer, display_width, truncate
from blacksite.door.layout import Layout, Rect
from blacksite.door.palette import Style

MECHANIC_GLYPHS = set("█░▒▓+≡§Ω»≈‼$*Θ☼■@☺☻τ")  # shapes that carry rules
DRESS_GLYPHS = set("·∙,`─│ ") | set("ABCDEFGHIJKLMNOPQRSTUVWXYZ-«»'")  # walkable-weight only

THING_ROLES = {"terminal": "thing_terminal", "vendor": "thing_vendor", "bank": "thing_vendor",
               "hardware": "thing_hardware", "door": "thing_door", "locked-door": "thing_door",
               "exit": "thing_exit", "light": "thing_light", "vat": "thing_vat", "relay": "relay_sablier",
               "hazard": "thing_hazard", "tram_stop": "thing_exit", "descent_console": "thing_terminal"}
OBJECT_GLYPHS = {"terminal": "§", "vendor": "$", "bank": "$", "hardware": "■", "door": "+", "relay": "Ω",
                 "light": "☼", "vat": "Θ", "descent_console": "§", "tram_stop": "»"}


class Paint:
    """Role names to Styles for one tier; raw dicts allowed for themes."""

    def __init__(self, data: dict[str, Any], tier: str) -> None:
        self.roles, self.tier = data["roles"], tier
        self.cache: dict[tuple[Any, ...], Style] = {}

    def value(self, spec: Any) -> int | tuple[int, int, int]:
        if isinstance(spec, str):
            spec = self.roles[spec]
        raw = spec["truecolor" if self.tier == "truecolor" else self.tier]
        if isinstance(raw, str):
            return tuple(int(raw[i:i + 2], 16) for i in (1, 3, 5))
        if self.tier == "16":
            assert 0 <= raw <= 15
        return raw

    def __call__(self, fg: Any, bg: Any = "black", *, bold: bool = False, reverse: bool = False) -> Style:
        key = (repr(fg), repr(bg), bold, reverse)
        if key not in self.cache:
            fgv, bgv = self.value(fg), self.value(bg)
            if self.tier == "16":
                assert isinstance(bgv, int) and bgv <= 7, "16-colour backgrounds stay in 0-7"
            attrs = (1,) if bold and self.tier != "16" else ()
            if reverse and self.tier == "16":
                attrs += (7,)  # let the terminal swap; bright colours never become a 16-colour background
            elif reverse:
                fgv, bgv = bgv, fgv
            self.cache[key] = Style(fgv, bgv, attrs, self.tier)
        return self.cache[key]

    def known(self, style: Style) -> Style:
        """Terrain you know but cannot see now: same hues, less light.

        256 and truecolor scale each colour toward black and snap to the
        nearest palette entry; 16 colours cannot dim, so known terrain
        becomes dark grey on black there."""
        if self.tier == "16":
            return Style(8 if style.fg != 0 else 0, 0, (), "16")
        return Style(self.scale(style.fg, KNOWN_FG), self.scale(style.bg, KNOWN_BG), (), self.tier)

    def scale(self, value: int | tuple[int, int, int], factor: float) -> int | tuple[int, int, int]:
        rgb = value if isinstance(value, tuple) else XTERM[value]
        dimmed = tuple(int(c * factor) for c in rgb)
        if self.tier == "truecolor":
            return dimmed
        return min(range(16, 256), key=lambda i: sum((a - b) ** 2 for a, b in zip(XTERM[i], dimmed)))


def _xterm() -> list[tuple[int, int, int]]:
    base = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
            (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)]
    steps = [0, 95, 135, 175, 215, 255]
    cube = [(steps[i // 36], steps[i // 6 % 6], steps[i % 6]) for i in range(216)]
    return base + cube + [(8 + 10 * i,) * 3 for i in range(24)]


XTERM = _xterm()
KNOWN_FG, KNOWN_BG = 0.55, 0.62  # proposal values, tuned by eye at 80x24


def stable(x: int, y: int) -> int:
    return (x * 73856093 ^ y * 19349663) & 0xFFFF


@dataclass
class Scene:
    layout: Layout
    paint: Paint
    data: dict[str, Any]
    tier: str


# ---------------------------------------------------------------- frame

def frame(buf: CellBuffer, scene: Scene, safety: str, segments: list[tuple[str, str]],
          right: list[tuple[str, str]]) -> None:
    """Outer frame: line style and colour carry the body's safety class."""
    lay, paint = scene.layout, scene.paint
    double = safety in ("safe", "pocket")
    h, v, tl, tr, bl, br = ("═", "║", "╔", "╗", "╚", "╝") if double else ("─", "│", "┌", "┐", "└", "┘")
    lj, rj, tj, bj = ("╟", "╢", "╤", "╧") if double else ("├", "┤", "┬", "┴")
    style = paint("frame_" + safety)
    w, hgt = lay.width, lay.height
    buf.put(0, 0, tl + h * (w - 2) + tr, style)
    for y in range(1, hgt - 1):
        buf.put(0, y, v, style)
        buf.put(w - 1, y, v, style)
    buf.put(0, hgt - 1, bl + h * (w - 2), style)  # never the bottom-right cell
    buf.put(0, lay.separator, lj + "─" * (w - 2) + rj, style)
    side = lay.side.x - 1
    buf.put(side, 0, tj, style)
    for y in range(1, lay.separator):
        buf.put(side, y, "│", style)
    buf.put(side, lay.separator, "┴", style)
    x = 2
    for text, role in segments:
        if x + display_width(text) > side - 1:
            break
        buf.put(x, 0, text, paint(role, bold=role in ("head_zone",) or role.startswith("word_")))
        x += display_width(text)
    rx = w - 2
    for text, role in reversed(right):
        rx -= display_width(text)
        if rx <= x:
            break
        buf.put(rx, 0, text, paint(role))


def rule(buf: CellBuffer, scene: Scene, y: int, label: str) -> None:
    x, w = scene.layout.side.x, scene.layout.side.width
    buf.put(x, y, "─" * w, scene.paint("rule"))
    if label:
        buf.put(x + 1, y, f" {label} ", scene.paint("label"))


def bar(buf: CellBuffer, scene: Scene, x: int, y: int, label: str, value: float, maximum: float,
        role: str, digits: str, width: int = 10, ticks: tuple[int, ...] = ()) -> None:
    paint = scene.paint
    buf.put(x, y, label.ljust(4), paint("label"))
    filled = max(0.0, min(1.0, value / max(1, maximum))) * width
    for i in range(width):
        if i in ticks:
            glyph, style = "│", paint("strong")
        elif i < int(filled):
            glyph, style = "█", paint(role)
        elif i < filled:
            glyph, style = "▌", paint(role)
        else:
            glyph, style = "░", paint("bar_empty")
        buf.put(x + 4 + i, y, glyph, style)
    buf.put(x + 5 + width, y, digits, paint("text"))


def log(buf: CellBuffer, scene: Scene, lines: list[tuple[str, str]]) -> None:
    """lines: (kind, text). Gutter glyph + kind colour; speaker names lit."""
    gutters = {"place": "∙", "ambient": "∙", "speech": '"', "combat": "*", "danger": "‼",
               "system": "+", "lattice": "∙"}
    lay, paint = scene.layout, scene.paint
    shown = lines[-lay.log.height:]
    for i, (kind, text) in enumerate(shown):
        y = lay.log.y + i
        role = "log_" + kind
        buf.put(lay.log.x, y, gutters.get(kind, " "), paint(role if kind != "system" else "dim"))
        if kind == "speech" and ": " in text:
            who, said = text.split(": ", 1)
            buf.put(lay.log.x + 2, y, who + ":", paint("log_speaker"))
            buf.put(lay.log.x + 4 + display_width(who), y, truncate(said, lay.log.width - 5 - display_width(who)), paint(role))
        else:
            buf.put(lay.log.x + 2, y, truncate(text, lay.log.width - 2), paint(role))


def hints(buf: CellBuffer, scene: Scene, pairs: list[tuple[str, str]]) -> None:
    x, limit = 1, scene.layout.width - 2
    for key, label in pairs:
        need = display_width(key) + 1 + display_width(label) + 2
        if x + need > limit:
            break
        buf.put(x, scene.layout.hint, key, scene.paint("hint_key", bold=True))
        buf.put(x + display_width(key) + 1, scene.layout.hint, label, scene.paint("hint_text"))
        x += need


# ---------------------------------------------------------------- zone

class ZoneArt:
    """Per-zone dressing resolved to cells: the proposed `dress` layer."""

    def __init__(self, data: dict[str, Any], zone_id: str, grid: list[str]) -> None:
        self.spec = data["zones"][zone_id]
        self.themes = data["themes"]
        self.grid = grid
        self.signs: dict[tuple[int, int], tuple[str, str]] = {}
        for sign in self.spec.get("signs", []):
            x, y = sign["at"]
            for i, ch in enumerate(sign["text"]):
                if self.char(x + i, y) == "#":  # signs only ever sit on wall cells
                    self.signs[(x + i, y)] = (ch, sign["role"])
        self.marks: dict[tuple[int, int], tuple[str, str]] = {}
        for mark in self.spec.get("marks", []):
            if "line" in mark:
                (ax, ay), (bx, by) = mark["line"]
                cells = [(x, ay) for x in range(ax, bx + 1)] if ay == by else [(ax, y) for y in range(ay, by + 1)]
                for cell in cells:
                    self.put_mark(cell, mark["glyph"], mark["role"])
            else:
                x, y = mark["at"]
                for i, ch in enumerate(mark["text"]):
                    self.put_mark((x + i, y), ch, mark["role"])
        self.glints = {tuple(c) for c in self.spec.get("water_glints", [])}

    def char(self, x: int, y: int) -> str:
        return self.grid[y][x] if 0 <= y < len(self.grid) and 0 <= x < len(self.grid[y]) else " "

    def put_mark(self, cell: tuple[int, int], glyph: str, role: str) -> None:
        assert glyph in DRESS_GLYPHS, glyph
        if self.char(*cell) == ".":  # marks only on plain floor
            self.marks[cell] = (glyph, role)

    def theme(self, x: int, y: int) -> dict[str, Any]:
        chosen = self.themes[self.spec["theme"]]
        for region in self.spec.get("regions", []):
            if "rect" in region:
                rx, ry, rw, rh = region["rect"]
                inside = rx <= x < rx + rw and ry <= y < ry + rh
            else:
                cx, cy, r = region["circle"]
                inside = (x - cx) ** 2 + ((y - cy) * 2) ** 2 <= (r * 2) ** 2
            if inside:
                chosen = {**chosen, **self.themes[region["theme"]]}
        return chosen

    def ground(self, x: int, y: int, theme: dict[str, Any], tier: str) -> str:
        if tier == "16":
            return "·"
        if theme.get("pattern") == "rings":
            cx, cy = theme["centre"]
            ring = int(max(abs(x - cx) / 2, abs(y - cy)))
            return theme["glyphs"][ring % 2] if (x + y) % 2 == 0 else " "
        texture = theme.get("texture", ["·"])
        return texture[stable(x, y) % len(texture)]


def actor_role(entry: dict[str, Any], light: bool) -> str:
    role = entry.get("role", "npc_neutral")
    if role == "player_self":
        return role
    if role.startswith("npc_"):
        base = role if role in ("npc_wardens", "npc_sablier", "npc_sable", "npc_hostile") else "npc_neutral"
    else:
        base = "player_other"
    return base + "@light" if light and base + "@light" in ACTIVE_ROLES else base


ACTIVE_ROLES: set[str] = set()


def render_zone(buf: CellBuffer, scene: Scene, body: dict[str, Any], art: ZoneArt, static: list[dict[str, Any]],
                focus: str | None = None) -> None:
    paint, area, tier = scene.paint, scene.layout.viewport, scene.tier
    ACTIVE_ROLES.update(scene.data["roles"])
    vp, legend = body["viewport"], body["legend"]
    tiles, memory = body["tiles"], body.get("remembered", [])
    charted = art.spec.get("charted", False)
    ids = {"#": "wall", ".": "floor", ";": "cover-1", "%": "cover-2", "&": "cover-3", "+": "door", "=": "locked-door",
           "T": "terminal", "R": "relay", ">": "exit", "~": "water", "!": "hazard", "$": "vendor", "V": "vat",
           "L": "light", "H": "hardware"}
    things = {(o["tile"][0], o["tile"][1]): o for o in static}
    for vy in range(min(area.height, vp["h"])):
        for vx in range(min(area.width, vp["w"])):
            zx, zy = vp["x"] + vx, vp["y"] + vy
            sx, sy = area.x + vx, area.y + vy
            state = tiles[vy][vx]
            if state >= 0:
                tile, now = legend[state]["id"], True
            elif state == -2:
                tile, now = legend[memory[vy][vx]]["id"], False
            elif charted:
                tile, now = ids.get(art.char(zx, zy), "floor"), False
            else:
                continue
            glyph, style = terrain_cell(paint, art, legend, tile, zx, zy, tier)
            if not now:
                if tile == "floor" and (zx, zy) in things:  # public anchors are part of charted geometry
                    o = things[(zx, zy)]
                    glyph = OBJECT_GLYPHS.get(o["kind"], "?")
                    style = Style(paint.value(THING_ROLES.get(o["kind"], "text")), style.bg if tier != "16" else 0, (), tier)
                if tier == "16" and tile == "floor" and glyph == "·":
                    glyph = "·" if stable(zx, zy) % 3 == 0 else " "  # known ground: sparse, grey
                style = paint.known(style)
            buf.put(sx, sy, glyph, style)
    for obj in body.get("objects", []):
        x, y = obj["x"] - vp["x"], obj["y"] - vp["y"]
        if 0 <= x < min(area.width, vp["w"]) and 0 <= y < min(area.height, vp["h"]):
            theme = art.theme(obj["x"], obj["y"])
            light = theme.get("luma") == "light"
            role = THING_ROLES.get(obj["kind"], "text")
            role = role + "@light" if light and role + "@light" in ACTIVE_ROLES else role
            glyph = obj["glyph"] if obj["glyph"] != "·" else OBJECT_GLYPHS.get(obj["kind"], "?")
            if obj["id"] == focus:
                buf.put(area.x + x, area.y + y, glyph, paint(role, theme.get("bg", "black"), bold=True, reverse=True))
            else:
                buf.put(area.x + x, area.y + y, glyph, paint(role, theme.get("bg", "black"), bold=True))
    for entry in body.get("actors", []):
        x, y = entry["x"] - vp["x"], entry["y"] - vp["y"]
        if not (0 <= x < min(area.width, vp["w"]) and 0 <= y < min(area.height, vp["h"])):
            continue
        theme = art.theme(entry["x"], entry["y"])
        if entry["role"] == "player_self":
            buf.put(area.x + x, area.y + y, "@", paint("self_fg", "self_bg", bold=True))
            continue
        glyph = "τ" if "drone" in entry.get("name", "").lower() else entry["glyph"]
        role = actor_role(entry, theme.get("luma") == "light")
        # Hostility is an attribute, not only a hue: hostile people are reverse video.
        hostile = role.startswith("npc_hostile")
        buf.put(area.x + x, area.y + y, glyph, paint(role, theme.get("bg", "black"), bold=True, reverse=hostile))


def legend_glyph(legend: list[dict[str, Any]], tile: str) -> str:
    return next((e["glyph"] for e in legend if e["id"] == tile), "?")


TILE_GLYPHS = {"cover-1": "░", "cover-2": "▒", "cover-3": "▓", "door": "+", "locked-door": "≡", "terminal": "§",
               "relay": "Ω", "exit": "»", "hazard": "‼", "vendor": "$", "vat": "Θ", "light": "☼", "hardware": "■",
               "water": "≈", "floor": "·", "wall": "█"}


def terrain_cell(paint: Paint, art: ZoneArt, legend: list[dict[str, Any]], tile: str, x: int, y: int,
                 tier: str) -> tuple[str, Style]:
    """One terrain cell, fully lit. Shape from the rule tile; colour from the place."""
    theme = art.theme(x, y)
    base = art.themes[art.spec["theme"]]
    light = theme.get("luma") == "light"
    bg = theme.get("bg", base["bg"])
    if tile == "wall":
        sign = art.signs.get((x, y))
        wall_bg = theme.get("wall_bg") or base["wall_bg"]
        if sign:
            return sign[0], paint(sign[1], wall_bg, bold=True)
        if tier == "16":
            return "█", paint(theme.get("wall_fg") or base["wall_fg"])
        return " ", paint("black", wall_bg)
    if tile == "water":
        return "≈", paint("ring_glint" if (x, y) in art.glints else theme["fg"], theme["bg"])
    if tile == "floor":
        mark = art.marks.get((x, y))
        if mark:
            return mark[0], paint(mark[1], bg)
        return art.ground(x, y, theme, tier), paint(theme["fg"], bg)
    glyph = legend_glyph(legend, tile) if legend else TILE_GLYPHS.get(tile, "?")
    if tile.startswith("cover"):
        return glyph, paint("thing_cover", bg)
    role = THING_ROLES.get(tile, "text")
    role = role + "@light" if light and role + "@light" in ACTIVE_ROLES else role
    return glyph, paint(role, bg, bold=True)


# ---------------------------------------------------------------- side panel

def zone_panel(buf: CellBuffer, scene: Scene, body: dict[str, Any], here: list[str],
               nearby: list[tuple[str, str, str]], wide: bool) -> None:
    """nearby: (glyph, role, text). Vitals are pinned to the bottom."""
    lay, paint = scene.layout, scene.paint
    x, w, top, bottom = lay.side.x, lay.side.width, lay.side.y, lay.side.y + lay.side.height - 1
    me = body["me"]
    vitals = 6 if wide else 5
    vy = bottom - vitals + 1
    y = top
    if here:
        rule(buf, scene, y, "HERE")
        y += 1
        for line in here:
            if y >= vy - 1:
                break
            key, _, rest = line.partition(" ")
            if len(key) == 1:
                buf.put(x + 1, y, key, paint("hint_key", bold=True))
                buf.put(x + 3, y, truncate(rest, w - 3), paint("text"))
            else:
                buf.put(x + 1, y, truncate(line, w - 1), paint("text"))
            y += 1
    rule(buf, scene, y, "TARGET")
    y += 1
    target = body.get("target")
    buf.put(x + 1, y, "none   Tab picks" if not target else truncate(target["name"], w - 1), paint("dim"))
    y += 1
    if nearby and y < vy - 2:
        rule(buf, scene, y, "NEARBY")
        y += 1
        for glyph, role, text in nearby:
            if y >= vy - 1:
                break
            buf.put(x + 1, y, glyph, paint(role, bold=True))
            buf.put(x + 3, y, truncate(text, w - 3), paint("text"))
            y += 1
    rule(buf, scene, vy - 1, "")
    name = me["name"] if me["name"] == me["handle"] else f"{me['name']} · {me['handle']}"
    buf.put(x + 1, vy, truncate(name, w - 6), paint("strong", bold=True))
    buf.put(x + w - 4, vy, f"G{me['grade']}", paint("label"))
    bar(buf, scene, x + 1, vy + 1, "HP", me["hp"], me["hp_max"], "bar_hp", str(me["hp"]))
    bar(buf, scene, x + 1, vy + 2, "STA", me["sta"], me["sta_max"], "bar_sta", str(me["sta"]))
    bar(buf, scene, x + 1, vy + 3, "SHK", me["shock"], 100, "bar_shock", f"{me['shock']:g}")
    buf.put(x + 1, vy + 4, f"{me['chits']} ch", paint("text"))
    buf.put(x + 10, vy + 4, f"lease {me['lease_days']}/90", paint("label"))
    if wide:
        buf.put(x + 1, vy + 5, f"discharge {me['xp']}/{me['discharge_xp']}", paint("label"))


# ---------------------------------------------------------------- lattice

def render_lattice(buf: CellBuffer, scene: Scene, body: dict[str, Any], sector: dict[str, Any],
                   cores: dict[str, dict[str, Any]]) -> None:
    paint, area = scene.paint, scene.layout.viewport
    cells = {c["id"]: c for c in body["cells"] if c.get("known", True)}
    cols = 1 + max(c["x"] for c in cells.values())
    rows = 1 + max(c["y"] for c in cells.values())
    sx = (area.width - 4) // max(1, cols - 1) if cols > 1 else 0
    sy = min(4, (area.height - 4) // max(1, rows - 1))
    def pos(c: dict[str, Any]) -> tuple[int, int]:
        return area.x + 2 + c["x"] * sx, area.y + 1 + c["y"] * sy
    here = body["me"]["cell"]
    for y in range(area.y, area.y + area.height - 3, 2):  # the old engineers' grid, faintly
        for x in range(area.x + 2, area.x + area.width - 1, 4):
            buf.put(x, y, "·", paint("lat_field"))
    for edge in body["edges"]:
        a, b = cells.get(edge["a"]), cells.get(edge["b"])
        if not a or not b:
            continue
        (ax, ay), (bx, by) = pos(a), pos(b)
        gated = edge["kind"] == "gated" or "gated" in (a["kind"], b["kind"])
        hidden = edge["kind"] == "hidden"
        role = "lat_gated" if gated else "lat_link"
        if ay == by:
            glyph = "·" if hidden else "═" if gated else "─"
            for x in range(min(ax, bx) + 2, max(ax, bx) - 1):
                buf.put(x, ay, glyph, paint(role))
        else:
            glyph = ":" if hidden else "║" if gated else "│"
            for y in range(min(ay, by) + 1, max(ay, by)):
                buf.put(ax, y, glyph, paint(role))
    for c in cells.values():
        x, y = pos(c)
        me = c["id"] == here
        if c["kind"] == "core_entrance":
            core = cores.get(c["core"], {})
            initial = sector["core_initials"].get(c["core"], "?")
            tier = str(core.get("tier", "?"))
            style = paint("lat_core", bold=True)
            hs = paint("lat_here_fg", "lat_here_bg") if me else style
            buf.put(x - 1, y - 1, "╔═╗", style)
            buf.put(x - 1, y, "║", style)
            buf.put(x, y, initial, hs)
            buf.put(x + 1, y, "║", style)
            buf.put(x - 1, y + 1, "╚", style)
            buf.put(x, y + 1, tier, paint("lat_core_tier", bold=True))
            buf.put(x + 1, y + 1, "╝", style)
        else:
            glyph, role = {"public": ("■", "lat_lit"), "gated": ("╪", "lat_gated"), "hidden": ("∙", "lat_gated"),
                           "descent": ("∞", "lat_descent")}.get(c["kind"], ("■", "lat_lit"))
            if c.get("uplink"):
                glyph = "∩"
            if me:
                buf.put(x - 1, y, f" {glyph} ", paint("lat_here_fg", "lat_here_bg", bold=True))
            else:
                buf.put(x, y, glyph, paint(role, bold=role == "lat_lit"))
    # caption: where you are and where the links go, in words
    cur = cells[here]
    cy = area.y + area.height - 3
    core = cores.get(cur.get("core") or "", {})
    kind = "core entrance" if core else cur["kind"] + " cell"
    buf.put(area.x + 1, cy, truncate(f"@ {cur['label']}", area.width - 2), paint("lat_caption", bold=True))
    buf.put(area.x + 4 + display_width(cur["label"]), cy, truncate(kind, area.width - 6 - display_width(cur["label"])), paint("dim"))
    links = []
    for n in sorted(cells.values(), key=lambda c: (c["y"], c["x"])):
        if any({e["a"], e["b"]} == {here, n["id"]} for e in body["edges"]):
            d = "<" if n["x"] < cur["x"] else ">" if n["x"] > cur["x"] else "^" if n["y"] < cur["y"] else "v"
            links.append(f"{d} {n['label']}")
    line, row = "", cy + 1
    for link in links:
        if line and display_width(line + "   " + link) > area.width - 2:
            buf.put(area.x + 1, row, line, paint("text"))
            line, row = "", row + 1
        line = f"{line}   {link}" if line else link
    if row < area.y + area.height:
        buf.put(area.x + 1, row, truncate(line, area.width - 2), paint("text"))


def lattice_panel(buf: CellBuffer, scene: Scene, body: dict[str, Any], body_zone: str,
                  core: dict[str, Any] | None, trace_note: str) -> None:
    lay, paint = scene.layout, scene.paint
    x, w, y = lay.side.x, lay.side.width, lay.side.y
    me = body["me"]
    rule(buf, scene, y, "RUNNER")
    bar(buf, scene, x + 1, y + 1, "INT", me["integrity"], me["integrity_max"], "bar_int", f"{me['integrity']:g}")
    bar(buf, scene, x + 1, y + 2, "TRC", me["trace"], 100, "bar_trace", f"{me['trace']:g}", ticks=(5,))
    buf.put(x + 1, y + 3, truncate(trace_note, w - 1), paint("label"))
    rule(buf, scene, y + 4, "BODY")
    safety = body["body_safety"]
    buf.put(x + 1, y + 5, truncate(body_zone, w - 9), paint("text"))
    buf.put(x + w - 1 - len(safety), y + 5, safety.upper(), paint("word_" + safety, bold=True))
    bar(buf, scene, x + 1, y + 6, "HP", me["body_hp"], me["body_hp_max"], "bar_hp", str(me["body_hp"]))
    buf.put(x + 1, y + 7, "alone: no crew guard", paint("label"))
    rule(buf, scene, y + 8, "RIG")
    for i, slot in enumerate(me["rig"][:3]):
        name = slot["name"] if slot["program"] else "-"
        buf.put(x + 1, y + 9 + i, str(slot["slot"]), paint("hint_key", bold=True))
        buf.put(x + 3, y + 9 + i, name, paint("text" if slot["program"] else "dim"))
        if slot["program"]:
            buf.put(x + w - 6, y + 9 + i, "ready", paint("bar_hp"))
    if core:
        rule(buf, scene, y + 12, "CORE")
        buf.put(x + 1, y + 13, truncate(core["name"], w - 1), paint("lat_core", bold=True))
        buf.put(x + 1, y + 14, f"{core['owner'].title()} · tier {core['tier']}", paint("text"))
        buf.put(x + 1, y + 15, f"trace: {core.get('trace_policy', '')}", paint("label"))
        buf.put(x + 1, y + 16, "ICE unknown: survey", paint("label"))
