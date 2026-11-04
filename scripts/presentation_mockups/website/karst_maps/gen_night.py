"""Atmospheric artboard: Karst at night under the Ring, seen obliquely from the south."""
import io, math, random
from karst import *

W, H = 1600, 1200
CX, CY, S, K = 820, 720, 12, 0.5   # K squashes north-south for the oblique view
P = lambda x, y: (CX + (x - 50) * S, CY + (y - 50) * S * K)
rnd = random.Random(41)

DCOL = {k: v[2] for k, v in DISTRICTS.items()}
DCOL.update(spire='#E0A030', core='#BFD7F2')
SODIUM = '#F2C46A'

o = []
o.append(f'<div style="width: {W}px; height: {H}px; position: relative; overflow: hidden; background: #05060A; font-family: \'IBM Plex Serif\', Georgia, serif; color: #E6E1D6">')
o.append(f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="position: absolute; left: 0; top: 0" role="img" aria-label="Karst at night, seen at an angle from the south: city lights in the colours of the districts, the Spire lit at the centre, the Sink a dark pit with a red rim, a searchlight from Gate Nine sweeping the Scour, and the debris Ring arching across the sky.">')
o.append('''<defs>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0B1222"></stop><stop offset="0.55" stop-color="#070A12"></stop><stop offset="1" stop-color="#05060A"></stop></linearGradient>
<radialGradient id="cityHaze" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#F2C46A" stop-opacity="0.16"></stop><stop offset="0.7" stop-color="#F2C46A" stop-opacity="0.05"></stop><stop offset="1" stop-color="#F2C46A" stop-opacity="0"></stop></radialGradient>
<radialGradient id="scourGlow" cx="0.5" cy="0.5" r="0.5"><stop offset="0.55" stop-color="#3A1E10" stop-opacity="0.55"></stop><stop offset="1" stop-color="#05060A" stop-opacity="0"></stop></radialGradient>
<radialGradient id="spire" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#FFE2A0" stop-opacity="0.9"></stop><stop offset="0.25" stop-color="#E0A030" stop-opacity="0.35"></stop><stop offset="1" stop-color="#E0A030" stop-opacity="0"></stop></radialGradient>
<radialGradient id="sinkRim" cx="0.5" cy="0.5" r="0.5"><stop offset="0.55" stop-color="#000000" stop-opacity="1"></stop><stop offset="0.72" stop-color="#D64545" stop-opacity="0.65"></stop><stop offset="1" stop-color="#D64545" stop-opacity="0"></stop></radialGradient>
<linearGradient id="beam" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#FFF3D6" stop-opacity="0.32"></stop><stop offset="1" stop-color="#FFF3D6" stop-opacity="0"></stop></linearGradient>
<linearGradient id="shaftBeam" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#FFE2A0" stop-opacity="0.35"></stop><stop offset="1" stop-color="#FFE2A0" stop-opacity="0"></stop></linearGradient>
<filter id="blur8" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="8"></feGaussianBlur></filter>
<filter id="blur30" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="30"></feGaussianBlur></filter>
<filter id="blur2" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.6"></feGaussianBlur></filter>''')
for k, c in DCOL.items():
    o.append(f'<radialGradient id="g-{k}" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{c}" stop-opacity="0.42"></stop><stop offset="1" stop-color="{c}" stop-opacity="0"></stop></radialGradient>')
o.append('</defs>')
o.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#sky)"></rect>')

# stars
o.append('<g fill="#E6E1D6">')
for _ in range(260):
    x, y = rnd.uniform(0, W), rnd.uniform(0, 520) ** 1.0
    o.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.choice([0.5, 0.6, 0.8, 1.1]):.1f}" opacity="{rnd.uniform(0.15, 0.6):.2f}"></circle>')
o.append('</g>')

