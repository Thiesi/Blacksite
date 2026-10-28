"""Lit scenes: a place at eye level, drawn from its look (#68, V0 and V1).

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

V1 makes it affordable. The static picture (everything but people) is
painted once per eye and known ground, and kept with its cells already
encoded; a frame then re-encodes only the cells people stand in. In the
door a worker thread paints, so input never waits for a picture: while a
new one is painted the last one stays up, only the latest position is
painted, and pictures of the tiles around you are prepared while you
stand still. While you walk, the picture goes out in a cheaper class
(half-blocks, paired columns, 256 colours) and is sharp again when you
stop. The scene view's fixed camera per place (V0-2) paints once on
entry, so a step there costs only the people.

Three outputs: sextants (2x3 pixels a cell, the modern glyph tier),
half-blocks (1x2) and, in 16 colours, whole cells.
"""

import json
import math
import time
from array import array
from collections import OrderedDict
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import Any

from blacksite.door.cells import Cell, CellBuffer, display_width
from blacksite.door.layout import Rect
from blacksite.door.palette import Style
from blacksite.door.present import street
from blacksite.door.present.paint import XTERM, Paint

RGB = tuple[float, float, float]
RGB8 = tuple[int, int, int]
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
"""Known but out of sight: the same place, a little dimmer."""
DECAL_KINDS = frozenset({"shelf", "sign", "board", "doorway", "screens"})
SHAPED = frozenset({"cans", "ring"})
INF = float("inf")
SETTLE = 0.35
"""Seconds after the last step or turn before the picture is sharp again."""
CACHE_BYTES = 24 * 1024 * 1024
"""The most static pictures a caller's door keeps, in bytes (LRU)."""
PREFETCH = 6
"""Pictures waiting to be prepared; older ones give way to newer."""
CLOCK = time.monotonic
WALK_RATE = 64 * 1024
"""Bytes a second the picture may take while you walk; it goes out less
often to fit (plan 13.5, provisional until measured over real transports)."""
BURST = WALK_RATE // 2
"""The most the walk may spend at once: half a second of its budget."""
FULL_EVERY = 1.0
"""Seconds between whole new pictures that are not the walk: the sharp one
when you stop, a cut to another place's camera."""
FLAT_CELLS = 3000
"""Above this many cells, the walk's picture is one colour a cell pair
(half the rows of pixels), so it can go out about 2.5 times a second
within WALK_RATE at 132x50; below, it keeps its half-blocks."""
"""When you last moved is measured on this clock (the door's own)."""


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
    key: str = ""

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
        cached.key = key
        _SCENES[key] = cached
        while len(_SCENES) > 4:
            _SCENES.popitem(last=False)
    return cached


_SCENES: "OrderedDict[str, Scene]" = OrderedDict()


class Known:
    """The tile at a zone position, memoised for one paint: what the view
    sent, or None where it sent nothing."""

    def __init__(self, world: "street.World | Ground") -> None:
        self.world = world
        self.memo: dict[tuple[int, int], str | None] = {}

    def __call__(self, x: int, y: int) -> str | None:
        key = (x, y)
        if key in self.memo:
            return self.memo[key]
        tile = self.memo[key] = self.world.at(x, y)[0]
        return tile


class Ground:
    """What views of one zone have sent this caller, by zone position: the
    latest tile at each, seen now or remembered. Pictures are painted from
    it, not from the current view alone, so a viewport that scrolls as you
    walk neither changes a kept picture nor cuts it off at its edge. It
    holds nothing the server did not send to this caller. `version`
    changes only when something new is learned."""

    def __init__(self, zone: str) -> None:
        self.zone = zone
        self.tiles: dict[tuple[int, int], str] = {}
        self.version = 0
        self.seen_arrays: Any = None

    def learn(self, world: street.World) -> None:
        if self.seen_arrays is not None and self.seen_arrays[0] is world.tiles and self.seen_arrays[1] is world.memory:
            return
        vx, vy = world.vp["x"], world.vp["y"]
        legend, memory, tiles = world.legend, world.memory, self.tiles
        changed = False
        for row_index, row in enumerate(world.tiles):
            for col, state in enumerate(row):
                if state == -1:
                    continue
                index = state if state >= 0 else memory[row_index][col]
                if 0 <= index < len(legend):
                    key, tile = (col + vx, row_index + vy), legend[index]["id"]
                    if tiles.get(key) != tile:
                        tiles[key] = tile
                        changed = True
        if changed:
            self.version += 1
        self.seen_arrays = (world.tiles, world.memory)  # keeps them alive, so `is` stays honest

    def at(self, x: int, y: int) -> tuple[str | None, int, dict[str, Any]]:
        """Like `World.at`: (tile or None, 1, no look)."""
        return self.tiles.get((x, y)), 1, {}


_GROUND: list[Ground] = []


