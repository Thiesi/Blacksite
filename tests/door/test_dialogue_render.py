"""Game 13.4: rowless talker actions and wide names at both native sizes."""

from dataclasses import replace

import pytest

from blacksite.content.loader import ContentTree
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from tests.character_helpers import act
from tests.fake_terminal import FakeTerminal
from tests.test_dialogue_runtime import content, open_talker, setup


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
    assert 'Vesper - fixer' in screen and 'Show me the card.' in screen
    assert 'Wide界' in screen and 'Work' in screen and 'Trade' in screen
    assert display.key('z', 1) == []  # Unadvertised keys grant no action.
    frames = display.key('c', 2)
    assert len(frames) == 1 and frames[0].data['args'] == {'row': '', 'key': 'c'}
    act(game, caller, frames[0])
    assert caller.session.id in game.core.contracts.panels.menus
    assert caller.session.id not in game.core.dialogue.menus
