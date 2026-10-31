"""Sodium Row at night: light the real engine frame and compose the crowd,
side panel and log. Run from the repository root after street_frame.py.

The terrain, objects, signs, marks and frame are the engine's. The light
is what V1's lit layer adds: lamp pools with falloff, neon spill from the
doorways and the signs, wet pavement. People and chrome text are placed
by hand, in their real palette roles and canon glyphs.
"""
import json, math, random, sys, tempfile
from pathlib import Path

ROOT = Path.cwd()
HERE = Path(__file__).parent
sys.path[:0] = [str(ROOT / 'src'), str(HERE)]
from blacksite.content.loader import load_content
from blacksite.content.places import wall
import raster

data = json.loads((Path(tempfile.gettempdir()) / 'blacksite-street-frame.json').read_text(encoding='utf-8'))
grid = data['cells']
meta = data['meta']
H, W = len(grid), len(grid[0])
content = load_content(ROOT / 'src/blacksite/content')
zone = content.zones['sodium-row']
look = json.loads((ROOT / 'src/blacksite/content/looks/sodium-row.json').read_text(encoding='utf-8'))
roles = content.palette.roles


def hx(s):
    s = s.lstrip('#')
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def role(name):
    v = roles[name]['truecolor']['default']
    return hx(v if isinstance(v, str) else v.get('fg', v.get('bg')))


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def add(a, b, k=1.0):
    return tuple(a[i] + b[i] * k for i in range(3))


def mul(a, k):
    return tuple(v * k for v in a)


ox, oy = meta['origin']
vp = meta['viewport']
rng = random.Random(1923)


def screen(mx, my):
    return ox + mx - vp['x'], oy + my - vp['y']


# ------------------------------------------------------------------ light
LAMP = hx('#FF9A3C')
POOL = {'sodium-lamp': (LAMP, 0.62, 1.25), 'sodium-door-pink': (hx('#FF3FC8'), 0.50, 1.05),
        'sodium-door-teal': (hx('#00D2E6'), 0.48, 1.05), 'sodium-stage': (hx('#9B55FF'), 0.55, 1.1)}
lights = []
for region in look['regions']:
    if 'circle' in region and region['theme'] in POOL:
        cx, cy, r = region['circle']
        col, k, s = POOL[region['theme']]
        lights.append((cx, cy, r * s, col, k))
SIGN_COL = {'thing_sign_pink': hx('#FF5FE8'), 'thing_sign_cyan': hx('#00F0FF'), 'thing_sign_amber': hx('#FFAF00')}
signs = []
for sign in look['signs']:
    col = role(sign['role'])
    for i, ch in enumerate(sign['text']):
        if ch != ' ':
            signs.append((sign['at'][0] + i, sign['at'][1], col))


def light(mx, my):
    total = (0.0, 0.0, 0.0)
    for cx, cy, sigma, col, k in lights:
        d2 = ((mx - cx) / 2) ** 2 + (my - cy) ** 2
        total = add(total, col, k * math.exp(-d2 / (2 * sigma * sigma)))
    for sx, sy, col in signs:
        dy = my - sy
        if 0 < dy <= 5 and abs(mx - sx) <= 3:
            total = add(total, col, 0.075 * math.exp(-(dy - 1) / 1.4) * math.exp(-((mx - sx) / 2.2) ** 2))
    return total


GROUND, GRAIN = hx('#15120F'), hx('#2E2416')
WALL, WALLGRAIN = hx('#2A2522'), hx('#3A332E')
puddles = [(rng.uniform(4, 96), rng.uniform(9, 27), rng.uniform(2.5, 6), rng.uniform(0.8, 1.6)) for _ in range(16)]


def wet(mx, my):
    return max((math.exp(-(((mx - px) / pw) ** 2 + ((my - py) / ph) ** 2) * 1.4) for px, py, pw, ph in puddles),
               default=0)


for my in range(zone.height):
    for mx in range(zone.width):
        sx, sy = screen(mx, my)
        if not (0 <= sx < W and 0 <= sy < H):
            continue
        cell = grid[sy][sx]
        tile = content.tiles[zone.tile_at((mx, my))]
        lit = light(mx, my)
        if wall(tile):
            cell[2] = add(WALL, lit, 0.32)
            if cell[0] in ' ·,':
                cell[1] = add(WALLGRAIN, lit, 0.30)
            continue
        w = wet(mx, my)
        bg = add(GROUND, lit, 0.42 + 0.22 * w)
        bg = mix(bg, hx('#0E1820'), 0.35 * w * (1 - min(1, sum(lit) / 300)))
        cell[2] = bg
        if cell[0] in ' ·,\'`.∙':
            cell[1] = add(GRAIN, lit, 0.55 + 0.4 * w)
            # wet pavement throws back the lamp: a few bright specks
            if w > 0.45 and sum(lit) > 120 and rng.random() < 0.20:
                cell[0], cell[1] = rng.choice('·∙'), add(mul(lit, 0.9), (40, 40, 40))
        else:  # things keep their colour, lit a little
            cell[1] = add(cell[1], lit, 0.15)

