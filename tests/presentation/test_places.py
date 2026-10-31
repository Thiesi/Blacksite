"""P6 / entities 1.1, 1.21; architecture 5.5; UI 2.2-2.4."""

from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from blacksite.content import schema as s
from blacksite.content.formats import decode
from blacksite.content.loader import load_content
from blacksite.content.place_validation import validate_places
from blacksite.content.places import charting_problems, public_tiles
from blacksite.content.validate import validate
from blacksite.door.cells import CellBuffer, display_width
from blacksite.door.palette import Palette
from blacksite.door.present import zone as drawing, chrome
from blacksite.door.present.paint import Paint, BAND_STEP, light_distance, theme_roles
from blacksite.door.present.places import for_frame
from blacksite.layout import compute
from blacksite.server.views.delta import changes
from blacksite.server.views.zone_view import build, Perception
from blacksite.server.world.actors import Actor
from blacksite.server.world.zone import ZoneInstance
from tests.fake_terminal import FakeTerminal
from tests.presentation.mechanics import projection
from tests.presentation.snapshots import canonical, snapshot

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/p6'


@pytest.fixture(scope='module')
def fixtures():
    return load_content(ROOT / 'src/blacksite/content', FIXTURE)


def problems(content):
    errors = []
    validate_places(content, lambda kind, rid, message: errors.append(message))
    return errors


def view(content, width=80, height=24, *, position=(4, 5), perception=None):
    instance = ZoneInstance(content.zones['p6-fixture'], content.tiles, 7)
    caller = Actor('test:caller', 'Wide界', handle='FixtureCaller', x=position[0], y=position[1])
    caller.zone = instance.id
    instance.actors[caller.id] = caller
    perception = perception if perception is not None else Perception()
    return build(caller, instance, perception, content, width, height, '12:00', False, 0), caller, instance, perception


def test_entities_1_21_fixture_loads_and_validates(fixtures):
    assert not fixtures.load_problems
    assert not validate(fixtures)
    assert not problems(fixtures)
    assert not list(charting_problems(fixtures.zones['p6-fixture'], fixtures.tiles))


def test_entities_1_21_local_merge_by_id_and_strict_formats(fixtures, tmp_path):
    # Existing ids are replaced, unrelated themes and palette roles survive.
    (tmp_path/'themes.json').write_text(json.dumps({'themes': {'replacement': {'texture': '·'}}}))
    loaded = load_content(FIXTURE, tmp_path)
    assert set(loaded.themes.themes) == {'p6-dark', 'p6-light', 'p6-ring', 'replacement'}
    with pytest.raises(ValueError):
        decode(s.Look, {'id': 'bad', 'theme': 'p6-dark', 'charted': True})
    assert decode(s.Region, [1, 2, 3, 4]) == s.Region(1, 2, 3, 4)
    assert not decode(s.Pocket, {'x':1, 'y':2, 'w':3, 'h':4}).charted


@pytest.mark.parametrize('change,needle', [
    ({'theme':'missing'}, 'theme'),
    ({'regions':(s.LookRegion('missing', rect=(1,1,2,2)),)}, 'theme'),
    ({'regions':(s.LookRegion('p6-dark', rect=(1,1,2,2), circle=(1,1,1)),)}, 'exactly one'),
    ({'signs':(s.LookSign((1,1),'TEST','thing_exit'),)}, 'wall-face'),
    ({'signs':(s.LookSign((2,0),'@','thing_exit'),)}, 'rule glyph'),
    ({'signs':(s.LookSign((2,0),'TEST','p6_grain'),)}, 'thing-band'),
    ({'marks':(s.LookMark('p6_grain', at=(6,6), text='WORD'),)}, 'plain passable'),
    ({'marks':(s.LookMark('p6_grain', line=((1,1),(2,2)), glyph='─'),)}, 'straight'),
    ({'marks':(s.LookMark('p6_grain', at=(1,1), text='»'),)}, 'dressing'),
    ({'marks':(s.LookMark('p6_grain', at=(30,10), text='X'),)}, 'hidden exit'),
    ({'glints':((1,1),)}, 'water'),
    ({'glint_role':'missing'}, 'palette role'),
    ({'ambient':('You hear a fan—then silence.',)}, 'voice'),
    ({'ambient':('x'*201,)}, 'voice'),
    ({'ambient':('You enter cyberspace.',)}, 'voice'),
])
def test_entities_1_21_rejects_misleading_dressing(fixtures, change, needle):
    content = deepcopy(fixtures)
    content.looks['p6-fixture'] = replace(content.looks['p6-fixture'], **change)
    assert any(needle in error for error in problems(content))


