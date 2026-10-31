"""Website mockup: the Tin Halo as an auto-view SCENE at 132x50,
truecolor, full Unicode. Hand-composed, not a harness capture.

The #68 visual target (target_tin_halo.py on design/presentation-v1),
brought up to the P5 chrome canon: log gutters per UI 2.5, HERE led by
the shape in reach, TARGET always present, NEARBY relation tags, ten-cell
bars, chits and lease. The glimpse is painted as a pixel image and
encoded in sextants (2x3 per cell). Needs Pillow and a monospace font
(MOCKUP_FONT, or Consolas/DejaVu).

    python scripts/presentation_mockups/website/tin_halo_final.py
"""

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 132, 50

# ---------------------------------------------------------------- palette
def hx(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))

R = {k: hx(v) for k, v in {
    "frame_pocket": "#2A8A8A", "word_pocket": "#5FD7D7", "head_zone": "#FFFFFF", "head_district": "#8A8A8A",
    "head_info": "#BCBCBC", "head_night": "#FFD7AF", "log_place": "#D7AF87", "log_ambient": "#8A8A8A",
    "log_speaker": "#87D7FF", "log_speech": "#DADADA", "log_system": "#585858", "panel_text": "#D0D0D0",
    "panel_label": "#808080", "panel_dim": "#6C6C6C", "panel_rule": "#4E4E4E", "panel_strong": "#FFFFFF",
    "key_cap": "#FFFFFF", "key_text": "#808080", "npc_vendor": "#FBBF24", "npc_neutral": "#D1D5DB",
    "player_neutral": "#E5E7EB", "thing_terminal": "#00D7FF", "thing_door": "#D7AF5F", "thing_vendor": "#FFD700",
    "thing_hardware": "#AF87FF", "thing_exit": "#FFFFFF", "bar_hp": "#5FAF5F", "bar_sta": "#5FAFD7",
    "bar_shock": "#D7AF5F", "bar_empty": "#3A3A3A", "sign_amber": "#FFAF00", "sign_pink": "#FF87FF",
    "self_fg": "#000000", "self_bg": "#FFFFFF", "npc_sable": "#DC2626",
}.items()}
BG = (10, 10, 13)

def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))

def add(a, b, k=1.0):
    return tuple(a[i] + b[i] * k for i in range(3))

def mul(a, k):
    return tuple(v * k for v in a)

def clamp(c):
    return tuple(max(0, min(255, int(round(v)))) for v in c)

# ---------------------------------------------------------------- cells
grid = [[[" ", R["panel_text"], BG, False] for _ in range(W)] for _ in range(H)]

def put(x, y, text, fg, bg=None, bold=False):
    for ch in text:
        if 0 <= x < W and 0 <= y < H and not (x == W - 1 and y == H - 1):
            cell = grid[y][x]
            cell[0], cell[1], cell[3] = ch, fg, bold
            if bg is not None:
                cell[2] = bg
        x += 1
    return x

def fill(x0, y0, w, h, bg):
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            grid[y][x] = [" ", R["panel_text"], bg, False]

# ---------------------------------------------------------------- the glimpse
GX, GY, GW, GR = 1, 1, 107, 19          # cells
PW, PH = GW * 2, GR * 3                 # pixels: 214 x 57
VP = (PW * 0.53, PH * 0.40)             # vanishing point
K = 0.64                                # how far the back wall sits toward VP
NEAR = dict(left=-30.0, right=PW + 40.0, top=-10.0, floor=PH + 14.0)
rng = random.Random(68)

def proj(X, Y, u):
    s = 1 - K * u
    return VP[0] + (X - VP[0]) * s, VP[1] + (Y - VP[1]) * s

def depth(u):
    return 1 / (1 - K * u) - 1          # 0 near, ~1.8 at the back wall

FLOOR, CEIL, LEFT, RIGHT = NEAR["floor"], NEAR["top"], NEAR["left"], NEAR["right"]
HT = FLOOR - CEIL

def surface(px, py):
    """Which surface a pixel sees, with its near-plane coordinates and depth."""
    best = None
    for name, axis, value in (("floor", 1, FLOOR), ("ceil", 1, CEIL), ("left", 0, LEFT), ("right", 0, RIGHT)):
        p = (px, py)[axis]
        denom = value - VP[axis]
        s = (p - VP[axis]) / denom if denom else 0
        if s <= 0:
            continue
        u = (1 - s) / K
        if not 0 <= u <= 1:
            continue
        other = 1 - axis
        q = VP[other] + ((px, py)[other] - VP[other]) / s
        lo, hi = (LEFT, RIGHT) if other == 0 else (CEIL, FLOOR)
        if lo <= q <= hi:
            X, Y = (value, q) if axis == 0 else (q, value)
            if best is None or u < best[3]:
                best = (name, X, Y, u)
    if best is None:
        s = 1 - K
        best = ("back", VP[0] + (px - VP[0]) / s, VP[1] + (py - VP[1]) / s, 1.0)
    return best

