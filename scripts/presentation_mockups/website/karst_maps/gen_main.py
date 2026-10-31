"""Main artboard: the full surface plan of Karst with every district and zone."""
import io
from karst import *

CX, CY, S, WALL = 600, 640, 8, 320
P = lambda x, y: (CX + (x - 50) * S, CY + (y - 50) * S)

# zone label placement: dx, dy, anchor
LAB = {
    'core-plaza': (10, 4, 'start'), 'core-tram-hub': (-9, 14, 'end'), 'core-precinct': (0, 18, 'middle'),
    'vatside-wake-hall': (9, -6, 'start'), 'vatside-clinics': (9, 4, 'start'), 'vatside-vat-row': (-9, 4, 'end'),
    'terraces-blocks': (9, -6, 'start'), 'terraces-lobby': (-9, 14, 'end'),
    'chapel-towers': (9, -4, 'start'), 'chapel-nave': (-9, 4, 'end'), 'chapel-cloister': (0, 18, 'middle'),
    'sodium-row': (9, -4, 'start'), 'sodium-tin-halo': (-9, 12, 'end'),
    'oldworks-main': (9, -4, 'start'), 'oldworks-drop': (-9, 12, 'end'), 'oldworks-yards': (0, 20, 'middle'),
    'oldworks-dynamo-hall': (0, 18, 'middle'),
    'sink-rim': (-9, -6, 'end'), 'sink-terraces': (12, 4, 'start'), 'sink-floor': (12, 8, 'start'),
    'tramyard-market': (0, 20, 'middle'), 'tramyard-depots': (-9, -8, 'end'), 'tramyard-wall-gate': (0, 0, 'none'),
    'tramyard-wallwalk': (0, 0, 'none'),
    'warmwater-lamp-street': (9, 12, 'start'), 'warmwater-baths': (-9, 4, 'end'), 'warmwater-courts': (0, -12, 'middle'),
    'warmwater-boilerhouse': (9, 4, 'start'),
    'intake-beds': (9, -6, 'start'), 'intake-hall': (0, -12, 'middle'), 'intake-wellhead': (0, 18, 'middle'),
    'intake-fungal-halls': (-9, -6, 'end'),
}
DLAB_R = {'vatside': 292, 'intake': 306, 'warmwater': 290, 'tramyard': 250, 'sink': 282,
          'oldworks': 292, 'sodium': 288, 'chapel': 300, 'terraces': 290}
DLAB_B = {'tramyard': 66, 'sink': 128, 'intake': 337, 'chapel': 244, 'warmwater': 30, 'terraces': 278}

boxes = []  # for the overlap check


def box(x, y, text, size, anchor, ls=0.0):
    w = len(text) * (size * 0.6 + ls)
    x0 = x if anchor == 'start' else x - w if anchor == 'end' else x - w / 2
    boxes.append((x0, y - size * 0.8, x0 + w, y + size * 0.2, text))


out = []
o = out.append
o('<div style="width: 1800px; height: 1200px; position: relative; overflow: hidden; background: #0B0E14; font-family: \'IBM Plex Mono\', ui-monospace, monospace; color: #E6E1D6">')
o('<svg width="1800" height="1200" viewBox="0 0 1800 1200" style="position: absolute; left: 0; top: 0" role="img" aria-label="Plan of the walled city of Karst: the Spire and the Core at the centre, nine districts in a ring with every zone marked, the streets and six tram lines between them, the Sink, Gate Nine and the Wallwalk in the east wall, and the Scour\'s four rings outside the gate.">')
o('''<defs>
<pattern id="grid" width="11" height="11" patternUnits="userSpaceOnUse" patternTransform="rotate(14)"><path d="M11 0H0V11" fill="none" stroke="#1C2330" stroke-width="1"></path></pattern>
<radialGradient id="scour" cx="600" cy="640" r="600" gradientUnits="userSpaceOnUse"><stop offset="0.5" stop-color="#2A1A12" stop-opacity="0.9"></stop><stop offset="1" stop-color="#0B0E14" stop-opacity="0"></stop></radialGradient>
<radialGradient id="spireGlow" cx="600" cy="568" r="80" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#E0A030" stop-opacity="0.5"></stop><stop offset="1" stop-color="#E0A030" stop-opacity="0"></stop></radialGradient>
<radialGradient id="sinkGlow" cx="812" cy="742" r="60" gradientUnits="userSpaceOnUse"><stop offset="0.6" stop-color="#D64545" stop-opacity="0.35"></stop><stop offset="1" stop-color="#D64545" stop-opacity="0"></stop></radialGradient>
<radialGradient id="skyHaze" cx="900" cy="0" r="900" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#1A2236" stop-opacity="0.9"></stop><stop offset="1" stop-color="#0B0E14" stop-opacity="0"></stop></radialGradient>
<clipPath id="city"><circle cx="600" cy="640" r="316"></circle></clipPath>
</defs>
<rect x="0" y="0" width="1800" height="1200" fill="url(#skyHaze)"></rect>''')

