"""Street view: Karst at eye level (paradigm prototype A).

A grid raycaster over the authorized ZoneView. Every pixel comes from a
tile the server sent: seen tiles are lit, remembered tiles are dim, and
unknown space is darkness, so the view knows exactly what the map knows.
People and things stand where the server says they are. Facing is the
client's; a step forward is an ordinary absolute move (the door
translates it), so the simulation does not know or care how you look.

Each terminal cell holds two pixels (`▀`, foreground above, background
below). Sign letters and names are drawn as text over the pixels.
"""

import math
from dataclasses import dataclass, field
from typing import Any

from blacksite.door.cells import CellBuffer, display_width, truncate
from blacksite.door.layout import Rect
from blacksite.door.palette import Style
from blacksite.door.present.paint import XTERM, Paint

RGB = tuple[int, int, int]
HEADINGS = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0)}
TURN_RIGHT = {"up": "right", "right": "down", "down": "left", "left": "up"}
TURN_LEFT = {v: k for k, v in TURN_RIGHT.items()}
BEHIND = {"up": "down", "down": "up", "left": "right", "right": "left"}
COMPASS = {"up": "north", "right": "east", "down": "south", "left": "west"}
OPAQUE = {"wall", "locked-door"}
FOV = 0.66
MAX_DEPTH = 26
STOREYS = 2.4  # buildings stand this many tiles tall: a street, not a maze
BASE16 = [XTERM[i] for i in range(16)]


def cardinal(facing: str | None) -> str:
    """The server's last move direction, rounded to a street heading."""
    facing = facing or "up"
    return facing if facing in HEADINGS else facing.split("_")[0] if facing.split("_")[0] in HEADINGS else "up"


@dataclass
class Colours:
    paint: Paint
    cache: dict[str, RGB] = field(default_factory=dict)

    def __call__(self, role: str | None, fallback: RGB = (60, 60, 60)) -> RGB:
        if not role:
            return fallback
        if role not in self.cache:
            raw = self.paint.palette.roles.get(role, {}).get("truecolor", {})
            value = raw.get(self.paint.palette.variant, raw.get("default"))
            self.cache[role] = tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)) if isinstance(value, str) else fallback
        return self.cache[role]


def shade(rgb: RGB, factor: float) -> RGB:
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)  # type: ignore[return-value]


def mix(a: RGB, b: RGB, t: float) -> RGB:
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


