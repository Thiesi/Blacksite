"""The Lattice, Sodium Row sector, 132x50 truecolor. Hand-composed to UI
section 3 (linework on black, D7) and the world doc's Sodium Row sector:
20 cells (14 public, 4 gated, 2 hidden), the Tin Halo and House Lights
cores, the Stage Door descent. Your body sits in a Tin Halo chair, so the
frame is the pocket's double line.

    python lattice_mock.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import raster

W, H = 132, 50


def hx(s):
    s = s.lstrip('#')
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


BLACK = (0, 0, 0)
C = {k: hx(v) for k, v in {
    'frame': '#2A8A8A', 'pocket': '#5FD7D7', 'head': '#FFFFFF', 'dim': '#8A8A8A', 'night': '#FFD7AF',
    'dot': '#262321', 'link': '#B8792A', 'link_dim': '#6E4A1C', 'cell': '#FFC46B', 'gate': '#9A7BFF',
    'gate_dim': '#5A4A9A', 'hidden': '#4FB8C4', 'descent': '#6F8CFF', 'uplink': '#F0F0F0',
    'vesper': '#FBBF24', 'house': '#E8E2F0', 'self_fg': '#000000', 'self_bg': '#FFE0A8',
    'crew': '#4ADE80', 'hostile': '#F87171', 'neutral': '#D1D5DB',
    'rule': '#4E4E4E', 'label': '#808080', 'text': '#D0D0D0', 'strong': '#FFFFFF', 'key': '#FFFFFF',
    'keyt': '#808080', 'int': '#5FD7D7', 'trace': '#FFAF00', 'hp': '#5FAF5F', 'empty': '#3A3A3A',
    'place': '#E7B77A', 'ambient': '#8A7A66', 'speaker': '#87D7FF', 'speech': '#DADADA',
    'system': '#6A6258', 'reward': '#9AA88A', 'danger': '#FFAF00', 'now': '#FFD7AF',
}.items()}

grid = [[[' ', C['text'], BLACK, False] for _ in range(W)] for _ in range(H)]
glow = []


def put(x, y, text, fg, bg=None, bold=False):
    for ch in text:
        if 0 <= x < W and 0 <= y < H and not (x == W - 1 and y == H - 1):
            c = grid[y][x]
            c[0], c[1], c[3] = ch, fg, bold
            if bg is not None:
                c[2] = bg
        x += 1
    return x


# ------------------------------------------------------------------ frame
FX0, FX1, FY0, FY1 = 1, 107, 1, 31          # the field
SX, SW = 109, 22
LOGY = 39
e = C['frame']
put(0, 0, '╔' + '═' * (W - 2) + '╗', e)
for y in range(1, H - 1):
    put(0, y, '║', e)
    put(W - 1, y, '║', e)
put(0, H - 1, '╚' + '═' * (W - 2), e)
put(108, 0, '╤', e)
for y in range(1, LOGY):
    put(108, y, '│', e)
put(0, LOGY, '╟' + '─' * 107 + '┴' + '─' * 22 + '╢', e)
x = put(2, 0, 'DOWN', C['dim'])
x = put(x, 0, '═', e)
x = put(x, 0, 'Sodium Row', C['head'], bold=True)
x = put(x, 0, ' / Lattice', C['cell'], bold=True)
x = put(78, 0, 'body', C['dim'])
x = put(x, 0, '═', e)
x = put(x, 0, 'The Tin Halo', C['head'])
x = put(x, 0, '═', e)
put(x, 0, 'POCKET', C['pocket'], bold=True)
put(118, 0, ' 23:58 ', C['night'])

# ------------------------------------------------------------------ the field
for y in range(FY0 + 1, FY1, 2):            # the old engineers' grid, faint
    for x in range(FX0 + 2, FX1, 4):
        put(x, y, '·', C['dot'])

COLS = [8, 31, 54, 77, 100]
ROWS = [5, 12, 19, 26]
# name, kind: public / gated / hidden / uplink / descent
CELLS = {
    (0, 0): ('Core uplink', 'uplink'), (1, 0): ('Neon Stair node', 'public'), (2, 0): ('Sign Grid', 'gated'),
    (3, 0): ('Ticket bus', 'public'), (4, 0): ('Open Late feed', 'public'),
    (0, 1): ('Row entrance', 'public'), (1, 1): ('Live Room bus', 'public'), (2, 1): ('Stage bus', 'public'),
    (3, 1): ('Card court relay', 'public'), (4, 1): ('Late bar cabinet', 'gated'),
    (0, 2): ('Narrow bar node', 'public'), (1, 2): ('Tin Halo Back Bar', 'public'), (2, 2): ('Puddle switch', 'public'),
    (3, 2): ('House Lights entrance', 'public'), (4, 2): ('Tin Halo square', 'public'),
    (0, 3): ('Stairwell cabinet', 'gated'), (1, 3): ('Drain tap', 'hidden'), (2, 3): ('Stage Door', 'descent'),
    (3, 3): ('Lockup cabinet', 'gated'), (4, 3): ('Alley relay', 'public'),
}
GLYPH = {'public': ('■', 'cell'), 'gated': ('╪', 'gate'), 'hidden': ('∙', 'hidden'),
         'uplink': ('∩', 'uplink'), 'descent': ('∞', 'descent')}


def at(c, r):
    return COLS[c], ROWS[r]


def hline(x0, x1, y, kind):
    ch, col = {'public': ('─', 'link'), 'gated': ('═', 'gate_dim'), 'hidden': ('·', 'hidden')}[kind]
    for x in range(min(x0, x1) + 1, max(x0, x1)):
        if kind == 'hidden' and x % 2:
            continue
        put(x, y, ch, C[col])


def vline(x, y0, y1, kind):
    ch, col = {'public': ('│', 'link'), 'gated': ('║', 'gate_dim'), 'hidden': ('·', 'hidden')}[kind]
    for y in range(min(y0, y1) + 1, max(y0, y1)):
        put(x, y, ch, C[col])


def dline(a, b, kind):
    """A diagonal link: '\\' or '/', two columns per row on a 2:1 cell."""
    (x0, y0), (x1, y1) = a, b
    ch = '\\' if (x1 - x0) * (y1 - y0) > 0 else '/'
    col = C['link'] if kind == 'public' else C['gate_dim']
    steps = abs(y1 - y0)
    for i in range(1, steps):
        put(round(x0 + (x1 - x0) * i / steps), y0 + (1 if y1 > y0 else -1) * i, ch, col)


def link_kind(a, b):
    ka, kb = CELLS[a][1], CELLS[b][1]
    if 'hidden' in (ka, kb) or 'descent' in (ka, kb):
        return 'hidden'
    if 'gated' in (ka, kb):
        return 'gated'
    return 'public'


LINKS = [((0, 0), (1, 0)), ((1, 0), (2, 0)), ((2, 0), (3, 0)), ((3, 0), (4, 0)),
         ((0, 1), (1, 1)), ((1, 1), (2, 1)), ((2, 1), (3, 1)), ((3, 1), (4, 1)),
         ((0, 2), (1, 2)), ((2, 2), (3, 2)),
         ((0, 3), (1, 3)), ((1, 3), (2, 3)), ((3, 3), (4, 3)),
         ((0, 0), (0, 1)), ((0, 1), (0, 2)), ((0, 2), (0, 3)),
         ((1, 0), (1, 1)), ((1, 1), (1, 2)),
         ((2, 0), (2, 1)), ((2, 1), (2, 2)), ((2, 2), (2, 3)),
         ((3, 0), (3, 1)), ((3, 1), (3, 2)), ((3, 2), (3, 3)),
         ((4, 0), (4, 1)), ((4, 1), (4, 2)), ((4, 2), (4, 3))]
for a, b in LINKS:
    (x0, y0), (x1, y1) = at(*a), at(*b)
    kind = link_kind(a, b)
    if y0 == y1:
        hline(x0, x1, y0, kind)
    else:
        vline(x0, y0, y1, kind)
dline(at(1, 2), at(2, 3), 'hidden')          # the found way to the Stage Door
dline(at(0, 1), at(1, 0), 'public')
dline(at(3, 0), at(4, 1), 'public')
dline(at(2, 1), at(3, 2), 'public')

# cores: buildings in the owner's colour, joined to their entrance cells
def core(cx, cy, initial, colour, entrance):
    put(cx - 2, cy - 1, '╔═══╗', colour, bold=True)
    put(cx - 2, cy, '║', colour, bold=True)
    put(cx - 1, cy, ' ' + initial + ' ', colour, bold=True)
    put(cx + 2, cy, '║', colour, bold=True)
    put(cx - 2, cy + 1, '╚═══╝', colour, bold=True)
    ex, ey = at(*entrance)
    if ey == cy:
        for x in range(min(ex, cx) + 1, max(ex, cx) - 2):
            put(x, cy, '─', C['link'])
    glow.append((cx, cy, colour, 3.2, 0.32))


core(42, 19, 'T', C['vesper'], (1, 2))       # the Tin Halo, Vesper's
core(88, 19, 'H', C['house'], (3, 2))        # House Lights, neutral, Sable-enforced
put(39, 17, 'Vesper', C['vesper'])
put(85, 17, 'neutral', C['dim'])

for (c, r), (name, kind) in CELLS.items():
    x, y = at(c, r)
    g, col = GLYPH[kind]
    put(x, y, g, C[col], bold=True)
    glow.append((x, y, C[col], 1.3 if kind != 'hidden' else 0.9, 0.30 if kind == 'public' else 0.22))

# you: the reverse-video cell; runners: ♦ beside their cell
yx, yy = at(3, 2)
put(yx, yy, '■', C['self_fg'], bg=C['self_bg'], bold=True)
glow.append((yx, yy, C['self_bg'], 2.0, 0.45))
put(yx - 2, yy + 1, '♦', C['crew'], bold=True)            # wren, crew
glow.append((yx - 2, yy + 1, C['crew'], 1.0, 0.25))
kx, ky = at(2, 1)
put(kx + 2, ky - 1, '♦', C['hostile'], bold=True)          # Kade Morrow
glow.append((kx + 2, ky - 1, C['hostile'], 1.2, 0.35))
ux, uy = at(0, 0)
put(ux + 2, uy - 1, '♦', C['neutral'], bold=True)          # a stranger at the uplink

# caption: where you are, then every link from your cell
cy = FY1 + 1
put(3, cy, '■', C['self_fg'], bg=C['self_bg'], bold=True)
x = put(5, cy, 'House Lights entrance', C['strong'], bold=True)
put(x + 2, cy, 'core entrance · Sable-enforced · tier 3', C['dim'])
x = 3
for arrow, name, note in (('←', 'Puddle switch', ''), ('↑', 'Card court relay', ''), ('→', 'House Lights', ' core'),
                          ('↗', 'Tin Halo square', ''), ('↓', 'Lockup cabinet', ' gated')):
    x = put(x, cy + 1, arrow + ' ', C['cell'], bold=True)
    x = put(x, cy + 1, name, C['text'])
    x = put(x, cy + 1, note + '   ', C['gate'] if 'gated' in note else C['dim'])
x = put(3, cy + 3, 'E', C['key'], bold=True)
put(x, cy + 3, ' enter House Lights: Tripwire at the door, trace read on entry (34 carried).', C['label'])
# square has no link from here in LINKS; keep the caption truthful
put(3, cy + 1, ' ' * 104, BLACK)
x = 3
for arrow, name, note in (('←', 'Puddle switch', ''), ('↖', 'Stage bus', ''), ('↑', 'Card court relay', ''),
                          ('→', 'House Lights', ' core'), ('↓', 'Lockup cabinet', ' gated')):
    x = put(x, cy + 1, arrow + ' ', C['cell'], bold=True)
    x = put(x, cy + 1, name, C['text'])
    x = put(x, cy + 1, note + '   ', C['gate'] if 'gated' in note else C['dim'])

# ------------------------------------------------------------------ side panel
def rule(y, label):
    put(SX, y, '─ ' + label + ' ', C['rule'])
    put(SX + len(label) + 3, y, '─' * (SW - len(label) - 3), C['rule'])


def bar(y, label, value, maximum, colour, marks=()):
    put(SX + 1, y, label, C['label'])
    cells = value / maximum * 10
    for i in range(10):
        part = cells - i
        ch, fg = ('█', colour) if part >= 1 else ('▌', colour) if part >= 0.5 else ('░', C['empty'])
        put(SX + 5 + i, y, ch, fg)
    for m in marks:  # thresholds: a bright tick in the bar
        put(SX + 5 + int(m / maximum * 10) - (1 if m == maximum else 0), y, '│', C['strong'], bold=True)
    put(SX + 16, y, f'{value}', C['text'])


rule(1, 'RUNNER')
bar(2, 'INT', 72, 100, C['int'])
bar(3, 'TRC', 34, 100, C['trace'], marks=(50,))
put(SX + 1, 4, 'at 50: House Lights', C['label'])
put(SX + 1, 5, 'learns a runner is in', C['label'])
rule(7, 'BODY')
put(SX + 1, 8, 'The Tin Halo', C['text'])
put(SX + 15, 8, 'POCKET', C['pocket'], bold=True)
put(SX + 1, 9, 'HP', C['label'])
for i in range(10):
    put(SX + 5 + i, 9, '█' if i < 9 else '░', C['hp'] if i < 9 else C['empty'])
put(SX + 16, 9, '118', C['text'])
put(SX + 1, 10, 'black ICE: none here', C['dim'])
rule(12, 'NOW')
put(SX + 1, 13, 'Lift the patron', C['now'])
put(SX + 1, 14, 'ledger, House Lights', C['now'])
rule(16, 'TARGET')
put(SX + 1, 17, 'none', C['dim'])
x = put(SX + 8, 17, 'Tab', C['key'], bold=True)
put(x, 17, ' picks', C['keyt'])
rule(19, 'NEAR')
for i, (g, name, col, tag) in enumerate((('♦', 'wren', 'crew', '+'), ('♦', 'Kade Morrow', 'hostile', '!'),
                                          ('♦', 'a runner', 'neutral', '~'))):
    put(SX + 1, 20 + i, g, C[col], bold=True)
    put(SX + 3, 20 + i, name, C['text'])
    put(SX + SW - 2, 20 + i, tag, C[col], bold=True)
put(SX + 1, 23, 'Kade: 2 cells NW', C['label'])
rule(25, 'RIG')
RIG = [('Drill', 0), ('Umbrella', 0), ('Compass', 0), ('Sneakers', 4), ('Lantern', 0), ('Slicker', 0), ('Cutout', 7)]
for i, (prog, cool) in enumerate(RIG):
    y = 26 + i
    put(SX + 1, y, str(i + 1), C['key'], bold=True)
    put(SX + 3, y, prog, C['text'] if not cool else C['label'])
    if cool:
        put(SX + 13, y, '▪' * min(cool, 4), C['trace'])
        put(SX + 18, y, f'{cool}s', C['label'])
put(SX, 34, '─' * SW, C['rule'])
put(SX + 1, 35, 'Tallis Reyne', C['strong'], bold=True)
put(SX + SW - 3, 35, 'G2', C['label'])
put(SX + 1, 36, '1,360 ch', C['text'])
put(SX + 11, 36, 'lease 23/90', C['label'])
put(SX + 1, 37, 'discharge 310/1500', C['label'])

# ------------------------------------------------------------------ log (sector colour, own gutters)
LOG = [('»', 'place', 'You go down. Sodium Row resolves, amber and loud, half its lights on a timer.', None),
       ('·', 'ambient', 'The Sign Grid pulses in time with the stage upstairs.', None),
       ('"', 'speaker', 'wren', ': On your left. Shiv first, before it reports.'),
       ('√', 'reward', 'Contract archive lifted from the Tin Halo.  120 ch', None),
       ('+', 'system', 'Trace carries: 34. House Lights reads it on entry.', None),
       ('‼', 'danger', 'Kade Morrow is two cells out, and coming.', None)]
for i, (gutter, kind, text, tail) in enumerate(LOG):
    y = LOGY + 1 + i
    put(2, y, gutter, C[kind], bold=kind in ('danger', 'speaker'))
    x = put(4, y, text, C[kind], bold=kind in ('danger', 'speaker'))
    if tail:
        put(x, y, tail, C['speech'])
x = 2
for cap, text in (('Arrows', 'links'), ('E', 'enter'), ('J', 'jack out'), ('Tab', 'target'), ('1-7', 'cast'),
                  ('R', 'rig'), ('G', 'crew'), ('?', 'help')):
    x = put(x, 48, cap, C['key'], bold=True)
    x = put(x, 48, ' ' + text + '   ', C['keyt'])

out = Path(__file__).resolve().parents[3] / 'docs/assets/website' / 'lattice-sodium-row-132x50-truecolor.png'
print(raster.render(grid, out, glow=glow), out)