@pytest.mark.parametrize('theme', ['p6-dark', 'p6-light'])
def test_ui_2_2_contrast_rejected_from_actual_ground(fixtures, theme):
    content = deepcopy(fixtures)
    record = content.themes.themes[theme]
    content.themes.themes[theme] = replace(record, wall_bg=record.ground_bg)
    assert any('contrast' in error for error in problems(content))


def test_ui_2_2_rejects_bright_ansi_background_and_unreadable_sign(fixtures):
    content = deepcopy(fixtures)
    content.palette.roles['p6_ground']['16']['default'] = 15
    assert any('background' in error for error in problems(content))
    content = deepcopy(fixtures)
    content.palette.roles['thing_exit'] = deepcopy(content.palette.roles['p6_wall'])
    assert any('sign contrast' in error for error in problems(content))


@pytest.mark.parametrize('region,needle', [
    (s.Region(29,10,1,1), 'hidden exit'),
    (s.Region(30,10,1,1), 'hidden exit'),
    (s.Region(32,10,1,1), 'unreachable'),
    (s.Region(22,5,1,1), 'gated'),
    (s.Region(-1,0,1,1), 'outside'),
])
def test_arch_5_5_5_charting_rejections(fixtures, region, needle):
    zone = fixtures.zones['p6-fixture']
    changed = replace(zone, meta=replace(zone.meta, public=(region,)))
    assert any(needle in error for error in charting_problems(changed, fixtures.tiles))


def test_arch_5_5_5_required_public_private_instanced_and_pocket(fixtures):
    zone = fixtures.zones['p6-fixture']
    assert any('requires' in error for error in charting_problems(replace(zone, meta=replace(zone.meta, public=())), fixtures.tiles))
    assert any('instanced' in error for error in charting_problems(replace(zone, meta=replace(zone.meta, instanced=True)), fixtures.tiles))
    anchor = decode(s.HousingAnchor, json.loads((ROOT/'tests/fixtures/p6-private-anchor.json').read_text()))
    obj = s.ObjectSpec('private-door', (11,13), 'apartment_door', housing=anchor)
    changed = replace(zone, meta=replace(zone.meta, objects=(*zone.meta.objects,obj), public=(s.Region(12,12,1,1),)))
    assert any('private interior' in error for error in charting_problems(changed, fixtures.tiles))
    pocket = replace(zone, meta=replace(zone.meta, charted=False, public=(), pockets=(s.Pocket(32,10,1,1,True),)))
    assert any('unreachable' in error for error in charting_problems(pocket, fixtures.tiles))
    # Uncharted public is not banned, but it is still validated and fingerprinted.
    plain = replace(zone, meta=replace(zone.meta, charted=False))
    assert not list(charting_problems(plain, fixtures.tiles))


def test_arch_5_5_4_masking_whole_only_and_memory(fixtures):
    body, caller, instance, perception = view(fixtures)
    remembered = deepcopy(perception.remembered)
    chart = body['charted']
    vp = body['viewport']
    known = {(vp['x']+x,vp['y']+y) for y,row in enumerate(body['tiles']) for x,n in enumerate(row)
             if n != -1 or chart[y][x] >= 0}
    look = body['looks']
    for region in look['regions']:
        if 'rect' in region:
            assert set(s.Region(*region['rect']).tiles()) <= known
    assert not any('circle' in region for region in look['regions'])
    assert 'ambient' not in look
    assert look['names'] == {'cover-2':'barrels'}
    assert not any(n >= 0 and body['legend'][n]['id'] in ('hazard','door') for row in chart for n in row)
    for hidden in ((30,10),(32,10),(22,5)):
        assert hidden not in known
    second = build(caller, instance, perception, fixtures, 80,24,'12:00',False,1)
    assert not any('/looks' in op['path'] for op in changes(body, second))
    assert perception.remembered == remembered
    assert (14,5) in public_tiles(instance.template)
    assert (14,5) not in perception.remembered[instance.id]