def ground(body: dict[str, Any], world: street.World) -> Ground:
    """This caller's known ground in the zone the view is of."""
    zone = str((body.get("me") or {}).get("zone", ""))
    if not _GROUND or _GROUND[0].zone != zone:
        _GROUND[:] = [Ground(zone)]
    _GROUND[0].learn(world)
    return _GROUND[0]


_SIGNATURE: list[Any] = [None, None, 0]


def signature(world: street.World) -> int:
    """The known ground of one view, by zone position."""
    tiles, memory = world.tiles, world.memory
    if _SIGNATURE[0] is tiles and _SIGNATURE[1] is memory:
        return _SIGNATURE[2]
    vx, vy = world.vp["x"], world.vp["y"]
    legend = world.legend
    out = []
    for row_index, row in enumerate(tiles):
        for col, state in enumerate(row):
            if state == -1:
                continue
            index = state if state >= 0 else memory[row_index][col]
            if 0 <= index < len(legend):
                out.append(((col + vx) << 16 | (row_index + vy), legend[index]["id"]))
    value = hash(frozenset(out))
    _SIGNATURE[:] = [tiles, memory, value]  # keeps the arrays alive, so `is` stays honest
    return value


_SIGHT: list[Any] = [None, None, None]


def sight(world: street.World, me: dict[str, Any]) -> int:
    """How far you see now, read off the tiles the view marks as seen. The
    picture dims ground beyond it from your eyes: the seen set changes with
    every step, its reach does not, so the picture can still be kept."""
    if _SIGHT[0] is world.tiles and _SIGHT[1] == (me["x"], me["y"]):
        return _SIGHT[2]
    vx, vy = world.vp["x"] - me["x"], world.vp["y"] - me["y"]
    reach = 0
    for row_index, row in enumerate(world.tiles):
        dy = (row_index + vy) ** 2
        for col, state in enumerate(row):
            if state >= 0:
                reach = max(reach, (col + vx) ** 2 + dy)
    value = int(math.sqrt(reach) + 0.5)
    _SIGHT[:] = [world.tiles, (me["x"], me["y"]), value]
    return value


@dataclass
class Frame:
    """The static picture: pixels (8-bit RGB), depth, sign text, and its
    cells once encoded, per output class."""

    width: int
    height: int
    rgb: bytearray
    depth: array
    labels: list[tuple[int, int, str, str, float]]
    grid: str = "half"
    encoded: dict[tuple[Any, ...], tuple[list[list[Cell]], list[list[RGB8]]]] = field(default_factory=dict)

    @property
    def nbytes(self) -> int:
        cells = sum(len(rows) * len(rows[0]) * 16 for rows, _ in self.encoded.values() if rows)
        return len(self.rgb) + len(self.depth) * self.depth.itemsize + cells + 256

    def pixel(self, p: int) -> RGB8:
        i = p * 3
        return self.rgb[i], self.rgb[i + 1], self.rgb[i + 2]


GRIDS = {"sextant": (2.0, 3), "half": (1.0, 2), "low": (0.5, 2)}
"""Pixels per cell, across and down. `sextant` is the modern tier, `half`
half-blocks, and `low` the cheap class while you walk: half-blocks whose
pixels are two cells wide, painted at that resolution."""


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
    grid: str = "half"

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


def paint_static(world: "street.World | Ground", sc: Scene, cam: Camera, reach: float | None = None) -> Frame:
    """Everything but people, painted now."""
    return finish(paint_columns(world, sc, cam, reach))


def finish(columns: Generator[None, None, Frame]) -> Frame:
    try:
        while True:
            next(columns)
    except StopIteration as done:
        return done.value


