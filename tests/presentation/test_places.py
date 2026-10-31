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
from blacksite.place import CHARTED_GROUND
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


def test_ui_2_2_ansi_uses_categories_not_numeric_band_floors(fixtures):
    content = deepcopy(fixtures)
    # The shipped green cover is below the grey ANSI wall in L*. It is
    # still the required categorical thing colour, with no numeric floor.
    content.palette.roles['thing_cover']['16'] = {variant:2 for variant in s.VARIANTS}
    assert not problems(content)  # 256 and truecolor retain valid floors.
    content.palette.roles['wall']['16']['default'] = 2
    assert any('wall foreground must be grey 8' in error for error in problems(content))
    content = deepcopy(fixtures)
    content.palette.roles['thing_exit']['16']['default'] = 0
    assert any('black wall background' in error for error in problems(content))


@pytest.mark.parametrize('variant',s.VARIANTS)
def test_ui_2_2_ansi_themed_people_equal_p5_including_halvard_and_jacked(fixtures,variant):
    paint = Paint(Palette(asdict(fixtures.palette),'16',variant))
    for theme in fixtures.themes.themes.values():
        for role in fixtures.palette.roles:
            if not role.startswith(('npc_','player_')):
                continue
            for reverse in (False,True):
                expected = paint(role,bold=True,reverse=reverse)
                assert paint.on_theme(role,theme,bold=True,reverse=reverse) == expected
                assert paint.on_theme(role,theme,bold=True,reverse=reverse,jacked=True) == paint.jacked(expected)
    assert paint.on_theme('npc_halvard',s.Theme()).fg == 7


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


@pytest.mark.parametrize('source,kind', [
    (source,kind) for source in ('object','interaction')
    for kind in ('door','gate','shutter','apartment_door')
] + [('requirement','door')])
def test_arch_5_5_5_public_barrier_face_does_not_admit_the_room(fixtures, source, kind):
    content = deepcopy(fixtures)
    zone = content.zones['p6-fixture']
    face = (20, 5)
    objects = tuple(obj for obj in zone.meta.objects if obj.tile != face)
    exits = zone.meta.exits
    grid = [list(row) for row in zone.grid]
    grid[5][20] = 'floor'
    if source == 'object':
        objects += (s.ObjectSpec('face', face, kind, {'open': True}),)
    elif source == 'interaction':
        grid[5][20] = 'door'
        content.tiles['door'] = replace(content.tiles['door'], interaction=kind)
    else:
        exits += (s.Exit('face', face, zone.id, (4, 5), 'door',
                         s.Requirement('story', 'fixture-access')),)
    zone = replace(zone, grid=tuple(tuple(row) for row in grid),
                   meta=replace(zone.meta, objects=objects, exits=exits,
                                public=(s.Region(*face, 1, 1),)))
    assert not list(charting_problems(zone, content.tiles))
    # Admitting the face must not extend the flood fill, even by one cell.
    for behind in ((21, 5), (22, 5)):
        room = replace(zone, meta=replace(zone.meta, public=(s.Region(*behind, 1, 1),)))
        assert any('unreachable' in error for error in charting_problems(room, content.tiles))
    # A second barrier cannot qualify merely by touching the admitted face.
    chained = replace(zone, meta=replace(zone.meta,
        objects=(*zone.meta.objects, s.ObjectSpec('second-face', (21, 5), 'door')),
        public=(s.Region(21, 5, 1, 1),)))
    assert any('unreachable' in error for error in charting_problems(chained, content.tiles))


def test_arch_5_5_5_barrier_face_never_admits_a_private_interior(fixtures):
    zone = fixtures.zones['p6-fixture']
    anchor = decode(s.HousingAnchor, json.loads((ROOT/'tests/fixtures/p6-private-anchor.json').read_text()))
    anchor = replace(anchor, origin=(20, 5))
    objects = tuple(obj for obj in zone.meta.objects if obj.tile != (20, 5))
    obj = s.ObjectSpec('private-face', (20, 5), 'apartment_door', housing=anchor)
    zone = replace(zone, meta=replace(zone.meta, objects=(*objects, obj),
                                    public=(s.Region(20, 5, 1, 1),)))
    assert any('private interior' in error for error in charting_problems(zone, fixtures.tiles))


