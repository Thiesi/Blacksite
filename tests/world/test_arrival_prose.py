"""S25b TR-9: retain the complete arrival paragraph at both terminal sizes."""

from dataclasses import replace
from copy import deepcopy
from pathlib import Path
from textwrap import fill

import pytest

from blacksite.door.log import rows
from blacksite.door.cells import display_width
from blacksite.door.model import Display
from blacksite.content.loader import ContentTree, load_content
from blacksite.door.layout import compute
from scripts import build_city_content as author
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer
from tests.character_helpers import create, place
from tests.door.test_display import welcome


@pytest.mark.parametrize('generated', [False, True])
def test_every_arrival_fits_two_rows_at_80x24(content_tree: ContentTree,
        tmp_path: Path, generated: bool) -> None:
    if generated:
        author.build(tmp_path / 'arrival-city')
        content_tree = load_content(tmp_path / 'arrival-city')
    width = compute(80, 24).log.width
    for zone in content_tree.zones.values():
        for asset_id in zone.meta.lore[:1]:
            paragraph = ' '.join(content_tree.text[asset_id].body.strip().split('\n\n', 1)[0].splitlines())
            wrapped = rows([{'channel': 'zone', 'text': paragraph}], width)
            assert len(wrapped) <= 2, (zone.id, wrapped)
            assert ' '.join(row['text'].strip() for row in wrapped) == '[zone] ' + paragraph


def test_travel_logs_paragraph_after_hook_and_arrival_notice(content_tree: ContentTree) -> None:
    game = HeadlessServer(content_tree, character_state={})
    caller = game.connect()
    create(game, caller)
    sim = game.core.characters.sim
    avatar = sim.avatars[caller.session.user_id]
    exit_ = next(ex for ex in game.core.world.zones[avatar.zone].template.meta.exits
                 if ex.target_zone == 'vatside-clinics')
    place(game, caller, avatar.zone, exit_.tile)
    game.frames_for(caller)
    sim.interact(caller.session, avatar, game.clock.now_tick())
    lines = [line for frame in game.frames_for(caller) if frame.type == 'log'
             for line in frame.data['lines']]
    zone = game.core.world.zones[avatar.zone].template
    paragraph = ' '.join(content_tree.text[zone.meta.lore[0]].body.strip().split('\n\n', 1)[0].splitlines())
    assert avatar.zone == 'vatside-clinics'
    assert lines[-1]['text'] == paragraph
    notice = next(i for i, line in enumerate(lines) if line['text'] == 'You arrive at ' + zone.meta.name + '.')
    assert notice == len(lines) - 2
    # Discovery XP is durable: its notice follows the storage receipt,
    # rather than being emitted synchronously by the arrival hook.
    assert (caller.session.player_id, 'zone', avatar.zone) in game.core.progression.pending_discoveries
    game.commit_commerce()
    committed = [line for frame in game.frames_for(caller) if frame.type == 'log'
                 for line in frame.data['lines']]
    assert any(line['text'] == 'You gain 25 XP.' for line in committed)
    layout = compute(80, 24)
    visible = rows([*lines, *committed], layout.log.width)[-layout.log.height:]
    assert paragraph in ' '.join(row['text'].strip() for row in visible)


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
    assert ' '.join(row['text'].strip() for row in wrapped) == '[zone] ' + expected
    display.key('ctrl-p', 2)
    terminal = FakeTerminal(width, height)
    terminal.write(display.render(2)[0])
    assert 'SCROLLBACK' in terminal.screen_text()
