"""Core/Silt authority rendered through the real display and ANSI terminal."""

from pathlib import Path
from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from blacksite.server.lattice.presence import EscapeChannel
from blacksite.server.lattice.encounters import EncounterMenu
from blacksite.door.model import Display
from blacksite.server.protocol import Frame
from tests.fake_terminal import FakeTerminal
from tests.door.test_lattice_render import draw
from tests.lattice.test_engine import jack, runners
from tests.lattice.test_encounters import enter
from tests.lattice.test_silt_encounters import descend


def encounter_views():
    root = Path(__file__).parents[2]
    game, a, b, c = runners.__wrapped__(root)
    lattice = game.core.lattice
    first, second = enter(game, a, 'lat-civic-ledger'), enter(game, b, 'lat-civic-ledger')
    first.room = second.room = 'r-foyer'
    game.core.characters.players[second.player_id].name = 'Guest\u754c'
    ice = lattice.encounters.defenders(first)[0]
    first.target = ice.id
    lattice.encounters.start_cast(first, 'prg_pick', ice.id)
    game.step()
    _, core = lattice.encounters.view(a.session, first, lattice.view(a.session, first))
    lattice.leave(a.session, transition=False)
    below = descend(game, a)
    lattice.encounters.enter_band(below, 3)
    sweep = next(i for i in lattice.encounters.core(below).ice.values() if i.template.class_ == 'sweeper')
    below.room, below.target = sweep.location[1], sweep.id
    below.escape = EscapeChannel(game.clock.now_tick()+20, lattice.encounters.hit_serial(below))
    game.step()
    _, silt = lattice.encounters.view(a.session, below, lattice.view(a.session, below))
    return game.core.loop.content, {'core': core, 'silt': silt}


@pytest.fixture(scope='module')
def views():
    return encounter_views()


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
@pytest.mark.parametrize('tier', ['16', '256'])
@pytest.mark.parametrize('scene', ['core', 'silt'])
def test_ui_3_encounter_warnings_costs_and_escape_remain_visible(info, views, size, tier, scene):
    content, bodies = views
    body = bodies[scene]
    display, terminal = draw(info, content, body, *size, tier)
    text = terminal.screen_text()
    assert 'INTEGRITY' in text and 'TRACE' in text and 'HP 130/130' in text
    assert 'ROOM /' in text
    assert 'J escape' in text
    if scene == 'core':
        assert 'Tripwire' in text and 'Guest\u754c' in text
        assert 'warning' in text and 'Pick 0.' in text
    else:
        assert 'BLACK ICE / BODY RISK' in text and 'SWEEP (' in text
        assert 'ESCAPE 1.9s' in text and 'Interruptions 0/3' in text
        assert 'Sweeper' in text
        assert len(body['room']['controls']) == 0
    # Check every marker's geometry independently of the drawing loop.
    area = display.layout.viewport
    columns, rows = body['layout_size']
    height = max(4, area.height-5)
    occupied = set()
    for cell in body['cells']:
        x = area.x+1+cell['x']*(area.width-6)//max(1, columns-1)
        y = area.y+1+cell['y']*(height-3)//max(1, rows-1)
        marker = {(x+i, y) for i in range(4)}
        assert not marker & occupied
        occupied |= marker
        assert terminal.cell(x, y) == '(' and terminal.cell(x+3, y) == ')'
    if tier == '256':
        path = Path(__file__).with_name('golden')/f'encounter_{scene}_{size[0]}x{size[1]}.txt'
        assert text+'\n' == path.read_text(encoding='utf-8')


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
@pytest.mark.parametrize('keymap', ['arrows', 'vi'])
def test_ui_3_danger_menu_keeps_risk_body_hits_and_jack_action(info, size, keymap):
    game, a, b, c = runners.__wrapped__(Path(__file__).parents[2])
    presence = descend(game, a)
    lattice = game.core.lattice
    a.session.keymap_id = keymap
    a.session.caps.update(width=size[0], height=size[1])
    lattice.encounters.menus[a.session.id] = EncounterMenu('rig')
    kind, body = lattice.encounters.view(a.session, presence, lattice.view(a.session, presence))
    display = Display(replace(info, width=size[0], height=size[1]))
    display.receive(Frame('welcome', {'keymap': asdict(game.core.loop.content.keymaps),
                                    'palette': asdict(game.core.loop.content.palette)}), 0)
    display.receive(Frame('view', {'rev': 1, 'kind': kind, 'body': body}), 1)
    terminal = FakeTerminal(*size)
    terminal.write(display.render(1)[0])
    assert 'BLACK ICE / BODY RISK' in terminal.screen_text()
    assert 'HP 130/130' in terminal.screen_text()
    changed = deepcopy(body)
    changed['me']['hit_serial'] += 1
    display.receive(Frame('view', {'rev': 2, 'kind': 'menu', 'body': changed}), 2)
    assert display.hit_flash
    key = 'ctrl-o' if keymap == 'vi' else 'j'
    frame = display.key(key, 3)[0]
    assert frame.type == 'intent' and frame.data['name'] == 'lat.jack_out'
    game.core.receive(a.session, frame)
    game.step()
    assert presence.escape


def test_ui_3_seven_slot_rig_keeps_budgets_and_escape_visible_at_80_columns(info, views):
    content, bodies = views
    body = deepcopy(bodies['silt'])
    programs = ['prg_pick', 'prg_umbrella', 'prg_understudy', 'prg_smoke',
                'prg_anchor', 'prg_tourniquet', 'prg_signet']
    body['me']['rig'] = [{'slot': i+1, 'program': pid, 'name': content.programs[pid].name, 'cd': 0}
                         for i, pid in enumerate(programs)]
    body['me']['shield'] = {'name': 'Bunker', 'budget': 14}
    body['me']['decoy'] = 10
    _, terminal = draw(info, content, body, 80, 24, '16')
    text = terminal.screen_text()
    assert all(s in text for s in ('SHIELD 14', 'DECOY 10', 'ESCAPE 1.9s', '7 Signet', 'ROOM /'))
