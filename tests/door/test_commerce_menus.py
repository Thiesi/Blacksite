"""S12 server menus through the cell buffer at both sizes/all tiers."""

from dataclasses import replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.door.model import Display
from blacksite.server.commerce import CommerceMenu
from blacksite.server.protocol import Frame, encode
from tests.character_helpers import create, place
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer


@pytest.mark.parametrize("width,height",[(80,24),(132,50)])
@pytest.mark.parametrize("tier",["16","256","truecolor"])
def test_commerce_menus_wide_handles_esc_and_no_stale_purchase(info,repo_root: Path,width,height,tier) -> None:
    game=HeadlessServer(load_content(repo_root/"src/blacksite/content"),character_state={})
    client=game.connect(width=width,height=height)
    create(game,client,name="Wake界")
    display=Display(replace(info,width=width,height=height,color_depth=tier))
    terminal=FakeTerminal(width,height)
    commerce=game.core.commerce
    player=game.core.characters.players[client.session.player_id]
    stamp=0
    def draw() -> str:
        nonlocal stamp
        stamp+=1
        game.step()
        for frame in game.frames_for(client):
            encode(frame)
            display.receive(frame,stamp)
        display.toast=None
        terminal.write(display.render(stamp)[0])
        return terminal.screen_text()
    place(game,client,"vatside-wake-hall",(34,15))
    for kind in ("inventory","equipment","vendor","bank"):
        if kind=="bank": place(game,client,"core-tram-hub",(12,7))
        target="wake-outfitter" if kind=="vendor" else "kestrel-bank" if kind=="bank" else ""
        commerce.menus[client.session.id]=CommerceMenu(kind,target)
        assert draw()
        assert display.kind=="menu"
        if kind=="inventory": assert "Kestrel Issue Sidearm" in terminal.screen_text()
        if kind=="vendor":
            assert "BUY" in terminal.screen_text()
            sell = commerce.body(client.session, CommerceMenu("vendor", target, sell=True))
            pistol = next(iid for iid in player.inventory if commerce.items[iid].template=="wpn_kestrel_sidearm")
            assert next(row for row in sell["rows"] if row["id"]==pistol)["cells"][2]=="48"
            before=player.chits_hand
            client.send(Frame("intent",{"name":"menu_select","args":{"row":"wpn_kestrel_sidearm","key":"enter"},"request_id":"stale","expected_revision":0}))
            game.step(); assert not commerce.outbox and player.chits_hand==before
        frames=display.key("escape",stamp+.5)
        assert frames[0].data["name"]=="menu_close"
        client.send(frames[0]); draw()
        assert client.session.id not in commerce.menus
        assert display.kind=="zone"
        assert not game.commit_commerce()


def test_bank_prompt_cancel_and_duplicate_line_have_no_extra_transfer(repo_root: Path) -> None:
    game=HeadlessServer(load_content(repo_root/"src/blacksite/content"),character_state={})
    client=game.connect(); create(game,client)
    place(game,client,"core-tram-hub",(12,7))
    commerce=game.core.commerce
    player=game.core.characters.players[client.session.player_id]
    commerce.prompt(client.session,"bank.deposit",{"target":"kestrel-bank"})
    token=commerce.prompts[client.session.id]["id"]
    client.send(Frame("intent",{"name":"prompt_cancel","args":{"id":token}}));game.step()
    assert not commerce.prompts and player.chits_bank==0 and not commerce.outbox
    commerce.prompt(client.session,"bank.deposit",{"target":"kestrel-bank"})
    token=commerce.prompts[client.session.id]["id"]
    for _ in range(2):client.send(Frame("line",{"id":token,"text":"100"}))
    game.step(); assert len(commerce.outbox)==1
    game.commit_commerce()
    assert player.chits_bank==100 and player.chits_hand==100