def paint_columns(world: "street.World | Ground", sc: Scene, cam: Camera, reach: float | None = None
                  ) -> Generator[None, None, Frame]:
    """Everything but people, a column at a time (the painter can stop
    between any two). With `reach`, ground further than that from the eye
    is drawn as remembered."""
    width, height = cam.width, cam.height
    far = (reach + 0.5) ** 2 if reach else INF
    at = Known(world)
    pixels = bytearray(width * height * 3)
    depth = array("f", [MAX_DEPTH]) * (width * height)
    plane_x, plane_y = cam.plane
    top = sc.ceiling if sc.interior else 6.0
    slopes = [(cam.horizon - (row + 0.5)) / cam.focal_y for row in range(height)]
    flats = [(-EYE / s, "floor") if s < 0 else ((sc.ceiling - EYE) / s, "ceiling") if s > 0 and sc.interior else (INF, "")
             for s in slopes]
    haze_r, haze_g, haze_b = sc.haze
    haze_reach = sc.haze_reach
    for col in range(width):
        yield
        camera = 2 * (col + 0.5) / width - 1
        rx, ry = cam.dx + plane_x * camera, cam.dy + plane_y * camera
        wall_t, wall_side, wall_tile, edge = march(at, cam.px, cam.py, rx, ry)
        boxes = column_pieces(sc, cam.px, cam.py, rx, ry, wall_t)
        # Each piece covers a band of rows in this column: from its top
        # edge (near or far, whichever is higher) to its bottom edge.
        spans = []
        for t0, t1, normal, index in boxes:
            piece = sc.pieces[index]
            rows_at = [cam.horizon - (z - EYE) * cam.focal_y / t for z in (piece.z0, piece.z1) for t in (t0, t1)]
            spans.append((int(min(rows_at)) - 1, int(max(rows_at)) + 1, t0, t1, normal, index))
        for row in range(height):
            slope = slopes[row]
            best_t, kind, data = wall_t if edge is None else float(MAX_DEPTH), "", None
            if edge is None:
                z = EYE + slope * wall_t
                if 0 <= z <= top:
                    kind, data = "wall", (wall_tile, wall_side, z)
                else:
                    best_t = float(MAX_DEPTH)
            flat_t, flat = flats[row]
            if flat_t < best_t:
                best_t, kind, data = flat_t, flat, None
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
            if kind == "floor" and (at(math.floor(x), math.floor(y)) is None or (edge is not None and best_t > edge)):
                continue
            r, g, b = shade(sc, kind, data, x, y, row)
            if (x - cam.px) ** 2 + (y - cam.py) ** 2 > far:
                r, g, b = r * REMEMBERED, g * REMEMBERED, b * REMEMBERED
            fog = 1 - math.exp(-best_t / haze_reach)
            r, g, b = r + (haze_r - r) * fog, g + (haze_g - g) * fog, b + (haze_b - b) * fog
            p = row * width + col
            i = p * 3
            pixels[i] = 255 if r >= 1 else int(r * 255) if r > 0 else 0
            pixels[i + 1] = 255 if g >= 1 else int(g * 255) if g > 0 else 0
            pixels[i + 2] = 255 if b >= 1 else int(b * 255) if b > 0 else 0
            depth[p] = best_t
    yield from glow(sc, cam, pixels, depth)
    return Frame(width, height, pixels, depth, sign_labels(at, sc, cam, depth), cam.grid)


def march(at: Known, px: float, py: float, rx: float, ry: float) -> tuple[float, int, tuple[int, int], float | None]:
    """DDA to the first opaque tile: (distance, side, tile, edge). `edge` is
    the distance at which known ground ends, when it does."""
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
        tile = at(mx, my)
        if tile is None:
            return float(MAX_DEPTH), side, (mx, my), distance
        if tile in street.OPAQUE:
            return max(0.05, distance), side, (mx, my), None
        if distance > MAX_DEPTH:
            break
    return float(MAX_DEPTH), 0, (mx, my), float(MAX_DEPTH)


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


def shade(sc: Scene, kind: str, data: Any, x: float, y: float, row: int) -> RGB:
    grain = (noise(int(x * 16), int(y * 16), row) - 0.5) * 0.04
    if kind == "floor":
        lit = sc.light(x, y, 0.0, 5)
        k = 0.85 + grain * 4
        return sc.floor[0] * k * lit[0] * GAIN, sc.floor[1] * k * lit[1] * GAIN, sc.floor[2] * k * lit[2] * GAIN
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


def glow(sc: Scene, cam: Camera, pixels: bytearray, depth: array) -> Generator[None, None, None]:
    """Light seen directly: a soft halo around each light the eye can see,
    and its smear on a wet floor. Yields between lights."""
    width, height = cam.width, cam.height
    for li in sc.lights:
        yield
        spot = cam.project(li.x, li.y, li.z)
        if spot is None:
            continue
        sx, sy, ahead = spot
        sigma = max(1.2, 2.2 * cam.focal_x / 60 / ahead)
        power = 0.55
        if 0 <= int(sy) < height and 0 <= int(sx) < width and depth[int(sy) * width + int(sx)] < ahead - 0.4:
            power = 0.0  # behind something
        reflect = cam.project(li.x, li.y, -li.z)
        lr, lg, lb = li.colour[0] * 255, li.colour[1] * 255, li.colour[2] * 255
        for cx, cy, sig_x, sig_y, k, floor_only in ((sx, sy, sigma, sigma, power, False),
                                                   (reflect[0] if reflect else -99, reflect[1] if reflect else -99,
                                                    sigma * 0.8, sigma * 2.6, sc.wet * 0.5, True)):
            if k <= 0:
                continue
            for row in range(max(0, int(cy - 3 * sig_y)), min(height, int(cy + 3 * sig_y) + 1)):
                if floor_only and row < cam.horizon:
                    continue
                for col in range(max(0, int(cx - 3 * sig_x)), min(width, int(cx + 3 * sig_x) + 1)):
                    p = row * width + col
                    if depth[p] < ahead - 0.5 and not floor_only:
                        continue
                    f = k * math.exp(-((col - cx) ** 2 / (2 * sig_x ** 2) + (row - cy) ** 2 / (2 * sig_y ** 2)))
                    if f > 0.004:
                        i = p * 3
                        pixels[i] = min(255, pixels[i] + int(lr * f))
                        pixels[i + 1] = min(255, pixels[i + 1] + int(lg * f))
                        pixels[i + 2] = min(255, pixels[i + 2] + int(lb * f))