# the Ring: a wide luminous arc with debris
ring = 'M-100 520 Q800 -40 1700 300'
o.append('<g fill="none" stroke-linecap="round">')
o.append(f'<path d="{ring}" stroke="{{{{ringColor}}}}" stroke-opacity="0.08" stroke-width="90" filter="url(#blur30)"></path>')
o.append(f'<path d="{ring}" stroke="{{{{ringColor}}}}" stroke-opacity="0.18" stroke-width="22" filter="url(#blur8)"></path>')
o.append(f'<path d="{ring}" stroke="#FFF3D6" stroke-opacity="0.7" stroke-width="2.5" stroke-dasharray="1 13" stroke-dashoffset="4"></path>')
o.append(f'<path d="M-100 526 Q800 -34 1700 306" stroke="#FFF3D6" stroke-opacity="0.45" stroke-width="1.5" stroke-dasharray="0.5 7"></path>')
o.append(f'<path d="M-100 512 Q800 -48 1700 292" stroke="{{{{ringColor}}}}" stroke-opacity="0.6" stroke-width="4" stroke-dasharray="0.5 41" stroke-dashoffset="19"></path>')
o.append('</g>')
# a falling fragment over the Scour
o.append('<path d="M1330 250 L1412 470" stroke="#FFF3D6" stroke-opacity="0.5" stroke-width="1.4" stroke-linecap="round"></path><circle cx="1412" cy="470" r="2.2" fill="#FFF3D6"></circle><circle cx="1412" cy="470" r="9" fill="#FFF3D6" opacity="0.18" filter="url(#blur2)"></circle>')

# the Scour, east of the wall
sx, sy = P(50, 50)
o.append(f'<ellipse cx="{sx}" cy="{sy}" rx="{60 * S:.0f}" ry="{60 * S * K:.0f}" fill="url(#scourGlow)"></ellipse>')
for r in (47, 54, 61):
    o.append(f'<ellipse cx="{sx}" cy="{sy}" rx="{r * S:.0f}" ry="{r * S * K:.0f}" fill="none" stroke="#B5653A" stroke-opacity="0.16" stroke-width="1" stroke-dasharray="2 9"></ellipse>')
o.append('<g>')
for _ in range(46):  # salvage fires, east only
    b = rnd.uniform(25, 160); r = rnd.uniform(43, 64)
    x, y = 50 + r * math.sin(math.radians(b)), 50 - r * math.cos(math.radians(b))
    px, py = P(x, y)
    if px > W - 10:
        continue
    s = rnd.uniform(0.8, 1.8)
    o.append(f'<circle cx="{px:.0f}" cy="{py:.0f}" r="{s * 4:.1f}" fill="#EE8434" opacity="0.18" filter="url(#blur2)"></circle><circle cx="{px:.0f}" cy="{py:.0f}" r="{s:.1f}" fill="#FFB060" opacity="0.85"></circle>')
o.append('</g>')
lx, ly = P(50 + 27 * 1.6 * math.sin(math.radians(110)), 50 - 27 * 1.6 * math.cos(math.radians(110)))
o.append(f'<circle cx="{lx:.0f}" cy="{ly:.0f}" r="16" fill="#EE8434" opacity="0.25" filter="url(#blur8)"></circle><circle cx="{lx:.0f}" cy="{ly:.0f}" r="2.6" fill="#FFD9A0"></circle>')

# searchlight from Gate Nine
gx, gy = P(88, 45)
o.append(f'<g opacity="{{{{beamOpacity}}}}"><path d="M{gx:.0f} {gy:.0f} L{W + 40} {gy - 170:.0f} L{W + 40} {gy - 20:.0f} Z" fill="url(#beam)"></path></g>')

# city haze and the plateau edge
o.append(f'<ellipse cx="{CX}" cy="{CY}" rx="{44 * S:.0f}" ry="{44 * S * K:.0f}" fill="url(#cityHaze)" filter="url(#blur8)"></ellipse>')
o.append(f'<ellipse cx="{CX}" cy="{CY}" rx="{40 * S:.0f}" ry="{40 * S * K:.0f}" fill="#0A0D15" fill-opacity="0.65"></ellipse>')

# district glows
for zid, name, dist, x, y, cls, planned in ZONES:
    px, py = P(x, y)
    rr = {'safe': 70, 'contested': 54, 'pocket': 30}[cls]
    o.append(f'<ellipse cx="{px:.0f}" cy="{py:.0f}" rx="{rr}" ry="{rr * K + 4:.0f}" fill="url(#g-{dist})"></ellipse>')

# lights: background fabric then zone clusters
o.append('<g>')
for _ in range(1100):
    r = 39 * math.sqrt(rnd.random()); b = rnd.uniform(0, 360)
    x, y = 50 + r * math.sin(math.radians(b)), 50 - r * math.cos(math.radians(b))
    if math.hypot(x - 78, y - 64) < 5.5:  # the Sink is dark
        continue
    px, py = P(x, y)
    o.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{rnd.choice([0.6, 0.8, 1.0]):.1f}" fill="{SODIUM}" opacity="{rnd.uniform(0.12, 0.45):.2f}"></circle>')
