"""P5 / UI 2.1-2.5: default-off chrome and the agreed #106 corrections."""

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.door.cells import CellBuffer, display_width
from blacksite.door import chrome as shared_chrome
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from blacksite.door.palette import Palette
from blacksite.door.present import chrome, screen, zone
from blacksite.door.present.context import Context
from blacksite.door.present.paint import Paint, BAND_STEP, light_distance
from blacksite.layout import compute
from blacksite.server.protocol import Frame
from tests.door.test_lattice_render import sector_views  # noqa: F401
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer, WIDE_HANDLE
from tests.presentation.snapshots import canonical, cp437_problems, snapshot

ROOT = Path(__file__).resolve().parents[2]
SIZES = [(80, 24), (132, 50)]
TIERS = ['16', '256', 'truecolor']


@pytest.fixture(scope='module')
def content():
    return load_content(ROOT / 'src/blacksite/content')


def display(content, width=80, height=24, tier='256', enabled=True):
    info = DoorInfo(Path('unused'), ROOT, {'handle': WIDE_HANDLE.text, 'user_id': 1}, width, height, tier, 3600)
    model = Display(info, presentation=enabled)
    model.receive(Frame('welcome', {'palette': asdict(content.palette), 'keymap': asdict(content.keymaps)}), 0)
    return model


def zone_body(content, width=80, height=24):
    game = HeadlessServer(content, 'core-plaza')
    caller = game.connect(width=width, height=height)
    game.step()
    return next(frame.data['body'] for frame in game.frames_for(caller)
                if frame.type == 'view' and frame.data['kind'] == 'zone')


@pytest.mark.parametrize('size', SIZES)
@pytest.mark.parametrize('tier', TIERS)
@pytest.mark.parametrize('kind', ['zone', 'menu', 'text', 'dead', 'wake', 'title', 'talker', 'lattice'])
def test_ui_2_p5_style_golden_every_kind(content, sector_views, size, tier, kind,
                                     request, caller_provenance):
    width, height = size
    model = display(content, width, height, tier)
    shown_kind = kind
    body = {'title': 'A quiet room', 'lines': ['You hear the fan.'], 'hint': 'Esc/B back'}
    if kind == 'zone':
        body = zone_body(content, width, height)
    elif kind in ('menu', 'talker', 'wake'):
        body = {'title': 'Offers', 'kind': 'talker' if kind == 'talker' else 'inventory',
                'columns': ['Item'], 'rows': [] if kind == 'talker' else [{'id': 'one', 'cells': ['A steel key']}],
                'cursor': 0, 'detail': 'You stand beside the counter.',
                'actions': [{'key': 'a', 'label': 'Ask'}], 'hint': 'A ask  Esc/B back'}
        shown_kind = 'menu'
        if kind == 'wake':
            body = {'kind': 'menu', 'body': body, 'stage': 'archetype', 'hint': 'Choose an archetype'}
            shown_kind = 'wake'
    elif kind == 'lattice':
        body = sector_views[1]['lat-core']
    if kind != 'title':
        model.receive(Frame('view', {'rev': 1, 'kind': shown_kind, 'body': body}), 1)
    terminal = FakeTerminal(width, height)
    terminal.write(model.render(2)[0])
    assert 'HP' in terminal.screen_text() if kind == 'zone' else WIDE_HANDLE.text in terminal.screen_text()
    assert not cp437_problems(terminal)
    path = ROOT / 'tests/presentation/golden/p5' / f'{kind}_{width}x{height}_{tier}.json'
    actual = canonical(snapshot(terminal))
    if request.config.getoption('--update-goldens'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding='utf-8', newline='\n')
    assert path.read_text(encoding='utf-8') == actual


