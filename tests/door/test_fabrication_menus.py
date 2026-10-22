"""UI 5 and game 8.4: workshop information at both native display sizes."""

from dataclasses import asdict, replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.door.model import Display
from blacksite.server.protocol import Frame, encode
from blacksite.server.commerce import CommerceMenu
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer
from tests.test_fabrication import caller, setup_recipe, grant


@pytest.mark.parametrize("size", [(80, 24), (132, 50)])
def test_ui_5_workshop_shows_inputs_skill_roll_and_back(info, repo_root, size):
    content = load_content(repo_root/"src/blacksite/content")
    game = HeadlessServer(content, character_state={})
    client, player = caller(game)
    target = setup_recipe(game, client, player, "sch_ring_wrench")
    player.skills["fabrication"] = 0
    body = game.core.fabrication.body(client.session, target, 0)
    assert body["rows"][0]["cells"][1] == "hull 2/2"
    display = Display(replace(info, width=size[0], height=size[1], color_depth="16"))
    display.receive(Frame("welcome", {"keymap": asdict(content.keymaps), "palette": asdict(content.palette)}), 0)
    frame = Frame("view", {"rev": 1, "kind": "menu", "body": body})
    encode(frame)
    display.receive(frame, 1)
    terminal = FakeTerminal(*size)
    terminal.write(display.render(1)[0])
    text = terminal.screen_text()
    assert "Ring Wrench" in text and "hull 2/2" in text and "Fab 0" in text
    assert "85-100%" in text and "F fabricate" in text and "Esc/B returns" in text
    assert text.splitlines()[-1][-1] == " "


@pytest.mark.parametrize("size", [(80, 24), (132, 50)])
def test_ui_5_effective_crafted_damage_precedes_flavour_in_inventory(info, repo_root, size):
    content = load_content(repo_root/"src/blacksite/content")
    game = HeadlessServer(content, character_state={})
    client, player = caller(game)
    item = grant(game, player, "wpn_ferry_wrench")
    item.quality = 1.1
    body = game.core.commerce.body(client.session, CommerceMenu("inventory", cursor=len(player.inventory)-1))
    display = Display(replace(info, width=size[0], height=size[1], color_depth="16"))
    display.receive(Frame("welcome", {"keymap": asdict(content.keymaps), "palette": asdict(content.palette)}), 0)
    display.receive(Frame("view", {"rev": 1, "kind": "menu", "body": body}), 1)
    terminal = FakeTerminal(*size)
    terminal.write(display.render(1)[0])
    assert "Quality 110%" in terminal.screen_text()
    assert "Damage 28.6" in terminal.screen_text()
