"""UI 5 / game 8.7: real menu rendering at both supported geometries."""

from dataclasses import asdict, replace

import pytest

from blacksite.door.model import Display
from blacksite.server.apartments import HousingMenu
from blacksite.server.protocol import Frame, encode
from tests.fake_terminal import FakeTerminal
from tests.test_apartments import housing_content, housing, rent, inside, item, action


@pytest.mark.parametrize("size", [(80, 24), (132, 50)])
@pytest.mark.parametrize("kind", ["apartment", "storage", "safe", "impound", "letting"])
def test_ui_5_game_8_7_apartment_menu_golden_80x24_and_132x50(info, housing, size, kind):
    game, client, _ = housing
    a, record, unit = rent(game, client)
    inside(game, client, unit)
    rifle = item(game, client)
    action(game, client, "deposit", record, item=rifle.id)
    if kind == "impound":
        action(game, client, "surrender", record)
        from tests.character_helpers import place
        place(game, client, unit.zone, (9, 8))
        target = "fixture-bank"
    elif kind == "letting":
        from tests.character_helpers import place
        place(game, client, unit.zone, (6, 8))
        target = "fixture-letting"
    else:
        target = record["id"]
    body = a.body(client.session, HousingMenu(kind, target, deposit=False))
    display = Display(replace(info, width=size[0], height=size[1], color_depth="16"))
    display.receive(Frame("welcome", {"keymap": asdict(a.content.keymaps), "palette": asdict(a.content.palette)}), 0)
    frame = Frame("view", {"rev": 1, "kind": "menu", "body": body})
    encode(frame)
    display.receive(frame, 1)
    terminal = FakeTerminal(*size)
    terminal.write(display.render(1)[0])
    text = terminal.screen_text()
    assert "Esc/B returns" in text
    assert terminal.cell(size[0]-1, size[1]-1) == " "
    if kind in ("storage", "impound"):
        assert "Halvard HV-7" in text and "Quality 108%" in text
    if kind == "apartment":
        assert "Core 1 / lock 1" in text and "Log out" in text
