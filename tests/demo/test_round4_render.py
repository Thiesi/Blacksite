"""Presentation lead's round4 spec: whole state words at both sizes."""

import pytest

from karst41.door.cells import display_width
from karst41.server.protocol import Frame
from tests.fake_terminal import FakeTerminal
from tests.presentation.test_client_foundations import display, zone_body
from scripts.demo_sodium.content import load_demo_content


@pytest.fixture(scope="module")
def content():
    return load_demo_content()


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('tier', ['16', '256', 'truecolor'])
def test_drawn_survives_target_crew_event_and_hazard(content, size, enabled, tier):
    width, height = size
    model = display(content, width, height, tier=tier, enabled=enabled)
    body = zone_body(content, width, height)
    body['me'].update(drawn=True, weapon='Sidearm with a very long name', grade=5, chits=5,
                      lease_days=3, xp=0, discharge_xp=100)
    body['target'] = {'id': 'target', 'name': 'Wide\u754cVeryLongPlayerName', 'class': 'player',
                      'drawn': True, 'name_role': 'player_neutral', 'hp_percent': 100,
                      'range': 3, 'cover': 0, 'faction': 'Freelance', 'relation': 'neutral'}
    body['crew'] = [{'name': 'Crewmate', 'hp_pct': 100, 'zone': 'Sodium Row', 'leader': True}]
    body['event'] = {'plans': [{'summary': 'Curfew'}]}
    body['hazards'] = [{'warning': 5, 'escape': ['north'], 'remaining': 10, 'tiles': []}]
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 0)
    terminal = FakeTerminal(width, height)
    terminal.write(model.render(0)[0])
    text = terminal.screen_text()
    assert 'DRAWN' in text
    assert 'drawn' in text
    for marker in ('DRAWN', 'drawn'):
        y = next(i for i,row in enumerate(text.splitlines()) if marker in row)
        row = text.splitlines()[y]
        x = display_width(row[:row.index(marker)])
        expected_right = model.layout.side.x + model.layout.side.width - (2 if enabled else 1)
        assert x + len(marker) - 1 == expected_right
        assert all(1 in terminal.renditions[x+i, y].attributes for i in range(len(marker)))
    if height == 50:
        assert 'd holsters' in text


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('tier', ['16', '256', 'truecolor'])
def test_nearby_drawn_keeps_its_whole_word(content, size, enabled, tier):
    width, height = size
    model = display(content, width, height, tier=tier, enabled=enabled)
    body = zone_body(content, width, height)
    body.update(target=None, crew=[], event=None, hazards=[])
    body['nearby'] = [{'id': 'peer', 'name': 'Another\u754cVeryLongPlayer', 'role': 'player_neutral',
                       'class': 'player', 'drawn': True, 'relation': '~'}]
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 0)
    terminal = FakeTerminal(width, height)
    terminal.write(model.render(0)[0])
    assert 'drawn' in terminal.screen_text()
