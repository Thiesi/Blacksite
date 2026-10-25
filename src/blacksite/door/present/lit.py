"""Lit scenes: a place at eye level, drawn from its look (V0 spike, #68).

The street raycaster shades by distance. Here a place's look carries
lights and dressing (`scene` in the view body, trial only), and the
renderer lights every surface from them: walls, floor, ceiling and set
pieces take their colour from the lamps, screens and signs near them,
with haze in depth, glow around each light and its reflection on a wet
floor. The place reads before anything is said about it.

What it may draw is still the view's. Walls, floor and pieces come only
from tiles the server sent; unknown ground is dark. People are the
view's actors, where the server put them, and a faction mark comes from
the role the view already discloses. Nothing here is read by a rule.

Static parts are painted once per position, heading and size and kept;
a frame only adds people. Three outputs: sextants (2x3 pixels a cell,
the modern glyph tier), half-blocks (1x2) and, in 16 colours, whole
cells.
"""

import json
import math
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from blacksite.door.cells import CellBuffer, display_width
from blacksite.door.layout import Rect
from blacksite.door.palette import Style
from blacksite.door.present import street
from blacksite.door.present.paint import XTERM, Paint

RGB = tuple[float, float, float]
EYE = 1.6
"""Eye height in tile units."""
FOV = 0.8
"""Camera plane half-width: about 77 degrees across."""
HORIZON = 0.44
"""Where eye level sits, as a share of the view's height from the top."""
MAX_DEPTH = 48
GAIN = 4.0
BODY_HEIGHT = 1.75
REMEMBERED = 0.72
"""Known but not seen now: the same place, a little dimmer."""
DECAL_KINDS = frozenset({"shelf", "sign", "board", "doorway", "screens"})
SHAPED = frozenset({"cans", "ring"})


def rgb(value: str, fallback: RGB = (0.2, 0.2, 0.2)) -> RGB:
    if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
        return int(value[1:3], 16) / 255, int(value[3:5], 16) / 255, int(value[5:7], 16) / 255
    return fallback


