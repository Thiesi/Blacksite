"""Karst geography from docs/world/01-gazetteer.md (City plan), shared by the map artboards."""
import math

# district id: (name, faction/lean line, colour, bearing from, bearing to, planned)
DISTRICTS = {
    'vatside':   ('VATSIDE', "Sablier's vats", '#4FC6D9', 290, 332, False),
    'intake':    ('THE INTAKE', 'beds and fungal halls', '#4D86E0', 332, 16, True),
    'warmwater': ('WARMWATER', 'the Lamp Compact', '#E58FB0', 16, 62, True),
    'tramyard':  ('TRAMYARD', 'Kestrel', '#EE8434', 62, 96, False),
    'sink':      ('THE SINK', 'Red Sable', '#D64545', 96, 131, False),
    'oldworks':  ('OLD WORKS', 'the Unmoored', '#5FB36B', 131, 176, False),
    'sodium':    ('SODIUM ROW', 'neutral, by agreement', '#E9C46A', 176, 212, False),
    'chapel':    ('CHAPEL WARD', 'the Choir', '#9B6BD6', 212, 250, False),
    'terraces':  ('THE TERRACES', 'where you live', '#8A94A6', 250, 290, False),
}

# zone id: (name, district, plan x, plan y, class, planned)
ZONES = [
    ('spire', 'The Spire', 'spire', 50, 41, 'safe', False),       # stack: mezzanine, atrium, shaft head
    ('core-plaza', 'Meridian Plaza', 'core', 50, 51, 'safe', False),
    ('core-tram-hub', 'Central Tram Hub', 'core', 47, 57, 'safe', False),
    ('core-precinct', 'Warden Precinct', 'core', 57, 55, 'safe', False),
    ('vatside-wake-hall', 'Wake Hall', 'vatside', 30, 26, 'pocket', False),
    ('vatside-clinics', 'Clinic Row', 'vatside', 35, 33, 'contested', False),
    ('vatside-vat-row', 'Vat Row', 'vatside', 27, 38, 'contested', False),
    ('terraces-blocks', 'Block Street', 'terraces', 28, 50, 'contested', False),
    ('terraces-lobby', 'Residence Lobby', 'terraces', 22, 52, 'pocket', False),
    ('chapel-towers', 'Cooling Towers', 'chapel', 30, 66, 'contested', False),
    ('chapel-nave', 'The Nave', 'chapel', 25, 71, 'pocket', False),
    ('chapel-cloister', 'The Cloister', 'chapel', 33, 70, 'pocket', True),
    ('sodium-row', 'Sodium Row', 'sodium', 47, 68, 'contested', False),
    ('sodium-tin-halo', 'The Tin Halo', 'sodium', 43, 72, 'pocket', False),
    ('oldworks-main', 'Contractor Street', 'oldworks', 62, 68, 'contested', False),
    ('oldworks-drop', 'The Drop', 'oldworks', 57, 74, 'pocket', False),
    ('oldworks-yards', 'Fabrication Yards', 'oldworks', 68, 78, 'contested', False),
    ('oldworks-dynamo-hall', 'The Dynamo Hall', 'oldworks', 72, 73, 'contested', True),
    ('sink-rim', 'The Rim', 'sink', 75, 56, 'contested', False),
    ('sink-terraces', 'Sink Terraces', 'sink', 78, 63, 'contested', False),
    ('sink-floor', 'The Floor', 'sink', 77, 68, 'contested', False),
    ('tramyard-market', 'Tramyard Market', 'tramyard', 71, 47, 'contested', False),
    ('tramyard-depots', 'Ration Depots', 'tramyard', 79, 43, 'contested', False),
    ('tramyard-wall-gate', 'Gate Nine', 'tramyard', 88, 45, 'contested', False),  # stack: Assay Floor
    ('tramyard-wallwalk', 'The Wallwalk', 'tramyard', 86, 36, 'contested', True),
    ('warmwater-lamp-street', 'Lamp Street', 'warmwater', 64, 32, 'contested', True),
    ('warmwater-baths', 'The Long Baths', 'warmwater', 59, 27, 'pocket', True),
    ('warmwater-courts', 'The Courts', 'warmwater', 69, 25, 'contested', True),
    ('warmwater-boilerhouse', 'The Boilerhouse', 'warmwater', 74, 31, 'contested', True),
    ('intake-beds', 'The Settling Beds', 'intake', 42, 23, 'contested', True),
    ('intake-hall', 'The Treatment Hall', 'intake', 50, 17, 'pocket', True),
    ('intake-wellhead', 'The Wellhead', 'intake', 56, 18, 'contested', True),
    ('intake-fungal-halls', 'The Fungal Halls', 'intake', 36, 19, 'contested', True),
]
ZPOS = {z[0]: (z[3], z[4]) for z in ZONES}