for zid, name, dist, x, y, cls, planned in ZONES:
    n = {'safe': 70, 'contested': 46, 'pocket': 16}[cls]
    for _ in range(n):
        dx, dy = rnd.gauss(0, 2.0), rnd.gauss(0, 2.0)
        if math.hypot(x + dx - 78, y + dy - 64) < 5.5:
            continue
        px, py = P(x + dx, y + dy)
        c = DCOL[dist] if rnd.random() < 0.55 else SODIUM
        o.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{rnd.choice([0.7, 0.9, 1.2, 1.5]):.1f}" fill="{c}" opacity="{rnd.uniform(0.45, 0.95):.2f}"></circle>')
o.append('</g>')
# tram lines as faint threads of light
hx, hy = P(47, 57)
o.append('<g stroke="#FFF3D6" stroke-opacity="0.22" stroke-width="1" stroke-dasharray="1 3">')
for line, term, planned in TRAMS:
    x, y = P(*ZPOS[term]); o.append(f'<line x1="{hx:.0f}" y1="{hy:.0f}" x2="{x:.0f}" y2="{y:.0f}"></line>')
o.append('</g>')

# the Sink
kx, ky = P(78, 64)
o.append(f'<ellipse cx="{kx:.0f}" cy="{ky:.0f}" rx="{7.5 * S:.0f}" ry="{7.5 * S * K:.0f}" fill="url(#sinkRim)"></ellipse>')
o.append(f'<ellipse cx="{kx:.0f}" cy="{ky:.0f}" rx="{4.6 * S:.0f}" ry="{4.6 * S * K:.0f}" fill="#000000"></ellipse>')
for i in range(7):  # cable-car lamps and terraces lights inside the pit
    a = rnd.uniform(200, 340)
    o.append(f'<circle cx="{kx + 3.6 * S * math.cos(math.radians(a)):.0f}" cy="{ky + 3.6 * S * K * math.sin(math.radians(a)) + 4:.0f}" r="1" fill="#FF7A6A" opacity="0.8"></circle>')

# the wall: a faint lit rim with lamps, brighter at Gate Nine and the Wallwalk
o.append(f'<ellipse cx="{CX}" cy="{CY}" rx="{40 * S:.0f}" ry="{40 * S * K:.0f}" fill="none" stroke="#5A6378" stroke-opacity="0.55" stroke-width="3"></ellipse>')
o.append('<g fill="#FFE2A0">')
for b in range(0, 360, 6):
    px, py = P(50 + 40 * math.sin(math.radians(b)), 50 - 40 * math.cos(math.radians(b)))
    o.append(f'<circle cx="{px:.0f}" cy="{py:.0f}" r="{1.4 if 40 <= b <= 95 else 0.8}" opacity="{0.9 if 40 <= b <= 95 else 0.35}"></circle>')
o.append('</g>')
o.append(f'<rect x="{gx - 4:.0f}" y="{gy - 9:.0f}" width="9" height="12" fill="#EE8434"></rect><circle cx="{gx:.0f}" cy="{gy - 4:.0f}" r="14" fill="#EE8434" opacity="0.3" filter="url(#blur8)"></circle>')

# the Spire: a lit tower on the shaft, its beacon reaching for the Ring
tx, ty = P(50, 41)
o.append(f'<rect x="{tx - 2:.0f}" y="120" width="4" height="{ty - 300:.0f}" fill="url(#shaftBeam)"></rect>')
o.append(f'<ellipse cx="{tx:.0f}" cy="{ty - 70:.0f}" rx="60" ry="110" fill="url(#spire)"></ellipse>')
o.append(f'<polygon points="{tx - 14:.0f},{ty:.0f} {tx - 6:.0f},{ty - 150:.0f} {tx:.0f},{ty - 186:.0f} {tx + 6:.0f},{ty - 150:.0f} {tx + 14:.0f},{ty:.0f}" fill="#0E1018" stroke="#E0A030" stroke-opacity="0.8" stroke-width="1.2"></polygon>')
o.append('<g fill="#FFE2A0">')
for i in range(26):
    yy = ty - 10 - i * 5.5
    if rnd.random() < 0.7:
        o.append(f'<rect x="{tx - 4 + rnd.choice([-3, 0, 3]):.0f}" y="{yy:.0f}" width="1.6" height="1.6" opacity="{rnd.uniform(0.5, 1):.2f}"></rect>')
o.append(f'</g><circle cx="{tx:.0f}" cy="{ty - 188:.0f}" r="2.5" fill="#FF5A4A"></circle><circle cx="{tx:.0f}" cy="{ty - 188:.0f}" r="10" fill="#FF5A4A" opacity="0.35" filter="url(#blur2)"></circle>')

