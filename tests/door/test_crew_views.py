"""UI 2/5: actual crew menu and crowded 80x24/132x50 views."""

from dataclasses import asdict, replace

import pytest

from blacksite.door.model import Display
from blacksite.server.crew_engine import CrewMenu
from blacksite.server.protocol import Frame, encode
from tests.fake_terminal import FakeTerminal
from tests.server.test_crews import content, callers, invite


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
@pytest.mark.parametrize('kind', ['menu', 'zone'])
def test_ui_2_crew_wide_names_and_health_keep_last_cell_safe(info, callers, size, kind):
    game, one, two, _ = callers
    invite(game, one, two)
    crews = game.core.crews
    display = Display(replace(info, width=size[0], height=size[1], color_depth='16'))
    display.receive(Frame('welcome', {'keymap': asdict(crews.content.keymaps), 'palette': asdict(crews.content.palette)}), 0)
    if kind == 'menu':
        crews.perform(one.session, 'beacon', two.session.player_id)
        body = crews.body(one.session, CrewMenu(1, game.clock.now_tick()))
    else:
        one.session.caps.update(width=size[0], height=size[1])
        game.step()
        body = game.core.characters.sim.views[one.session.id].previous['body']
    frame = Frame('view', {'rev': 1, 'kind': kind, 'body': body})
    encode(frame)
    display.receive(frame, 1)
    terminal = FakeTerminal(*size)
    terminal.write(display.render(1)[0])
    text = terminal.screen_text()
    assert terminal.cell(size[0]-1, size[1]-1) == ' '
    assert 'CREW' in text and 'Caller' in text
    assert '%' in text
    if kind == 'menu':
        assert 'Route: here' in text


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
def test_ui_2_crowded_crew_panel_keeps_hazard_warning(info, callers, size):
    game, one, two, _ = callers
    invite(game, one, two)
    game.step()
    body = game.core.characters.sim.views[one.session.id].previous['body']
    body['hazards'] = [{'warning': 5, 'escape': ['west']}]
    body['target'] = {'id': two.session.player_id, 'name': 'Crew界', 'faction': 'Freelance',
        'hp_percent': 100, 'range': 1, 'cover': 0, 'relation': 'crew'}
    display = Display(replace(info, width=size[0], height=size[1]))
    display.receive(Frame('welcome', {'keymap': asdict(game.core.crews.content.keymaps), 'palette': asdict(game.core.crews.content.palette)}), 0)
    display.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 0)
    terminal = FakeTerminal(*size)
    terminal.write(display.render(1)[0])
    assert 'WARNING 5s' in terminal.screen_text()
    assert 'Escape: west' in terminal.screen_text()