@pytest.mark.parametrize('tier', TIERS)
@pytest.mark.parametrize('variant', ['default', 'deutan', 'protan'])
def test_ui_2_2_walls_roofs_and_adjacent_floor_in_all_palettes(content, tier, variant):
    paint = Paint(Palette(asdict(content.palette), tier, variant))
    floor, floor_style = zone.cell(paint, {'id': 'floor', 'glyph': '·'})
    wall, wall_style = zone.cell(paint, {'id': 'wall', 'glyph': '█'})
    roof, roof_style = zone.cell(paint, {'id': 'wall', 'glyph': '█'}, roof=True)
    assert floor == '·' and roof == ' '
    assert wall == ('█' if tier == '16' else ' ')
    if tier != '16':
        assert light_distance(wall_style.bg, floor_style.bg) >= BAND_STEP
        assert light_distance(roof_style.bg, floor_style.bg) < light_distance(wall_style.bg, floor_style.bg)
    # Every shipped opaque class, seen and remembered. P5 has no place themes.
    for tile in (tile for tile in content.tiles.values() if tile.opaque):
        for remembered in (False, True):
            body = {'viewport': {'x': 0, 'y': 0, 'w': 3, 'h': 3},
                    'legend': [{'id': tile.id, 'glyph': content.glyphs.glyphs[tile.glyph], 'role': tile.colour},
                               {'id': 'floor', 'glyph': '·', 'role': 'floor'}],
                    'tiles': [[0, -2 if remembered else 1, 0]] * 3,
                    'remembered': [[0, 1, 0]] * 3}
            buffer = CellBuffer(80, 24)
            layout = compute(80, 24)
            zone.terrain(buffer, body, layout, paint)
            ox, oy = zone.origin(body, layout)
            terminal = FakeTerminal()
            terminal.write(buffer.full())
            assert all(terminal.cell(ox + 1, oy + y) == '·' for y in range(3))


@pytest.mark.parametrize('tier', TIERS)
def test_ui_2_2_jacked_hostile_never_reverse_and_drone_keeps_shape(content, tier):
    body = {'viewport': {'x': 0, 'y': 0, 'w': 3, 'h': 3},
            'actors': [{'id': 'self', 'x': 0, 'y': 0, 'role': 'player_self', 'glyph_id': 'actor-self'},
                       {'id': 'drone', 'x': 1, 'y': 1, 'role': 'player_hostile', 'class': 'drone',
                        'glyph_id': 'actor-drone', 'jacked': True}],
            'nearby': [{'id': 'drone', 'relation': '!'}]}
    paint = Paint(Palette(asdict(content.palette), tier))
    buffer = CellBuffer(80, 24)
    layout = compute(80, 24)
    zone.people(buffer, body, layout, paint)
    ox, oy = zone.origin(body, layout)
    term = FakeTerminal()
    term.write(buffer.full())
    assert term.cell(ox + 1, oy + 1) == 'τ'
    assert 7 not in term.renditions[ox + 1, oy + 1].attributes
    assert 7 in term.renditions[ox, oy].attributes
    if tier == '16':
        assert term.renditions[ox + 1, oy + 1].foreground == (0, 0)
        assert 1 in term.renditions[ox + 1, oy + 1].attributes  # ANSI bright black.


def test_ui_2_4_here_only_focus_and_visible_adjacent_cover(content):
    body = {'viewport': {'x': 10, 'y': 10, 'w': 4, 'h': 3},
            'actors': [{'id': 'me', 'role': 'player_self', 'x': 11, 'y': 11}],
            'legend': [{'id': 'floor'}, {'id': 'cover-1'}, {'id': 'cover-3'}, {'id': 'exit'}],
            'tiles': [[1, 0, -1, 2], [0, 0, -2, 0], [0, 0, 3, 0]],
            'remembered': [[0] * 4, [0, 0, 2, 0], [0] * 4],
            'objects': [{'id': 'hidden', 'kind': 'exit', 'name': 'Hidden passage', 'x': 12, 'y': 12}],
            'escape': {'routes': ['Hidden passage']},
            'focus': {'id': 'counter', 'label': 'A counter', 'verb': 'open'},
            'jack_focus': {'id': 'counter', 'label': 'A counter', 'verb': 'open'}}
    assert zone.at_hand(body) == ['A counter', '░ Light cover']
    body['focus'] = body['jack_focus'] = None
    body['tiles'][0][0] = -1
    assert zone.at_hand(body) == []