# The Scour, compressed rings east of the wall
o('<circle cx="600" cy="640" r="600" fill="url(#scour)"></circle>')
rings = [('WALL RING', 320, 390), ('BEACON RING', 390, 460), ('CRASH RING', 460, 530), ('FAR RING', 530, 600)]
for i, (n, r0, r1) in enumerate(rings):
    if i:
        o(f'<circle cx="600" cy="640" r="{r0}" fill="none" stroke="#B5653A" stroke-opacity="{0.45 - i * 0.08:.2f}" stroke-width="1" stroke-dasharray="2 {5 + i * 2}"></circle>')
    x, y = bearing_point(CX, CY, (r0 + r1) / 2, 148)
    o(f'<text x="{x:.0f}" y="{y:.0f}" font-size="10" letter-spacing="2.5" fill="#C9875F" text-anchor="middle">{n}</text>')
    box(x, y, n, 10, 'middle', 2.5)
o('<g fill="#B5653A" fill-opacity="0.6">')
for b, r, rr in [(40, 410, 1.6), (58, 470, 1.2), (72, 540, 1.8), (96, 500, 1.4), (124, 560, 1.2), (34, 520, 2), (64, 420, 1.2), (118, 440, 1.6), (88, 575, 1)]:
    x, y = bearing_point(CX, CY, r, b)
    o(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rr}"></circle>')
o('</g>')
tx, ty = bearing_point(CX, CY, 520, 50)
o(f'<text x="{tx:.0f}" y="{ty:.0f}" font-size="15" font-weight="600" letter-spacing="5" fill="#C9875F">THE SCOUR</text>')
o(f'<text x="{tx:.0f}" y="{ty + 19:.0f}" font-size="10" font-style="italic" fill="#A3ACBA">salvage, Ferrymen roads, Ring-fall</text>')
box(tx, ty, 'THE SCOUR', 15, 'start', 5); box(tx, ty + 19, 'salvage, Ferrymen roads, Ring-fall', 10, 'start')
# Gate Nine, causeway, the Landing, the cave mouth
gx, gy = P(88, 45)
lx, ly = bearing_point(CX, CY, 392, 110)
mx, my = bearing_point(CX, CY, 424, 135)
o(f'<path d="M{gx + 12:.0f} {gy + 4:.0f} Q{gx + 60:.0f} {gy + 40:.0f} {lx:.0f} {ly - 8:.0f}" fill="none" stroke="#E6E1D6" stroke-opacity="0.55" stroke-width="1.5" stroke-dasharray="6 4"></path>')
o(f'<path d="M{lx:.0f} {ly - 8:.0f} L{lx + 7:.0f} {ly + 5:.0f} L{lx - 7:.0f} {ly + 5:.0f} Z" fill="#B5653A"></path>')
o(f'<text x="{lx + 14:.0f}" y="{ly + 4:.0f}" font-size="10" letter-spacing="2" fill="#E6E1D6">THE LANDING</text>')
box(lx + 14, ly + 4, 'THE LANDING', 10, 'start', 2)
o(f'<text x="{(gx + lx) / 2 + 30:.0f}" y="{(gy + ly) / 2 - 2:.0f}" font-size="9" font-style="italic" fill="#A3ACBA">the causeway</text>')
box((gx + lx) / 2 + 30, (gy + ly) / 2 - 2, 'the causeway', 9, 'start')
o(f'<g opacity="{{{{hiddenOpacity}}}}"><circle cx="{mx:.0f}" cy="{my:.0f}" r="5" fill="#050608" stroke="#5FB36B" stroke-width="1.2" stroke-dasharray="2 2"></circle>')
o(f'<text x="{mx + 10:.0f}" y="{my + 4:.0f}" font-size="9" font-style="italic" fill="#A3ACBA">the cave mouth, once found</text></g>')
box(mx + 10, my + 4, 'the cave mouth, once found', 9, 'start')

