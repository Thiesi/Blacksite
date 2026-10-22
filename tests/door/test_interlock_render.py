"""UI 3/5 and game 6.4: visible costs and complete resident records."""

from dataclasses import asdict, replace

import pytest

from blacksite.door.model import Display
from blacksite.server.protocol import Frame
from tests.character_helpers import act
from tests.fake_terminal import FakeTerminal
from tests.lattice.test_engine import runners
from tests.lattice.test_interlock import cut_fixture
from tests.lattice.test_private_cores import apartment_fixture


def render(info, game, body, size):
    display = Display(replace(info, width=size[0], height=size[1], color_depth="16"))
    content = game.core.loop.content
    display.receive(Frame("welcome", {"keymap": asdict(content.keymaps), "palette": asdict(content.palette)}), 0)
    display.receive(Frame("view", {"rev": 1, "kind": "menu", "body": body}), 1)
    terminal = FakeTerminal(*size)
    terminal.write(display.render(1)[0])
    return terminal.screen_text()


@pytest.mark.parametrize("size", [(80, 24), (132, 50)])
def test_ui_5_hardware_discloses_channel_shock_offline_and_safety(info, runners, size):
    game, a, b, c = runners
    a.session.caps.update(width=size[0], height=size[1])
    cut_fixture(game, a)
    act(game, a, Frame("key", {"k": "e", "t": 0}))
    body = game.core.characters.sim.external_views[a.session.id][1]
    text = render(info, game, body, size)
    assert "5s channel" in text and "damage interrupts" in text
    assert "100 shock" in text and "offline 10 minutes" in text
    assert "Protected bodies" in text and "manual cut" in text


@pytest.mark.parametrize("size", [(80, 24), (132, 50)])
def test_ui_5_resident_can_read_last_record_and_full_item_name(info, runners, size):
    game, a, b, c = runners
    a.session.caps.update(width=size[0], height=size[1])
    interlock, record = apartment_fixture(game, a)
    template = interlock.commerce.items[record["storage"][0]].template
    apartment = interlock.state["apartments"][record["id"]]
    apartment["hack_log"] = [{"at": f"2026-01-{day:02}T03:12:00+00:00", "item": template, "unit": 1}
                             for day in range(1,21)]
    interlock.private.open_log(a.session, record["id"], cursor=19)
    text = render(info, game, interlock.sim.external_views[a.session.id][1], size)
    assert "2026-01-20" in text and "03:12" in text
    assert all(word in text for word in interlock.content.items[template].name.split()), text
    assert "Someone was in your core" in text