# street routes: (name, from, to, planned, bend) bend = plan point a curve passes
ROUTES = [
    ('The Spire steps', 'spire', 'core-plaza', False, None),
    ('Sablier Boulevard', 'core-plaza', 'vatside-clinics', False, None),
    ('The Neon Stair', 'core-plaza', 'sodium-row', False, None),
    ('The Long Stair', 'tramyard-market', 'sink-rim', False, None),
    ('The freight siding', 'oldworks-main', 'tramyard-depots', False, (74, 54)),
    ('The rim cable cars', 'sink-rim', 'sink-terraces', False, None),
    ('The tolled tunnel', 'sink-terraces', 'oldworks-yards', False, (75, 72)),
    ('The Lamp Walk', 'core-plaza', 'warmwater-lamp-street', True, (61, 42)),
    ('The Steam Stair', 'tramyard-market', 'warmwater-lamp-street', True, None),
    ('The Cistern Walk', 'core-plaza', 'intake-beds', True, (39, 38)),
    ('The Filter Lane', 'vatside-clinics', 'intake-beds', True, None),
]
TRAMS = [  # line, terminus, planned
    ('Clinic', 'vatside-clinics', False), ('Terraces', 'terraces-blocks', False),
    ('Chapel', 'chapel-towers', False), ('Rim', 'sink-rim', False),
    ('Market', 'tramyard-market', False), ('Lamp', 'warmwater-lamp-street', True),
]
UNDER = [  # id, name, plan x, y, note
    ('under-service', 'Service Level', 36, 58, 'arc from Vat Row to the Yards'),
    ('under-drowned', 'The Drowned Level', 58, 62, 'under Sodium Row'),
    ('under-outworks', 'Blacksite Outworks', 52, 50, 'around the shaft'),
    ('under-shaft-foot', 'Shaft Foot', 50, 41, 'bottom of the shaft'),
    ('under-caverns', 'Karst Caverns', 77, 71, 'under the Sink, past the wall'),
]
FACTIONS = [('Halvard', '#E0A030'), ('Sablier', '#4FC6D9'), ('Kestrel', '#EE8434'),
            ('the Wardens', '#4D86E0'), ('the Choir', '#9B6BD6'), ('Red Sable', '#D64545'),
            ('the Unmoored', '#5FB36B'), ('the Ferrymen', '#B5653A'), ('the Lamp Compact', '#E58FB0')]


def bearing_point(cx, cy, r, b):
    a = math.radians(b)
    return cx + r * math.sin(a), cy - r * math.cos(a)


def sector(cx, cy, r0, r1, b0, b1):
    """SVG path for an annular sector, clockwise bearings b0 to b1."""
    if b1 <= b0:
        b1 += 360
    p0 = bearing_point(cx, cy, r0, b0); p1 = bearing_point(cx, cy, r1, b0)
    p2 = bearing_point(cx, cy, r1, b1); p3 = bearing_point(cx, cy, r0, b1)
    large = 1 if b1 - b0 > 180 else 0
    f = lambda p: f'{p[0]:.1f} {p[1]:.1f}'
    return (f'M{f(p0)} L{f(p1)} A{r1} {r1} 0 {large} 1 {f(p2)} '
            f'L{f(p3)} A{r0} {r0} 0 {large} 0 {f(p0)} Z')


def mid_bearing(b0, b1):
    if b1 <= b0:
        b1 += 360
    return ((b0 + b1) / 2) % 360


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def page(title, w, h, body, fonts, props='{}', vals='{}', bg='#0B0E14', extra_css=''):
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="">
<link href="https://fonts.googleapis.com/css2?{fonts}&amp;display=swap" rel="stylesheet">
<style>
body{{margin:0}}
a{{color:#F2D9A0}}a:hover{{color:#FFF3D6}}{extra_css}
</style>
</helmet>
{body}
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{props[:-1] + ("," if props != "{}" else "")}"$preview":{{"width":{w},"height":{h}}}}}'>
class Component extends DCLogic {{
renderVals() {{
return {vals};
}}
}}
</script>
</body>
</html>
'''