# City fabric and districts
o('<circle cx="600" cy="640" r="318" fill="#121722"></circle><circle cx="600" cy="640" r="318" fill="url(#grid)"></circle>')
o('<g clip-path="url(#city)" stroke="#0B0E14" stroke-width="5" stroke-linejoin="round">')
for k, (n, sub, col, b0, b1, planned) in DISTRICTS.items():
    d = f'<path d="{sector(CX, CY, 124, 330, b0, b1)}" fill="{col}" fill-opacity="0.2"></path>'
    o(f'<g opacity="{{{{plannedOpacity}}}}">{d}</g>' if planned else d)
o('</g>')
# covered beds north of the Spire: plain fabric texture
o('<g opacity="{{plannedOpacity}}" stroke="#4D86E0" stroke-opacity="0.18" stroke-width="1">')
for i in range(7):
    y = 400 + i * 9
    o(f'<line x1="{520 + abs(i - 3) * 6}" y1="{y}" x2="{690 - abs(i - 3) * 6}" y2="{y}"></line>')
o('</g>')

# The Sink
o('<circle cx="812" cy="742" r="60" fill="url(#sinkGlow)"></circle>')
o('<circle cx="812" cy="742" r="46" fill="#050608" stroke="#D64545" stroke-opacity="0.6" stroke-width="1.5"></circle>')
for r, op in [(34, 0.4), (22, 0.3), (11, 0.25)]:
    o(f'<circle cx="812" cy="742" r="{r}" fill="none" stroke="#D64545" stroke-opacity="{op}" stroke-width="1"></circle>')

# Core and Spire
o('<circle cx="600" cy="640" r="121" fill="#4D86E0" fill-opacity="0.13" stroke="#0B0E14" stroke-width="5"></circle>')
o('<path d="M504.1 567 A121 121 0 0 1 695.9 567 Z" fill="#E0A030" fill-opacity="0.12"></path>')
o('<circle cx="600" cy="568" r="80" fill="url(#spireGlow)"></circle>')

# Streets
o('<g fill="none" stroke="#E6E1D6" stroke-opacity="0.7" stroke-width="2" stroke-linecap="round">')
for name, a, b, planned, bend in ROUTES:
    x0, y0 = P(*ZPOS[a]); x1, y1 = P(*ZPOS[b])
    if bend:
        bx, by = P(*bend)
        d = f'<path d="M{x0:.0f} {y0:.0f} Q{bx:.0f} {by:.0f} {x1:.0f} {y1:.0f}"'
    else:
        d = f'<path d="M{x0:.0f} {y0:.0f} L{x1:.0f} {y1:.0f}"'
    dash = ' stroke-dasharray="7 4"' if name in ('The freight siding', 'The tolled tunnel', 'The rim cable cars') else ''
    el = f'{d}{dash}></path>'
    o(f'<g opacity="{{{{plannedOpacity}}}}">{el}</g>' if planned else el)
o('</g>')
# Tram lines
hx, hy = P(*ZPOS['core-tram-hub'])
o('<g opacity="{{tramOpacity}}" stroke="#F2D9A0" stroke-opacity="0.8" stroke-width="1.5" stroke-dasharray="1 5" stroke-linecap="round">')
for line, term, planned in TRAMS:
    x, y = P(*ZPOS[term])
    el = f'<line x1="{hx}" y1="{hy}" x2="{x}" y2="{y}"></line>'
    o(f'<g opacity="{{{{plannedOpacity}}}}">{el}</g>' if planned else el)
o('</g>')

# The wall, Gate Nine, the Wallwalk
o('<circle cx="600" cy="640" r="320" fill="none" stroke="#3A4152" stroke-width="10"></circle>')
o('<circle cx="600" cy="640" r="320" fill="none" stroke="#5A6378" stroke-width="10" stroke-dasharray="3 9"></circle>')
o('<g opacity="{{plannedOpacity}}"><path d="M{0:.1f} {1:.1f} A320 320 0 0 1 {2:.1f} {3:.1f}" fill="none" stroke="#EE8434" stroke-opacity="0.75" stroke-width="4"></path></g>'.format(
    *bearing_point(CX, CY, 320, 52), *bearing_point(CX, CY, 320, 80)))