@pytest.mark.parametrize('dx,dy', [(x,y) for x in (-1,0,1) for y in (-1,0,1)])
def test_arch_5_5_5_barrier_exception_preserves_hidden_exclusions(fixtures, dx, dy):
    zone = fixtures.zones['p6-fixture']
    at = (30+dx, 10+dy)
    grid = [list(row) for row in zone.grid]
    grid[at[1]][at[0]] = 'floor'
    zone = replace(zone, grid=tuple(tuple(row) for row in grid),
        meta=replace(zone.meta, public=(s.Region(*at, 1, 1),),
                     objects=(*zone.meta.objects, s.ObjectSpec('near-hidden', at, 'door'))))
    assert any('hidden exit' in error for error in charting_problems(zone, fixtures.tiles))
    # In valid content those cells remain outside the chart, including diagonals.
    body, _, _, _ = view(fixtures, 132, 50)
    vp = body['viewport']
    assert body['charted'][at[1]-vp['y']][at[0]-vp['x']] == -1


@pytest.mark.parametrize('tier', ['16', '256', 'truecolor'])
@pytest.mark.parametrize('size', [(80,24), (132,50)])
@pytest.mark.parametrize('region', [False, True])
def test_arch_5_5_5_door_terminal_and_required_exit_have_identical_ground(fixtures, tier, size, region):
    content = deepcopy(fixtures)
    original = content.zones['p6-fixture']
    face = (20, 5)
    look = content.looks[original.id]
    if region:
        content.looks[original.id] = replace(look, regions=(s.LookRegion('p6-light', rect=(*face,1,1)),))
    frames, charts = [], []
    for kind in ('door', 'terminal', 'requirement'):
        objects = tuple(obj for obj in original.meta.objects if obj.tile != face)
        exits = original.meta.exits
        grid = [list(row) for row in original.grid]
        grid[5][20] = 'floor'
        if kind == 'requirement':
            exits += (s.Exit('face', face, original.id, (4,5), 'door',
                             s.Requirement('story', 'fixture-access')),)
        else:
            objects += (s.ObjectSpec('face', face, kind),)
        content.zones[original.id] = replace(original, grid=tuple(tuple(row) for row in grid),
            meta=replace(original.meta, objects=objects, exits=exits,
                         public=(*original.meta.public, s.Region(*face,1,1))))
        assert not list(charting_problems(content.zones[original.id], content.tiles))
        body, caller, instance, perception = view(content, *size)
        remembered = deepcopy(perception.remembered)
        for opened in (False, True):
            if kind == 'door':
                instance.objects['face'].open = opened
            # Rebuild both chart and sight; the result must not depend on caches.
            perception.chart_key = perception.grid_key = perception.look_key = None
            body = build(caller, instance, perception, content, *size, '12:00', False, 1)
            vp = body['viewport']
            x,y = face[0]-vp['x'],face[1]-vp['y']
            assert body['tiles'][y][x] == body['remembered'][y][x] == -1
            assert body['charted'][y][x] == CHARTED_GROUND
            assert not any((obj['x'],obj['y']) == face for obj in body['objects'])
            assert perception.remembered == remembered and face not in remembered[instance.id]
            buffer = CellBuffer(*size)
            drawing.terrain(buffer, body, compute(*size), Paint(Palette(asdict(content.palette), tier)))
            terminal = FakeTerminal(*size)
            terminal.write(buffer.full())
            frames.append(canonical(snapshot(terminal)))
            charts.append((body['charted'],body['looks']))
    assert all(frame == frames[0] for frame in frames)
    assert all(chart == charts[0] for chart in charts)


def test_arch_5_5_4_masking_whole_only_and_memory(fixtures):
    body, caller, instance, perception = view(fixtures)
    remembered = deepcopy(perception.remembered)
    chart = body['charted']
    vp = body['viewport']
    known = {(vp['x']+x,vp['y']+y) for y,row in enumerate(body['tiles']) for x,n in enumerate(row)
             if n != -1 or chart[y][x] >= 0 or chart[y][x] == CHARTED_GROUND}
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


