"""Wake / sheet rendering at 80x24 and 132x50 with wide names, all tiers."""

from dataclasses import asdict, replace
from pathlib import Path
import pytest
from karst41.content.loader import load_content
from karst41.door.model import Display
from karst41.door.doorinfo import DoorInfo
from karst41.server.protocol import Frame
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer
from tests.character_helpers import create
from karst41.server.wake import cards


@pytest.mark.parametrize("width,height",[(80,24),(132,50)])
@pytest.mark.parametrize("tier",["16","256","truecolor"])
def test_wake_golden_wide_name_scroll_and_character_sheet(info: DoorInfo,repo_root: Path,width: int,height: int,tier: str,golden) -> None:
    game=HeadlessServer(load_content(repo_root/"src/karst41/content"),character_state={})
    client=game.connect(width=width,height=height)
    model=Display(replace(info,width=width,height=height,color_depth=tier))
    terminal=FakeTerminal(width,height)
    game.step()
    assert game.core.characters.open_record(client.session,"door")  # S48c1: E at the street door.
    game.step()
    for frame in game.frames_for(client):model.receive(frame,0)
    terminal.write(model.render(0)[0])
    golden(f'wake_record_{width}x{height}', terminal, tier, trim=True)
    assert model.key("down",1)[0].data["name"]=="menu_cursor"
    create(game,client)
    for frame in game.frames_for(client):model.receive(frame,2)
    model.toast=None
    terminal.write(model.render(2)[0])
    assert "Wide界" in terminal.screen_text() and "Chits 200" in terminal.screen_text()
    assert "Lease days" in terminal.screen_text() and "Signatory XP" in terminal.screen_text()
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
    content = load_content(repo_root/'src/karst41/content')
    body = cards(content, len(content.wake_cards), width, height)  # The table in the hall (S48c1).
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


@pytest.mark.parametrize("width,height", [(80, 24), (132, 50)])
@pytest.mark.parametrize("tier", ["16", "256", "truecolor"])
def test_s48c1_card_table_in_the_hall(info: DoorInfo, repo_root: Path, width: int, height: int, tier: str, golden) -> None:
    from tests.character_helpers import act, place
    game = HeadlessServer(load_content(repo_root/"src/karst41/content"), character_state={})
    client = game.connect(width=width, height=height)
    model = Display(replace(info, width=width, height=height, color_depth=tier))
    terminal = FakeTerminal(width, height)
    game.step(2)
    place(game, client, "vatside-wake-hall", (8, 9))
    act(game, client, Frame("key", {"k": "e", "t": 0}))
    assert game.core.characters.screens[client.session.id][0] == "cards"
    for frame in game.frames_for(client):
        model.receive(frame, 0)
    terminal.write(model.render(0)[0])
    golden(f"wake_cards_{width}x{height}", terminal, tier, trim=True)
    assert "Esc/B put the cards down" in terminal.screen_text()