def test_arch_5_5_6_looks_remove_without_rules_or_other_view_change(fixtures):
    clean = deepcopy(fixtures)
    clean.looks.clear()
    clean.themes = None
    before, *_ = view(fixtures)
    after, *_ = view(clean)
    before.pop('looks')
    before['legend'] = [{key: value for key,value in tile.items() if key not in ('wall','plain','water')}
                        for tile in before['legend']]
    assert before == after
    assert projection(fixtures) == projection(clean)


@pytest.mark.parametrize('size', [(80,24),(132,50)])
@pytest.mark.parametrize('tier', ['16','256','truecolor'])
@pytest.mark.parametrize('light', [False,True])
def test_ui_2_2_p6_fixture_style_golden(fixtures, size, tier, light, request):
    content = deepcopy(fixtures)
    if light:
        content.looks['p6-fixture'] = replace(content.looks['p6-fixture'], theme='p6-light')
    body, *_ = view(content, *size)
    paint = Paint(Palette(asdict(content.palette), tier))
    buf = CellBuffer(*size)
    drawing.render(buf, body, compute(*size), paint)
    term = FakeTerminal(*size)
    term.write(buf.full())
    path = ROOT/'tests/presentation/golden/p6'/f'{"light" if light else "dark"}_{size[0]}x{size[1]}_{tier}.json'
    actual = canonical(snapshot(term))
    if request.config.getoption('--update-goldens'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding='utf-8', newline='\n')
    assert path.read_text(encoding='utf-8') == actual
    # A charted-only tile has known-ground dimming and is still blank on
    # the legacy path. Sign letters never draw on a block at ANSI depth.
    places = for_frame(paint, body)
    sign, style = places.cell(paint, {'wall':True}, (2,0), roof=False, beside_wall=False, live=False)
    assert sign == 'T'
    if tier == '16':
        assert style.bg == 0


@pytest.mark.parametrize('tier', ['16','256','truecolor'])
def test_ui_2_2_person_lift_uses_region_ground_and_cached(fixtures, tier):
    body, *_ = view(fixtures, position=(9,5))
    paint = Paint(Palette(asdict(fixtures.palette), tier))
    places = for_frame(paint, body)
    theme = places.theme((9,5))
    assert theme.luma == 'light'
    args = ('npc_neutral', theme)
    first = paint.on_theme(*args)
    count = len(paint.ground_lifts)
    assert paint.on_theme(*args) is first
    assert len(paint.ground_lifts) == count
    ground, wall, _ = theme_roles(theme,tier)
    assert light_distance(first.fg, first.bg) >= paint.bands_on(ground,wall).people
    assert paint.on_theme('npc_neutral',replace(theme,luma='dark')).fg == first.fg
    dimmed = paint.on_theme('npc_neutral',theme,jacked=True,reverse=True)
    assert 7 not in dimmed.attrs
    if tier == '16':
        assert dimmed.fg == 8 and dimmed.bg == 0


def test_ui_2_4_here_shapes_authored_cover_and_distinct_suffix():
    for name in ('Public terminal (Plaza)', 'Public terminal (Clinic)', 'Public terminal (界東)'):
        fitted = drawing.fit_here('§ '+name, 21)
        assert name[name.index('('):] in fitted
        assert fitted.startswith('§ ') and display_width(fitted) <= 21


def test_ui_2_1_notice_header_preserves_zone_when_notice_can_shorten(fixtures):
    paint = Paint(Palette(asdict(fixtures.palette)))
    buf = CellBuffer(80,24)
    chrome.header(buf, compute(80,24), paint, [('Fixture hall','head_zone'),('SAFE','word_safe')],
                  [], notice=('A notice that shares the header and can be shortened to fit safely.', 'log_system',0))
    term = FakeTerminal()
    term.write(buf.full())
    assert 'Fixture hall SAFE' in term.screen_text().splitlines()[0]