def test_ui_2_2_mark_rejects_only_wall_adjacent_spaces_and_names_cell(fixtures):
    content = deepcopy(fixtures)
    look = content.looks['p6-fixture']
    content.looks[look.id] = replace(look,marks=(s.LookMark('p6_grain',at=(2,1),text='A B'),))
    assert any('mark space at (3, 1)' in error for error in problems(content))
    # Letters may border the same wall; spaces away from it remain legal.
    for at,text in (((2,1),'A·B'),((2,2),'A B')):
        content.looks[look.id] = replace(look,marks=(s.LookMark('p6_grain',at=at,text=text),))
        assert not problems(content)


@pytest.mark.parametrize('tier',['16','256','truecolor'])
@pytest.mark.parametrize('light',[False,True])
@pytest.mark.parametrize('at',[(14,4),(11,7)])
def test_arch_5_5_5_withheld_charted_cells_are_uniform_ground_not_void(fixtures,tier,light,at):
    content = deepcopy(fixtures)
    original = content.zones['p6-fixture']
    look = content.looks[original.id]
    if light:
        look = replace(look,theme='p6-light')
    # Make grain nonblank at the test cell, without changing its class or
    # introducing a new authored rule. Dressing must not expose its kind.
    for tid,record in list(content.themes.themes.items()):
        content.themes.themes[tid] = replace(record,texture='·')
    # (11,7) is inside the light region, even when the base is dark.
    # This also proves the server keeps region ground over marker cells.
    theme = content.themes.themes['p6-light' if at==(11,7) else look.theme]
    content.looks[look.id] = replace(look,marks=(s.LookMark('p6_grain',at=at,text='X'),),
        glints=(at,),glint_role='p6_grain',signs=())
    frames,charts = [],[]
    for tile_id,kind in (('floor','hardware'),('terminal',None),('hazard',None)):
        grid = [list(row) for row in original.grid]
        grid[at[1]][at[0]] = tile_id
        objects = original.meta.objects + ((s.ObjectSpec('withheld',at,kind),) if kind else ())
        content.zones[original.id] = replace(original,grid=tuple(tuple(row) for row in grid),
                                              meta=replace(original.meta,objects=objects))
        body,caller,instance,perception = view(content)
        vp = body['viewport']
        x,y = at[0]-vp['x'],at[1]-vp['y']
        assert body['tiles'][y][x] == -1
        assert body['charted'][y][x] == CHARTED_GROUND
        assert at not in perception.remembered[instance.id]
        assert not any(obj['x']==at[0] and obj['y']==at[1] for obj in body['objects'])
        assert not body['looks']['marks'] and not body['looks']['glints']
        charts.append((body['charted'],body['looks']))
        paint = Paint(Palette(asdict(content.palette),tier))
        buffer = CellBuffer(80,24)
        drawing.terrain(buffer,body,compute(80,24),paint)
        terminal = FakeTerminal()
        terminal.write(buffer.full())
        ox,oy = drawing.origin(body,compute(80,24))
        assert terminal.cell(ox+x,oy+y) == '·'
        places = for_frame(paint,body)
        glyph,style = places.cell(paint,{'id':':charted-ground','plain':True,'ground_only':True},
            at,roof=False,beside_wall=False,live=False)
        assert glyph == '·' and style == paint.known(paint('floor') if tier=='16'
                                                   else paint(theme.ground_fg,theme.ground_bg))
        frames.append(canonical(snapshot(terminal)))
        before = deepcopy(body['charted'])
        instance.geometry[at] = 'wall'
        instance.geometry_revision += 1
        assert build(caller,instance,perception,content,80,24,'12:00',False,1)['charted'] == before
    assert frames[0] == frames[1] == frames[2]
    assert charts[0] == charts[1] == charts[2]


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
    if tier == '16':
        assert first == paint('npc_neutral')
    else:
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