wx, wy = bearing_point(CX, CY, 340, 64)
o(f'<g opacity="{{{{plannedOpacity}}}}"><text x="{wx:.0f}" y="{wy:.0f}" font-size="10" letter-spacing="2" fill="#E6E1D6">THE WALLWALK</text></g>')
box(wx, wy, 'THE WALLWALK', 10, 'start', 2)
o(f'<rect x="{gx + 5}" y="{gy - 8}" width="16" height="16" fill="#EE8434" transform="rotate(-7 {gx + 13} {gy})"></rect>')
o(f'<text x="{gx + 30}" y="{gy - 2}" font-size="10" letter-spacing="2" fill="#E6E1D6">GATE NINE</text>')
o(f'<g opacity="{{{{plannedOpacity}}}}"><text x="{gx + 30}" y="{gy + 11}" font-size="9" font-style="italic" fill="#A3ACBA">the Assay Floor</text></g>')
box(gx + 30, gy - 2, 'GATE NINE', 10, 'start', 2); box(gx + 30, gy + 11, 'the Assay Floor', 9, 'start')

# Zones
for zid, name, dist, x, y, cls, planned in ZONES:
    if zid == 'spire':
        continue
    px, py = P(x, y)
    if zid == 'oldworks-drop':
        mark = f'<g opacity="{{{{hiddenOpacity}}}}"><circle cx="{px}" cy="{py}" r="4" fill="#0B0E14" stroke="#E6E1D6" stroke-width="1.2" stroke-dasharray="2 2"></circle>'
    elif cls == 'pocket':
        mark = f'<rect x="{px - 3.5}" y="{py - 3.5}" width="7" height="7" fill="#0B0E14" stroke="#E6E1D6" stroke-width="1.4"></rect>'
    elif cls == 'safe':
        mark = f'<circle cx="{px}" cy="{py}" r="4.5" fill="#E6E1D6"></circle>'
    else:
        mark = f'<circle cx="{px}" cy="{py}" r="4" fill="#0B0E14" stroke="#E6E1D6" stroke-width="1.6"></circle>'
    if zid in ('tramyard-wall-gate', 'tramyard-wallwalk'):
        lab = ''
    else:
        dx, dy, anc = LAB[zid]
        lab = f'<text x="{px + dx}" y="{py + dy}" font-size="10" text-anchor="{anc}" fill="#C9C4BA">{esc(name)}</text>'
        box(px + dx, py + dy, name, 10, anc)
    el = mark + lab + ('</g>' if zid == 'oldworks-drop' else '')
    o(f'<g opacity="{{{{plannedOpacity}}}}">{el}</g>' if planned else el)
# hub ring
o(f'<circle cx="{hx}" cy="{hy}" r="7" fill="none" stroke="#F2D9A0" stroke-width="1.5"></circle>')

# The Spire
o('<polygon points="612.4,538 630,555.6 630,580.4 612.4,598 587.6,598 570,580.4 570,555.6 587.6,538" fill="#1A1F2A" stroke="#E0A030" stroke-width="2"></polygon>')
o('<circle cx="600" cy="568" r="8" fill="#000000" stroke="#E0A030" stroke-opacity="0.8" stroke-width="1.5"></circle>')

# District labels
o('<g font-size="13" font-weight="600" letter-spacing="2.5" text-anchor="middle" fill="#E6E1D6">')
o('<text x="600" y="530">THE SPIRE</text>'); box(600, 530, 'THE SPIRE', 13, 'middle', 2.5)
o('<text x="610" y="748">THE CORE</text>'); box(610, 748, 'THE CORE', 13, 'middle', 2.5)
for k, (n, sub, col, b0, b1, planned) in DISTRICTS.items():
    b = DLAB_B.get(k, mid_bearing(b0, b1))
    x, y = bearing_point(CX, CY, DLAB_R[k], b)
    el = f'<text x="{x:.0f}" y="{y:.0f}">{n}</text>'
    box(x, y, n, 13, 'middle', 2.5)
    o(f'<g opacity="{{{{plannedOpacity}}}}">{el}</g>' if planned else el)