def noise(*keys: int) -> float:
    """Stable 0..1 from integers: grain, bottles, dead segments."""
    h = 2166136261
    for k in keys:
        h = ((h ^ (k & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0x5BD1E995) & 0xFFFFFFFF
    return (h ^ (h >> 15)) / 0xFFFFFFFF


@dataclass
class Piece:
    kind: str
    x0: float
    y0: float
    x1: float
    y1: float
    z0: float
    z1: float
    colour: RGB
    glow: RGB | None
    text: str
    role: str
    decal: bool = False

    @property
    def centre(self) -> tuple[float, float]:
        return (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2


@dataclass
class Light:
    x: float
    y: float
    z: float
    colour: RGB
    reach: float


@dataclass
class Scene:
    """A body's `scene`, parsed once, with its lighting memo."""

    interior: bool
    ceiling: float
    walls: RGB
    floor: RGB
    wet: float
    ambient: RGB
    haze: RGB
    haze_reach: float
    lights: list[Light]
    pieces: list[Piece]
    by_tile: dict[tuple[int, int], list[int]] = field(default_factory=dict)
    memo: dict[tuple[int, int, int, int], RGB] = field(default_factory=dict)

    @classmethod
    def parse(cls, data: dict[str, Any], world: street.World) -> "Scene":
        pieces = []
        for p in data.get("pieces", []):
            x, y, w, h = p["rect"]
            piece = Piece(p["kind"], x, y, x + w, y + h, p["z"][0], p["z"][1], rgb(p.get("colour", ""), (0.25, 0.22, 0.2)),
                          rgb(p["glow"]) if p.get("glow") else None, p.get("text", ""), p.get("role", ""))
            tiles = list(footprint(piece))
            piece.decal = piece.kind in DECAL_KINDS and all(world.at(*t)[0] in street.OPAQUE for t in tiles)
            pieces.append(piece)
        scene = cls(bool(data.get("interior", True)), float(data.get("ceiling", 3.2)), rgb(data.get("walls", "")),
                    rgb(data.get("floor", "")), float(data.get("wet", 0)), rgb(data.get("ambient", ""), (0.04,) * 3),
                    rgb(data.get("haze", ""), (0, 0, 0)), float(data.get("haze_reach", 40)),
                    [Light(li["at"][0], li["at"][1], li["z"], tuple(c * li.get("power", 1) for c in rgb(li["colour"])),
                           li["reach"]) for li in data.get("lights", [])], pieces)
        for index, piece in enumerate(pieces):
            for tile in footprint(piece):
                scene.by_tile.setdefault(tile, []).append(index)
        return scene

    def light(self, x: float, y: float, z: float, normal: int) -> RGB:
        """Light arriving at a point, by surface normal (0 none, 1-4 the
        four wall faces, 5 up, 6 down). Memoised on a quarter-tile grid."""
        key = (round(x * 4), round(y * 4), round(z * 4), normal)
        hit = self.memo.get(key)
        if hit is not None:
            return hit
        qx, qy, qz = key[0] / 4, key[1] / 4, key[2] / 4
        nx, ny, nz = NORMALS[normal]
        r, g, b = self.ambient
        for li in self.lights:
            dx, dy, dz = li.x - qx, li.y - qy, li.z - qz
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if d >= li.reach:
                continue
            f = (1 - d / li.reach) ** 1.5
            if normal:
                facing = (nx * dx + ny * dy + nz * dz) / max(d, 1e-3)
                f *= 0.25 + 0.75 * max(0.0, facing)
            r, g, b = r + li.colour[0] * f, g + li.colour[1] * f, b + li.colour[2] * f
        self.memo[key] = (r, g, b)
        return r, g, b


NORMALS = {0: (0, 0, 0), 1: (-1, 0, 0), 2: (1, 0, 0), 3: (0, -1, 0), 4: (0, 1, 0), 5: (0, 0, 1), 6: (0, 0, -1)}


def footprint(piece: Piece) -> list[tuple[int, int]]:
    return [(tx, ty) for tx in range(int(piece.x0), int(piece.x1 - 1e-6) + 1)
            for ty in range(int(piece.y0), int(piece.y1 - 1e-6) + 1)]


def scene_of(body: dict[str, Any], world: street.World) -> Scene | None:
    data = body.get("scene")
    if not data:
        return None
    key = json.dumps(data, sort_keys=True)
    cached = _SCENES.get(key)
    if cached is None:
        cached = Scene.parse(data, world)
        _SCENES[key] = cached
        while len(_SCENES) > 4:
            _SCENES.popitem(last=False)
    return cached


_SCENES: "OrderedDict[str, Scene]" = OrderedDict()
_FRAMES: "OrderedDict[tuple[Any, ...], Frame]" = OrderedDict()


@dataclass
class Frame:
    """The static picture: pixels, depth, what each pixel is, sign text."""

    pixels: list[list[RGB]]
    depth: list[list[float]]
    labels: list[tuple[int, int, str, str, float]]


@dataclass
class Camera:
    px: float
    py: float
    dx: int
    dy: int
    width: int
    height: int
    focal_x: float
    focal_y: float
    horizon: float

    @property
    def plane(self) -> tuple[float, float]:
        return -self.dy * FOV, self.dx * FOV

    def project(self, x: float, y: float, z: float) -> tuple[float, float, float] | None:
        """Screen x, screen y, depth; None behind the eye."""
        rel_x, rel_y = x - self.px, y - self.py
        ahead = rel_x * self.dx + rel_y * self.dy
        if ahead <= 0.1:
            return None
        side = rel_x * -self.dy + rel_y * self.dx
        return (self.width / 2 * (1 + side / (ahead * FOV)), self.horizon - (z - EYE) * self.focal_y / ahead, ahead)


# --- the static picture -------------------------------------------------------


def paint_static(world: street.World, sc: Scene, cam: Camera) -> Frame:
    width, height = cam.width, cam.height
    pixels: list[list[RGB]] = [[(0.0, 0.0, 0.0)] * width for _ in range(height)]
    depth = [[float(MAX_DEPTH)] * width for _ in range(height)]
    plane_x, plane_y = cam.plane
    top = sc.ceiling if sc.interior else 6.0
    for col in range(width):
        camera = 2 * (col + 0.5) / width - 1
        rx, ry = cam.dx + plane_x * camera, cam.dy + plane_y * camera
        wall_t, wall_side, wall_tile, wall_seen, edge = march(world, sc, cam.px, cam.py, rx, ry)
        boxes = column_pieces(sc, cam.px, cam.py, rx, ry, wall_t)
        # Each piece covers a band of rows in this column: from its top
        # edge (near or far, whichever is higher) to its bottom edge.
        spans = []
        for t0, t1, normal, index in boxes:
            piece = sc.pieces[index]
            rows_at = [cam.horizon - (z - EYE) * cam.focal_y / t for z in (piece.z0, piece.z1) for t in (t0, t1)]
            spans.append((int(min(rows_at)) - 1, int(max(rows_at)) + 1, t0, t1, normal, index))
        for row in range(height):
            slope = (cam.horizon - (row + 0.5)) / cam.focal_y
            best_t, kind, data = wall_t if edge is None else float(MAX_DEPTH), "", None
            if edge is None:
                z = EYE + slope * wall_t
                if 0 <= z <= top:
                    kind, data = "wall", (wall_tile, wall_side, z)
                else:
                    best_t = float(MAX_DEPTH)
            if slope < 0:
                t = -EYE / slope
                if t < best_t:
                    best_t, kind, data = t, "floor", None
            elif slope > 0 and sc.interior:
                t = (sc.ceiling - EYE) / slope
                if t < best_t:
                    best_t, kind, data = t, "ceiling", None
            for low, high, t0, t1, normal, index in spans:
                if not low <= row <= high or t0 >= best_t:
                    continue
                piece = sc.pieces[index]
                z = EYE + slope * t0
                hit = None
                if piece.z0 <= z <= piece.z1 and piece.kind not in SHAPED:
                    hit = (t0, normal, z)
                elif slope < 0 and piece.z1 < EYE:
                    t = (piece.z1 - EYE) / slope
                    if t0 <= t <= t1:
                        hit = (t, 5, piece.z1)
                elif slope > 0 and piece.z0 > EYE:
                    t = (piece.z0 - EYE) / slope
                    if t0 <= t <= t1:
                        hit = (t, 6, piece.z0)
                if hit is None or hit[0] >= best_t:
                    continue
                if piece.kind in SHAPED and not shaped(piece, cam.px + rx * hit[0], cam.py + ry * hit[0]):
                    continue
                best_t, kind, data = hit[0], "piece", (index, hit[1], hit[2])
            if not kind:
                continue  # darkness: beyond what you know
            x, y = cam.px + rx * best_t, cam.py + ry * best_t
            tile, seen, _ = world.at(int(math.floor(x)), int(math.floor(y)))
            if kind == "floor" and (tile is None or (edge is not None and best_t > edge)):
                continue
            colour = shade(sc, kind, data, x, y, best_t, row, col)
            if kind != "wall" and not seen:
                colour = tuple(c * REMEMBERED for c in colour)
            elif kind == "wall" and not wall_seen:
                colour = tuple(c * REMEMBERED for c in colour)
            fog = 1 - math.exp(-best_t / sc.haze_reach)
            pixels[row][col] = tuple(c + (h - c) * fog for c, h in zip(colour, sc.haze))  # type: ignore[assignment]
            depth[row][col] = best_t
    glow(sc, cam, pixels, depth)
    return Frame(pixels, depth, sign_labels(world, sc, cam, depth))


def march(world: street.World, sc: Scene, px: float, py: float, rx: float, ry: float
          ) -> tuple[float, int, tuple[int, int], bool, float | None]:
    """DDA to the first opaque tile: (distance, side, tile, seen, edge).
    `edge` is the distance at which known ground ends, when it does."""
    mx, my = int(px), int(py)
    delta_x = abs(1 / rx) if rx else 1e30
    delta_y = abs(1 / ry) if ry else 1e30
    step_x, side_x = (-1, (px - mx) * delta_x) if rx < 0 else (1, (mx + 1 - px) * delta_x)
    step_y, side_y = (-1, (py - my) * delta_y) if ry < 0 else (1, (my + 1 - py) * delta_y)
    for _ in range(MAX_DEPTH * 2):
        if side_x < side_y:
            side_x, mx, side = side_x + delta_x, mx + step_x, 0
            distance = side_x - delta_x
        else:
            side_y, my, side = side_y + delta_y, my + step_y, 1
            distance = side_y - delta_y
        tile, seen, _ = world.at(mx, my)
        if tile is None:
            return float(MAX_DEPTH), side, (mx, my), False, distance
        if tile in street.OPAQUE:
            return max(0.05, distance), side, (mx, my), bool(seen), None
        if distance > MAX_DEPTH:
            break
    return float(MAX_DEPTH), 0, (mx, my), False, float(MAX_DEPTH)


def column_pieces(sc: Scene, px: float, py: float, rx: float, ry: float, limit: float
                  ) -> list[tuple[float, float, int, int]]:
    """Pieces this column's ray passes through, as (enter, leave, normal, index)."""
    out = []
    for index, piece in enumerate(sc.pieces):
        if piece.decal:
            continue
        t0, t1, normal = 0.0, limit, 0
        for origin, direction, low, high, faces in ((px, rx, piece.x0, piece.x1, (1, 2)),
                                                    (py, ry, piece.y0, piece.y1, (3, 4))):
            if abs(direction) < 1e-9:
                if not low <= origin <= high:
                    t0 = t1 + 1
                continue
            a, b = (low - origin) / direction, (high - origin) / direction
            face = faces[0] if direction > 0 else faces[1]
            if a > b:
                a, b = b, a
            if a > t0:
                t0, normal = a, face
            t1 = min(t1, b)
        if t0 < t1 and t1 > 0.05:
            out.append((max(t0, 0.05), t1, normal, index))
    return out


def shaped(piece: Piece, x: float, y: float) -> bool:
    """Rings and halos are annuli inside their box."""
    cx, cy = piece.centre
    outer = min(piece.x1 - piece.x0, piece.y1 - piece.y0) / 2
    r = math.hypot(x - cx, y - cy)
    inner = outer * (0.5 if piece.kind == "cans" else 0.86)
    return inner <= r <= outer


def shade(sc: Scene, kind: str, data: Any, x: float, y: float, t: float, row: int, col: int) -> RGB:
    grain = (noise(int(x * 16), int(y * 16), row) - 0.5) * 0.04
    if kind == "floor":
        lit = sc.light(x, y, 0.0, 5)
        base = tuple(c * (0.85 + grain * 4) for c in sc.floor)
        return mul(base, lit, GAIN)
    if kind == "ceiling":
        lit = sc.light(x, y, sc.ceiling, 6)
        return mul(tuple(c * 0.55 for c in sc.walls), lit, GAIN)
    if kind == "wall":
        (tx, ty), side, z = data
        normal = (2 if x >= tx + 0.5 else 1) if side == 0 else (4 if y >= ty + 0.5 else 3)
        along = y if side == 0 else x
        for index in sc.by_tile.get((tx, ty), ()):
            piece = sc.pieces[index]
            if not piece.decal or not piece.z0 <= z <= piece.z1:
                continue
            low, high = (piece.y0, piece.y1) if side == 0 else (piece.x0, piece.x1)
            if low <= along <= high:
                u = (along - low) / max(1e-6, high - low)
                v = (piece.z1 - z) / max(1e-6, piece.z1 - piece.z0)
                return material(sc, piece, u, v, x, y, z, normal, along)
        lit = sc.light(x, y, z, normal)
        panel = 0.9 if int(along * 2) % 4 else 0.8  # wall panels, a seam every two tiles
        base = tuple(c * (panel + grain * 3) for c in sc.walls)
        if z < 0.12:
            base = tuple(c * 0.6 for c in base)  # skirting
        return mul(base, lit, GAIN)
    index, normal, z = data
    piece = sc.pieces[index]
    if normal in (5, 6):
        u, v = (x - piece.x0) / max(1e-6, piece.x1 - piece.x0), (y - piece.y0) / max(1e-6, piece.y1 - piece.y0)
    else:
        along = y if normal in (1, 2) else x
        low, high = (piece.y0, piece.y1) if normal in (1, 2) else (piece.x0, piece.x1)
        u, v = (along - low) / max(1e-6, high - low), (piece.z1 - z) / max(1e-6, piece.z1 - piece.z0)
    return material(sc, piece, u, v, x, y, z, normal, x + y)


def mul(base: tuple[float, ...], lit: RGB, gain: float) -> RGB:
    return base[0] * lit[0] * gain, base[1] * lit[1] * gain, base[2] * lit[2] * gain


def add(a: RGB, b: RGB, k: float = 1.0) -> RGB:
    return a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k


def material(sc: Scene, piece: Piece, u: float, v: float, x: float, y: float, z: float, normal: int,
             along: float) -> RGB:
    """A piece's surface at (u across, v down) in its face."""
    lit = sc.light(x, y, z, normal)
    base, glow_colour, kind = piece.colour, piece.glow, piece.kind
    out = mul(base, lit, GAIN)
    if kind == "counter":
        if normal == 5:
            out = mul(tuple(c * 1.35 for c in base), lit, GAIN)  # the worn top catches the light
        elif v < 0.06:
            out = mul((0.55, 0.42, 0.24), lit, GAIN)  # brass edge
        elif 0.86 < v < 0.9:
            out = mul((0.5, 0.38, 0.22), lit, GAIN * 0.8)  # foot rail
    elif kind == "bench":
        out = mul(tuple(c * (0.8 + 0.3 * (int(u * 6) % 2)) for c in base), lit, GAIN)  # tufted leather
    elif kind == "screens" and glow_colour:
        panel = int(u * 3)
        inside = 0.08 < (u * 3) % 1 < 0.92 and 0.12 < v < 0.9
        if inside and normal not in (5, 6):
            line = 0.55 + 0.45 * noise(panel, int(v * 9), int((u * 3 % 1) * 6))
            out = add(out, glow_colour, 0.9 * line)
    elif kind == "lamp" and glow_colour:
        out = add(out, glow_colour, 1.4 if normal == 6 else 0.35 if v > 0.7 else 0.0)
    elif kind == "cans":
        cell = noise(int(x * 5), int(y * 5))
        tin = (0.55 + 0.35 * cell, 0.53 + 0.3 * cell, 0.48 + 0.25 * cell)
        out = mul(tin, lit, GAIN * 0.9)
        if cell > 0.82:
            out = add(out, lit, 1.6)  # a can catching the light
    elif kind == "ring" and glow_colour:
        angle = math.atan2(y - piece.centre[1], x - piece.centre[0])
        segment = int((angle + math.pi) / (2 * math.pi) * 24)
        if noise(segment, 7) > 0.3:
            out = add(out, glow_colour, 0.85)  # most of it still works
    elif kind == "shelf":
        band = v * 4
        if band % 1 > 0.88:
            out = mul((0.3, 0.2, 0.12), lit, GAIN)  # a shelf plank
        else:
            slot = int(along * 9)
            pick = noise(slot, int(band))
            hue = ((0.5, 0.32, 0.1), (0.15, 0.35, 0.18), (0.55, 0.55, 0.5), (0.45, 0.12, 0.1))[int(pick * 4) % 4]
            if (along * 9) % 1 < 0.62 and band % 1 > 0.25 - 0.2 * pick:
                out = mul(hue, lit, GAIN * 1.4)
                if (along * 9) % 1 < 0.14:
                    out = add(out, lit, 1.2)  # glass highlight
                if glow_colour:
                    out = add(out, glow_colour, 0.12)
    elif kind == "sign" and glow_colour:
        edge = min(u, 1 - u, v * 0.3, (1 - v) * 0.3)
        out = add(out, glow_colour, 0.9 if edge < 0.025 else 0.22)
    elif kind == "doorway" and glow_colour:
        frame = min(u, 1 - u, v) < 0.07
        out = add(out, glow_colour, 0.8 if frame else 0.08)
    elif kind == "board" and glow_colour:
        rows = v * 7
        if 0.08 < u < 0.92 and 0.1 < v < 0.92 and rows % 1 < 0.45 and noise(int(rows), int(u * 5)) > 0.2:
            out = add(out, glow_colour, 0.55)
        else:
            out = add(out, glow_colour, 0.08)
    elif glow_colour:
        out = add(out, glow_colour, 0.3)
    return out


def glow(sc: Scene, cam: Camera, pixels: list[list[RGB]], depth: list[list[float]]) -> None:
    """Light seen directly: a soft halo around each light the eye can see,
    and its smear on a wet floor."""
    height, width = len(pixels), len(pixels[0])
    for li in sc.lights:
        spot = cam.project(li.x, li.y, li.z)
        if spot is None:
            continue
        sx, sy, ahead = spot
        sigma = max(1.2, 2.2 * cam.focal_x / 60 / ahead)
        power = 0.55
        if 0 <= int(sy) < height and 0 <= int(sx) < width and depth[int(sy)][int(sx)] < ahead - 0.4:
            power = 0.0  # behind something
        reflect = cam.project(li.x, li.y, -li.z)
        for cx, cy, sig_x, sig_y, k, floor_only in ((sx, sy, sigma, sigma, power, False),
                                                   (reflect[0] if reflect else -99, reflect[1] if reflect else -99,
                                                    sigma * 0.8, sigma * 2.6, sc.wet * 0.5, True)):
            if k <= 0:
                continue
            for row in range(max(0, int(cy - 3 * sig_y)), min(height, int(cy + 3 * sig_y) + 1)):
                for col in range(max(0, int(cx - 3 * sig_x)), min(width, int(cx + 3 * sig_x) + 1)):
                    if floor_only and row < cam.horizon:
                        continue
                    if depth[row][col] < ahead - 0.5 and not floor_only:
                        continue
                    f = k * math.exp(-((col - cx) ** 2 / (2 * sig_x ** 2) + (row - cy) ** 2 / (2 * sig_y ** 2)))
                    if f > 0.004:
                        pixels[row][col] = add(pixels[row][col], li.colour, f)


def sign_labels(world: street.World, sc: Scene, cam: Camera, depth: list[list[float]]
                ) -> list[tuple[int, int, str, str, float]]:
    """Signs with letters: where the middle of their open face shows, in
    pixels, how wide it shows, and the text."""
    out = []
    for piece in sc.pieces:
        if not piece.text:
            continue
        cx, cy = piece.centre
        open_ground = lambda x, y: world.at(int(math.floor(x)), int(math.floor(y)))[0] not in (None, *street.OPAQUE)
        faces = [((cx, piece.y0), (piece.x0, piece.y0), (piece.x1, piece.y0), (0, -1)),
                 ((cx, piece.y1), (piece.x0, piece.y1), (piece.x1, piece.y1), (0, 1)),
                 ((piece.x0, cy), (piece.x0, piece.y0), (piece.x0, piece.y1), (-1, 0)),
                 ((piece.x1, cy), (piece.x1, piece.y0), (piece.x1, piece.y1), (1, 0))]
        z = (piece.z0 + piece.z1) / 2
        for (fx, fy), a, b, (nx, ny) in faces:
            if not open_ground(fx + nx * 0.5, fy + ny * 0.5) or (cam.px - fx) * nx + (cam.py - fy) * ny <= 0:
                continue  # against the wall, or facing away from you
            spot, ends = cam.project(fx, fy, z), (cam.project(a[0], a[1], z), cam.project(b[0], b[1], z))
            if spot is None or None in ends:
                continue
            sx, sy, ahead = spot
            if not (0 <= int(sy) < len(depth) and 0 <= int(sx) < len(depth[0])) or depth[int(sy)][int(sx)] < ahead - 0.6:
                continue
            span = abs(ends[0][0] - ends[1][0])  # type: ignore[index]
            out.append((int(sx), int(sy), piece.text, piece.role or "sign_amber", span))
            break
    return out


# --- people -------------------------------------------------------------------


def figures(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Who may be drawn: the view's actors, not you. Nobody else, ever."""
    return [a for a in body.get("actors", []) if a.get("role") != "player_self"]


def draw_people(body: dict[str, Any], sc: Scene, cam: Camera, colours: street.Colours,
                pixels: list[list[RGB]], depth: list[list[float]]) -> None:
    height, width = len(pixels), len(pixels[0])
    people = []
    for actor in figures(body):
        spot = cam.project(actor["x"] + 0.5, actor["y"] + 0.5, 0.0)
        if spot is not None:
            people.append((spot[2], actor))
    for ahead, actor in sorted(people, key=lambda item: -item[0]):
        drone = actor.get("kind") == "drone"
        tall, lift = (0.5, 1.1) if drone else (BODY_HEIGHT, 0.0)
        x, y = actor["x"] + 0.5, actor["y"] + 0.5
        foot = cam.project(x, y, lift)
        head = cam.project(x, y, lift + tall)
        if foot is None or head is None:
            continue
        cx, bottom, top = foot[0], foot[1], head[1]
        span = bottom - top
        half = 0.3 * cam.focal_x / ahead
        if span < 2:
            continue
        lit = sc.light(x, y, 1.2, 0)
        key = max(sc.lights, key=lambda li: sum(li.colour) / (1 + (li.x - x) ** 2 + (li.y - y) ** 2), default=None)
        rim_side = 0
        if key is not None:
            side = (key.x - x) * -cam.dy + (key.y - y) * cam.dx
            rim_side = 1 if side > 0 else -1
        role = actor.get("role", "npc_neutral")
        accent = colours(role, (180, 180, 180))
        accent_f = (accent[0] / 255, accent[1] / 255, accent[2] / 255)
        mark = role.startswith("npc_") and role not in ("npc_neutral", "npc_vendor", "npc_hostile")
        fog = 1 - math.exp(-ahead / sc.haze_reach)
        # The rim keeps the light's colour but never burns out to white.
        rim = tuple(c * 1.8 * min(1.0, 0.75 / max(1e-3, max(lit) * 1.8)) for c in lit)
        for row in range(max(0, int(top)), min(height, int(bottom) + 1)):
            v = (row - top) / span
            for col in range(max(0, int(cx - half * 1.1)), min(width, int(cx + half * 1.1) + 1)):
                if depth[row][col] < ahead:
                    continue
                u = (col - cx) / half
                if not silhouette(u, v, drone):
                    continue
                edge = not silhouette(u + 0.22 * rim_side, v, drone) or not silhouette(u, v - 0.04, drone)
                body_c = (0.05 + 0.08 * accent_f[0], 0.045 + 0.08 * accent_f[1], 0.055 + 0.08 * accent_f[2])
                colour = mul(body_c, lit, GAIN * 0.8)
                if edge:
                    colour = add(colour, rim, 1.0)  # rim light from the nearest lamp
                if mark and 0.27 < v < 0.33 and u * rim_side < -0.55:
                    colour = add(colour, accent_f, 0.55)  # an armband in the colours the view shows
                if not drone and v < 0.12 and abs(u) < 0.18 and 0.05 < v < 0.09:
                    colour = add(colour, lit, 0.2)
                pixels[row][col] = tuple(c + (h - c) * fog for c, h in zip(colour, sc.haze))  # type: ignore[assignment]
                depth[row][col] = ahead


def silhouette(u: float, v: float, drone: bool) -> bool:
    """A standing figure in (u across, -1..1; v down, 0..1)."""
    if drone:
        return abs(u) < 0.9 * (1 - abs(v - 0.5) * 1.6)
    if v < 0:
        return False
    if v < 0.13:
        return u * u / 0.09 + (v - 0.065) ** 2 / 0.0042 <= 1  # head
    if v < 0.16:
        return abs(u) < 0.14
    if v < 0.55:
        return abs(u) < 0.95 - (v - 0.16) * 0.55  # shoulders, arms and torso
    if v <= 1.0:
        return 0.08 < abs(u) < 0.42 - (v - 0.55) * 0.25  # legs
    return False


# --- pixels to cells ----------------------------------------------------------


def sextant(pattern: int) -> str:
    """The cell for six pixels (bit 0 top left, row by row). Sextants have
    no glyph for empty, full, or a whole left or right column."""
    if pattern == 0:
        return " "
    if pattern == 63:
        return "█"
    if pattern == 21:
        return "▌"
    if pattern == 42:
        return "▐"
    return chr(0x1FB00 + pattern - 1 - (pattern > 21) - (pattern > 42))


def to8(colour: RGB) -> tuple[int, int, int]:
    return (max(0, min(255, int(colour[0] * 255))), max(0, min(255, int(colour[1] * 255))),
            max(0, min(255, int(colour[2] * 255))))


class Colours16:
    """Sixteen colours for lit pictures. The shipped street quantiser turns
    dim light grey; a lit room is mostly dim and warm, so a dim colour that
    still has a hue takes the dark ANSI colour of that hue (brown, red,
    cyan), and only light without hue is grey. Backgrounds stop at 7."""

    DARK = {1: (128, 0, 0), 2: (0, 128, 0), 3: (128, 80, 0), 4: (0, 0, 128), 5: (128, 0, 128), 6: (0, 128, 128)}
    BRIGHT = {9: (255, 85, 85), 10: (85, 255, 85), 11: (255, 255, 85), 12: (85, 85, 255), 13: (255, 85, 255),
              14: (85, 255, 255), 15: (255, 255, 255), 7: (192, 192, 192)}

    def __init__(self) -> None:
        self.cache: dict[tuple[tuple[int, int, int], bool], int] = {}

    def __call__(self, colour: tuple[int, int, int], background: bool) -> int:
        key = ((colour[0] // 8 * 8, colour[1] // 8 * 8, colour[2] // 8 * 8), background)
        if key not in self.cache:
            r, g, b = key[0]
            light, chroma = (r + g + b) / 3, max(r, g, b) - min(r, g, b)
            if light < 34:
                choice = 0
            elif chroma > 40 and light < 140:
                hue = (r / max(1, max(r, g, b)), g / max(1, max(r, g, b)), b / max(1, max(r, g, b)))
                choice = min(self.DARK, key=lambda i: sum((a / 128 - c) ** 2 for a, c in zip(self.DARK[i], hue)))
            elif light < 100:
                choice = 8
            else:
                choice = min(self.BRIGHT, key=lambda i: sum((a - c) ** 2 for a, c in zip(self.BRIGHT[i], key[0])))
            if background and choice > 7:
                choice = 0 if choice == 8 else choice - 8
            self.cache[key] = choice
        return self.cache[key]


class Colours256:
    """256 colours for lit pictures. The cube has almost no dark warm
    colours, so a plain match turns a lamplit room grey and a hue-first
    match turns it red. Take the nearest colour, and a hued one only when
    it is nearly as near as the grey."""

    def __init__(self) -> None:
        self.cache: dict[tuple[int, int, int], int] = {}

    def __call__(self, colour: tuple[int, int, int], background: bool) -> int:
        key = (colour[0] // 4 * 4, colour[1] // 4 * 4, colour[2] // 4 * 4)
        if key not in self.cache:
            far = lambda i: sum((a - b) ** 2 for a, b in zip(XTERM[i], key))
            best = min(range(16, 256), key=far)
            if max(key) - min(key) > 18 and max(XTERM[best]) - min(XTERM[best]) < 8:
                hued = min((i for i in range(16, 232) if max(XTERM[i]) - min(XTERM[i]) >= 8), key=far)
                if far(hued) <= far(best) * 1.7 + 60:
                    best = hued
            self.cache[key] = best
        return self.cache[key]


def quantiser(tier: str):  # type: ignore[no-untyped-def]
    """One per tier for the life of the door: the caches are the point."""
    if tier not in _QUANT:
        _QUANT[tier] = Colours16() if tier == "16" else Colours256() if tier == "256" else street.Quantiser("truecolor")
    return _QUANT[tier]


_QUANT: dict[str, Any] = {}


def encode(buffer: CellBuffer, area: Rect, rows: int, pixels: list[list[RGB]], paint: Paint, modern: bool
           ) -> list[list[tuple[int, int, int]]]:
    """Write the picture into cells; returns each cell's background (for text over it)."""
    quant = quantiser(paint.tier)
    styles: dict[tuple[Any, Any], Style] = {}

    def style(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> Style:
        key = (quant(fg, False), quant(bg, True))
        found = styles.get(key)
        if found is None:
            found = styles[key] = Style(key[0], key[1], (), paint.tier)
        return found

    ints = [[(min(255, max(0, int(p[0] * 255))), min(255, max(0, int(p[1] * 255))), min(255, max(0, int(p[2] * 255))))
             for p in line] for line in pixels]
    backs = [[(0, 0, 0)] * area.width for _ in range(rows)]
    for row in range(rows):
        for col in range(area.width):
            if modern:
                upper, middle, lower = ints[row * 3], ints[row * 3 + 1], ints[row * 3 + 2]
                x = col * 2
                cells = [upper[x], upper[x + 1], middle[x], middle[x + 1], lower[x], lower[x + 1]]
                lum = [p[0] * 2 + p[1] * 5 + p[2] for p in cells]
                mean = sum(lum) / 6
                bright = [i for i in range(6) if lum[i] > mean]
                if not bright or (max(lum) - min(lum)) < 48:  # flat: one colour
                    avg = (sum(p[0] for p in cells) // 6, sum(p[1] for p in cells) // 6, sum(p[2] for p in cells) // 6)
                    glyph, fg, bg = " ", avg, avg
                else:
                    dark = [i for i in range(6) if lum[i] <= mean]
                    fg = tuple(sum(cells[i][c] for i in bright) // len(bright) for c in range(3))  # type: ignore[assignment]
                    bg = tuple(sum(cells[i][c] for i in dark) // len(dark) for c in range(3))  # type: ignore[assignment]
                    glyph = sextant(sum(1 << i for i in bright))
                backs[row][col] = bg
                buffer.put(area.x + col, area.y + row, glyph, style(fg, bg))
                continue
            top, bottom = ints[row * 2][col], ints[row * 2 + 1][col]
            backs[row][col] = bottom
            buffer.put(area.x + col, area.y + row, "▀", style(top, bottom))
    return backs


# --- the frame ----------------------------------------------------------------


def camera(me: dict[str, Any], columns: int, rows: int, modern: bool, heading: str) -> Camera:
    """The eye for a view of `columns` x `rows` cells, in that tier's pixels."""
    sub_x, sub_y = (2, 3) if modern else (1, 2)
    width, height = columns * sub_x, rows * sub_y
    focal_x = width / 2 / FOV
    # Pixel shape: a sextant pixel is half a cell wide and a third tall.
    focal_y = focal_x * ((0.5 / (2 / 3)) if modern else 1.0)
    dx, dy = street.HEADINGS[heading]
    return Camera(me["x"] + 0.5, me["y"] + 0.5, dx, dy, width, height, focal_x, focal_y, height * HORIZON)


def render(buffer: CellBuffer, body: dict[str, Any], area: Rect, paint: Paint, heading: str,
           hud: bool = True) -> bool:
    """Draw the place lit, if its look has a scene; False if it has none
    (the caller then uses the street view)."""
    world = street.World(body)
    sc = scene_of(body, world)
    me = next((a for a in body.get("actors", []) if a.get("role") == "player_self"), None)
    if sc is None or me is None:
        return False
    rows = area.height - (1 if hud else 0)
    if rows < 2 or area.width < 4:
        return True
    modern = paint.glyphs == "modern" and paint.tier != "16"
    sub_x, sub_y = (2, 3) if modern else (1, 2)
    cam = camera(me, area.width, rows, modern, heading)
    width, height = cam.width, cam.height
    key = (me["x"], me["y"], heading, width, height, modern, id(sc),
           hash(tuple(tuple(r) for r in body.get("tiles", []))), body.get("viewport", {}).get("x"),
           body.get("viewport", {}).get("y"))
    frame = _FRAMES.get(key)
    if frame is None:
        frame = paint_static(world, sc, cam)
        _FRAMES[key] = frame
        while len(_FRAMES) > 6:
            _FRAMES.popitem(last=False)
    else:
        _FRAMES.move_to_end(key)
    pixels = [row[:] for row in frame.pixels]
    depth = [row[:] for row in frame.depth]
    draw_people(body, sc, cam, street.Colours(paint), pixels, depth)
    backs = encode(buffer, area, rows, pixels, paint, modern)
    for sx, sy, text, role, span in frame.labels:
        cells = span / sub_x
        shown = " ".join(text) if cells >= len(text) * 2 else text if cells >= len(text) * 0.8 else ""
        if not shown:
            continue
        col, row = int(sx / sub_x) - display_width(shown) // 2, int(sy / sub_y)
        if not (0 <= row < rows and 0 <= col and col + display_width(shown) <= area.width):
            continue
        for i, ch in enumerate(shown):
            style = paint(role, bold=True)
            if paint.tier != "16" and ch != " ":
                back = backs[row][col + i]
                style = Style(style.fg, quantiser(paint.tier)(street.mix(back, (60, 30, 8), 0.3), True),
                              style.attrs, paint.tier)
            if ch != " ":
                buffer.put(area.x + col + i, area.y + row, ch, style)
    if hud:
        street.hud_line(buffer, body, area, paint, heading, world, me)
    return True