# sign letters: lit tubes on a dark face
for sx_, sy_, col in signs:
    x, y = screen(sx_, sy_)
    c = grid[y][x]
    c[1], c[2], c[3] = add(col, (30, 30, 30)), add(WALL, col, 0.22), True
for sign in look['signs']:
    for i, ch in enumerate(sign['text']):
        if ch == ' ':
            x, y = screen(sign['at'][0] + i, sign['at'][1])
            grid[y][x][2] = add(WALL, role(sign['role']), 0.16)

# ------------------------------------------------------------------ people
SELF = tuple(meta['me'])


def free(at):
    """Nearest plain floor tile without an object, actor or the player."""
    taken = {tuple(p[0]) for p in crowd_done} | {SELF}
    objects = {o.tile for o in zone.meta.objects}
    for r in range(0, 6):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                t = (at[0] + dx, at[1] + dy)
                if 0 <= t[0] < zone.width and 0 <= t[1] < zone.height and t not in taken and t not in objects:
                    kind = content.tiles[zone.tile_at(t)]
                    if not wall(kind) and kind.id in ('floor', 'street', 'pavement') or kind.plain if hasattr(kind, 'plain') else False:
                        return t
    return at


crowd_done = []
REG, SABLE = role('npc_neutral'), role('npc_sable')
CREW, HOSTILE = role('player_crew'), role('player_hostile')
crowd = [((9, 9), '☻', REG), ((19, 9), '☻', REG), ((21, 10), '☻', REG), ((29, 9), '☻', REG),
         ((32, 9), '☻', SABLE), ((48, 9), '☻', REG), ((51, 10), '☻', REG), ((63, 9), '☻', REG),
         ((65, 10), '☻', REG), ((74, 9), '☻', REG), ((37, 14), '☻', REG), ((61, 14), '☻', REG),
         ((26, 21), '☻', REG), ((24, 22), '☻', REG), ((72, 21), '☻', REG), ((47, 26), '☻', REG),
         ((86, 24), '☻', SABLE), ((88, 25), '☻', SABLE), ((55, 18), '☺', CREW), ((80, 15), '☺', 'hostile')]
for at, glyph, col in crowd:
    t = free(at)
    crowd_done.append((t, glyph, col))
    x, y = screen(*t)
    c = grid[y][x]
    if col == 'hostile':  # hostile: reverse video, the role colour as the cell
        c[0], c[1], c[2], c[3] = '☺', (0, 0, 0), HOSTILE, True
    else:
        c[0], c[1], c[3] = glyph, col, True
x, y = screen(*SELF)
grid[y][x] = ['@', (0, 0, 0), (255, 255, 255), True]
hostile_at = next(t for t, g, c in crowd_done if c == 'hostile')

# ------------------------------------------------------------------ chrome
PANEL, RULE, LABEL, TEXT, DIM, STRONG = (hx('#D0D0D0'), hx('#4E4E4E'), hx('#808080'), hx('#D0D0D0'),
                                         hx('#6C6C6C'), hx('#FFFFFF'))
KEY, KEYT = hx('#FFFFFF'), hx('#808080')
FRAME = None


def put(x, y, text, fg, bg=None, bold=False):
    for ch in text:
        if 0 <= x < W and 0 <= y < H:
            c = grid[y][x]
            c[0], c[1], c[3] = ch, fg, bold
            if bg is not None:
                c[2] = bg
        x += 1
    return x


def clear(x0, y0, w, h):
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            grid[y][x] = [' ', TEXT, (0, 0, 0), False]


# find the panel's left rule and the log rule from the engine frame
PX = next(x for x in range(W - 2, 60, -1) if grid[5][x][0] == '│')
LY = next(y for y in range(20, H - 2) if grid[y][PX][0] in '┴┼╧')
FRAME = tuple(grid[LY][2][1])
# header clock: night
row0 = ''.join(c[0] for c in grid[0])
t = row0.find('00:0')
if t >= 0:
    put(t, 0, '23:41', hx('#FFD7AF'))

SX = PX + 1
SW = W - 1 - SX
clear(SX, 1, SW, LY - 1)


def rule(y, label):
    put(SX, y, '─ ' + label + ' ', RULE)
    put(SX + len(label) + 3, y, '─' * (SW - len(label) - 3), RULE)


def bar(y, label, value, maximum, colour):
    put(SX + 1, y, label, LABEL)
    cells = value / maximum * 10
    for i in range(10):
        part = cells - i
        ch, fg = ('█', colour) if part >= 1 else ('▌', colour) if part >= 0.5 else ('░', hx('#3A3A3A'))
        put(SX + 5 + i, y, ch, fg)
    put(SX + 16, y, f'{value}', TEXT)


