"""UI 2.1: truce header and keeper warning in both presentations."""

from dataclasses import replace

import pytest

from blacksite.content.loader import load_content
from blacksite.door.model import Display
from blacksite.server.protocol import Frame
from tests.character_helpers import create, place
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer
from tests.presentation.snapshots import assert_golden


@pytest.mark.parametrize("width,height", [(80, 24), (132, 50)])
@pytest.mark.parametrize("tier", ["16", "256", "truecolor"])
@pytest.mark.parametrize("presentation", [False, True])
@pytest.mark.parametrize("keeper", ["sable", "unmoored"])
def test_ui_2_1_truce_header_and_warning(repo_root, info, request, caller_provenance, width, height, tier, presentation, keeper):
    game = HeadlessServer(load_content(repo_root/"src/blacksite/content"), character_state={})
    caller = game.connect({"user_id": 1, "handle": "Truce界", "node_name": "S38"}, width=width, height=height)
    create(game, caller, card="none")
    place(game, caller, "sodium-row", (25, 3))
    zone = game.core.world.zones["sodium-row"]
    zone.template = replace(zone.template, meta=replace(zone.template.meta, truce=keeper))
    game.core.characters.sim.discover(caller.session, game.core.characters.sim.avatars[caller.session.user_id])
    actor = caller.session.player_id
    source = game.core.world.actors[actor]
    target = next(a for a in zone.actors.values() if a.behaviour.get("template") == "npc-sodium-regular")
    game.core.world.enter(target, zone.id, game.core.world.free_tile(zone.id, (27, 3), target))
    source.target = target.id
    game.step()
    display = Display(replace(info, width=width, height=height, color_depth=tier), presentation=presentation)
    for frame in game.frames_for(caller):
        display.receive(frame, 0)
        if frame.type == "prompt":
            # create() accepted the default name directly on the server.
            # Replay that input through the client too, as a real caller
            # does, so the zone golden has no unfinished creation prompt.
            assert display.key("enter", 0) == [Frame("line", {"id": frame.data["id"], "text": ""})]
    assert display.prompt is None
    display.toast = None
    display.update(20, 20)
    terminal = FakeTerminal(width, height)
    terminal.write(display.render(20)[0])
    text = terminal.screen_text()
    assert "Name (Enter keeps default):" not in text
    assert "CONTESTED─TRUCE─PvP G5+" in text.splitlines()[0]
    keeper_name = game.core.loop.content.factions[keeper].short
    warning = "Truce: Sable answers" if keeper == "sable" else "Unmoored answers"
    assert warning in text
    assert display.body["me"]["truce_text"] == keeper_name + " keeps the peace here."
    assert any(line["text"] == "Nobody draws on Sodium Row. " + keeper_name + " makes sure of it." for line in caller.session.log_ring)
    assert_golden(repo_root/"tests/presentation/golden/s38-truce", f"s38_truce_{'present' if presentation else 'legacy'}_{keeper}_{width}x{height}_{tier}", terminal, tier, trim=True,
                  update=request.config.getoption("--update-goldens"))