def test_ui_2_5_declared_rewards_identical_kinds_and_ten_second_protection():
    def line(kind, text, second, arrived=0):
        return {'kind': kind, 'text': text, 'at': f'2026-10-30T12:00:{second:02}+00:00', '_arrived': arrived}
    reward = chrome.digest([line('reward', 'You gain 5 XP.', 0), line('reward', 'You gain 10 XP.', 2)])
    assert [(r.kind, r.shown) for r in reward] == [('reward', '15 XP')]
    mixed = chrome.digest([line('danger', 'Move now.', 0), line('system', 'Move now.', 1),
                           line('danger', 'Move now.', 2), line('danger', 'Keep moving.', 3)])
    assert [(r.kind, r.shown) for r in mixed] == [('danger', 'Move now. (x2)'), ('system', 'Move now.'), ('danger', 'Keep moving.')]
    lines = [line('danger', 'Move now.', 0), line('combat', 'A drone fires.', 1)]
    lines += [line('system', f'Message {i}', i + 2, arrived=1) for i in range(12)]
    visible = chrome.visible_rows(lines, 78, 3, 9.9)
    assert {'Move now.', 'A drone fires.'} <= {row[1] for row in visible}
    assert 'Move now.' not in {row[1] for row in chrome.visible_rows(lines, 78, 3, 10.1)}
    assert not chrome.digest([line('notice', 'Maintenance', 0)])


def test_p5_context_is_pure_map_only_and_keys_keep_their_meaning(content):
    bodies = [{}, {'me': {'zone': 'core-plaza'}, 'target': {'id': 'x'}, 'hazards': [{'tiles': [[1, 1]]}]},
              {'nearby': [{'relation': '!'}], 'place': {'places': ['ignored']}, 'me': {'walking': [1, 1]}}]
    left, right = Context(), Context()
    for now, body in enumerate(bodies):
        saved = deepcopy(body)
        assert left.choose(body, now) == right.choose(body, now)
        assert left.last.view == 'map' and not left.last.looking and body == saved
    on, off = display(content), display(content, enabled=False)
    for key in ('f5', 'f7', 'f9', 'f10', 'up', 'j', 'e'):
        assert on.key(key, 1) == off.key(key, 1)


@pytest.mark.parametrize('size', SIZES)
def test_ui_11_new_hint_hosts_the_single_p3_fitter(content, size):
    from blacksite.hints import focus_context
    width, height = size
    body = zone_body(content, width, height)
    body['objective'] = None
    body['focus'] = {'label': 'A counter', 'verb': 'open'}
    body['jack_focus'] = None
    context = focus_context(body['focus'], None)
    body['hint'] = '  '.join((prefix + ' ' + label).rstrip() for prefix, label in context) + '  ? help  I inventory'
    for enabled in (False, True):
        model = display(content, width, height, enabled=enabled)
        model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 1)
        term = FakeTerminal(width, height)
        term.write(model.render(1)[0])
        if not enabled:
            expected = term.screen_text().splitlines()[model.layout.hint.y][1:-1]
        else:
            assert term.screen_text().splitlines()[model.layout.hint.y][1:-1] == expected
    groups = ['V abilities', 'E interact', 'I inventory', 'Q contracts', 'H character',
              'N journal', 'M map', 'G crew', '? help', 'Ctrl-X leave']
    raw = '  '.join(groups)
    for kind in ('zone', 'menu', 'text'):
        body = zone_body(content, width, height) if kind == 'zone' else {
            'title': 'Report', 'lines': ['You read.'], 'rows': [], 'actions': []}
        body.update(hint=raw, focus=None, jack_focus=None, objective=None)
        model = display(content, width, height)
        model.receive(Frame('view', {'rev': 1, 'kind': kind, 'body': body}), 1)
        model.render(1)
        shown = ''.join(cell.glyph for cell in model.previous.cells[model.layout.hint.y][1:-1]).strip()
        assert shown == shared_chrome.focus_hint(raw, model.layout.hint.width, [], fit_all=True)
        assert all(group in groups for group in shown.split('  '))
        assert display_width(shown) <= model.layout.hint.width


@pytest.mark.parametrize('size', SIZES)
def test_ui_6_long_wide_prompt_retains_borders_and_matches_legacy(content, size):
    from blacksite.door.views import LinePrompt
    width, height = size
    interiors = []
    for enabled in (False, True):
        model = display(content, width, height, enabled=enabled)
        model.prompt = LinePrompt('name', 'Name', 200, '界' * 80)
        term = FakeTerminal(width, height)
        term.write(model.render(1)[0])
        assert term.cell(width - 1, model.layout.hint.y) == ('║' if enabled else '│')
        interiors.append(term.screen_text().splitlines()[model.layout.hint.y][1:-1])
    assert interiors[0] == interiors[1]


