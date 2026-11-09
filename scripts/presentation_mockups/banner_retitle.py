"""Replace BLACKSITE with KARST 41 on the banner, reusing the original letters.

Input is the pre-rename banner, docs/assets/blacksite-banner.png at
282caa2; running it on the edited banner would apply the edit twice:

    git show 282caa2:docs/assets/blacksite-banner.png > old.png
    python scripts/presentation_mockups/banner_retitle.py old.png out.png

K, A, S, T are copied from the painted title. R is B's upper half on K's
lower leg. 4 and 1 are built from the I stem, the T crossbar and two
textured polygons. The old title is removed by multi-scale masked blur
plus grain. Pure Pillow, no numpy.
"""
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

SRC, OUT = sys.argv[1], sys.argv[2]
im = Image.open(SRC).convert('RGB')
W, H = im.size
TOP, BOT = 280, 388           # rows holding the title (caps 282..385)
X0, X1 = 590, 1585
CAP0 = 282

lum = im.convert('L')

# ---- letter alpha from the original painting
def alpha_of(box):
    l = lum.crop(box)
    return l.point(lambda v: max(0, min(255, int((v - 55) * 255 / (165 - 55)))))

def sprite(x0, x1):
    box = (x0, TOP, x1, BOT)
    return im.crop(box), alpha_of(box)

K = sprite(1095, 1189)
A = sprite(842, 957)
S = sprite(1217, 1302)
T = sprite(1386, 1467)
I = sprite(1332, 1362)
B = sprite(607, 710)

# R: B above the split row, K's stem and leg below it
split = 343 - TOP
R_rgb = Image.new('RGB', (103, BOT - TOP)); R_a = Image.new('L', (103, BOT - TOP), 0)
R_rgb.paste(B[0].crop((0, 0, 103, split)), (0, 0)); R_a.paste(B[1].crop((0, 0, 103, split)), (0, 0))
R_rgb.paste(K[0].crop((0, split, 94, BOT - TOP)), (0, split)); R_a.paste(K[1].crop((0, split, 94, BOT - TOP)), (0, split))
R = (R_rgb, R_a)

# texture for polygons: paper colour of the letters, low-frequency mottling and grain
PAPER = (246, 239, 223)
def texture(w, h, seed=41):
    r = random.Random(seed)
    low = Image.new('L', (w, h)); lp = low.load()
    for y in range(h):
        for x in range(w):
            lp[x, y] = max(0, min(255, int(128 + r.gauss(0, 60))))
    low = low.filter(ImageFilter.GaussianBlur(6))
    t = Image.new('RGB', (w, h)); tp = t.load(); lo = low.load()
    for y in range(h):
        for x in range(w):
            m = (lo[x, y] - 128) * 0.35 + r.gauss(0, 2.2)
            tp[x, y] = (int(PAPER[0] + m * 0.6), int(PAPER[1] + m * 0.8), int(PAPER[2] + m * 1.1))
    return t

def poly_mask(w, h, polys, ss=4):
    m = Image.new('L', (w * ss, h * ss), 0)
    d = ImageDraw.Draw(m)
    for p in polys:
        d.polygon([(x * ss, y * ss) for x, y in p], fill=255)
    return m.resize((w, h), Image.LANCZOS)

o = CAP0 - TOP   # cap top inside sprite
capH = 103

def build_four():
    w = 108
    sx = 70                      # stem x
    bar0, bar1 = 62, 82          # bar rows (relative to cap top)
    rgb = texture(w, BOT - TOP)
    a = poly_mask(w, BOT - TOP, [
        [(54, o), (sx + 30, o), (42, o + bar0), (0, o + bar0)],   # diagonal
        [(sx, o), (sx + 30, o), (sx + 30, o + capH), (sx, o + capH)],  # stem
        [(0, o + bar0), (w, o + bar0), (w, o + bar1), (0, o + bar1)],  # bar
    ])
    return rgb, a

def build_one():
    w = 66
    sx = 36
    rgb = texture(w, BOT - TOP)
    a = poly_mask(w, BOT - TOP, [
        [(sx + 2, o), (sx + 2, o + 40), (0, o + 66), (0, o + 26)],
        [(sx, o), (sx + 30, o), (sx + 30, o + capH), (sx, o + capH)],
    ])
    return rgb, a

FOUR, ONE = build_four(), build_one()

# ---- remove the old title
PAD = 30
region = (X0 - PAD, TOP - PAD, X1 + PAD, BOT + 14)
reg = im.crop(region)
rl = reg.convert('L')
seed = Image.new('L', reg.size, 0)
band = rl.crop((PAD - 15, PAD, reg.width - PAD + 15, PAD + BOT - TOP)).point(lambda v: 255 if v > 48 else 0)
seed.paste(band, (PAD - 15, PAD))
HALO = 27
mask = seed.filter(ImageFilter.MaxFilter(HALO))
keep = mask.point(lambda v: 255 - v)
black = Image.new('RGB', reg.size)
pre = Image.composite(reg, black, keep)
fills = []
for r in (8, 20, 45, 90):
    num = pre.filter(ImageFilter.GaussianBlur(r))
    den = keep.filter(ImageFilter.GaussianBlur(r))
    fills.append((num.load(), den.load()))
out = reg.copy(); op = out.load(); mp = mask.load()
rnd = random.Random(41)
for y in range(reg.height):
    for x in range(reg.width):
        if not mp[x, y]:
            continue
        for num, den in fills:
            d = den[x, y]
            if d > 30:
                n = num[x, y]
                g = rnd.gauss(0, 1.6)
                op[x, y] = tuple(max(0, min(255, int(c * 255 / d + g))) for c in n)
                break
blend = mask.filter(ImageFilter.GaussianBlur(4))
clean = Image.composite(out, reg, blend)
result = im.copy()
result.paste(clean, region[:2])

# ---- set KARST 41
glyphs = [K, 22, A, 25, R, 29, S, 28, T, 68, FOUR, 26, ONE]
total = sum(g[0].width if isinstance(g, tuple) else g for g in glyphs)
x = W // 2 - total // 2
alpha_full = Image.new('L', (W, H), 0)
xx = x
for g in glyphs:
    if isinstance(g, int):
        xx += g
        continue
    alpha_full.paste(g[1], (xx, TOP), g[1])
    xx += g[0].width
shadow = alpha_full.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(14))
SHADOW = float(sys.argv[3]) if len(sys.argv) > 3 else 0.55
dark = result.point(lambda v: int(v * (1 - SHADOW)))
result = Image.composite(dark, result, shadow)
for g in glyphs:
    if isinstance(g, int):
        x += g
        continue
    rgb, a = g
    result.paste(rgb, (x, TOP), a)
    x += rgb.width
result.save(OUT, optimize=True)
print('title width', total, 'start', W // 2 - total // 2)