def sign_labels(at: Known, sc: Scene, cam: Camera, depth: array) -> list[tuple[int, int, str, str, float]]:
    """Signs with letters: where the middle of their open face shows, in
    pixels, how wide it shows, and the text."""
    out = []
    width, height = cam.width, cam.height
    open_ground = lambda x, y: at(math.floor(x), math.floor(y)) not in (None, *street.OPAQUE)
    for piece in sc.pieces:
        if not piece.text:
            continue
        cx, cy = piece.centre
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
            if not (0 <= int(sy) < height and 0 <= int(sx) < width) or depth[int(sy) * width + int(sx)] < ahead - 0.6:
                continue
            span = abs(ends[0][0] - ends[1][0])  # type: ignore[index]
            out.append((int(sx), int(sy), piece.text, piece.role or "sign_amber", span))
            break
    return out


# --- people -------------------------------------------------------------------


def figures(body: dict[str, Any], me_too: bool = False) -> list[dict[str, Any]]:
    """Who may be drawn: the view's actors (you only when the camera is
    not your eyes). Nobody else, ever."""
    return [a for a in body.get("actors", []) if me_too or a.get("role") != "player_self"]


def draw_people(body: dict[str, Any], sc: Scene, cam: Camera, colours: street.Colours, frame: Frame,
                me_too: bool = False) -> dict[int, RGB8]:
    """The people over the static picture, as pixels by index; the static
    picture itself is left alone (it is shared)."""
    width, height = frame.width, frame.height
    depth = frame.depth
    over: dict[int, RGB8] = {}
    people = []
    for actor in figures(body, me_too):
        spot = cam.project(actor["x"] + 0.5, actor["y"] + 0.5, 0.0)
        if spot is not None:
            people.append((spot[2], actor))
    for ahead, actor in sorted(people, key=lambda item: -item[0]):  # far first: the near cover them
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
        body_c = (0.05 + 0.08 * accent_f[0], 0.045 + 0.08 * accent_f[1], 0.055 + 0.08 * accent_f[2])
        for row in range(max(0, int(top)), min(height, int(bottom) + 1)):
            v = (row - top) / span
            for col in range(max(0, int(cx - half * 1.1)), min(width, int(cx + half * 1.1) + 1)):
                p = row * width + col
                if depth[p] < ahead:
                    continue
                u = (col - cx) / half
                if not silhouette(u, v, drone):
                    continue
                edge = not silhouette(u + 0.22 * rim_side, v, drone) or not silhouette(u, v - 0.04, drone)
                colour = mul(body_c, lit, GAIN * 0.8)
                if edge:
                    colour = add(colour, rim, 1.0)  # rim light from the nearest lamp
                if mark and 0.27 < v < 0.33 and u * rim_side < -0.55:
                    colour = add(colour, accent_f, 0.55)  # an armband in the colours the view shows
                if not drone and v < 0.12 and abs(u) < 0.18 and 0.05 < v < 0.09:
                    colour = add(colour, lit, 0.2)
                over[p] = to8(tuple(c + (h - c) * fog for c, h in zip(colour, sc.haze)))  # type: ignore[arg-type]
    return over


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


def to8(colour: RGB) -> RGB8:
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


class Steps:
    """Truecolor in 16 steps a channel, even to the eye (gamma 2.2): fine in
    the dark, where a lit room lives, coarse in the light. Neighbouring
    cells then share colours often enough that the terminal diff skips
    most colour changes. The walk's cheap class; 256 colours would turn
    the room grey and olive, and even steps would erase the dark."""

    LEVELS = 16

    def __init__(self) -> None:
        n = self.LEVELS
        self.table = [int(round((round((v / 255) ** (1 / 2.2) * n) / n) ** 2.2 * 255)) for v in range(256)]

    def __call__(self, colour: RGB8, background: bool) -> RGB8:
        t = self.table
        return t[colour[0]], t[colour[1]], t[colour[2]]


_STEPS = Steps()