# low fog banks
o.append('<g filter="url(#blur30)">')
for x, y, rx, ry, op in [(560, 960, 420, 40, 0.10), (1180, 990, 380, 36, 0.08), (820, 1060, 600, 50, 0.10), (300, 700, 260, 26, 0.06), (1260, 760, 300, 28, 0.06)]:
    o.append(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="#A3ACBA" opacity="{op}"></ellipse>')
o.append('</g>')

# whispered labels
o.append('<g opacity="{{labelOpacity}}" font-style="italic" font-size="15" fill="#E6E1D6" fill-opacity="0.62" text-anchor="middle" letter-spacing="1">')
cent = {}
for zid, name, dist, x, y, cls, planned in ZONES:
    cent.setdefault(dist, []).append((x, y))
names = {'spire': 'the Spire', 'core': 'the Core', 'vatside': 'Vatside', 'intake': 'the Intake', 'warmwater': 'Warmwater',
         'tramyard': 'Tramyard', 'sink': 'the Sink', 'oldworks': 'Old Works', 'sodium': 'Sodium Row', 'chapel': 'Chapel Ward',
         'terraces': 'the Terraces'}
nudge = {'spire': (60, -40), 'core': (0, 34), 'sink': (0, 52), 'tramyard': (-10, -24), 'sodium': (0, 30), 'oldworks': (-10, 34),
         'intake': (-110, -6), 'warmwater': (10, -24), 'vatside': (-20, -18), 'chapel': (-20, 26), 'terraces': (-30, 0)}
for d, pts in cent.items():
    x = sum(p[0] for p in pts) / len(pts); y = sum(p[1] for p in pts) / len(pts)
    px, py = P(x, y); nx, ny = nudge[d]
    o.append(f'<text x="{px + nx:.0f}" y="{py + ny:.0f}">{names[d]}</text>')
o.append(f'<text x="{gx + 24:.0f}" y="{gy + 22:.0f}" text-anchor="start">Gate Nine</text>')
o.append(f'<text x="{lx + 14:.0f}" y="{ly + 22:.0f}" text-anchor="start" fill="#E6B98A">the Landing</text>')
o.append('<text x="1470" y="560" fill="#C9875F">the Scour</text>')
o.append('<text x="1060" y="190" font-size="13" fill="#FFF3D6" fill-opacity="0.5">the Ring</text>')
o.append('</g>')
o.append('</svg>')

o.append('''<div style="position: absolute; left: 64px; top: 930px; width: 420px; display: flex; flex-direction: column; gap: 12px">
<p style="margin: 0; font-family: 'IBM Plex Mono', monospace; font-size: 12px; letter-spacing: 4px; color: #F2D9A0">KARST, YEAR 41, AFTER CURFEW</p>
<h1 style="margin: 0; font-family: 'Big Shoulders Display', sans-serif; font-weight: 900; font-size: 72px; line-height: 0.9; letter-spacing: 2px; color: #E6E1D6">BY RINGLIGHT</h1>
<p style="margin: 0; font-size: 15px; line-height: 1.5; font-style: italic; color: #C9C4BA">The city was built to keep something in. Nobody remembers what. At night you can see where everyone is: the Spire burning over the shaft, the vats of Vatside cold and blue, the Sink a black mouth with a red rim, and out past Gate Nine, the salvage fires of the Scour.</p>
</div>
<p style="position: absolute; right: 64px; bottom: 48px; margin: 0; font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 2px; color: #7E8796">BLACKSITE · A NATIVE NETBBS DOOR</p>
''')
o.append('</div>')

props = '{"ringColor":{"editor":"color","default":"#F2D9A0","options":["#F2D9A0","#BFD7F2","#F2B8A0"]},"showLabels":{"editor":"boolean","default":true},"searchlight":{"editor":"boolean","default":true}}'
vals = "{ ringColor: this.props.ringColor ?? '#F2D9A0', labelOpacity: (this.props.showLabels ?? true) ? 1 : 0, beamOpacity: (this.props.searchlight ?? true) ? 1 : 0 }"
html = page('Karst by Ringlight', W, H, '\n'.join(o),
            'family=Big+Shoulders+Display:wght@900&amp;family=IBM+Plex+Mono:wght@400&amp;family=IBM+Plex+Serif:ital,wght@0,400;1,400', props, vals)
io.open('project/Night.dc.html', 'w', encoding='utf-8', newline='\n').write(html)
print(len(html))