def test_arch_5_5_5_projection_changes_only_the_flagged_zone(fixtures):
    before = projection(fixtures)
    content = deepcopy(fixtures)
    zone = content.zones['core-plaza']
    content.zones[zone.id] = replace(zone,meta=replace(zone.meta,charted=True,public=(s.Region(1,1,2,2),)))
    after = projection(content)
    changed = [zid for zid in before['zones'] if before['zones'][zid] != after['zones'][zid]]
    assert changed == ['core-plaza']
    assert after['zones']['core-plaza']['charted'] is True
    assert after['zones']['core-plaza']['public'] == [{'x':1,'y':1,'w':2,'h':2}]
    # Default-false pocket metadata is intentionally absent, never rebaselined.
    assert all('charted' not in pocket for value in before['zones'].values() for pocket in value['pockets'])


def test_entities_1_21_validation_uses_tile_classes_not_ids(fixtures):
    content = deepcopy(fixtures)
    aliases = {'floor':'custom-paving','wall':'custom-facade','water':'custom-runoff'}
    for old,new in aliases.items():
        content.tiles[new] = replace(content.tiles[old],id=new)
    zone = content.zones['p6-fixture']
    content.zones[zone.id] = replace(zone,grid=tuple(tuple(aliases.get(key,key) for key in row) for row in zone.grid))
    assert not problems(content)
    body, *_ = view(content)
    assert any(entry['id']=='custom-facade' and entry['wall'] for entry in body['legend'])


def test_arch_5_5_4_charting_does_not_disclose_live_actors_or_object_state(fixtures):
    body, caller, instance, perception = view(fixtures)
    unseen = Actor('test:unseen','Unseen',x=14,y=5,kind='npc',zone=instance.id)
    instance.actors[unseen.id] = unseen
    from blacksite.server.world.zone import ObjectState
    obj = s.ObjectSpec('unseen-state',(14,6),'door')
    instance.objects[obj.id] = ObjectState(obj,open=True)
    body = build(caller,instance,perception,fixtures,80,24,'12:00',False,1)
    assert unseen.id not in {actor['id'] for actor in body['actors']}
    assert obj.id not in {obj['id'] for obj in body['objects']}
    assert (14,5) not in perception.remembered[instance.id]


def test_ui_2_2_stable_grain_and_required_grain_beside_walls(fixtures):
    body, caller, instance, perception = view(fixtures)
    paint = Paint(Palette(asdict(fixtures.palette)))
    places = for_frame(paint,body)
    places.base = replace(places.base,texture=' ')
    floor = {'plain':True}
    assert places.cell(paint,floor,(2,1),roof=False,beside_wall=True,live=True)[0] == '·'
    assert places.cell(paint,floor,(2,1),roof=False,beside_wall=False,live=True)[0] == ' '
    places.base = replace(places.base,texture='· ,')
    state = instance.rng.getstate()
    first = places.cell(paint,floor,(3,1),roof=False,beside_wall=False,live=True)
    assert places.cell(paint,floor,(3,1),roof=False,beside_wall=False,live=True) == first
    assert instance.rng.getstate() == state
    body = deepcopy(body)
    body['looks']['marks'].append({'at':[2,1],'text':' ','role':'p6_grain'})
    places = for_frame(paint,body)
    assert places.cell(paint,floor,(2,1),roof=False,beside_wall=True,live=True)[0] == '·'


def test_ui_2_legacy_renderer_ignores_places_and_charting(fixtures):
    from tests.presentation.test_client_foundations import display
    from blacksite.server.protocol import Frame
    body, *_ = view(fixtures)
    bare = deepcopy(body)
    bare.pop('looks')
    bare.pop('charted')
    outputs = []
    for value in (body,bare):
        model = display(fixtures,enabled=False)
        model.receive(Frame('view',{'rev':1,'kind':'zone','body':value}),1)
        outputs.append(model.render(2)[0])
    assert outputs[0] == outputs[1]