class Encoder:
    """Pixels to cells for one frame and tier. `sextant` frames have 2x3
    pixels a cell, `half` frames 1x2, and `low` frames (the walk) 1x2 over
    two cells, in truecolor steps: the cheap class. `flat`: a low frame
    with one colour a cell pair, for large pictures."""

    def __init__(self, frame: Frame, tier: str, flat: bool = False) -> None:
        self.frame, self.tier, self.flat = frame, tier, flat and frame.grid == "low"
        self.quant = _STEPS if frame.grid == "low" and tier == "truecolor" else quantiser(tier)
        self.styles: dict[tuple[Any, Any], Style] = {}
        self.cells: dict[tuple[str, Any, Any], Cell] = {}

    def cell(self, glyph: str, fg: RGB8, bg: RGB8) -> Cell:
        key = (glyph, self.quant(fg, False), self.quant(bg, True))
        found = self.cells.get(key)
        if found is None:
            style = self.styles.get(key[1:])
            if style is None:
                style = self.styles[key[1:]] = Style(key[1], key[2], (), self.tier)
            found = self.cells[key] = Cell(glyph, style)
        return found

    def encode(self, row: int, col: int, over: dict[int, RGB8] | None = None) -> tuple[Cell, RGB8]:
        """One cell and its background colour."""
        frame = self.frame
        width = frame.width
        px = frame.pixel if not over else (lambda p: over.get(p) or frame.pixel(p))
        if frame.grid == "sextant":
            p = row * 3 * width + col * 2
            cells = [px(p), px(p + 1), px(p + width), px(p + width + 1), px(p + 2 * width), px(p + 2 * width + 1)]
            lum = [c[0] * 2 + c[1] * 5 + c[2] for c in cells]
            average = sum(lum) / 6
            bright = [i for i in range(6) if lum[i] > average]
            if not bright or (max(lum) - min(lum)) < 48:  # flat: one colour
                flat = mean(cells)
                return self.cell(" ", flat, flat), flat
            dark = [i for i in range(6) if lum[i] <= average]
            fg, bg = mean([cells[i] for i in bright]), mean([cells[i] for i in dark])
            return self.cell(sextant(sum(1 << i for i in bright)), fg, bg), bg
        if frame.grid == "low":
            col //= 2
        top, bottom = px(row * 2 * width + col), px((row * 2 + 1) * width + col)
        if self.flat:
            both = mean([top, bottom])
            return self.cell(" ", both, both), both
        return self.cell("▀", top, bottom), bottom


def mean(colours: list[RGB8]) -> RGB8:
    n = len(colours)
    return sum(c[0] for c in colours) // n, sum(c[1] for c in colours) // n, sum(c[2] for c in colours) // n


def encoded(frame: Frame, tier: str, columns: int, rows: int) -> tuple[list[list[Cell]], list[list[RGB8]], Encoder]:
    """The static picture's cells, encoded once per tier."""
    encoder = Encoder(frame, tier, columns * rows > FLAT_CELLS)
    found = frame.encoded.get((tier,))
    if found is None:
        grid, backs = [], []
        for row in range(rows):
            line, back = [], []
            for col in range(columns):
                if frame.grid == "low" and col % 2:
                    cell, bg = line[-1], back[-1]  # one pixel spans the pair
                else:
                    cell, bg = encoder.encode(row, col)
                line.append(cell)
                back.append(bg)
            grid.append(line)
            backs.append(back)
        found = frame.encoded[(tier,)] = (grid, backs)
    return found[0], found[1], encoder


def blit(buffer: CellBuffer, x: int, y: int, cells: list[Cell]) -> None:
    """Cells in one go, width-safe like `put` (every picture glyph is one
    cell wide) and never into the bottom-right cell."""
    if not 0 <= y < buffer.height:
        return
    limit = buffer.width - (y == buffer.height - 1)
    left, right = max(0, x), min(limit, x + len(cells))
    if left >= right:
        return
    row = buffer.cells[y]
    if row[left].glyph == "":
        buffer._clear_glyph(left, y)
    if right < buffer.width and row[right].glyph == "":
        buffer._clear_glyph(right, y)
    row[left:right] = cells[left - x:right - x]


# --- painting now, or in the background --------------------------------------