o('</g><g font-size="10" font-style="italic" text-anchor="middle" fill="#A3ACBA">')
o('<text x="600" y="514">Halvard</text>'); box(600, 514, 'Halvard', 10, 'middle')
o('<text x="610" y="762">safe streets</text>'); box(610, 762, 'safe streets', 10, 'middle')
for k, (n, sub, col, b0, b1, planned) in DISTRICTS.items():
    b = DLAB_B.get(k, mid_bearing(b0, b1))
    x, y = bearing_point(CX, CY, DLAB_R[k], b)
    el = f'<text x="{x:.0f}" y="{y + 14:.0f}">{esc(sub)}</text>'
    box(x, y + 14, sub, 10, 'middle')
    o(f'<g opacity="{{{{plannedOpacity}}}}">{el}</g>' if planned else el)
o('</g>')

# The Ring
o('''<g fill="none" stroke-linecap="round">
<path d="M-60 250 Q760 -100 1860 110" stroke="{{ringColor}}" stroke-opacity="0.07" stroke-width="34"></path>
<path d="M-60 250 Q760 -100 1860 110" stroke="{{ringColor}}" stroke-opacity="0.5" stroke-width="10" stroke-dasharray="0.5 9"></path>
<path d="M-60 258 Q760 -92 1860 118" stroke="{{ringColor}}" stroke-opacity="0.35" stroke-width="16" stroke-dasharray="0.5 31" stroke-dashoffset="13"></path>
<path d="M-60 244 Q760 -106 1860 104" stroke="#FFF3D6" stroke-opacity="0.9" stroke-width="3" stroke-dasharray="1.5 23" stroke-dashoffset="7"></path>
</g>''')

# Legend
o('<g transform="translate(64 980)" font-size="10" fill="#C9C4BA">')
leg = [('<circle cx="6" cy="0" r="4.5" fill="#E6E1D6"></circle>', 'safe zone'),
       ('<circle cx="6" cy="0" r="4" fill="#0B0E14" stroke="#E6E1D6" stroke-width="1.6"></circle>', 'contested zone'),
       ('<rect x="2.5" y="-3.5" width="7" height="7" fill="#0B0E14" stroke="#E6E1D6" stroke-width="1.4"></rect>', 'pocket'),
       ('<line x1="0" y1="0" x2="14" y2="0" stroke="#E6E1D6" stroke-opacity="0.7" stroke-width="2"></line>', 'street'),
       ('<line x1="0" y1="0" x2="14" y2="0" stroke="#F2D9A0" stroke-width="1.5" stroke-dasharray="1 5" stroke-linecap="round"></line>', 'tram line'),
       ('<line x1="0" y1="0" x2="14" y2="0" stroke="#E6E1D6" stroke-opacity="0.7" stroke-width="2" stroke-dasharray="7 4"></line>', 'siding, cable car, tunnel')]
for i, (g, t) in enumerate(leg):
    yy = i * 18
    o(f'<g transform="translate(0 {yy})">{g}<text x="22" y="4">{t}</text></g>')
o('</g>')
o('''<g transform="translate(64 1112)">
<path d="M16 0 L22 18 L16 14 L10 18 Z" fill="#E6E1D6"></path>
<text x="16" y="34" font-size="11" font-weight="600" text-anchor="middle" fill="#E6E1D6">N</text>
<text x="48" y="22" font-family="'Big Shoulders Display', sans-serif" font-size="40" font-weight="900" letter-spacing="3" fill="#E6E1D6">KARST</text>
<text x="48" y="44" font-size="11" letter-spacing="1" fill="#A3ACBA">one wall, ten kilometres across, Year 41</text>
</g>''')
o('</svg>')

