"""UI 4: drone condition, tools and orders survive both terminal sizes."""

import pytest

from tests.door.test_progression_menus import render
from tests.server.test_drone_combat import deploy
from tests.server.test_drone_ownership import operator


@pytest.mark.parametrize("size",[(80,24),(132,50)])
def test_ui_4_drone_menu_keeps_condition_and_order_keys_visible(info,operator,size):
    game,a,b,player,engine = operator
    drone = deploy(game,a,player,engine,"drn_ostrom_eye")
    drone.health = 17
    engine.menus[a.session.id] = 0
    text = render(info,game.core.loop.content,engine.view(a.session),size)
    assert "Ostrom Eye" in text and f"17/{drone.health_max}" in text
    assert "Drone slots 1/2" in text and "Control range" in text
    assert "U deploy" in text and "T current target" in text and "Esc/B" in text