def test_arch_5_5_2_fixture_terminals_are_actual_focus_targets(fixtures):
    from tests.harness import HeadlessServer
    from tests.character_helpers import create, place
    game = HeadlessServer(fixtures,character_state={})
    client = game.connect(width=80,height=24)
    create(game,client,archetype=0,name='Fixture界',card='none')
    for at,suffix in (((4,5),'(Plaza)'),((9,5),'(Clinic)')):
        place(game,client,'p6-fixture',at)
        focus,jack = game.core.interaction_views(client.session)
        assert jack is not None and jack['label'].endswith(suffix)
        avatar = game.core.characters.sim.avatars[client.session.user_id]
        body = build(avatar.actor,game.core.world.zones[avatar.zone],avatar.perception,
                     fixtures,80,24,'12:00',False,game.clock.now_tick())
        body['focus'],body['jack_focus'] = focus,jack
        assert any(line.startswith('§ ') and suffix in drawing.fit_here(line,21) for line in drawing.at_hand(body))


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


@pytest.mark.parametrize('tier',['16','256','truecolor'])
def test_ui_2_2_look_keeps_p5_rule_glyphs_roles_and_attributes(fixtures,tier):
    body, *_ = view(fixtures)
    paint = Paint(Palette(asdict(fixtures.palette),tier))
    places = for_frame(paint,body)
    for tid in ('locked-door','cover-1','cover-2','cover-3','water','terminal','hazard'):
        tile = fixtures.tiles[tid]
        entry = {'id':tid,'glyph':fixtures.glyphs.glyphs[tile.glyph], 'role':tile.colour,
                 'water':tid=='water'}
        expected_glyph,expected_style = drawing.cell(paint,entry)
        glyph,style = places.cell(paint,entry,(7,3),roof=False,beside_wall=False,live=True)
        assert glyph == expected_glyph
        assert style.fg == expected_style.fg and style.attrs == expected_style.attrs
        assert style.bg == (0 if tier=='16' else paint.palette.style('p6_ground').fg)
        if tid == 'locked-door':
            assert glyph == '≡'


def test_arch_5_5_4_mask_cache_does_not_enumerate_whole_memory(fixtures):
    class ViewportMemory(dict):
        def __iter__(self):
            raise AssertionError('Do not enumerate the remembered map to mask one viewport')
    body,caller,instance,perception = view(fixtures)
    perception.remembered[instance.id] = ViewportMemory(perception.remembered[instance.id])
    caller.x += 1
    caller.sight_key = None
    body = build(caller,instance,perception,fixtures,80,24,'12:00',False,1)
    same = build(caller,instance,perception,fixtures,80,24,'12:01',False,2)
    assert same['looks'] is body['looks']


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


@pytest.mark.parametrize('tier',['16','256','truecolor'])
def test_ui_2_cached_terrain_matches_fresh_paint_through_movement(fixtures,tier):
    body,caller,instance,perception = view(fixtures)
    palette = asdict(fixtures.palette)
    cached = Paint(Palette(palette,tier))
    layout = compute(80,24)
    origin = layout.viewport.x,layout.viewport.y
    for step,x in enumerate((4,5,6,5,4)):
        caller.x = x
        caller.sight_key = None
        instance.geometry.clear()
        if step == 2:
            instance.geometry[6,7] = 'cover-1'
        instance.geometry_revision += 1
        body = build(caller,instance,perception,fixtures,80,24,'12:00',False,x)
        body['hazards'] = [{'tiles':[[6,7]]}] if step in (1,2) else []
        draw_origin = origin[0] + (step == 4), origin[1]
        frames = []
        for paint in (cached,Paint(Palette(palette,tier))):
            buffer = CellBuffer(80,24)
            drawing.terrain(buffer,body,layout,paint,draw_origin)
            drawing.people(buffer,body,layout,paint,draw_origin)
            term = FakeTerminal()
            term.write(buffer.full())
            frames.append(canonical(snapshot(term)))
        assert frames[0] == frames[1]
        places = for_frame(cached,body)
        assert not any(cell.glyph == '@' for row in places.terrain_buffer.cells for cell in row)