class Quantiser:
    """Pixels to terminal colours for one tier."""

    def __init__(self, tier: str) -> None:
        self.tier = tier
        self.cache: dict[tuple[RGB, bool], int] = {}

    def __call__(self, rgb: RGB, background: bool) -> int | RGB:
        if self.tier == "truecolor":
            return rgb
        key = ((rgb[0] // 4 * 4, rgb[1] // 4 * 4, rgb[2] // 4 * 4), background)
        if key not in self.cache:
            if self.tier == "256":
                pool = range(16, 256)
                self.cache[key] = min(pool, key=lambda i: sum((a - b) ** 2 for a, b in zip(XTERM[i], key[0])))
            else:
                # Sixteen colours cannot shade, so light decides first: dark
                # is black, dim is grey, and only bright pixels keep a hue.
                r, g, b = key[0]
                light, chroma = (r + g + b) / 3, max(r, g, b) - min(r, g, b)
                if light < 30:
                    self.cache[key] = 0
                elif light < 96 and chroma < 110:
                    self.cache[key] = 8 if not background else 0
                else:
                    pool = range(8) if background else range(16)
                    self.cache[key] = min(pool, key=lambda i: sum((a - b) ** 2 for a, b in zip(BASE16[i], key[0])))
        return self.cache[key]


class World:
    """The view's tiles, looks and people, addressed in zone coordinates."""

    def __init__(self, body: dict[str, Any]) -> None:
        self.vp = body["viewport"]
        self.tiles, self.memory, self.legend = body["tiles"], body.get("remembered", []), body["legend"]
        self.looks, self.looks_legend = body.get("looks", []), body.get("looks_legend", [])
        self.hazard = {tuple(t) for h in body.get("hazards", []) for t in h.get("tiles", [])}

    def at(self, x: int, y: int) -> tuple[str | None, int, dict[str, Any]]:
        """(tile id or None if unknown, 1 seen / 0 remembered, look)."""
        vx, vy = x - self.vp["x"], y - self.vp["y"]
        if not (0 <= vy < len(self.tiles) and 0 <= vx < len(self.tiles[vy])):
            return None, 0, {}
        state = self.tiles[vy][vx]
        if state == -1:
            return None, 0, {}
        index = state if state >= 0 else self.memory[vy][vx]
        if not 0 <= index < len(self.legend):
            return None, 0, {}
        look_index = self.looks[vy][vx] if vy < len(self.looks) and vx < len(self.looks[vy]) else -1
        look = self.looks_legend[look_index] if 0 <= look_index < len(self.looks_legend) else {}
        return self.legend[index]["id"], 1 if state >= 0 else 0, look


SPRITES = {  # kind: (role, width, height, lift) in tile units
    "terminal": ("thing_terminal", 0.25, 0.55, 0.0), "descent_console": ("thing_terminal", 0.3, 0.5, 0.0),
    "vendor": ("thing_vendor", 0.7, 0.4, 0.0), "bank": ("thing_vendor", 0.8, 0.45, 0.0),
    "hardware": ("thing_hardware", 0.4, 0.5, 0.0), "relay": ("thing_terminal", 0.35, 0.7, 0.0),
    "light": ("thing_light", 0.08, 1.1, 0.0), "vat": ("thing_vat", 0.5, 0.8, 0.0),
    "cache": ("thing_vendor", 0.25, 0.15, 0.0), "door": ("thing_door", 0.9, 0.85, 0.0),
    "beacon": ("player_crew", 0.1, 0.2, 0.9),
}


def render(buffer: CellBuffer, body: dict[str, Any], area: Rect, paint: Paint, heading: str,
           hud: bool = True) -> None:
    colours, quant = Colours(paint), Quantiser(paint.tier)
    world = World(body)
    me = next((a for a in body.get("actors", []) if a.get("role") == "player_self"), None)
    if me is None:
        return
    rows = area.height - (1 if hud else 0)
    width, height = area.width, rows * 2
    px, py = me["x"] + 0.5, me["y"] + 0.5
    dx, dy = HEADINGS[heading]
    plane_x, plane_y = -dy * FOV, dx * FOV
    base_angle = {"up": 0, "right": 90, "down": 180, "left": 270}[heading]
    horizon = height // 2
    pixels: list[list[RGB]] = [[(0, 0, 0)] * width for _ in range(height)]
    depth = [float(MAX_DEPTH)] * width
    labels: list[tuple[int, int, str, str, float]] = []  # column, row, text, role, distance

    # Sky: the Ring over Karst (bible 2: the sky is the antagonist's clock).
    for x in range(width):
        camera = 2 * x / width - 1
        angle = math.radians(base_angle) + math.atan(camera * FOV)
        ring_y = int(height * (0.16 + 0.06 * math.sin(angle * 2 + 0.7)))
        for y in range(horizon):
            pixels[y][x] = mix((4, 5, 14), (22, 18, 34), y / max(1, horizon))
        seed = (int(math.degrees(angle) * 3) * 2654435761) & 0xFFFF
        if seed % 5 == 0 and 0 <= ring_y < horizon:
            pixels[ring_y][x] = (200, 190, 170) if seed % 3 else (120, 110, 100)
        elif seed % 7 == 0 and 0 <= ring_y + 1 < horizon:
            pixels[ring_y + 1][x] = (70, 64, 60)

    floor_limit = [float(MAX_DEPTH)] * width
    signs: dict[tuple[int, int], list[tuple[int, int, str, str, float]]] = {}
    for x in range(width):
        camera = 2 * x / width - 1
        rx, ry = dx + plane_x * camera, dy + plane_y * camera
        mx, my = int(px), int(py)
        delta_x = abs(1 / rx) if rx else 1e30
        delta_y = abs(1 / ry) if ry else 1e30
        step_x, side_x = (-1, (px - mx) * delta_x) if rx < 0 else (1, (mx + 1 - px) * delta_x)
        step_y, side_y = (-1, (py - my) * delta_y) if ry < 0 else (1, (my + 1 - py) * delta_y)
        hit, side, distance = None, 0, float(MAX_DEPTH)
        for _ in range(MAX_DEPTH * 2):
            if side_x < side_y:
                side_x, mx, side = side_x + delta_x, mx + step_x, 0
            else:
                side_y, my, side = side_y + delta_y, my + step_y, 1
            tile, seen, look = world.at(mx, my)
            distance = (side_x - delta_x) if side == 0 else (side_y - delta_y)
            if tile is None:
                floor_limit[x] = distance  # the edge of what you know: darkness
                break
            if tile in OPAQUE:
                hit = (tile, seen, look, mx, my)
                break
            if distance > MAX_DEPTH:
                break
        if hit is None:
            continue
        tile, seen, look, hx, hy = hit
        distance = max(0.05, distance)
        depth[x] = floor_limit[x] = distance
        line = int(height / distance)
        base = horizon + line // 2
        tall = int(line * STOREYS)
        top, bottom = max(0, base - tall), min(height - 1, base)
        face = colours(look.get("bg") if look.get("bg") != "ground_black" else None, (70, 72, 80))
        if tile == "locked-door":
            face = colours("thing_door")
        sign = look.get("g") if tile == "wall" and look.get("g", " ").strip() else None
        light = max(0.22, 1 - distance / (MAX_DEPTH * 0.9)) * (0.78 if side else 1.0) * (1.0 if seen else 0.5)
        wall_x = (py + distance * ry) if side == 0 else (px + distance * rx)
        wall_x -= math.floor(wall_x)
        # v runs from the roofline (0) to the pavement (1). Signs hang at
        # street height; upper storeys get windows, some of them lit.
        sign_band = (1 - 0.62 / STOREYS, 1 - 0.3 / STOREYS)
        dark_district = not look.get("light")
        for y in range(top, bottom + 1):
            v = (y - (base - tall)) / max(1, tall)
            colour, glow = face, False
            if v < 0.03:
                colour = mix(face, (0, 0, 0), 0.55)  # the roofline against the sky
            elif sign and sign_band[0] < v < sign_band[1]:
                colour, glow = colours(look.get("fg"), (255, 120, 200)), True
            elif v < sign_band[0] - 0.05 and 0.18 < (wall_x * 2) % 1 < 0.62 and (v * 6) % 1 < 0.55:
                storey = int(v * 6)
                lit = (hx * 7 + hy * 13 + storey * 5 + int(wall_x * 2)) % 5 == 0
                colour = (200, 160, 90) if lit and dark_district else mix(face, (0, 0, 0), 0.45)
                glow = lit and dark_district
            pixels[y][x] = shade(colour, max(light, 0.7 if seen else 0.4) if glow else light)
        if sign:
            signs.setdefault((hx, hy), []).append((x, (base - int(tall * (sign_band[0] + sign_band[1]) / 2)) // 2,
                                                   sign, look.get("fg") or "panel_text", distance))

    for cells in signs.values():  # one letter per sign cell, at its middle
        if len(cells) >= 2:
            column, row, char, role, distance = cells[len(cells) // 2]
            labels.append((column, row, char, role, distance))

    # The ground: floor casting over known tiles, dark beyond them.
    for y in range(horizon + 1, height):
        row_distance = height / (2.0 * y - height)
        for x in range(width):
            if row_distance > floor_limit[x]:
                if floor_limit[x] == depth[x] and depth[x] < MAX_DEPTH:
                    continue  # a wall stands here; keep its lower storeys
                pixels[y][x] = (3, 3, 5)
                continue
            camera = 2 * x / width - 1
            fx = px + row_distance * (dx + plane_x * camera)
            fy = py + row_distance * (dy + plane_y * camera)
            tile, seen, look = world.at(int(fx), int(fy))
            if tile is None:
                pixels[y][x] = (3, 3, 5)
                continue
            role = look.get("bg")
            colour = colours(role, (40, 40, 46))
            if tile.startswith("cover"):
                colour = colours("thing_cover")
            elif tile == "water":
                colour = mix(colours(role, (10, 30, 80)), colours(look.get("fg"), (40, 120, 255)), 0.35)
            elif tile == "exit":
                colour = mix(colour, (220, 220, 220), 0.35)
            elif (int(fx), int(fy)) in world.hazard:
                colour = (150, 30, 20)
            elif look.get("g", " ").strip() and row_distance > 1.5 and (fx * 4 % 1 < 0.2 and fy * 4 % 1 < 0.2):
                colour = mix(colour, colours(look.get("fg")), 0.3)  # grain and paint, faint
            light = max(0.18, 1 - row_distance / (MAX_DEPTH * 0.8)) * (1.0 if seen else 0.5)
            pixels[y][x] = shade(colour, light)

    # People and things, far to near, behind walls where walls are nearer.
    inverse = 1.0 / (plane_x * dy - dx * plane_y)
    relation = {n["id"]: n.get("relation", "~") for n in body.get("nearby", [])}
    sprites = []
    for obj in body.get("objects", []):
        role, w, h, lift = SPRITES.get(obj.get("kind", ""), ("panel_text", 0.3, 0.3, 0.0))
        sprites.append((obj["x"] + 0.5, obj["y"] + 0.5, role, w, h, lift, str(obj.get("name") or ""), False))
    for actor in body.get("actors", []):
        if actor is me:
            continue
        hostile = relation.get(actor["id"]) == "!"
        name = next((n.get("name", "") for n in body.get("nearby", []) if n["id"] == actor["id"]), "")
        tall = 0.45 if actor.get("kind") == "drone" else 0.8
        lift = 0.35 if actor.get("kind") == "drone" else 0.0
        sprites.append((actor["x"] + 0.5, actor["y"] + 0.5, actor.get("role", "npc_neutral"), 0.32, tall, lift, name, hostile))
    sprites.sort(key=lambda s: -((s[0] - px) ** 2 + (s[1] - py) ** 2))
    for sx, sy, role, w, h, lift, name, hostile in sprites:
        rel_x, rel_y = sx - px, sy - py
        tx = inverse * (dy * rel_x - dx * rel_y)
        ty = inverse * (-plane_y * rel_x + plane_x * rel_y)
        if ty <= 0.2:
            continue
        screen_x = int(width / 2 * (1 + tx / ty))
        size = height / ty
        sprite_h, sprite_w = max(1, int(size * h)), max(1, int(size * w))
        floor_y = horizon + int(size / 2)
        top = floor_y - sprite_h - int(size * lift)
        colour = colours(role, (200, 200, 200))
        light = max(0.35, 1 - ty / (MAX_DEPTH * 0.9))
        for x in range(screen_x - sprite_w // 2, screen_x + sprite_w // 2 + 1):
            if not 0 <= x < width or ty >= depth[x]:
                continue
            for y in range(max(0, top), min(height, top + sprite_h)):
                head = y < top + max(1, sprite_h // 5)
                tint = mix(colour, (255, 255, 255), 0.35) if head else colour
                if hostile and (y - top) % 3 == 0:
                    tint = (255, 60, 50)
                pixels[y][x] = shade(tint, light)
        if name and ty < 9 and 0 <= screen_x < width:
            labels.append((screen_x, max(0, top // 2 - 1), name, "log_danger" if hostile else role, ty))

    # Pixels to cells.
    for row in range(rows):
        for x in range(width):
            top, bottom = pixels[row * 2][x], pixels[row * 2 + 1][x]
            if paint.tier == "16":
                # Backgrounds stop at colour 7, so half-cells would lose the
                # greys that carry buildings. Whole cells, one colour each.
                colour = quant(mix(top, bottom, 0.5), False)
                buffer.put(area.x + x, area.y + row, "█" if colour else " ", Style(colour, 0, (), "16"))
                continue
            buffer.put(area.x + x, area.y + row, "▀", Style(quant(top, False), quant(bottom, True), (), paint.tier))
    taken: set[tuple[int, int]] = set()
    for column, row, text, role, distance in sorted(labels, key=lambda item: item[4]):
        text = truncate(text, 16)
        start = max(0, min(width - display_width(text), column - display_width(text) // 2))
        cells = {(start + i, row) for i in range(display_width(text))}
        if row >= rows or cells & taken:
            continue
        taken |= cells
        buffer.put(area.x + start, area.y + row, text, paint(role, bold=True))
    if hud:
        hud_line(buffer, body, area, paint, heading, world, me)


def widest(body: dict[str, Any], prefer: str) -> str:
    """Where an establishing look should face: across the most open known
    ground to a facade still in view (a horizon with nothing on it is not
    a place). Ties keep the preferred heading."""
    world = World(body)
    me = next((a for a in body.get("actors", []) if a.get("role") == "player_self"), None)
    if me is None:
        return prefer

    def reach(heading: str) -> tuple[bool, int]:
        dx, dy = HEADINGS[heading]
        for step in range(1, MAX_DEPTH + 1):
            tile, _, _ = world.at(me["x"] + dx * step, me["y"] + dy * step)
            if tile in OPAQUE:
                return step >= 6, step  # a facade worth looking at, not a wall in your face
            if tile is None:
                return False, step
        return False, MAX_DEPTH

    order = [prefer, *(h for h in HEADINGS if h != prefer)]
    return max(order, key=reach)


def hud_line(buffer: CellBuffer, body: dict[str, Any], area: Rect, paint: Paint, heading: str, world: World,
             me: dict[str, Any]) -> None:
    """Under the view: which way you face, where you are, what is in front."""
    y = area.y + area.height - 1
    buffer.put(area.x, y, " " * area.width, paint("panel_text"))
    place = (body.get("place") or {}).get("here") or body["me"].get("zone_name", "")
    dx, dy = HEADINGS[heading]
    ahead = "open ground"
    for step in range(1, 6):
        tx, ty = me["x"] + dx * step, me["y"] + dy * step
        thing = next((o for o in body.get("objects", []) if (o["x"], o["y"]) == (tx, ty)), None)
        person = next((n for n in body.get("nearby", []) for a in body.get("actors", [])
                       if a["id"] == n["id"] and (a["x"], a["y"]) == (tx, ty)), None)
        tile, _, _ = world.at(tx, ty)
        if person:
            ahead = f"{person.get('name', 'someone')}, {step} m"
            break
        if thing:
            ahead = f"{thing.get('name') or thing.get('kind')}, {step} m"
            break
        if tile is None:
            ahead = "darkness"
            break
        if tile in OPAQUE:
            ahead = "a wall" + (f", {step} m" if step > 1 else "")
            break
        if tile == "exit":
            ahead = f"a way out, {step} m"
            break
    text = f"facing {COMPASS[heading]}  ·  {place}  ·  ahead: {ahead}"
    buffer.put(area.x + 1, y, truncate(text, area.width - 2), paint("panel_label"))


def radar(buffer: CellBuffer, body: dict[str, Any], area: Rect, paint: Paint, heading: str | None) -> None:
    """A small top-down view, turned so that ahead is up when facing is known."""
    world = World(body)
    me = next((a for a in body.get("actors", []) if a.get("role") == "player_self"), None)
    if me is None:
        return
    d = HEADINGS.get(heading or "up", (0, -1))
    right = (-d[1], d[0])
    people = {(a["x"], a["y"]): a for a in body.get("actors", [])}
    things = {(o["x"], o["y"]): o for o in body.get("objects", [])}
    relation = {n["id"]: n.get("relation", "~") for n in body.get("nearby", [])}
    cx, cy = area.width // 2, area.height // 2
    glyphs = {"wall": "█", "locked-door": "≡", "door": "+", "exit": "»", "water": "≈", "hazard": "‼",
              "cover-1": "░", "cover-2": "▒", "cover-3": "▓"}
    for ry in range(area.height):
        for rx in range(area.width):
            ox, oy = rx - cx, ry - cy
            wx = me["x"] + right[0] * ox - d[0] * oy
            wy = me["y"] + right[1] * ox - d[1] * oy
            tile, seen, _ = world.at(wx, wy)
            if tile is None:
                continue
            glyph, role = glyphs.get(tile, "·"), "panel_dim" if tile == "floor" else "panel_label"
            if (wx, wy) in things:
                obj = things[(wx, wy)]
                glyph, role = {"terminal": "§", "vendor": "$", "bank": "$", "hardware": "■", "light": "☼",
                               "door": "+", "relay": "Ω", "vat": "Θ"}.get(obj.get("kind", ""), "*"), "thing_terminal"
            if (wx, wy) in people and seen:
                actor = people[(wx, wy)]
                if actor.get("role") == "player_self":
                    buffer.put(area.x + rx, area.y + ry, "@", paint("self_fg", "self_bg", bold=True))
                    continue
                else:
                    glyph = "τ" if actor.get("kind") == "drone" else "☺" if actor.get("kind") == "player" else "☻"
                    role = "log_danger" if relation.get(actor["id"]) == "!" else actor.get("role", "npc_neutral")
            style = paint(role, bold=role != "panel_dim")
            buffer.put(area.x + rx, area.y + ry, glyph, style if seen else paint.known(style))
