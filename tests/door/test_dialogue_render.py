"""Game 13.4: rowless talker actions and wide names at both native sizes."""

from dataclasses import asdict, replace
from copy import deepcopy

import pytest

from karst41.content.loader import ContentTree
from karst41.door.doorinfo import DoorInfo
from karst41.door.model import Display
from tests.character_helpers import act
from tests.fake_terminal import FakeTerminal
from tests.test_dialogue_runtime import content, open_talker, setup
from karst41.server.protocol import Frame


@pytest.mark.parametrize('width,height', [(80, 24), (132, 50)])
@pytest.mark.parametrize('tier', ['16', '256', 'truecolor'])
def test_game_13_4_rowless_talker_renders_and_dispatches_its_advertised_hotkey(
        content: ContentTree, info: DoorInfo, width: int, height: int, tier: str) -> None:
    game, caller, player = setup(content, width, height)
    open_talker(game, caller)
    display = Display(replace(info, width=width, height=height, color_depth=tier))
    for frame in game.frames_for(caller):
        display.receive(frame, 0)
    display.toast = None
    terminal = FakeTerminal(width, height)
    terminal.write(display.render(0)[0])
    screen = terminal.screen_text()
    assert 'move or Esc/B leaves' in screen
    assert 'Vesper - fixer' in screen and 'Show me the card.' in screen
    assert 'Wide界' in screen and 'Work' in screen and 'Trade' in screen
    assert display.key('z', 1) == []  # Unadvertised keys grant no action.
    frames = display.key('c', 2)
    assert len(frames) == 1 and frames[0].data['args'] == {'row': '', 'key': 'c'}
    act(game, caller, frames[0])
    assert caller.session.id in game.core.contracts.panels.menus
    assert caller.session.id not in game.core.dialogue.menus


@pytest.mark.parametrize('keymap,key,expected', [
    ('arrows', 'up', 'key'), ('arrows', 'home', 'key'),
    ('arrows', 'end', 'key'), ('arrows', 'pgup', 'key'),
    ('arrows', 'pgdn', 'key'), ('vi', 'h', 'key'),
    ('vi', 'down', None), ('vi', 'pageup', None),
    ('vi', 'j', 'menu_select'), ('vi', 'b', 'menu_close'),
])
def test_ui_4_physical_talker_keys_use_welcome_keymap(content, info, keymap, key, expected):
    display = Display(info)
    display.receive(Frame('welcome', {'keymap': asdict(content.keymaps), 'player': {'settings': {'keymap': keymap}}}), 0)
    display.receive(Frame('view', {'rev': 1, 'kind': 'menu', 'body': {
        'kind': 'talker', 'walk_away': True, 'title': 'Person', 'rows': [],
        'actions': [{'key': 'j', 'label': 'Job'}, {'key': 'b', 'label': 'Back'}]}}), 0)
    frames = display.key(key, 1)
    if expected is None:
        assert not frames
    elif expected == 'key':
        assert len(frames) == 1 and frames[0].type == 'key' and frames[0].data['k'] == key
    else:
        assert len(frames) == 1 and frames[0].data['name'] == expected


def test_ui_4_talker_movement_binding_can_be_changed_by_server(content, info):
    keymap = asdict(content.keymaps)
    table = next(table for table in keymap['keymaps'] if table['id'] == 'arrows')
    table['bindings']['move_up'] = ('z',)
    display = Display(info)
    display.receive(Frame('welcome', {'keymap': keymap}), 0)
    display.receive(Frame('view', {'rev': 1, 'kind': 'menu', 'body': {
        'kind': 'talker', 'walk_away': True, 'title': 'Person', 'rows': [], 'actions': []}}), 0)
    assert display.key('z', 1)[0].type == 'key'
    assert display.key('up', 1) == []


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
@pytest.mark.parametrize('tier', ['16', '256', 'truecolor'])
def test_ui_4_no_offer_talker_hint_fits_without_asking_for_an_action(content, info, size, tier):
    content = deepcopy(content)
    content.dialogue['vesper'] = replace(content.dialogue['vesper'], offers=())
    game, caller, _ = setup(content, *size)
    open_talker(game, caller)
    display = Display(replace(info, width=size[0], height=size[1], color_depth=tier))
    for frame in game.frames_for(caller):
        display.receive(frame, 0)
    display.toast = None
    terminal = FakeTerminal(*size)
    terminal.write(display.render(0)[0])
    text = terminal.screen_text()
    assert 'Move or Esc/B leaves' in text and 'Choose an action' not in text


@pytest.mark.parametrize('kind,walk_away', [('vendor', False), ('talker', False)])
def test_ui_4_other_menus_and_lattice_talkers_swallow_movement(info, kind, walk_away):
    display = Display(info)
    display.receive(Frame('welcome', {}), 0)
    display.receive(Frame('view', {'rev': 1, 'kind': 'menu', 'body': {
        'kind': kind, 'walk_away': walk_away, 'title': 'Menu', 'rows': [], 'actions': []}}), 0)
    frames = display.key('up', 1)
    assert len(frames) == 1 and frames[0].data['name'] == 'menu_cursor'