# lights: near-plane X, Y, depth u, colour, strength, reach
LIGHTS = [
    (PW * 0.48, CEIL + 6, 0.04, hx("#FFD9A0"), 0.85, 46),     # the halo overhead
    (LEFT + 22, FLOOR - 22, 0.46, hx("#FFB45A"), 0.80, 22),    # booth lamps
    (LEFT + 22, FLOOR - 22, 0.66, hx("#FFB45A"), 0.70, 20),
    (LEFT + 22, FLOOR - 22, 0.86, hx("#FFB45A"), 0.60, 18),
    (RIGHT - 52, FLOOR - 30, 0.36, hx("#3FD8FF"), 0.80, 16),   # Vesper's screens
    (PW * 0.53, FLOOR - 20, 1.0, hx("#E0402E"), 1.10, 34),     # back room spill
    (RIGHT - 30, FLOOR - 62, 0.50, hx("#FF8C3A"), 0.65, 40),   # pendants over the bar
    (LEFT + 60, FLOOR - 38, 1.0, hx("#00D7FF"), 0.55, 18),     # contract board
]

def light_at(X, Y, u, base_k=1.0):
    total = (0.0, 0.0, 0.0)
    D = depth(u) * 160
    for lx, ly, lu, col, k, reach in LIGHTS:
        LD = depth(lu) * 160
        d2 = (X - lx) ** 2 + (Y - ly) ** 2 + (D - LD) ** 2
        f = k * math.exp(-d2 / (2 * (reach * 1.6) ** 2))
        total = add(total, col, f * base_k)
    return total

def noise(x, y, scale=1.0):
    return (rng.random() - 0.5) * scale

px = [[(0, 0, 0)] * PW for _ in range(PH)]
info = [[None] * PW for _ in range(PH)]

for y in range(PH):
    for x in range(PW):
        name, X, Y, u = surface(x + 0.5, y + 0.5)
        info[y][x] = (name, X, Y, u)
        if name == "floor":
            base = hx("#17120F")
            seam = (abs((X / 34) % 1 - 0.5) > 0.47) or (abs((depth(u) * 9) % 1 - 0.5) > 0.46)
            if seam:
                base = mul(base, 0.75)
        elif name == "ceil":
            base = hx("#0D0A0A")
            if abs(X - PW * 0.18) < 5 or abs(X - PW * 0.86) < 4:     # ducts
                base = hx("#231C19")
        elif name == "left":
            base = hx("#14201F")
            if Y > FLOOR - 30 and u > 0.30:                         # booth backs
                base = hx("#3A1517")
            elif Y > FLOOR - 33 and u > 0.30:
                base = hx("#5A3A22")                                # rail
            elif FLOOR - 62 < Y < FLOOR - 44 and int(u * 9) % 2:
                base = hx("#1E2A28")                                # framed prints
        elif name == "right":
            base = hx("#1C130E")
            if FLOOR - 64 < Y < FLOOR - 30:                         # mirror behind the bottles
                base = hx("#1A1D22")
        else:
            base = hx("#1E1515")
        c = add(base, light_at(X, Y, u), 0.55 if name in ("ceil",) else 0.75)
        fog = min(1.0, depth(u) / 1.8) * 0.30
        c = mix(c, hx("#2A1E1E"), fog)
        px[y][x] = c

def poly(points, colour_fn):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    for y in range(max(0, int(min(ys))), min(PH, int(max(ys)) + 1)):
        for x in range(max(0, int(min(xs))), min(PW, int(max(xs)) + 1)):
            cx, cy, inside = x + 0.5, y + 0.5, False
            j = len(points) - 1
            for i in range(len(points)):
                xi, yi = points[i]
                xj, yj = points[j]
                if (yi > cy) != (yj > cy) and cx < (xj - xi) * (cy - yi) / (yj - yi) + xi:
                    inside = not inside
                j = i
            if inside:
                c = colour_fn(x, y)
                if c is not None:
                    px[y][x] = c