# Side panel
fac = ''.join(f'<div style="display: flex; align-items: center; gap: 8px"><span style="width: 10px; height: 10px; border-radius: 50%; background: {c}; flex-shrink: 0"></span>{n}</div>' for n, c in FACTIONS)
o(f'''<div style="position: absolute; left: 1240px; top: 180px; width: 500px; display: flex; flex-direction: column; gap: 22px">
<div style="display: flex; flex-direction: column; gap: 6px">
<p style="margin: 0; font-size: 13px; letter-spacing: 3px; color: #F2D9A0">A REAL-TIME MULTIPLAYER TERMINAL RPG</p>
<h1 style="margin: 0; font-family: 'Big Shoulders Display', sans-serif; font-weight: 900; font-size: 132px; line-height: 0.9; letter-spacing: 2px; color: #E6E1D6">BLACKSITE</h1>
</div>
<p style="margin: 0; font-size: 17px; line-height: 1.5; font-style: italic; color: #E6E1D6">The city was built to keep something in. Nobody remembers what.</p>
<p style="margin: 0; font-size: 14px; line-height: 1.65; color: #A3ACBA">Four million people on a limestone plateau, sealed inside one wall for forty-one years. Eleven districts, forty-seven places: the Spire over the sealed shaft, the safe Core at its foot, nine districts in a ring, the Undercity beneath, and the Scour outside the only gate that opens.</p>
<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 24px; font-size: 12px; line-height: 1.5; color: #C9C4BA">
<div><span style="color: #F2D9A0; letter-spacing: 2px">STREETS</span><br>Sablier Boulevard, the Neon Stair, the Long Stair, the Lamp Walk, the Steam Stair, the Cistern Walk, the Filter Lane</div>
<div><span style="color: #F2D9A0; letter-spacing: 2px">TRAMS</span><br>Six lines out of the Central Tram Hub, no stops between: Clinic, Terraces, Chapel, Rim, Market, Lamp</div>
<div><span style="color: #F2D9A0; letter-spacing: 2px">UNDER THE STREET</span><br>Service Level, the Drowned Level, Karst Caverns, Blacksite Outworks, Shaft Foot</div>
<div><span style="color: #F2D9A0; letter-spacing: 2px">NEW SINCE THE LAST MAP</span><br>the Wallwalk, the Assay Floor, the Cloister, the Dynamo Hall, the Fungal Halls, and every zone of Warmwater and the Intake</div>
</div>
<div style="display: flex; flex-direction: column; gap: 12px">
<p style="margin: 0; font-size: 11px; letter-spacing: 3px; color: #F2D9A0">NINE FACTIONS</p>
<div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px 16px; font-size: 12px; color: #E6E1D6">{fac}</div>
</div>
<p style="margin: 0; font-size: 11px; line-height: 1.6; color: #A3ACBA">Planned places are drawn with the rest; turn them off with the Planned tweak to see the city as it ships today.</p>
</div>
''')
o('<p style="position: absolute; left: 1240px; top: 1130px; width: 500px; margin: 0; font-size: 11px; letter-spacing: 1px; color: #A3ACBA">Two layers, one city. A native NetBBS door.</p>')
o('</div>')

props = '{"showPlanned":{"editor":"boolean","default":true},"showTram":{"editor":"boolean","default":true},"showHidden":{"editor":"boolean","default":true},"ringColor":{"editor":"color","default":"#F2D9A0","options":["#F2D9A0","#BFD7F2","#F2B8A0"]}}'
vals = "{ plannedOpacity: (this.props.showPlanned ?? true) ? 1 : 0, tramOpacity: (this.props.showTram ?? true) ? 1 : 0, hiddenOpacity: (this.props.showHidden ?? true) ? 1 : 0, ringColor: this.props.ringColor ?? '#F2D9A0' }"
html = page('Blacksite: the city of Karst', 1800, 1200, '\n'.join(out),
            'family=Big+Shoulders+Display:wght@700;900&amp;family=IBM+Plex+Mono:ital,wght@0,400;0,600;1,400', props, vals)
io.open('project/Main.dc.html', 'w', encoding='utf-8', newline='\n').write(html)

# overlap check
hits = []
for i in range(len(boxes)):
    for j in range(i + 1, len(boxes)):
        a, b = boxes[i], boxes[j]
        if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
            hits.append((a[4], b[4]))
print('overlaps:', hits)
# labels against zone dots
for zid, name, dist, x, y, cls, planned in ZONES:
    px, py = P(x, y)
    for bx in boxes:
        if bx[0] - 4 < px < bx[2] + 4 and bx[1] - 4 < py < bx[3] + 4:
            print('dot under label:', zid, bx[4])