@pytest.mark.parametrize('size', SIZES)
def test_ui_4_text_uses_full_width_and_hit_flash_keeps_frame_shape(content, size):
    width, height = size
    model = display(content, width, height)
    body = {'title': 'REPORT', 'lines': ['x' * (width - 10)], 'me': {'safety': 'safe', 'hit_serial': 0}}
    model.receive(Frame('view', {'rev': 1, 'kind': 'text', 'body': body}), 1)
    term = FakeTerminal(width, height)
    term.write(model.render(1)[0])
    assert term.screen_text().splitlines()[2].count('x') == width - 10
    normal = term.renditions[0, 0]
    body['me']['hit_serial'] = 1
    model.receive(Frame('view', {'rev': 2, 'kind': 'text', 'body': body}), 2)
    term.write(model.render(2)[0])
    assert term.cell(0, 0) == '╔' and term.renditions[0, 0] != normal
    term.write(model.render(2.2)[0])
    assert term.cell(0, 0) == '╔' and term.renditions[0, 0] == normal


def test_ui_2_4_crew_and_jacked_state_survive_a_busy_small_panel(content):
    body = zone_body(content)
    body['crew'] = [{'name': 'Peer界', 'hp_pct': 72, 'zone': 'Meridian Plaza', 'jacked': True}]
    body['nearby'] += [{'id': str(i), 'name': f'Civilian {i}', 'role': 'npc_neutral'} for i in range(12)]
    model = display(content)
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 1)
    term = FakeTerminal()
    term.write(model.render(1)[0])
    assert all(text in term.screen_text() for text in ('CREW', '72%', 'jacked', 'Meridian Plaza', 'HP', 'STA', 'SHK'))


@pytest.mark.parametrize('local', [True, False])
def test_ui_2_1_local_and_disconnected_screens_keep_server_body_safety(content, local):
    body = zone_body(content)
    body['me']['safety'] = 'open'
    model = display(content)
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 1)
    if local:
        model.open_help(['You read a note.'])
    else:
        # The I/O pump replaces the body when the connection drops.
        model.kind, model.body = 'text', {'title': 'DISCONNECTED', 'lines': ['You try again.']}
    term = FakeTerminal()
    term.write(model.render(2)[0])
    assert term.cell(0, 0) == '┌' and 'OPEN' in term.screen_text().splitlines()[0]
    assert 'SAFE' not in term.screen_text().splitlines()[0]


@pytest.mark.parametrize('size', SIZES)
def test_ui_2_5_p5_uses_word_boundaries_and_preserves_wide_text(size):
    width, height = size
    text = ('White light, warm plastic, a floor drain. You reach the fountain. '
            'The drone cannot kill. Wide界 words stay whole. ' * 3).strip()
    rows = chrome.visible_rows([{'kind': 'place', 'text': text}], compute(width, height).log.width, 100, 0)
    assert ' '.join(row[1] for row in rows) == text
    assert all(display_width(row[1]) <= width - 4 for row in rows)
    word = '界e\u0301' * 20
    rows = chrome.visible_rows([{'kind': 'system', 'text': word}], 20, 100, 0)
    assert ''.join(row[1] for row in rows) == word
    assert all(not row[1].endswith('e') for row in rows)


@pytest.mark.parametrize('size', SIZES)
def test_ui_2_4_objective_and_notice_never_overwrite_separator(content, size):
    width, height = size
    model = display(content, width, height)
    body = zone_body(content, width, height)
    body.update(focus=None, jack_focus=None, event=None,
                hint='Next: Complete training 0/1 | 3 chits  Tab target  F fire  ? help')
    body['objective'] = {'next_action': 'Complete training', 'progress': '0/1', 'cost': '3 chits'}
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 1)
    model.receive(Frame('toast', {'text': 'The corridor teaches targeting.', 'role': 'ui_text', 'seconds': 5}), 1)
    model.render(1)
    rows = [''.join(cell.glyph for cell in row) for row in model.previous.cells]
    assert set(rows[model.layout.separator.y]) <= set('─┴╟╢├┤')
    assert 'The corridor teaches targeting.' in rows[model.layout.log.bottom - 1]
    hint = rows[model.layout.hint.y]
    side = '\n'.join(row[model.layout.side.x:model.layout.side.right] for row in rows[:model.layout.side.bottom])
    if model.layout.wide:
        assert 'NOW' in side and 'Complete training' in side
        assert 'Next:' not in hint
    else:
        assert 'Next: Complete training 0/1 | 3 chits' in hint
        assert 'NOW' not in side