def glow(cx, cy, r, col, k):
    for y in range(max(0, int(cy - 3 * r)), min(PH, int(cy + 3 * r) + 1)):
        for x in range(max(0, int(cx - 3 * r)), min(PW, int(cx + 3 * r) + 1)):
            d2 = (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2
            px[y][x] = add(px[y][x], col, k * math.exp(-d2 / (2 * r * r)))

# --- back wall: the back room door, the boards, the sign
def back_rect(X0, Y0, X1, Y1, colour_fn):
    a, b = proj(X0, Y0, 1), proj(X1, Y1, 1)
    poly([a, (b[0], a[1]), b, (a[0], b[1])], colour_fn)

back_rect(PW * 0.53 - 15, FLOOR - 54, PW * 0.53 + 15, FLOOR, lambda x, y: hx("#2B0F0C"))
back_rect(PW * 0.53 - 11, FLOOR - 50, PW * 0.53 + 11, FLOOR,
          lambda x, y: mix(hx("#C2382A"), hx("#5A140E"), max(0, min(1, (y - 20) / 12))))
dx, dy = proj(PW * 0.53, FLOOR - 30, 1)
glow(dx, dy, 7, hx("#E0402E"), 0.35)
back_rect(LEFT + 44, FLOOR - 52, LEFT + 80, FLOOR - 30,
          lambda x, y: hx("#062A33") if (y % 2) else mix(hx("#0FB8D8"), hx("#062A33"), rng.random() * 0.6))
bx, by = proj(LEFT + 62, FLOOR - 41, 1)
glow(bx, by, 4, hx("#00D7FF"), 0.30)
back_rect(RIGHT - 96, FLOOR - 50, RIGHT - 70, FLOOR - 30,
          lambda x, y: hx("#2A2206") if (y % 2) else mix(hx("#E8B020"), hx("#2A2206"), rng.random() * 0.6))

# --- left: booth partitions, tables and lamps
for u in (0.36, 0.56, 0.76, 0.96):
    a, b = proj(LEFT, FLOOR - 30, u), proj(LEFT + 26, FLOOR - 30, u)
    c, d = proj(LEFT + 26, FLOOR, u), proj(LEFT, FLOOR, u)
    poly([a, b, c, d], lambda x, y, u=u: mix(hx("#2A0E10"), hx("#4A1C1E"), 0.5 + noise(x, y, 0.3)))
    e = proj(LEFT + 26, FLOOR - 30, u)
    for t in range(3):
        if 0 <= int(e[1]) + t < PH and 0 <= int(e[0]) < PW:
            px[int(e[1]) + t][int(e[0])] = hx("#7A4A2A")
for u in (0.46, 0.66, 0.86):
    lx, ly = proj(LEFT + 22, FLOOR - 22, u)
    poly([proj(LEFT + 6, FLOOR - 18, u - 0.05), proj(LEFT + 40, FLOOR - 18, u - 0.05),
          proj(LEFT + 40, FLOOR - 18, u + 0.05), proj(LEFT + 6, FLOOR - 18, u + 0.05)],
         lambda x, y: hx("#3A2416"))
    glow(lx, ly, 2.2 * (1 - K * u) + 0.6, hx("#FFC070"), 0.9)
    if 0 <= int(ly) < PH and 0 <= int(lx) < PW:
        px[int(ly)][int(lx)] = hx("#FFF0C0")

# --- right: back-bar shelves and bottles
for shelf in (FLOOR - 36, FLOOR - 47, FLOOR - 58):
    for i in range(150):
        u = 0.04 + i * 0.0064
        sx, sy = proj(RIGHT, shelf, u)
        if 0 <= int(sy) < PH and 0 <= int(sx) < PW:
            px[int(sy)][int(sx)] = add(hx("#5A3A22"), light_at(RIGHT, shelf, u), 0.5)
    u = 0.05
    while u < 0.95:
        s = 1 - K * u
        hgt = max(1, int(round(8 * s)))
        col = rng.choice(["#C98A2B", "#3F8F4A", "#B8C4C8", "#9A2A2A", "#3A6AB0", "#D8B060", "#6A3A8A"])
        bx, by = proj(RIGHT - 2, shelf, u)
        lit = light_at(RIGHT, shelf - 6, u)
        for k in range(hgt):
            yy = int(by) - 1 - k
            for w in range(max(1, int(round(3 * s)))):
                xx = int(bx) - w
                if 0 <= yy < PH and 0 <= xx < PW:
                    c = add(mul(hx(col), 0.35 + 0.25 * (k / hgt)), lit, 0.6)
                    if w == 0 and k > hgt * 0.4:
                        c = add(c, (120, 110, 90), 0.8)            # glint
                    px[yy][xx] = c
        u += 0.018 + rng.random() * 0.02
# a thin warm strip under the bottom shelf
for i in range(300):
    u = 0.03 + i * 0.0031
    sx, sy = proj(RIGHT, FLOOR - 35, u)
    if 0 <= int(sy) + 1 < PH and 0 <= int(sx) < PW:
        px[int(sy) + 1][int(sx)] = mix(hx("#FF9A40"), px[int(sy) + 1][int(sx)], u * 0.5)

# --- figures
def figure(X, u, head_y, width, body, rim, rim_side=1, seated=False, accent=None):
    s = 1 - K * u
    hx_, hy = proj(X, head_y, u)
    r = 2.6 * s
    shoulder = width * s
    top = hy + r * 1.4
    bottom = proj(X, FLOOR - (18 if seated else 0), u)[1]
    for y in range(int(hy - r - 1), int(bottom) + 1):
        for x in range(int(hx_ - shoulder), int(hx_ + shoulder) + 2):
            if not (0 <= x < PW and 0 <= y < PH):
                continue
            cx, cy = x + 0.5, y + 0.5
            inside_head = (cx - hx_) ** 2 + ((cy - hy) * 1.1) ** 2 <= r * r
            half = shoulder * (0.55 + 0.45 * min(1, max(0, (cy - top) / (2.5 * s + 0.1))))
            inside_body = cy >= top and abs(cx - hx_) <= half * (1 if cy < top + 18 * s else 0.8)
            if inside_head or inside_body:
                edge = (cx - hx_) * rim_side
                lim = r if inside_head else half
                c = body
                if edge > lim - 1.6:
                    c = add(body, rim, 0.9)
                px[y][x] = c
    if accent:
        ax, ay = hx_ - shoulder * 0.7 * rim_side, top + 6 * s
        for y in range(int(ay), int(ay + 2.5 * s) + 1):
            for x in range(int(ax), int(ax + 2.5 * s) + 1):
                if 0 <= x < PW and 0 <= y < PH:
                    px[y][x] = accent
    return hx_, hy, r

# the bar counter (drawn over the back-bar, before the people on the floor side)
INNER, TOP = RIGHT - 64, FLOOR - 26
U0, U1 = 0.0, 0.88
# Vesper first: she stands behind the counter
vx, vy, vr = figure(RIGHT - 40, 0.36, FLOOR - 41, 6.0, hx("#120C0E"), hx("#3FD8FF"), rim_side=-1)
for y in range(int(vy - vr - 1), int(vy - vr * 0.2)):
    for x in range(int(vx - vr), int(vx + vr) + 1):
        if 0 <= x < PW and 0 <= y < PH and (x + 0.5 - vx) ** 2 + (y + 0.5 - vy) ** 2 <= vr * vr * 1.1:
            px[y][x] = hx("#3A2030")                                # her hair, dark plum
poly([proj(INNER, TOP, U0), proj(RIGHT, TOP, U0), proj(RIGHT, TOP, U1), proj(INNER, TOP, U1)],
     lambda x, y: add(hx("#24140D"), light_at(INNER, TOP, info[y][x][3] if info[y][x] else 0.5), 0.45))
poly([proj(INNER, TOP, U0), proj(INNER, TOP, U1), proj(INNER, FLOOR, U1), proj(INNER, FLOOR, U0)],
     lambda x, y: mix(hx("#140C08"), hx("#2C190E"), ((x * 7) % 5) / 10))
poly([proj(INNER, TOP, U1), proj(RIGHT, TOP, U1), proj(RIGHT, FLOOR, U1), proj(INNER, FLOOR, U1)],
     lambda x, y: hx("#1A0F0A"))
for i in range(400):                                                # amber lip light
    u = U0 + (U1 - U0) * i / 400
    sx, sy = proj(INNER, TOP + 3, u)
    if 0 <= int(sy) < PH and 0 <= int(sx) < PW:
        px[int(sy)][int(sx)] = mix(hx("#FFB040"), hx("#7A4010"), u * 0.6)
for i in range(400):                                                # counter edge highlight
    u = U0 + (U1 - U0) * i / 400
    sx, sy = proj(INNER, TOP, u)
    if 0 <= int(sy) < PH and 0 <= int(sx) < PW:
        px[int(sy)][int(sx)] = mix(hx("#B07A4A"), hx("#4A2E1C"), u)
# Vesper's three screens and her drink, on the counter
for k, off in enumerate((-12, -2, 8)):
    sx, sy = proj(RIGHT - 40 + off, TOP - 3, 0.33)
    for yy in range(int(sy) - 2, int(sy) + 1):
        for xx in range(int(sx) - 1, int(sx) + 2):
            if 0 <= yy < PH and 0 <= xx < PW:
                px[yy][xx] = hx("#7FEFFF") if yy == int(sy) - 2 else hx("#1FB8E0")
    glow(sx, sy - 1, 2.5, hx("#3FD8FF"), 0.35)
sx, sy = proj(RIGHT - 22, TOP - 2, 0.33)
px[int(sy)][int(sx)] = hx("#FFC060")
px[int(sy) - 1][int(sx)] = hx("#C08030")

for u in (0.30, 0.50, 0.70):                                         # pendants over the bar
    lx, ly = proj(RIGHT - 34, FLOOR - 62, u)
    top = proj(RIGHT - 34, CEIL, u)[1]
    for yy in range(max(0, int(top)), int(ly)):
        px[yy][int(lx)] = mix(px[yy][int(lx)], hx("#4A3A30"), 0.7)
    glow(lx, ly + 1, 2.5 * (1 - K * u) + 0.5, hx("#FFB060"), 0.8)
    px[int(ly)][int(lx)] = hx("#FFE6B0")

# stools and regulars on the floor side of the counter
for u, sit in ((0.55, True), (0.66, False), (0.78, True), (0.48, False)):
    sx, sy = proj(INNER - 8, FLOOR - 18, u)
    s = 1 - K * u
    for xx in range(int(sx - 3 * s), int(sx + 3 * s) + 1):
        if 0 <= int(sy) < PH and 0 <= xx < PW:
            px[int(sy)][xx] = hx("#4A3A30")
    leg_bottom = proj(INNER - 8, FLOOR, u)[1]
    for yy in range(int(sy) + 1, int(leg_bottom)):
        if 0 <= yy < PH:
            px[yy][int(sx)] = hx("#2A221E")
    if sit:
        figure(INNER - 8, u - 0.01, FLOOR - 36, 6.0, hx("#100B0B"), hx("#FFB45A"), rim_side=1, seated=True)
# regulars in the booths
figure(LEFT + 32, 0.52, FLOOR - 32, 6.0, hx("#0E0A0A"), hx("#FFB45A"), rim_side=-1, seated=True)
figure(LEFT + 34, 0.72, FLOOR - 32, 6.0, hx("#0E0A0A"), hx("#FFB45A"), rim_side=-1, seated=True)
figure(PW * 0.47, 0.70, FLOOR - 42, 5.5, hx("#120D10"), hx("#E0402E"), rim_side=1)  # crossing to the back

# floor reflections of the bright things
for lx, ly, lu, col, k, reach in LIGHTS:
    sx, sy = proj(lx, ly, lu)
    mx, my = proj(lx, FLOOR + (FLOOR - ly), lu)
    for y in range(PH):
        for x in range(max(0, int(mx - 4)), min(PW, int(mx + 5))):
            n = info[y][x]
            if n and n[0] == "floor" and y > proj(lx, FLOOR, lu)[1]:
                d = abs(x + 0.5 - mx) / 2.2 + abs(y - my) / 9
                px[y][x] = add(px[y][x], col, 0.16 * k * math.exp(-d * d))

# the Halo bouncer, near the door on your left, big and close
figure(LEFT + 70, 0.10, FLOOR - 44, 8.5, hx("#0B0809"), hx("#FFD9A0"), rim_side=1, accent=hx("#B01E1E"))

# haze under the halo
glow(*proj(PW * 0.48, CEIL + 30, 0.10), 26, hx("#FFD9A0"), 0.10)

# the halo itself: tin cans on strings, at the top of the frame, near and out of focus
cans = []
for i in range(34):
    th = i / 34 * 2 * math.pi + 0.15
    X = PW * 0.48 + 135 * math.cos(th)
    u = 0.08 + 0.07 * math.sin(th)
    hang = CEIL + 6 + rng.random() * 10 + 4 * math.sin(th * 3)
    cans.append((u, X, hang, rng.random()))
for u, X, hang, tone in sorted(cans, reverse=True):
    if u < 0:
        continue
    s = 1 - K * u
    cx, top = proj(X, CEIL, u)
    _, cy = proj(X, hang, u)
    cw, ch = 3.4 * s, 5.0 * s
    for yy in range(max(0, int(top)), int(cy)):                     # the string
        if 0 <= int(cx) < PW and yy < PH:
            px[yy][int(cx)] = mix(px[yy][int(cx)], hx("#6A5A4A"), 0.6)
    for yy in range(int(cy), int(cy + ch) + 1):
        for xx in range(int(cx - cw / 2), int(cx + cw / 2) + 1):
            if 0 <= yy < PH and 0 <= xx < PW:
                f = (xx + 0.5 - (cx - cw / 2)) / max(1, cw)
                metal = mix(hx("#3A3C44"), hx("#F2EEE4"), max(0, 1 - abs(f - 0.30) * 2.6))
                warm = mix(metal, hx("#FFB060"), 0.10 + 0.25 * tone)
                if (yy - int(cy)) % 2 == 1:
                    warm = mul(warm, 0.88)                          # ridges
                if yy == int(cy) or yy == int(cy + ch):
                    warm = mul(warm, 0.7)                           # rims
                px[yy][xx] = warm
    glow(cx, cy + ch / 2, 2.4 * s, hx("#FFD9A0"), 0.06)

# a little film grain, so the dark reads as a room rather than a fill
for y in range(PH):
    for x in range(PW):
        px[y][x] = clamp(add(px[y][x], (1, 1, 1), noise(x, y, 6)))

# encode in sextants: two colours per cell, chosen by luminance split
def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

def sextant(pattern):
    if pattern == 0:
        return " "
    if pattern == 63:
        return "█"
    if pattern == 21:
        return "▌"
    if pattern == 42:
        return "▐"
    return chr(0x1FB00 + pattern - 1 - (pattern > 21) - (pattern > 42))

for cy_ in range(GR):
    for cx_ in range(GW):
        cells = [px[cy_ * 3 + r][cx_ * 2 + c] for r in range(3) for c in range(2)]
        ls = [lum(c) for c in cells]
        best = None
        for threshold in sorted(set(ls)):
            hi = [i for i in range(6) if ls[i] > threshold]
            lo = [i for i in range(6) if ls[i] <= threshold]
            if not hi:
                continue
            a = tuple(sum(cells[i][k] for i in hi) / len(hi) for k in range(3))
            b = tuple(sum(cells[i][k] for i in lo) / len(lo) for k in range(3))
            err = sum(sum((cells[i][k] - a[k]) ** 2 for k in range(3)) for i in hi) + \
                  sum(sum((cells[i][k] - b[k]) ** 2 for k in range(3)) for i in lo)
            if best is None or err < best[0]:
                best = (err, hi, a, b)
        if best is None or best[0] < 40:
            avg = tuple(sum(c[k] for c in cells) / 6 for k in range(3))
            grid[GY + cy_][GX + cx_] = [" ", avg, clamp(avg), False]
            continue
        _, hi, a, b = best
        pattern = sum(1 << i for i in hi)
        grid[GY + cy_][GX + cx_] = [sextant(pattern), clamp(a), clamp(b), False]

def cell_bg(x, y):
    return grid[y][x][2]

# the sign over the back room door: whole letters, lit
sign = "T I N   H A L O"
sx, sy = proj(PW * 0.53, FLOOR - 62, 1)
row = GY + int(sy // 3)
col = GX + int(sx // 2) - len(sign) // 2
for i, ch in enumerate(sign):
    bg = clamp(mix(cell_bg(col + i, row), hx("#5A2410"), 0.55))
    grid[row][col + i] = [ch, R["sign_amber"], bg, True]
for i in range(-1, len(sign) + 1):
    for r in (row - 1, row + 1):
        c = grid[r][col + i]
        c[2] = clamp(mix(c[2], hx("#3A1A08"), 0.35))

# ---------------------------------------------------------------- frame and header
edge = R["frame_pocket"]
put(0, 0, "╔" + "═" * (W - 2) + "╗", edge)
for y in range(1, H - 1):
    put(0, y, "║", edge)
    put(W - 1, y, "║", edge)
put(0, H - 1, "╚" + "═" * (W - 2), edge)                            # never the bottom-right cell
put(108, 0, "╤", edge)
for y in range(1, 39):
    put(108, y, "│", edge)
put(0, 39, "╟" + "─" * 107 + "┴" + "─" * 22 + "╢", edge)
x = put(2, 0, "SODIUM ROW", R["head_district"])
x = put(x, 0, "═", edge)
x = put(x, 0, "The Tin Halo", R["head_zone"], bold=True)
x = put(x, 0, "═", edge)
x = put(x, 0, "POCKET", R["word_pocket"], bold=True)
put(99, 0, " SCENE ", BG, bg=hx("#808080"))
put(118, 0, " 23:41 ", R["head_night"])

# ---------------------------------------------------------------- below the glimpse
y = GY + GR
fill(1, y, 107, 1, hx("#141416"))
put(3, y, "U N D E R   T H E   H A L O", R["head_zone"], bold=True)
put(80, y, "facing east · lit warm", R["panel_dim"])
y += 2
lore = ["You step under a halo of tin cans. You see Vesper at the end of the bar, three screens beside a",
        "drink. You come here for work. The cans turn in the draught from the door and throw the light",
        "across the room."]
for line in lore:
    put(3, y, line, R["log_place"])
    y += 1
y += 1
x = put(3, y, "Here  ", R["panel_label"])
for name, role, tail in (("Vesper", "npc_vendor", ", "), ("the Halo bouncer", "npc_neutral", ", "),
                         ("four regulars", "npc_neutral", ", "), ("wren", "player_neutral", "")):
    x = put(x, y, name, R[role])
    x = put(x, y, tail, R["panel_text"])
put(x, y, ".", R["panel_text"])
y += 1
x = put(3, y, "Reach ", R["panel_label"])
x = put(x, y, "Enter ", R["key_cap"], bold=True)
put(x, y, "the bouncer: talk", R["panel_text"])
y += 2

put(1, y, "─ WAYS ", R["panel_rule"])
x = put(8, y, "─" * 20, R["panel_rule"])
x = put(x + 1, y, ", .", R["key_cap"], bold=True)
x = put(x, y, " choose  ", R["key_text"])
x = put(x, y, "Space", R["key_cap"], bold=True)
x = put(x, y, " go ", R["key_text"])
put(x, y, "─" * (58 - x), R["panel_rule"])
y += 1
ways = [("»", "Sodium Row", "door", 1, "NW", "thing_exit"),
        ("·", "Vesper's end of the bar", "vendor", 11, "S", "npc_vendor"),
        ("·", "The long bar", "bar", 13, "SE", "thing_vendor"),
        ("·", "The booths", "", 9, "E", "panel_text"),
        ("·", "The back room", "door", 28, "SE", "thing_door"),
        ("∙", "Halo contract board", "terminal", 35, "E", "thing_terminal"),
        ("∙", "Halo market board", "terminal", 34, "SE", "thing_terminal"),
        ("∙", "Ferrymen liaison", "vendor", 31, "SE", "npc_vendor"),
        ("∙", "Tin Halo hardware", "Lattice", 15, "SE", "thing_hardware")]
selected = 1
for i, (mark, name, kind, dist, way, role) in enumerate(ways):
    row = y + i
    sel = i == selected
    bg = hx("#2A2A30") if sel else None
    if sel:
        fill(1, row, 57, 1, bg)
        put(1, row, "▌", R["key_cap"], bg=bg)
    put(3, row, mark, R[role], bg=bg)
    put(5, row, name, R["panel_strong"] if sel else R["panel_text"], bg=bg, bold=sel)
    put(31, row, kind, R["panel_dim"], bg=bg)
    put(42, row, f"{dist:>3} m", R["panel_text"] if sel else R["panel_label"], bg=bg)
    put(49, row, f"{way:<2}", R["panel_label"], bg=bg)
    arrow = {"N": "↑", "NE": "↗", "E": "→", "SE": "↘", "S": "↓", "SW": "↙", "W": "←", "NW": "↖"}[way]
    put(52, row, arrow, R["panel_text"] if sel else R["panel_dim"], bg=bg)

# the selected way, described
bx, by_, bw, bh = 62, y - 1, 45, 11
put(bx, by_, "┌─ VESPER'S END OF THE BAR " + "─" * (bw - 28) + "┐", R["panel_rule"])
for r in range(1, bh - 1):
    put(bx, by_ + r, "│", R["panel_rule"])
    put(bx + bw - 1, by_ + r, "│", R["panel_rule"])
put(bx, by_ + bh - 1, "└" + "─" * (bw - 2) + "┘", R["panel_rule"])
put(bx + 2, by_ + 1, "☻ ", R["npc_vendor"])
put(bx + 4, by_ + 1, "The Tin Halo (Vesper)", R["panel_strong"], bold=True)
put(bx + 2, by_ + 2, "vendor · contracts · trade counter", R["panel_dim"])
for i, line in enumerate(["Three screens and a drink, the far stool.",
                          "Work in Sodium Row comes through her, or",
                          "it does not come."]):
    put(bx + 2, by_ + 4 + i, line, R["log_place"])
put(bx + 2, by_ + 8, "11 m south · about 7 s on foot", R["panel_label"])
x = put(bx + 2, by_ + 9, "Space", R["key_cap"], bold=True)
put(x, by_ + 9, " walks there   any key stops", R["key_text"])

# ---------------------------------------------------------------- side panel
SX, SW = 109, 22
put(SX, 1, "─ AROUND ", R["panel_rule"])
put(SX + 9, 1, "─" * 6, R["panel_rule"])
put(SX + 15, 1, " E ↗ ", R["panel_dim"])
room = ["┌──────────────────┐",
        "│+·· ····· ·····§· │",
        "│@ ·· ·· · · ··  · │",
        "│·:::: · · ·· · ·  │",
        "│▓▓  · ·  · · ▓▓ · │",
        "│ ·  · · ·  ·   ·  │",
        "│▓▓ · ··  · · ▓▓ · │",
        "│ ☻☻ ·  · ·   ·§·  │",
        "│═☻══$═▒═══  ☻═+═· │",
        "│  · ·   ·  ·  ·   │",
        "└──────────────────┘"]
for r, line in enumerate(room):
    for c, ch in enumerate(line):
        role = {"@": None, "☻": "npc_neutral", "§": "thing_terminal", "+": "thing_door", "$": "npc_vendor",
                "▒": "thing_hardware", "═": None, "▓": None, ":": None}.get(ch, "panel_rule" if ch in "┌┐└┘─│" else "panel_dim")
        fg = R[role] if role else R["panel_dim"]
        bg = None
        if ch == "@":
            put(SX + c, 2 + r, "@", R["self_fg"], bg=R["self_bg"], bold=True)
            continue
        if ch == ":":
            fg, bg, ch = hx("#FFD9A0"), hx("#2A2418"), "·"
        if ch == "═":
            fg = hx("#8A5A30")
        if ch == "▓":
            fg = hx("#5A2022")
        # the view cone, faintly lit
        if 1 <= r <= 9 and 1 <= c <= 18 and abs((r - 2) * 3) <= c and ch in "· ":
            bg = hx("#16181A") if bg is None else bg
        put(SX + c, 2 + r, ch, fg, bg=bg)
grid[2 + 8][SX + 5][1] = R["npc_vendor"]                            # Vesper behind the bar
def rule(y, label):
    put(SX, y, "─ " + label + " ", R["panel_rule"])
    put(SX + len(label) + 3, y, "─" * (SW - len(label) - 3), R["panel_rule"])

rule(14, "HERE")
put(SX + 1, 15, "☻", R["npc_neutral"], bold=True)
put(SX + 3, 15, "Halo bouncer", R["panel_strong"], bold=True)
put(SX + SW - 2, 15, "~", R["npc_neutral"], bold=True)
x = put(SX + 1, 16, "Enter", R["key_cap"], bold=True)
put(x, 16, " talk", R["key_text"])
rule(18, "TARGET")
put(SX + 1, 19, "none", R["panel_dim"])
x = put(SX + 8, 19, "Tab", R["key_cap"], bold=True)
put(x, 19, " picks", R["key_text"])
rule(21, "NEARBY")
for i, (g, name, role, tag) in enumerate((("☻", "Halo bouncer", "npc_neutral", "~"),
                                          ("☺", "wren", "player_neutral", "~"),
                                          ("☻", "Regular ×4", "npc_neutral", "~"),
                                          ("☻", "Vesper", "npc_vendor", "~"))):
    put(SX + 1, 22 + i, g, R[role], bold=True)
    put(SX + 3, 22 + i, name, R["panel_text"])
    put(SX + SW - 2, 22 + i, tag, R[role], bold=True)
rule(27, "CREW")
put(SX + 1, 28, "none", R["panel_dim"])
x = put(SX + 8, 28, "G", R["key_cap"], bold=True)
put(x, 28, " invites", R["key_text"])
put(SX, 30, "─" * SW, R["panel_rule"])
put(SX + 1, 31, "Tallis Reyne", R["panel_strong"], bold=True)
put(SX + SW - 3, 31, "G2", R["panel_label"])

def bar(y, label, value, maximum, role):
    put(SX + 1, y, label, R["panel_label"])
    cells = value / maximum * 10
    for i in range(10):
        part = cells - i
        ch, fg = ("█", R[role]) if part >= 1 else ("▌", R[role]) if part >= 0.5 else ("░", R["bar_empty"])
        put(SX + 5 + i, y, ch, fg)
    put(SX + 16, y, f"{value}", R["panel_text"])

bar(32, "HP", 118, 130, "bar_hp")
bar(33, "STA", 61, 70, "bar_sta")
bar(34, "SHK", 4, 100, "bar_shock")
put(SX + 1, 35, "1,240 ch", R["panel_text"])
put(SX + 11, 35, "lease 23/90", R["panel_label"])
put(SX + 1, 36, "discharge 310/1500", R["panel_label"])

# ---------------------------------------------------------------- log
log = [("»", "log_place", "You step under a halo of tin cans.", None),
       ("·", "log_ambient", "Somebody at the bar laughs at something the screens said.", None),
       ('"', "log_speaker", "wren", ": anyone riding the Scour tonight? I have room for two."),
       ('"', "log_speaker", "Halo regular", ": Not with that face, you don't."),
       ("+", "log_system", "Three contracts open on the Halo board.", None),
       ("·", "log_ambient", "The cans turn in the draught from the door.", None)]
for i, (lead, role, text, tail) in enumerate(log):
    row = 41 + i
    put(2, row, lead, R[role], bold=lead == '"')
    x = put(4, row, text, R[role], bold=(role == "log_speaker"))
    if tail:
        put(x, row, tail, R["log_speech"])

# ---------------------------------------------------------------- hint
x = 2
for cap, text in (("Arrows", "step"), (", .", "choose a way"), ("Space", "go"), ("Enter", "talk"),
                  ("Tab", "target"), ("F5", "look"), ("F7", "view"), ("?", "help"), ("Ctrl-X", "leave")):
    x = put(x, 48, cap, R["key_cap"], bold=True)
    x = put(x, 48, " " + text + "   ", R["key_text"])

import sys
sys.path.insert(0, str(Path(__file__).parent))
import raster
glow = [(GX + c, GY + r, (255, 175, 0), 1.6, 0.22) for r in range(GR) for c in range(GW)
        if grid[GY + r][GX + c][0].isalpha() and grid[GY + r][GX + c][1] == R["sign_amber"]]
print(raster.render(grid, Path(__file__).resolve().parents[3] / 'docs/assets/website' / 'tin-halo-scene-132x50-truecolor.png', glow=glow))