class Painter:
    """Static pictures, cached by eye and known ground (LRU, bounded in
    bytes).

    In the door it paints in the background, on the door's own loop: `work`
    paints a few columns at a time and returns, so keys and frames are
    handled between slices and input never waits for a picture. `frame`
    returns None while the wanted picture is painted; the latest request
    replaces an older one (coalescing), and a prepared picture gives way
    to a wanted one, parked half-painted until there is time again.
    Elsewhere (tests, captures) pictures are painted on the spot."""

    def __init__(self, background: bool = False, wake: Callable[[], None] | None = None,
                 kick: Callable[[], None] | None = None, limit: int = CACHE_BYTES) -> None:
        self.background, self.wake, self.kick, self.limit = background, wake, kick, limit
        self.cache: OrderedDict[Any, Frame] = OrderedDict()
        self.size = self.peak = 0
        self.wanted: tuple[Any, Callable[[], Generator[None, None, Frame]]] | None = None
        self.queue: OrderedDict[Any, Any] = OrderedDict()
        """Pictures to prepare: a job, or a parked paint."""
        self.current: list[Any] | None = None
        """[key, columns, 'wanted' or 'prepared', seconds spent]."""
        self.fresh = False
        self.shown: dict[tuple[Any, ...], tuple[Frame, Camera]] = {}
        self.eye: Any = None
        self.moved_at = -INF
        self.unsettled = False
        self.log: list[tuple[str, float]] = []
        """(what, seconds) per finished paint, for measurement."""
        self.tokens, self.tokens_at = float(BURST), None
        self.charging = False
        self.last_full = -INF
        self.held_until: float | None = None

    def clear(self) -> None:
        self.cache.clear()
        self.queue.clear()
        self.shown.clear()
        self.wanted = self.current = None
        self.size = 0

    def frame(self, key: Any, job: Callable[[], Generator[None, None, Frame]]) -> Frame | None:
        hit = self.cache.get(key)
        if hit is not None:
            self.cache.move_to_end(key)
            return hit
        if not self.background:
            started = time.perf_counter()
            frame = finish(job())
            self._done(key, frame, "wanted", time.perf_counter() - started)
            return frame
        if self.current is not None and self.current[0] == key:
            self.current[2] = "wanted"  # already being painted: it is wanted now
            self.wanted = None
            return None
        self.wanted = (key, job)
        self._kick()
        return None

    def prepare(self, key: Any, job: Callable[[], Generator[None, None, Frame]]) -> None:
        """Paint ahead, when nothing is wanted (background only)."""
        if not self.background or key in self.cache or key in self.queue:
            return
        if self.current is not None and self.current[0] == key:
            return
        self.queue[key] = job
        while len(self.queue) > PREFETCH:
            self.queue.popitem(last=False)
        self._kick()

    def busy(self) -> bool:
        return bool(self.wanted or self.current or self.queue)

    def work(self, budget: float = 0.004) -> None:
        """Paint for about `budget` seconds, a column at a time."""
        end = time.perf_counter() + budget
        while True:
            if self.wanted is not None and (self.current is None or self.current[2] == "prepared"):
                if self.current is not None:  # park the prepared one where it got to
                    self.queue[self.current[0]] = self.current
                    self.queue.move_to_end(self.current[0], last=False)
                key, job = self.wanted
                self.wanted = None
                self.current = [key, job(), "wanted", 0.0]
            elif self.current is None:
                if not self.queue:
                    return
                key, item = self.queue.popitem(last=False)
                if key in self.cache:
                    continue
                self.current = item if isinstance(item, list) else [key, item(), "prepared", 0.0]
            now = time.perf_counter()
            try:
                next(self.current[1])
            except StopIteration as done:
                key, _, what, spent = self.current
                self.current = None
                self._done(key, done.value, what, spent + time.perf_counter() - now)
                if what == "wanted":
                    self.fresh = True
                    if self.wake is not None:
                        self.wake()
            else:
                self.current[3] += time.perf_counter() - now
            if time.perf_counter() >= end:
                return

    def take_fresh(self) -> bool:
        """True once after a wanted picture lands."""
        fresh, self.fresh = self.fresh, False
        return fresh

    def motion(self, eye: Any, now: float) -> bool:
        """Note where the eye is; True while it is moving."""
        if eye != self.eye:
            if self.eye is not None:
                self.moved_at, self.unsettled = now, True
            self.eye = eye
        return now - self.moved_at < SETTLE

    def wake_in(self, now: float) -> float | None:
        """Seconds until the picture should be drawn again on its own: sharp
        after you stop, or a picture held back by the budget."""
        times = [t for t in (self.moved_at + SETTLE if self.unsettled else None, self.held_until) if t is not None]
        return max(0.0, min(times) - now) if times else None

    def due(self, now: float) -> bool:
        """True once when the picture should be drawn again on its own."""
        held = self.held_until is not None and now >= self.held_until
        if held:
            self.held_until = None
        return self.settled(now) or held

    def allow(self, moving: bool, now: float) -> bool:
        """May a new picture go out now? While you walk, from a budget that
        refills at WALK_RATE (charged with what the frame cost); otherwise
        (sharp on stop, a cut) at most one every FULL_EVERY seconds. When
        not, the last picture stays up and `held_until` says when to try."""
        if moving:
            self._refill(now)
            if self.tokens > 0:
                self.charging = True
                return True
            self.held_until = now + -self.tokens / WALK_RATE + 0.001
            return False
        if now - self.last_full >= FULL_EVERY:
            self.last_full = now
            return True
        self.held_until = self.last_full + FULL_EVERY
        return False

    def charge(self, sent: int, now: float) -> None:
        """What a frame cost, while you walk (every frame then, so the budget
        covers the walk, not only its pictures)."""
        if self.charging or now - self.moved_at < SETTLE:
            self._refill(now)
            self.tokens -= sent
            self.charging = False

    def _refill(self, now: float) -> None:
        if self.tokens_at is not None:
            self.tokens = min(float(BURST), self.tokens + (now - self.tokens_at) * WALK_RATE)
        self.tokens_at = now

    def settled(self, now: float) -> bool:
        """True once when the eye has stopped long enough."""
        if self.unsettled and now - self.moved_at >= SETTLE:
            self.unsettled = False
            return True
        return False

    def _kick(self) -> None:
        if self.kick is not None:
            self.kick()

    def _done(self, key: Any, frame: Frame, what: str, spent: float) -> None:
        self.log.append((what, spent))
        del self.log[:-256]
        if key in self.cache:
            return
        self.cache[key] = frame
        self.size += frame.nbytes
        while self.size > self.limit and len(self.cache) > 1:
            _, old = self.cache.popitem(last=False)
            self.size -= old.nbytes
        self.peak = max(self.peak, self.size)

    def grew(self, frame: Frame, before: int) -> None:
        """A cached frame gained encoded cells: count them."""
        self.size += frame.nbytes - before
        self.peak = max(self.peak, self.size)


