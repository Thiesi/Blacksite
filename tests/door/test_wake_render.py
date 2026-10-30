"""Wake / sheet rendering at 80x24 and 132x50 with wide names, all tiers."""

from dataclasses import asdict, replace
from pathlib import Path
import pytest
from blacksite.content.loader import load_content
from blacksite.door.model import Display
from blacksite.door.doorinfo import DoorInfo
from blacksite.server.protocol import Frame
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer
from tests.character_helpers import create
from blacksite.server.wake import Wake


@pytest.mark.parametrize("width,height",[(80,24),(132,50)])
@pytest.mark.parametrize("tier",["16","256","truecolor"])
def test_wake_golden_wide_name_scroll_and_character_sheet(info: DoorInfo,repo_root: Path,width: int,height: int,tier: str,golden) -> None:
    game=HeadlessServer(load_content(repo_root/"src/blacksite/content"),character_state={})
    client=game.connect(width=width,height=height)
    model=Display(replace(info,width=width,height=height,color_depth=tier))
    terminal=FakeTerminal(width,height)
    game.step()
    for frame in game.frames_for(client):model.receive(frame,0)
    terminal.write(model.render(0)[0])
    golden(f'wake_archetype_{width}x{height}', terminal, tier, trim=True)
    assert model.key("down",1)[0].data["name"]=="menu_cursor"
    create(game,client)
    for frame in game.frames_for(client):model.receive(frame,2)
    model.toast=None
    terminal.write(model.render(2)[0])
    assert "Wide界" in terminal.screen_text() and "Chits 200" in terminal.screen_text()
    assert "Lease days" in terminal.screen_text() and "Discharge XP" in terminal.screen_text()
    client.send(Frame("key",{"k":"P","t":0}));game.step()
    for frame in game.frames_for(client):model.receive(frame,3)
    terminal.write(model.render(3)[0])
    assert "CHARACTER" in terminal.screen_text() and "Ghost" in terminal.screen_text()
    assert model.key("D",4)[0].data["args"]["key"]=="d"
    # A long skill sheet scrolls its server-selected row into view at 80x24.
    body=model.body
    body["cursor"]=next(i for i,row in enumerate(body["rows"]) if row["id"]=="skill:listening")
    model.dirty=True;terminal.write(model.render(4)[0])
    assert "Listening" in terminal.screen_text()


@pytest.mark.parametrize('width,height', [(80, 24), (132, 50)])
@pytest.mark.parametrize('tier', ['16', '256', 'truecolor'])
def test_issue_67_all_recruiters_visible_with_no_card_selected(
        info: DoorInfo, repo_root: Path, width: int, height: int, tier: str) -> None:
    content = load_content(repo_root/'src/blacksite/content')
    wake = Wake(stage='card', cursor=len(content.wake_cards))
    body = wake.body(content, 'Wide界', width, height)['body']
    model = Display(replace(info, width=width, height=height, color_depth=tier))
    model.receive(Frame('welcome', {'palette': asdict(content.palette),
        'keymap': asdict(content.keymaps)}), 0)
    model.receive(Frame('view', {'rev': 1, 'kind': 'menu', 'body': body}), 1)
    terminal = FakeTerminal(width, height)
    terminal.write(model.render(1)[0])
    screen = terminal.screen_text()
    for card in content.wake_cards.values():
        assert card.name in screen
    assert 'Take no card' in screen and 'No standing changes.' in screen
    assert body['rows'][body['cursor']]['id'] == 'none'
