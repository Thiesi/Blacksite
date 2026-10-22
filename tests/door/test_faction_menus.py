"""UI 5: recruitment, pitch and last-key confirmation at both widths."""
from dataclasses import asdict, replace
import pytest
from blacksite.door.model import Display
from blacksite.server.faction_engine import FactionMenu
from blacksite.server.protocol import Frame, encode
from tests.fake_terminal import FakeTerminal
from tests.server.test_faction_engine import content, contacts


@pytest.mark.parametrize("size", [(80, 24), (132, 50)])
@pytest.mark.parametrize("mode", ["browse", "pitch", "join", "leave", "perk", "vat"])
def test_ui_5_faction_menu_width_safe_with_wide_name(info, contacts, size, mode):
    game, client, _, _ = contacts
    f = game.core.factions
    screen = FactionMenu("recruiter-cards", 0, game.clock.now_tick(),
                         confirm=mode if mode in ("join", "leave") else "", pitch=mode == "pitch")
    if mode in ("perk", "vat"):
        p = game.core.characters.players[client.session.player_id]
        fid = "wardens" if mode == "perk" else "sablier"
        p.faction, p.standing[fid] = fid, 90
        screen.cursor = list(f.station(client.session, screen.target)).index(fid)
        screen.vat = mode == "vat"
    kind, body = f.body(client.session, screen)
    display = Display(replace(info, width=size[0], height=size[1], color_depth="16"))
    display.receive(Frame("welcome", {"keymap": asdict(f.content.keymaps), "palette": asdict(f.content.palette)}), 0)
    frame = Frame("view", {"rev": 1, "kind": kind, "body": body})
    encode(frame); display.receive(frame, 1)
    terminal = FakeTerminal(*size)
    terminal.write(display.render(1)[0])
    text = terminal.screen_text()
    assert terminal.cell(size[0]-1, size[1]-1) == " "
    assert "Esc" in text
    if mode not in ("perk", "vat"):
        assert "Halvard" in text
    if mode == "browse":
        assert "Taking a card is not membership" in text
    elif mode in ("join", "leave"):
        assert "Y confirms" in text

    if mode == "perk":
        assert "Inspector" in text and "Sitrep reveals active Marked" in text
    elif mode == "vat":
        assert "NEXT DECANT" in text and "next decant here" in text
