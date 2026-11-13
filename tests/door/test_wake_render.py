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


@pytest.mark.parametrize("width,height",[(80,24),(132,50)])
@pytest.mark.parametrize("tier",["16","256","truecolor"])
def test_s48c1_card_table_for_a_finished_character_offers_the_recruiters(
        info: DoorInfo, repo_root: Path, width: int, height: int, tier: str, golden) -> None:
    # #241 ruling (b): until a card is taken, a character with a template gets
    # one more row, between the cards and "Take no card", to the recruiter menu.
    from tests.character_helpers import act, place
    game = HeadlessServer(load_content(repo_root/"src/karst41/content"), character_state={})
    client = game.connect(width=width, height=height)
    model = Display(replace(info, width=width, height=height, color_depth=tier))
    terminal = FakeTerminal(width, height)
    create(game, client, card="none")
    place(game, client, "vatside-wake-hall", (8, 9))
    act(game, client, Frame("key", {"k": "e", "t": 0}))
    manager = game.core.characters
    assert manager.screens[client.session.id][0] == "cards"
    deck = len(manager.content.wake_cards)
    screens = {}
    for cursor in range(deck + 2):
        if cursor:
            act(game, client, Frame("intent", {"name": "menu_cursor", "args": {"delta": 1}}))
        for frame in game.frames_for(client):
            model.receive(frame, cursor + 1)
        output, ack = model.render(cursor + 1)
        terminal.write(output)
        if ack:
            client.send(ack)
        screens[cursor] = terminal.screen_text()
        if cursor in (0, deck, deck + 1):
            golden(f"wake_cards_finished_{width}x{height}_{cursor}", terminal, tier, trim=True)
    names = [*(card.name for card in manager.content.wake_cards.values()), "Ask about joining", "Take no card"]
    for cursor, text in screens.items():
        # Every row, the way out included, stays visible at every cursor; at
        # 80x24 the `Choice` header gives way to make room (presentation lead).
        assert all(name in text for name in names), (width, cursor)
        assert ("Choice" in text) == (height > 24), (width, cursor)
    assert "Enter ask about joining  Esc/B put the cards down" in screens[deck]
    assert "Enter take none  Esc/B put the cards down" in screens[deck + 1]


def test_a_select_list_drops_its_column_header_only_when_it_would_not_fit() -> None:
    from karst41.layout import compute
    shape = compute(80, 24).menu_for()
    fits = shape.listing.height
    header, listing = shape.listing_for(fits)
    assert header and listing == shape.listing  # A list that fits keeps `Choice`.
    header, listing = shape.listing_for(fits + 1)
    assert not header and listing.y == shape.columns.y and listing.height == fits + 1  # Every row visible.
    header, listing = shape.listing_for(fits + 5)
    assert not header and listing.height == fits + 1  # Beyond that, the list scrolls.
