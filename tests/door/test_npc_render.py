"""NPC relation glyphs and heat at the supported terminal sizes."""

from dataclasses import replace

import pytest

from blacksite.content.loader import load_content
from blacksite.door.model import Display
from blacksite.server.protocol import encode
from tests.character_helpers import create, place
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer


@pytest.mark.parametrize("width,height",[(80,24),(132,50)])
@pytest.mark.parametrize("tier",["16","256","truecolor"])
def test_npc_glyph_heat_and_wide_handle_are_width_safe(repo_root,info,width,height,tier):
    game=HeadlessServer(load_content(repo_root/"src/blacksite/content"),character_state={})
    caller=game.connect(width=width,height=height)
    create(game,caller,name="Patrol界",card="none")
    place(game,caller,"core-plaza",(20,6))
    actor=game.core.characters.sim.avatars[caller.session.user_id].actor
    resident=next(a for a in game.core.world.actors.values() if a.zone==actor.zone and a.kind=="npc")
    game.core.npcs.refused(actor,resident)
    game.step()
    view=game.core.characters.sim.views[caller.session.id].previous["body"]
    assert any(a["role"].startswith("npc_") and a["glyph"]!="@" for a in view["actors"])
    assert any(a["relation"]=="~" for a in view["nearby"])
    display=Display(replace(info,width=width,height=height,color_depth=tier))
    for frame in game.frames_for(caller):
        encode(frame)
        display.receive(frame,1)
    display.toast=None
    terminal=FakeTerminal(width,height)
    terminal.write(display.render(2)[0])
    header=terminal.screen_text().splitlines()[0]
    assert "HEAT" in header and "SAFE" in header and "00:00" in header
    assert "Patrol界" in terminal.screen_text()
