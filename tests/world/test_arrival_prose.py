"""S25b TR-9: retain the complete arrival paragraph at both terminal sizes."""

from dataclasses import replace
from copy import deepcopy
from pathlib import Path
from textwrap import fill

import pytest

from blacksite.door.log import rows
from blacksite.door.cells import display_width
from blacksite.door.model import Display
from blacksite.content.loader import ContentTree
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer
from tests.character_helpers import create
from tests.door.test_display import welcome


@pytest.mark.parametrize('width,height', [(80, 24), (132, 50)])
def test_arrival_paragraph_survives_wrapping_and_scrollback(content_tree: ContentTree,
        repo_root: Path, tmp_path: Path, width: int, height: int) -> None:
    content_tree = deepcopy(content_tree)
    game = HeadlessServer(content_tree, character_state={})
    caller = game.connect()
    create(game, caller)
    sim = game.core.characters.sim
    avatar = sim.avatars[caller.session.user_id]
    template = game.core.world.zones[avatar.zone].template
    asset_id = template.meta.lore[0]
    text = ('You follow the warm pipes past the station. ' * 4 + 'You see the final marker.')
    content_tree.text[asset_id] = replace(content_tree.text[asset_id],
        body=fill(text, 72)+'\n\nSecond paragraph stays separate.')
    avatar.seen_zones.clear()
    game.frames_for(caller)
    sim.discover(caller.session, avatar)
    frames = game.frames_for(caller)
    line = next(f.data['lines'][0] for f in frames if f.type == 'log')
    expected = text
    assert line['text'] == expected
    sim.discover(caller.session, avatar)
    assert not game.frames_for(caller)

    from blacksite.door.doorinfo import DoorInfo
    info = DoorInfo(tmp_path/'door_info.json', tmp_path,
                    {'user_id': 1, 'handle': 'Wide\u754c'}, width, height, '256', 3600)
    display = Display(replace(info, width=width, height=height))
    display.receive(welcome(repo_root), 0)
    for frame in frames:
        display.receive(frame, 1)
    assert list(display.logs)[-1]['text'] == expected
    wrapped = rows([line], display.layout.viewport.width-2)
    assert all(display_width(row['text']) <= display.layout.viewport.width-2 for row in wrapped)
    assert ''.join(row['text'].strip() for row in wrapped).endswith('You see the final marker.')
    display.key('ctrl-p', 2)
    terminal = FakeTerminal(width, height)
    terminal.write(display.render(2)[0])
    assert 'SCROLLBACK' in terminal.screen_text()
