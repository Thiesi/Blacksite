"""UI 4: review a real bill before the final keystroke at both sizes."""

from dataclasses import asdict, replace

import pytest

from blacksite.door.model import Display
from blacksite.server.protocol import Frame
from tests.door.test_progression_menus import render
from tests.server.test_clinics import clinic, review
from tests.server.test_substances import give


@pytest.mark.parametrize("size",[(80,24),(132,50)])
def test_ui_4_clinic_confirmation_keeps_total_risk_fees_and_tolerance_visible(info,clinic,size):
    game,client,player,engine = clinic
    iid = give(game,client,"imp_halvard_reflex_arm")
    screen = review(game,client,engine,"install:"+iid+":arms1")
    body = engine.view(client.session,screen)
    text = render(info,game.core.loop.content,body,size)
    assert "TOTAL" in text and "Failure 2%" in text and "2/4" in text
    assert "Item 0" in text and "Service" in text and "Removal 0" in text
    assert "Y confirms" in text and "Esc/B leaves" in text
    display = Display(replace(info,width=size[0],height=size[1]))
    display.receive(Frame("welcome",{"keymap":asdict(game.core.loop.content.keymaps),
        "palette":asdict(game.core.loop.content.palette)}),0)
    display.receive(Frame("view",{"rev":client.session.view_revision,"kind":"menu","body":body}),1)
    frames = display.key("Y",2)
    assert len(frames) == 1 and frames[0].data["args"]["key"] == "y"
    client.send(frames[0]); game.step()
    assert game.core.commerce.pending and "arms1" not in player.implants


@pytest.mark.parametrize("size",[(80,24),(132,50)])
def test_ui_4_detox_bill_explains_cost_time_and_offline_completion(info,clinic,size):
    game,client,player,engine = clinic
    player.dependencies.append({"template":"drug_sable_redline","since":game.clock.now_utc().timestamp()})
    screen = review(game,client,engine,"detox")
    text = render(info,game.core.loop.content,engine.view(client.session,screen),size)
    assert "TOTAL 400" in text and "ten minutes" in text and "continues offline" in text
    assert "Y confirms" in text