def test_arch_5_5_4_whole_known_ring_and_sign_can_cross_viewport(fixtures):
    from blacksite.server.views.looks import masked
    content = deepcopy(fixtures)
    zone = content.zones['p6-fixture']
    content.zones[zone.id] = replace(zone,
        meta=replace(zone.meta,public=(s.Region(0,0,120,50),),exits=(),objects=()),
        grid=tuple(tuple('wall' if x in (0,119) or y in (0,49) else 'floor'
                         for x in range(120)) for y in range(50)))
    look = replace(content.looks['p6-fixture'],regions=(s.LookRegion('p6-ring',circle=(40,24,14)),),
                   signs=(s.LookSign((62,0),'KNOWN SIGN','thing_exit'),),marks=(),glints=())
    content.looks['p6-fixture'] = look
    assert not problems(content)
    for size in ((80,24),(132,50)):
        body, *_ = view(content,*size,position=(40,5))
        assert any('circle' in region for region in body['looks']['regions'])
        assert body['looks']['signs'][0]['text'] == 'KNOWN SIGN'
    # A clipped viewport knows only a subset of the ring/sign, while the
    # caller's chart or memory authorizes their complete footprint.
    known = {(40,24),(62,0)}
    ring = {(x,y) for y in range(10,39) for x in range(12,69)
            if (x-40)**2+4*(y-24)**2 <=4*14**2}
    whole = ring | {(x,0) for x in range(62,72)}
    result = masked(content,content.zones['p6-fixture'],known,set(),known_at=whole.__contains__)
    assert len(result['regions']) == 1 and result['regions'][0]['circle'] == [40,24,14]
    assert result['signs'][0]['text'] == 'KNOWN SIGN'
    blocked = masked(content,content.zones['p6-fixture'],known,set(),known_at=(whole-{(40,10),(71,0)}).__contains__)
    assert not blocked['regions'] and not blocked['signs']
    # P1's fully-explored preparation invalidates the grid without moving
    # the caller. The dependent look mask must observe that rebuild too.
    zone = content.zones['p6-fixture']
    content.zones[zone.id] = replace(zone,meta=replace(zone.meta,charted=False,public=()))
    body,caller,instance,perception = view(content,position=(40,5))
    assert not body['looks']['regions']
    perception.remembered[zone.id] = {(x,y):zone.grid[y][x] for y in range(50) for x in range(120)}
    perception.grid_key = None
    restored = build(caller,instance,perception,content,80,24,'12:00',False,1)
    assert any('circle' in region for region in restored['looks']['regions'])


@pytest.mark.parametrize('tier',['16','256','truecolor'])
def test_ui_2_cached_terrain_follows_actual_server_camera_scroll(fixtures,tier):
    content = deepcopy(fixtures)
    zone = content.zones['p6-fixture']
    content.zones[zone.id] = replace(zone,
        meta=replace(zone.meta,public=(s.Region(0,0,120,50),),exits=(),objects=()),
        grid=tuple(tuple('wall' if x in (0,119) or y in (0,49) else 'floor'
                         for x in range(120)) for y in range(50)))
    instance = ZoneInstance(content.zones[zone.id],content.tiles,7)
    caller = Actor('camera:caller','Wide界',zone=zone.id,x=52,y=24)
    instance.actors[caller.id] = caller
    perception = Perception()
    cached = Paint(Palette(asdict(content.palette),tier))
    crops = []
    for x in (52,78,79,52):
        caller.x = x
        body = build(caller,instance,perception,content,80,24,'12:00',False,x)
        crops.append(body['viewport']['x'])
        frames = []
        for paint in (cached,Paint(Palette(asdict(content.palette),tier))):
            buffer = CellBuffer(80,24)
            drawing.render(buffer,body,compute(80,24),paint)
            terminal = FakeTerminal()
            terminal.write(buffer.full())
            frames.append(canonical(snapshot(terminal)))
        assert frames[0] == frames[1]
    assert len(set(crops)) > 1