y = 1
rule(y, 'TARGET')
put(SX + 1, y + 1, '☺', (0, 0, 0), bg=HOSTILE, bold=True)
put(SX + 3, y + 1, 'Kade Morrow', HOSTILE, bold=True)
put(SX + 16, y + 1, '!', HOSTILE, bold=True)
bar(y + 2, 'HP', 87, 120, HOSTILE)
dist = round(math.hypot(hostile_at[0] - SELF[0], hostile_at[1] - SELF[1]))
put(SX + 1, y + 3, f'{dist} m · no cover', TEXT)
put(SX + 1, y + 4, 'player · hostile', DIM)
put(SX + 1, y + 5, 'Firing marks you', hx('#FFAF00'))
put(SX + 1, y + 6, 'Kessler 9 pistol', DIM)
y = 9
rule(y, 'NEARBY')
near = [('☺', 'wren', CREW, '+', 'crew'), ('☻', 'Regular ×3', REG, '~', ''),
        ('☻', 'Sable enforcer', SABLE, '~', ''), ('$', 'Noodle stall', role('thing_vendor') if 'thing_vendor' in roles else hx('#FFD700'), ' ', ''),
        ('☺', 'Kade Morrow', HOSTILE, '!', 'rev'), ('☻', 'Regular ×9', REG, '~', '')]
for i, (g, name, col, tag, kind) in enumerate(near):
    if kind == 'rev':
        put(SX + 1, y + 1 + i, g, (0, 0, 0), bg=col, bold=True)
    else:
        put(SX + 1, y + 1 + i, g, col, bold=True)
    put(SX + 3, y + 1 + i, name, TEXT)
    put(SX + SW - 2, y + 1 + i, tag, col if tag != ' ' else DIM, bold=True)
y = 17
rule(y, 'CREW')
put(SX + 1, y + 1, '♦', CREW, bold=True)
put(SX + 3, y + 1, 'wren', TEXT)
put(SX + 9, y + 1, '+', CREW, bold=True)
put(SX + 11, y + 1, '██████████'[:8], CREW)
put(SX + 1, y + 2, 'Sodium Row · here', DIM)
# pinned to the bottom
y = LY - 8
put(SX, y, '─' * SW, RULE)
put(SX + 1, y + 1, 'Tallis Reyne', STRONG, bold=True)
put(SX + SW - 3, y + 1, 'G2', LABEL)
bar(y + 2, 'HP', 118, 130, hx('#5FAF5F'))
bar(y + 3, 'STA', 61, 70, hx('#5FAFD7'))
bar(y + 4, 'SHK', 4, 100, hx('#D7AF5F'))
put(SX + 1, y + 5, '1,240 ch', TEXT)
put(SX + 11, y + 5, 'lease 23/90', LABEL)
put(SX + 1, y + 6, 'discharge 310/1500', LABEL)

# log
clear(1, LY + 1, W - 2, H - LY - 3)
LOG = [('»', hx('#D7AF87'), 'Orange lamps, wet pavement, music from six doorways at once.', None, None),
       ('·', hx('#8A8A8A'), 'A tram goes over somewhere above the roofs. The puddles shiver.', None, None),
       ('"', hx('#87D7FF'), 'wren', ': Halo bouncer says Vesper has work. Two of us, tonight.', None),
       ('"', role('npc_neutral'), 'Sodium regular', ': Keep walking, the stage is full.', None),
       ('+', hx('#585858'), 'Sodium Row is contested. Player fights are on here.', None, None),
       ('‼', hx('#FFAF00'), 'Kade Morrow draws on you.', None, True)]
for i, (gutter, col, text, tail, bold) in enumerate(LOG):
    row = LY + 1 + i
    put(1, row, gutter, col, bold=bool(bold) or gutter == '‼')
    x = put(3, row, text, col, bold=bool(bold) or gutter == '"')
    if tail:
        put(x, row, tail, hx('#DADADA'))
# hint line
hint = [('Arrows', 'step'), ('Tab', 'target'), ('F', 'fire'), ('E', 'use'), ('Enter', 'talk'), ('G', 'crew'),
        ('F7', 'view'), ('?', 'help'), ('Ctrl-X', 'leave')]
hy = H - 2
clear(1, hy, W - 2, 1)
x = 2
for cap, text in hint:
    x = put(x, hy, cap, KEY, bold=True)
    x = put(x, hy, ' ' + text + '   ', KEYT)

# ------------------------------------------------------------------ bloom
glow = []
for sx_, sy_, col in signs:
    x, y = screen(sx_, sy_)
    glow.append((x, y, col, 1.4, 0.30))
for cx, cy, sigma, col, k in lights:
    x, y = screen(cx, cy)
    glow.append((x, y, col, sigma * 1.4, 0.10 * k / 0.5))
x, y = screen(*hostile_at)
glow.append((x, y, HOSTILE, 1.0, 0.25))
out = Path(__file__).resolve().parents[3] / 'docs/assets/website' / 'sodium-row-night-132x50-truecolor.png'
print(raster.render(grid, out, glow=glow), out)
