"""P5 / UI 2.1-2.5: default-off chrome and the agreed #106 corrections."""

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.door.cells import CellBuffer
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from blacksite.door.palette import Palette
from blacksite.door.present import chrome, screen, zone
from blacksite.door.present.context import Context
from blacksite.door.present.paint import Paint, XTERM
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
        rgb = lambda value: value if isinstance(value, tuple) else XTERM[value]
        lightness = lambda value: sum(rgb(value)) / (3 * 255)
        assert lightness(wall_style.bg) - lightness(floor_style.bg) >= .08
        assert lightness(roof_style.bg) < lightness(wall_style.bg)
    # Every shipped opaque class, seen and remembered. P5 has no place themes.
    for tile in (tile for tile in content.tiles.values() if tile.opaque):
        for remembered in (False, True):
            body = {'viewport': {'x': 0, 'y': 0, 'w': 3, 'h': 3},
                    'legend': [{'id': tile.id, 'glyph': content.glyphs.glyphs[tile.glyph], 'role': tile.colour},
                               {'id': 'floor', 'glyph': '·', 'role': 'floor'}],
                    'tiles': [[0, -2 if remembered else 1, 0]] * 3,
                    'remembered': [[0, 1, 0]] * 3}
            buffer = CellBuffer(80, 24)
            zone.terrain(buffer, body, compute(80, 24), paint)
            terminal = FakeTerminal()
            terminal.write(buffer.full())
            assert all(terminal.cell(2, y) == '·' for y in (1, 2, 3))


@pytest.mark.parametrize('tier', TIERS)
def test_ui_2_2_jacked_hostile_never_reverse_and_drone_keeps_shape(content, tier):
    body = {'viewport': {'x': 0, 'y': 0, 'w': 3, 'h': 3},
            'actors': [{'id': 'self', 'x': 0, 'y': 0, 'role': 'player_self', 'glyph_id': 'actor-self'},
                       {'id': 'drone', 'x': 1, 'y': 1, 'role': 'player_hostile', 'class': 'drone',
                        'glyph_id': 'actor-drone', 'jacked': True}],
            'nearby': [{'id': 'drone', 'relation': '!'}]}
    paint = Paint(Palette(asdict(content.palette), tier))
    buffer = CellBuffer(80, 24)
    zone.people(buffer, body, compute(80, 24), paint)
    term = FakeTerminal()
    term.write(buffer.full())
    assert term.cell(2, 2) == 'τ'
    assert 7 not in term.renditions[2, 2].attributes
    assert 7 in term.renditions[1, 1].attributes
    if tier == '16':
        assert term.renditions[2, 2].foreground == (0, 0)
        assert 1 in term.renditions[2, 2].attributes  # ANSI bright black.


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


def test_ui_11_new_hint_hosts_the_single_p3_fitter(content):
    body = zone_body(content)
    for enabled in (False, True):
        model = display(content, enabled=enabled)
        model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 1)
        term = FakeTerminal()
        term.write(model.render(1)[0])
        if not enabled:
            expected = term.screen_text().splitlines()[model.layout.hint.y][1:-1]
        else:
            assert term.screen_text().splitlines()[model.layout.hint.y][1:-1] == expected


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
