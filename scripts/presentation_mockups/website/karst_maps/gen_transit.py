"""Graphic variation: a transit diagram of Karst's trams, streets and hidden ways."""
import io
from karst import page, esc

W, H = 1700, 1240
INK, PAPER, MUTE = '#1E2230', '#F3EEE2', '#6B6458'
# node: x, y, label, dx, dy, anchor, kind (stop|hub|pocket|planned|hidden|scour|under)
from transit_data import *
pt = lambda p: (N[p][0], N[p][1]) if isinstance(p, str) else p
path = lambda pts: 'M' + ' L'.join(f'{x} {y}' for x, y in map(pt, pts))

o = []
o.append(f'<div style="width: {W}px; height: {H}px; position: relative; overflow: hidden; background: {PAPER}; font-family: \'IBM Plex Sans Condensed\', \'Arial Narrow\', sans-serif; color: {INK}">')
o.append(f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="position: absolute; left: 0; top: 0" role="img" aria-label="Transit diagram of Karst: six tram lines out of the Central Tram Hub, the named streets and stairs between districts, the freight siding, cable cars and tolled tunnel in the Sink, the causeway from Gate Nine to the Landing in the Scour, and the ways down to the Undercity.">')
for name, x, y, w, h, c in DISTRICT_BOX:
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{c}" fill-opacity="0.09" stroke="{c}" stroke-opacity="0.45" stroke-width="1.2"></rect>')
    corner = BOX_LABEL.get(name, 'bl')
    lx, anc = (x + 14, 'start') if corner[1] == 'l' else (x + w - 14, 'end')
    ly = y + 22 if corner[0] == 't' else y + h - 12
    o.append(f'<text x="{lx}" y="{ly}" font-size="11" font-weight="700" letter-spacing="2" fill="{c}" text-anchor="{anc}" style="filter: brightness(0.6)">{name}</text>')
# the Undercity band
o.append(f'<rect x="300" y="975" width="1060" height="190" rx="18" fill="{INK}" fill-opacity="0.06" stroke="{INK}" stroke-opacity="0.35" stroke-width="1.2" stroke-dasharray="6 4"></rect>')
o.append(f'<text x="316" y="996" font-size="11" font-weight="700" letter-spacing="2" fill="{INK}" fill-opacity="0.7">UNDER THE STREET</text>')
for a, b, lab in UNDER_LINKS:
    (x0, y0), (x1, y1) = pt(a), pt(b)
    o.append(f'<path d="M{x0} {y0} L{x1} {y1}" stroke="{INK}" stroke-opacity="0.45" stroke-width="2" stroke-dasharray="2 5" stroke-linecap="round" fill="none"></path>')
    if False:
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        o.append(f'<text x="{mx + 6:.0f}" y="{my:.0f}" font-size="10" font-style="italic" fill="{MUTE}">{lab}</text>')
# hidden link: the cave mouth
(cx0, cy0), (cx1, cy1) = pt('caverns'), pt('ring2')
o.append(f'<g opacity="{{{{hiddenOpacity}}}}"><path d="M{cx0} {cy0} Q{cx1 - 40} {cy0} {cx1} {cy1}" fill="none" stroke="#5FB36B" stroke-width="2.5" stroke-dasharray="1 6" stroke-linecap="round"></path>')
o.append(f'<text x="{cx1 - 40}" y="{cy0 - 90}" font-size="11" font-style="italic" fill="#3F7F49" text-anchor="end">the cave mouth, once found</text></g>')

# tram lines
for name, col, pts, planned in TRAM:
    dash = ' stroke-dasharray="14 7"' if planned else ''
    el = f'<path d="{path(pts)}" fill="none" stroke="{col}" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"{dash}></path>'
    o.append(f'<g opacity="{{{{plannedOpacity}}}}">{el}</g>' if planned else el)
# walks
for name, pts, planned, kind in WALK:
    d = path(pts)
    if kind == 'street':
        el = f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="5" stroke-linejoin="round"></path><path d="{d}" fill="none" stroke="{PAPER}" stroke-width="2" stroke-linejoin="round"></path>'
    elif kind == 'siding':
        el = f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="3" stroke-linejoin="round"></path><path d="{d}" fill="none" stroke="{INK}" stroke-width="9" stroke-dasharray="1.5 8" stroke-linejoin="round"></path>'
    elif kind == 'cable':
        el = f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="2" stroke-dasharray="6 4"></path>'
    else:
        el = f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="5" stroke-dasharray="10 5" stroke-opacity="0.75"></path>'
    o.append(f'<g opacity="{{{{plannedOpacity}}}}">{el}</g>' if planned else el)

# route names along the way
for t, x, y, a in RN:
    pl = t in ('Lamp Walk', 'Steam Stair', 'Cistern Walk', 'Filter Lane')
    el = f'<text x="{x}" y="{y}" font-size="10" font-style="italic" fill="{MUTE}" text-anchor="{a}">{t}</text>'
    o.append(f'<g opacity="{{{{plannedOpacity}}}}">{el}</g>' if pl else el)

# stations
for k, (x, y, lab, dx, dy, anc, kind) in N.items():
    planned = kind.startswith('planned')
    if kind == 'hub':
        m = f'<circle cx="{x}" cy="{y}" r="15" fill="{PAPER}" stroke="{INK}" stroke-width="5"></circle><circle cx="{x}" cy="{y}" r="5" fill="{INK}"></circle>'
    elif kind.endswith('pocket'):
        m = f'<rect x="{x - 7}" y="{y - 7}" width="14" height="14" rx="2" fill="{PAPER}" stroke="{INK}" stroke-width="3"></rect>'
    elif kind == 'hidden':
        m = f'<g opacity="{{{{hiddenOpacity}}}}"><rect x="{x - 7}" y="{y - 7}" width="14" height="14" rx="2" fill="{PAPER}" stroke="{INK}" stroke-width="2.5" stroke-dasharray="3 2"></rect>'
    elif kind == 'under':
        m = f'<circle cx="{x}" cy="{y}" r="9" fill="{INK}"></circle><circle cx="{x}" cy="{y}" r="3.5" fill="{PAPER}"></circle>'
    else:
        m = f'<circle cx="{x}" cy="{y}" r="8" fill="{PAPER}" stroke="{INK}" stroke-width="3.5"></circle>'
    if planned:
        m = m.replace(f'stroke="{INK}"', f'stroke="{INK}" stroke-dasharray="4 3"', 1)
    t = f'<text x="{x + dx}" y="{y + dy}" font-size="14" font-weight="600" text-anchor="{anc}" fill="{INK}">{esc(lab)}</text>'
    for i, line in enumerate(UNDER_SUB.get(k, [])):
        t += f'<text x="{x}" y="{y + dy + 16 + i * 13}" font-size="11" font-style="italic" text-anchor="middle" fill="{MUTE}">{line}</text>'
    el = m + t + ('</g>' if kind == 'hidden' else '')
    o.append(f'<g opacity="{{{{plannedOpacity}}}}">{el}</g>' if planned else el)
o.append('</svg>')

# title and key
key = ''.join(f'<div style="display: flex; align-items: center; gap: 10px"><span style="width: 34px; height: 8px; border-radius: 4px; background: {c}; flex-shrink: 0"></span>{n} line{" (planned)" if p else ""}</div>' for n, c, _, p in TRAM)
o.append(f'''<div style="position: absolute; left: 64px; top: 52px; width: 420px; display: flex; flex-direction: column; gap: 8px">
<p style="margin: 0; font-size: 13px; font-weight: 600; letter-spacing: 4px; color: {MUTE}">KESTREL TRANSIT AUTHORITY · ISSUE 41</p>
<h1 style="margin: 0; font-family: 'Big Shoulders Display', sans-serif; font-weight: 900; font-size: 64px; line-height: 0.95; color: {INK}">KARST BY TRAM AND ON FOOT</h1>
</div>
<div style="position: absolute; left: 64px; top: 720px; width: 230px; display: flex; flex-direction: column; gap: 9px; font-size: 13px; color: {INK}">
<p style="margin: 0 0 4px; font-size: 11px; font-weight: 700; letter-spacing: 2px; color: {MUTE}">TRAMS FROM THE HUB</p>
{key}
<p style="margin: 10px 0 0; font-size: 12px; line-height: 1.5; color: {MUTE}">One terminus a line, no stops between. Double lines are streets and stairs. Squares are pockets. Dashed: planned. Dotted green: a way you have to find first.</p>
</div>
<p style="position: absolute; right: 48px; top: 60px; width: 300px; margin: 0; font-size: 12px; line-height: 1.5; text-align: right; color: {MUTE}">Fares payable in chits. Gate Nine closes at curfew. The Kestrel Transit Authority accepts no liability for Ring-fall.</p>
''')
o.append('</div>')

props = '{"showPlanned":{"editor":"boolean","default":true},"showHidden":{"editor":"boolean","default":true}}'
vals = "{ plannedOpacity: (this.props.showPlanned ?? true) ? 1 : 0, hiddenOpacity: (this.props.showHidden ?? true) ? 1 : 0 }"
html = page('Karst transit diagram', W, H, '\n'.join(o), 'family=Big+Shoulders+Display:wght@900&amp;family=IBM+Plex+Sans+Condensed:ital,wght@0,400;0,600;0,700;1,400', props, vals,
            bg=PAPER, extra_css='\na{color:#1E2230}a:hover{color:#000000}')
io.open('project/Transit.dc.html', 'w', encoding='utf-8', newline='\n').write(html)
print(len(html))