PAINTER = Painter()
"""Paints on the spot. The door installs a background painter at start."""


# --- the frame ----------------------------------------------------------------


def camera_at(x: float, y: float, heading: str, columns: int, rows: int, grid: str) -> Camera:
    """The eye on tile (x, y) for a view of `columns` x `rows` cells, in
    the pixels of `grid`."""
    sub_x, sub_y = GRIDS[grid]
    width, height = math.ceil(columns * sub_x), rows * sub_y
    focal_x = width / 2 / FOV
    # Pixel shape: a cell is about twice as tall as it is wide.
    focal_y = focal_x * sub_y / (2 * sub_x)
    dx, dy = street.HEADINGS[heading]
    return Camera(x + 0.5, y + 0.5, dx, dy, width, height, focal_x, focal_y, height * HORIZON, grid)


def camera(me: dict[str, Any], columns: int, rows: int, modern: bool, heading: str) -> Camera:
    """Your eyes, at full resolution."""
    return camera_at(me["x"], me["y"], heading, columns, rows, "sextant" if modern else "half")


def viewpoint(body: dict[str, Any], world: street.World) -> tuple[int, int, str] | None:
    """The scene view's fixed camera for the place you are in: the one its
    look gives, when the server sent it, or else one picked from ground
    the view already shows. None outside any place."""
    place = body.get("place") or {}
    spot = next((p for p in place.get("places", []) if p.get("name") == place.get("here")), None)
    if spot is None:
        return None
    view = spot.get("view")
    if view and view.get("facing") in street.HEADINGS:
        return int(view["at"][0]), int(view["at"][1]), view["facing"]
    key = (tuple(spot["rect"]), str((body.get("me") or {}).get("zone", "")), signature(world))
    if key not in _VIEWS:
        _VIEWS[key] = choose_view(world, tuple(spot["rect"]))
        while len(_VIEWS) > 32:
            _VIEWS.pop(next(iter(_VIEWS)))
    return _VIEWS[key]


_VIEWS: dict[Any, tuple[int, int, str] | None] = {}