def test_ui_2_5_notice_and_newest_protected_combat_both_remain_visible(content):
    model = display(content)
    lines = [{'kind': 'combat', 'text': f'Critical {i}', '_arrived': 0} for i in range(model.layout.log.height)]
    buffer = CellBuffer(80, 24)
    chrome.log(buffer, model.layout, model.paint, lines, 1, ('A notice.', 'ui_text', 5))
    rows = [''.join(cell.glyph for cell in row) for row in buffer.cells]
    assert f'Critical {model.layout.log.height - 1}' in '\n'.join(rows)
    assert 'A notice.' in '\n'.join(rows)


def test_ui_2_small_wake_hall_centres_on_the_player(content):
    width, height = 132, 50
    game = HeadlessServer(content, 'vatside-wake-hall')
    caller = game.connect(width=width, height=height)
    game.step()
    body = next(frame.data['body'] for frame in game.frames_for(caller)
                if frame.type == 'view' and frame.data['kind'] == 'zone')
    model = display(content, width, height)
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 1)
    model.render(1)
    area, vp = model.layout.viewport, body['viewport']
    assert vp['w'] < area.width and vp['h'] < area.height
    assert model.previous.cells[area.y + area.height // 2][area.x + area.width // 2].glyph == '@'


@pytest.mark.parametrize('size', SIZES)
def test_ui_2_small_viewport_has_one_origin_for_every_overlay(content, size):
    layout = compute(*size)
    body = {'viewport': {'x': 100, 'y': 200, 'w': 7, 'h': 5},
            'legend': [{'id': 'floor', 'glyph': '·'}], 'tiles': [[0] * 7 for _ in range(5)],
            'actors': [{'id': 'self', 'x': 101, 'y': 201, 'role': 'player_self', 'glyph_id': 'actor-self'},
                       {'id': 'drone', 'x': 103, 'y': 201, 'role': 'npc_neutral', 'glyph_id': 'actor-drone'}],
            'objects': [{'x': 102, 'y': 201, 'kind': 'door'}, {'x': 105, 'y': 201, 'kind': 'beacon'}],
            'hazards': [{'tiles': [[106, 201]]}],
            'patrol_routes': [{'waypoints': [{'x': 104, 'y': 201}]}]}
    paint = Paint(Palette(asdict(content.palette)))
    buffer = CellBuffer(*size)
    at = zone.origin(body, layout)
    zone.terrain(buffer, body, layout, paint, at)
    zone.people(buffer, body, layout, paint, at)
    ox, oy = at
    for x, glyph in enumerate(('·', '@', '+', 'τ', '°', '♦', '·')):
        assert buffer.cells[oy + 1][ox + x].glyph == glyph
    assert buffer.cells[oy + 1][ox + 6].style.bg == paint('thing_hazard', 'hazard_warn').bg
    assert all(cell.glyph == ' ' for y, row in enumerate(buffer.cells) for x, cell in enumerate(row)
               if not (layout.viewport.x <= x < layout.viewport.right and layout.viewport.y <= y < layout.viewport.bottom))


@pytest.mark.parametrize('size', SIZES)
def test_ui_2_4_nearby_always_has_an_explicit_relation_tag(content, size):
    body = zone_body(content, *size)
    body.update(objective=None, event=None, focus=None, jack_focus=None, crew=[], hazards=[], target=None)
    body['nearby'] = [{'id': str(i), 'name': f'Visitor{i}', 'role': 'npc_neutral', 'relation': tag}
                      for i, tag in enumerate(('!', '~', '+'))]
    layout = compute(*size)
    buffer = CellBuffer(*size)
    zone.panel(buffer, body, layout, Paint(Palette(asdict(content.palette))))
    text = '\n'.join(''.join(cell.glyph for cell in row) for row in buffer.cells)
    assert all(f'Visitor{i} {tag}' in text for i, tag in enumerate(('!', '~', '+')))


@pytest.mark.parametrize('tier', ['256', 'truecolor'])
@pytest.mark.parametrize('variant', ['default', 'deutan', 'protan'])
def test_ui_2_2_every_band_and_jacked_floor_after_actual_tier_mapping(content, tier, variant):
    from math import atan2, degrees, hypot
    from blacksite.door.present.paint import HUE_TOLERANCE, hue_distance, lab
    palette = Palette(asdict(content.palette), tier, variant)
    paint = Paint(palette)
    bands = paint.bands
    assert bands.structure >= BAND_STEP
    assert bands.things >= bands.structure + BAND_STEP
    assert bands.people == bands.things + BAND_STEP
    assert bands.jacked == bands.structure + BAND_STEP
    assert light_distance(paint('floor').fg, bands.ground) < bands.structure
    roles = [role for role in palette.roles if role.startswith(('npc_', 'player_'))]
    assert roles
    for role in roles:
        for reverse in (False, True):
            style = paint(role, reverse=reverse)
            assert light_distance(style.fg, bands.ground) >= bands.people
            assert (7 in style.attrs) == reverse  # Reversed role colour is the displayed background.
        dim = paint.jacked(paint(role))
        assert 7 not in dim.attrs
        assert bands.jacked <= light_distance(dim.fg, bands.ground) < bands.people
        old, new = lab(palette.colour(role, 7)), lab(paint(role).fg)
        if hypot(old[1], old[2]) > 1:
            assert hue_distance(degrees(atan2(old[2], old[1])), degrees(atan2(new[2], new[1]))) <= HUE_TOLERANCE


@pytest.mark.parametrize('variant', ['default', 'deutan', 'protan'])
def test_ui_2_2_people_16_categories_and_halvard_exception(content, variant):
    from blacksite.door.present.paint import HALVARD_16, JACKED_16, PEOPLE_16
    palette = Palette(asdict(content.palette), '16', variant)
    paint = Paint(palette)
    for role in palette.roles:
        if role.startswith(('npc_', 'player_')):
            expected = HALVARD_16 if role == 'npc_halvard' else PEOPLE_16[palette.colour(role, 7)]
            assert paint(role).fg == expected and paint(role).fg != JACKED_16
            assert paint.jacked(paint(role)).fg == JACKED_16
    assert paint('npc_halvard', bold=True).fg == HALVARD_16
    assert 1 not in paint('npc_halvard', bold=True).attrs


@pytest.mark.parametrize('tier', ['256', 'truecolor'])
@pytest.mark.parametrize('variant', ['default', 'deutan', 'protan'])
def test_ui_2_2_shared_distance_helper_handles_a_synthetic_light_ground(content, tier, variant):
    from blacksite.door.present.paint import lift
    palette = Palette(asdict(content.palette), tier, variant)
    ground, structure, thing = ((238, 238, 238), (198, 198, 198), (128, 128, 128)) if tier == 'truecolor' else (255, 251, 244)
    structure_floor, things_floor = light_distance(structure, ground), light_distance(thing, ground)
    assert structure_floor >= BAND_STEP and things_floor >= structure_floor + BAND_STEP
    people_floor, jacked_floor = things_floor + BAND_STEP, structure_floor + BAND_STEP
    for role in palette.roles:
        if role.startswith(('npc_', 'player_')):
            person = lift(palette.colour(role, 7), people_floor, tier, ground=ground)
            assert light_distance(person, ground) >= people_floor
            jacked = lift(person, jacked_floor, tier, ground=ground, ceiling=people_floor)
            assert jacked_floor <= light_distance(jacked, ground) < people_floor


def test_ui_2_2_lift_is_cached_and_does_not_mutate_palette(content, monkeypatch):
    from blacksite.door.present import paint as paint_module
    data = asdict(content.palette)
    saved = deepcopy(data)
    palette = Palette(data, '256')
    calls, conversions = [], []
    lookup, convert = palette.colour, paint_module.lift
    def colour(role, fallback):
        calls.append(role)
        return lookup(role, fallback)
    def lift(*args, **kwargs):
        conversions.append(args)
        return convert(*args, **kwargs)
    monkeypatch.setattr(palette, 'colour', colour)
    monkeypatch.setattr(paint_module, 'lift', lift)
    paint = Paint(palette)
    plain, reverse = paint('npc_sable'), paint('npc_sable', reverse=True)
    dim = paint.jacked(plain)
    for _ in range(20):
        assert paint('npc_sable') is plain and paint('npc_sable', reverse=True) is reverse
        assert paint.jacked(plain) is dim
    assert calls.count('npc_sable') == 1 and len(conversions) == 2
    assert data == saved


def test_ui_2_2_cie_d65_reference_anchors():
    from blacksite.door.present.paint import lab
    assert lab((0, 0, 0))[0] == 0
    assert lab((255, 255, 255))[0] == pytest.approx(100)
    assert lab((255, 0, 0))[0] == pytest.approx(53.24, abs=.05)
    assert lab((128, 128, 128))[0] == pytest.approx(53.59, abs=.05)
