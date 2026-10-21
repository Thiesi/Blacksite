"""S08 city menu and tram TextView in the fake terminal at all tiers."""

from dataclasses import replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from blacksite.server.protocol import Frame, encode
from tests.fake_terminal import FakeTerminal
from tests.character_helpers import act, create, place
from tests.harness import HeadlessServer


@pytest.mark.parametrize("width,height",[(80,24),(132,50)])
@pytest.mark.parametrize("tier",["16","256","truecolor"])
def test_city_map_and_tram_log_escape(info: DoorInfo,repo_root: Path,width: int,height: int,tier: str) -> None:
    game=HeadlessServer(load_content(repo_root/"src/blacksite/content"),character_state={})
    client=game.connect(width=width,height=height)
    create(game,client)
    display=Display(replace(info,width=width,height=height,color_depth=tier))
    terminal=FakeTerminal(width,height)
    act(game,client,Frame("key",{"k":"m","t":0}))
    for frame in game.frames_for(client):
        encode(frame)
        display.receive(frame,0)
    display.toast=None
    terminal.write(display.render(0)[0])
    assert "CITY MAP" in terminal.screen_text()
    act(game,client,display.key("enter",1)[0])
    for frame in game.frames_for(client): display.receive(frame,1)
    terminal.write(display.render(1)[0])
    assert "KNOWN EXITS" in terminal.screen_text()
    act(game,client,display.key("escape",2)[0])
    place(game,client,"core-tram-hub",(24,14))
    act(game,client,Frame("key",{"k":"e","t":0}))
    avatar=game.core.characters.sim.avatars[client.session.user_id]
    while not avatar.travel.departed: game.step()
    for frame in game.frames_for(client):
        encode(frame)
        display.receive(frame,3)
    terminal.write(display.render(3)[0])
    assert "The tram hums." in terminal.screen_text()
    assert display.key("escape",4)==[]
    terminal.write(display.render(4)[0])
    assert "SCROLLBACK" in terminal.screen_text()
    assert avatar.travel.departed