def choose_view(world: street.World, rect: tuple[int, int, int, int]) -> tuple[int, int, str] | None:
    """A camera for a place from known ground only: on an open tile of the
    place with its back to the place's edge, facing the way that frames
    the most of it, near the middle of that edge."""
    x, y, w, h = rect
    passable = lambda tile: tile is not None and tile not in street.OPAQUE
    inside = [(tx, ty) for ty in range(y, y + h) for tx in range(x, x + w) if passable(world.at(tx, ty)[0])]
    if not inside:
        return None
    members = set(inside)
    sample = inside[::max(1, len(inside) // 160)]
    best: tuple[Any, ...] | None = None
    for tx, ty in inside:
        for heading, (dx, dy) in street.HEADINGS.items():
            if (tx - dx, ty - dy) in members:
                continue  # stand at the edge, facing in
            seen = 0
            for ox, oy in sample:
                ahead = (ox - tx) * dx + (oy - ty) * dy
                if ahead >= 2 and abs((ox - tx) * -dy + (oy - ty) * dx) <= ahead * FOV:
                    seen += 1
            middle = abs((tx - (x + w / 2)) * -dy + (ty - (y + h / 2)) * dx)
            choice = (seen, -middle, -ty, -tx, heading)
            if best is None or choice > best:
                best = choice
    if best is None or best[0] == 0:
        return None
    return int(-best[3]), int(-best[2]), str(best[4])


def render(buffer: CellBuffer, body: dict[str, Any], area: Rect, paint: Paint, heading: str,
           hud: bool = True, fixed: bool = False) -> bool:
    """Draw the place lit, if its look has a scene; False if it has none
    (the caller then uses the street view). `fixed`: the scene view's
    fixed camera for the place you are in, when there is one."""
    world = street.World(body)
    sc = scene_of(body, world)
    me = next((a for a in body.get("actors", []) if a.get("role") == "player_self"), None)
    if sc is None or me is None:
        return False
    known = ground(body, world)
    rows = area.height - (1 if hud else 0)
    if rows < 2 or area.width < 4:
        return True
    modern = paint.glyphs == "modern" and paint.tier != "16"
    view = viewpoint(body, world) if fixed else None
    eye = view or (me["x"], me["y"], heading)
    reach = None if view else sight(world, me)  # a fixed camera is not your eyes
    now = CLOCK()
    # Walking moves your eyes, not a fixed camera: only then the cheap class.
    moving = PAINTER.motion((me["x"], me["y"], heading), now) and view is None and paint.tier != "16"
    sharp = "sextant" if modern else "half"

    def key_of(x: int, y: int, facing: str, grid: str) -> tuple[Any, ...]:
        return (x, y, facing, grid, area.width, rows, sc.key, known.zone, known.version, reach)

    def job_of(x: int, y: int, facing: str, grid: str) -> Callable[[], Generator[None, None, Frame]]:
        eye_cam = camera_at(x, y, facing, area.width, rows, grid)
        return lambda: paint_columns(known, sc, eye_cam, reach)

    grid = "low" if moving else sharp
    frame = PAINTER.frame(key_of(*eye, grid), job_of(*eye, grid))
    slot = (area.width, rows, view is not None)
    if frame is None:  # being painted: the last picture stays up meanwhile
        shown = PAINTER.shown.get(slot)
        if shown is None:
            buffer.fill(area.x, area.y, area.width, rows, Style(0, 0, (), paint.tier))
            if hud:
                street.hud_line(buffer, body, area, paint, heading, world, me)
            return True
        frame, cam = shown
    else:
        cam = camera_at(eye[0], eye[1], eye[2], area.width, rows, grid)
        shown = PAINTER.shown.get(slot)
        if shown is not None and shown[0] is not frame and not PAINTER.allow(moving, now):
            frame, cam = shown  # over budget: the last picture stays up a moment longer
        else:
            PAINTER.shown[slot] = (frame, cam)
        if view is not None:
            prepare_places(body, view, sharp, key_of, job_of)
        else:
            prepare_around(eye, moving, sharp, world, key_of, job_of)
    sub_x, sub_y = GRIDS[frame.grid]
    before = frame.nbytes
    cells, backs, encoder = encoded(frame, paint.tier, area.width, rows)
    if frame.nbytes != before:
        PAINTER.grew(frame, before)
    lines = [line[:] for line in cells]
    over = draw_people(body, sc, cam, street.Colours(paint), frame, me_too=view is not None)
    for row, col in touched(over, frame, area.width, rows):
        lines[row][col], _ = encoder.encode(row, col, over)
    for row, line in enumerate(lines):
        blit(buffer, area.x, area.y + row, line)
    for sx, sy, text, role, span in frame.labels:
        width = span / sub_x
        shown_text = " ".join(text) if width >= len(text) * 2 else text if width >= len(text) * 0.8 else ""
        if not shown_text:
            continue
        col, row = int(sx / sub_x) - display_width(shown_text) // 2, int(sy / sub_y)
        if not (0 <= row < rows and 0 <= col and col + display_width(shown_text) <= area.width):
            continue
        for i, ch in enumerate(shown_text):
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


def touched(over: dict[int, RGB8], frame: Frame, columns: int, rows: int) -> list[tuple[int, int]]:
    """The cells people cover."""
    sub_x, sub_y = GRIDS[frame.grid]
    cells = set()
    for p in over:
        row, col = p // frame.width // sub_y, p % frame.width
        for cell in ((col * 2, col * 2 + 1) if frame.grid == "low" else (int(col // sub_x),)):
            if row < rows and cell < columns:
                cells.add((row, cell))
    return sorted(cells)


def prepare_places(body: dict[str, Any], view: tuple[int, int, str], sharp: str,
                   key_of: Callable[..., Any], job_of: Callable[..., Any]) -> None:
    """The fixed cameras of the other places whose viewpoints the view sent
    (only over known ground), so a cut to the next place is already
    painted. The camera here does not move while you do."""
    if not PAINTER.background:
        return
    for spot in (body.get("place") or {}).get("places", []):
        other = spot.get("view")
        if other and other.get("facing") in street.HEADINGS:
            at = (int(other["at"][0]), int(other["at"][1]), other["facing"])
            if at != view:
                PAINTER.prepare(key_of(*at, sharp), job_of(*at, sharp))


def prepare_around(eye: tuple[int, int, str], moving: bool, sharp: str, world: street.World,
                   key_of: Callable[..., Any], job_of: Callable[..., Any]) -> None:
    """Pictures you are likely to want next, from ground the view already
    shows. While you walk: the cheap picture a step on and of the turns.
    Standing: the sharp one here, then the turns."""
    if not PAINTER.background:
        return
    x, y, heading = eye
    dx, dy = street.HEADINGS[heading]
    turns = [(x, y, street.TURN_LEFT[heading]), (x, y, street.TURN_RIGHT[heading])]
    if moving:
        around = [(x + dx, y + dy, heading, "low"), *((tx, ty, f, "low") for tx, ty, f in turns),
                  (x, y, heading, sharp)]
    else:
        around = [*((tx, ty, f, sharp) for tx, ty, f in turns), (x + dx, y + dy, heading, "low"),
                  (x, y, street.BEHIND[heading], sharp)]
    for nx, ny, facing, grid in around:
        tile = world.at(nx, ny)[0]
        if tile is not None and tile not in street.OPAQUE:
            PAINTER.prepare(key_of(nx, ny, facing, grid), job_of(nx, ny, facing, grid))
